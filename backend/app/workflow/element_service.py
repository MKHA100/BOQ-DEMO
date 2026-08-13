from __future__ import annotations

import math
import re
from typing import Any

from app.core.errors import bad_request, not_found
from app.database.session import get_connection
from app.jobs.job_service import job_service
from app.workflow.constants import SOURCE_USER_CONFIRMED, VALUE_SOURCE_PRIORITY
from app.workflow.dependencies import DependencyJob, dependency_planner
from app.workflow.repo import dumps, loads, now_iso, workflow_repository

PROPERTY_NAME_PATTERN = re.compile(r"^[a-z][a-z0-9_]{0,79}$")

class ElementServiceMixin:
    def create_element(self, *, project_id: str, payload: dict, created_by: str | None) -> dict:
        floor_id = payload["floor_id"]
        with get_connection() as connection:
            self._require_floor(connection, project_id, floor_id)
            versions = workflow_repository.increment_floor_version(connection, project_id, floor_id, "element_version")
            element = workflow_repository.create_element(
                connection,
                project_id=project_id,
                floor_id=floor_id,
                element_type=payload["element_type"],
                type_code=payload.get("type_code"),
                geometry=payload.get("geometry") or {},
                source=payload.get("source") or "model",
                confidence=payload.get("confidence"),
                status=payload.get("status") or "needs_review",
                element_version=versions["element_version"],
                created_by=created_by,
                source_versions=workflow_repository.get_versions(connection, project_id, floor_id),
            )
            event = workflow_repository.create_outbox_event(
                connection,
                project_id=project_id,
                floor_id=floor_id,
                event_type="element.created",
                entity_type="element",
                entity_id=element["id"],
                dedupe_key=f"element.created:{element['id']}:{versions['element_version']}",
                payload={"element_type": element["element_type"], "versions": self._version_values(versions)},
            )
        workflow_repository.mark_outbox_published(event["id"])
        return {"record": self._decode_record(element), "protected": False, "changed": True, "versions": self._version_values(versions), "jobs": []}

    def update_element_property(
        self,
        *,
        project_id: str,
        element_id: str,
        property_name: str,
        value: Any,
        unit: str | None,
        source: str,
        confirm: bool,
        created_by: str | None,
    ) -> dict:
        if not PROPERTY_NAME_PATTERN.fullmatch(property_name):
            raise bad_request("Invalid property name.")
        if source not in VALUE_SOURCE_PRIORITY:
            raise bad_request("Invalid value source.")

        planned_jobs: list[DependencyJob] = []
        with get_connection() as connection:
            element = workflow_repository.get_element(connection, project_id, element_id)
            if not element:
                raise not_found("Element not found.")
            floor_id = element["floor_id"]
            existing = workflow_repository.get_element_property(connection, element_id, property_name)
            incoming_confirmed = bool(confirm or source == SOURCE_USER_CONFIRMED)
            incoming_priority = VALUE_SOURCE_PRIORITY[SOURCE_USER_CONFIRMED if incoming_confirmed else source]

            if existing and self._same_property(existing, value, unit, source, incoming_confirmed):
                versions = workflow_repository.get_versions(connection, project_id, floor_id)
                return {
                    "record": self._decode_record(existing),
                    "protected": False,
                    "changed": False,
                    "versions": versions,
                    "jobs": [],
                }

            protected = bool(
                existing
                and not incoming_confirmed
                and (int(existing.get("is_confirmed") or 0) == 1 or int(existing.get("source_priority") or 0) > incoming_priority)
            )
            if protected:
                property_row = workflow_repository.save_property_suggestion(
                    connection,
                    property_row=existing,
                    value=value,
                    source=source,
                )
                floor_versions = workflow_repository.increment_floor_version(connection, project_id, floor_id, "review_version")
                workflow_repository.increment_project_version(connection, project_id, "review_version")
                issue = workflow_repository.upsert_review_issue(
                    connection,
                    project_id=project_id,
                    floor_id=floor_id,
                    entity_type="element",
                    entity_id=element_id,
                    issue_type=f"conflicting_{property_name}",
                    title="Conflicting value",
                    detail=f"A new {property_name.replace('_', ' ')} value needs review.",
                    suggestion={"property": property_name, "value": value, "unit": unit},
                    source=source,
                    review_version=floor_versions["review_version"],
                )
                event = workflow_repository.create_outbox_event(
                    connection,
                    project_id=project_id,
                    floor_id=floor_id,
                    event_type="element.property.suggested",
                    entity_type="element",
                    entity_id=element_id,
                    dedupe_key=f"element.property.suggested:{element_id}:{property_name}:{floor_versions['review_version']}",
                    payload={"property": property_name, "review_issue_id": issue["id"]},
                )
                versions = self._version_values(floor_versions)
            else:
                floor_versions = workflow_repository.increment_floor_version(connection, project_id, floor_id, "element_version")
                property_row = workflow_repository.upsert_element_property(
                    connection,
                    project_id=project_id,
                    floor_id=floor_id,
                    element_id=element_id,
                    property_name=property_name,
                    value=value,
                    unit=unit,
                    source=SOURCE_USER_CONFIRMED if incoming_confirmed else source,
                    source_priority=incoming_priority,
                    is_confirmed=incoming_confirmed,
                    element_version=floor_versions["element_version"],
                    created_by=created_by,
                )
                wall_ids = workflow_repository.related_wall_ids(connection, project_id, floor_id, element_id)
                workflow_repository.mark_element_dependents_stale(
                    connection,
                    project_id=project_id,
                    floor_id=floor_id,
                    element_id=element_id,
                    wall_ids=wall_ids,
                )
                planned_jobs = dependency_planner.for_element_property(
                    floor_id=floor_id,
                    element_id=element_id,
                    property_name=property_name,
                    wall_ids=wall_ids,
                )
                event = workflow_repository.create_outbox_event(
                    connection,
                    project_id=project_id,
                    floor_id=floor_id,
                    event_type="element.property.changed",
                    entity_type="element",
                    entity_id=element_id,
                    dedupe_key=f"element.property.changed:{element_id}:{property_name}:{floor_versions['element_version']}",
                    payload={"property": property_name, "versions": self._version_values(floor_versions)},
                )
                versions = self._version_values(floor_versions)

        jobs = self._enqueue_jobs(
            project_id=project_id,
            created_by=created_by,
            input_versions=versions,
            jobs=planned_jobs,
        )
        workflow_repository.mark_outbox_published(event["id"])
        return {
            "record": self._decode_record(property_row),
            "protected": protected,
            "changed": True,
            "versions": versions,
            "jobs": jobs,
        }

    def apply_generated_properties_bulk(
        self,
        *,
        project_id: str,
        floor_id: str,
        updates: list[dict[str, Any]],
        created_by: str | None = None,
    ) -> dict:
        """Apply schedule/model/default values in one short transaction.

        Automatic enrichment must not create one dependency job and one version
        increment per property. Confirmed higher-priority values remain protected
        and receive suggestions instead.
        """
        clean: list[dict[str, Any]] = []
        for update in updates:
            name = str(update.get("property_name") or "")
            source = str(update.get("source") or "")
            if not PROPERTY_NAME_PATTERN.fullmatch(name) or source not in VALUE_SOURCE_PRIORITY:
                continue
            if update.get("value") in (None, ""):
                continue
            clean.append({**update, "property_name": name, "source": source})
        if not clean:
            return {"changed": 0, "protected": 0, "jobs": [], "versions": {}}

        changed = 0
        protected = 0
        affected_elements: set[str] = set()
        affected_walls: set[str] = set()
        with get_connection() as connection:
            self._require_floor(connection, project_id, floor_id)
            valid_elements = {
                str(row["id"])
                for row in connection.execute(
                    "SELECT id FROM elements WHERE project_id=? AND floor_id=? AND COALESCE(excluded,0)=0",
                    (project_id, floor_id),
                ).fetchall()
            }
            pending = [item for item in clean if str(item.get("element_id") or "") in valid_elements]
            if not pending:
                versions = workflow_repository.get_versions(connection, project_id, floor_id)
                return {"changed": 0, "protected": 0, "jobs": [], "versions": self._version_values(versions)}

            element_version: int | None = None
            review_version: int | None = None
            for item in pending:
                element_id = str(item["element_id"])
                property_name = str(item["property_name"])
                value = item.get("value")
                unit = item.get("unit")
                source = str(item["source"])
                existing = workflow_repository.get_element_property(connection, element_id, property_name)
                priority = VALUE_SOURCE_PRIORITY[source]
                if existing and self._same_property(existing, value, unit, source, False):
                    continue
                is_protected = bool(
                    existing
                    and (int(existing.get("is_confirmed") or 0) == 1 or int(existing.get("source_priority") or 0) > priority)
                )
                if is_protected:
                    workflow_repository.save_property_suggestion(
                        connection, property_row=existing, value=value, source=source
                    )
                    if review_version is None:
                        review_versions = workflow_repository.increment_floor_version(
                            connection, project_id, floor_id, "review_version"
                        )
                        workflow_repository.increment_project_version(connection, project_id, "review_version")
                        review_version = int(review_versions["review_version"])
                    workflow_repository.upsert_review_issue(
                        connection,
                        project_id=project_id,
                        floor_id=floor_id,
                        entity_type="element",
                        entity_id=element_id,
                        issue_type=f"conflicting_{property_name}",
                        title="Conflicting value",
                        detail=f"A new {property_name.replace('_', ' ')} value needs review.",
                        suggestion={"property": property_name, "value": value, "unit": unit},
                        source=source,
                        review_version=review_version,
                    )
                    protected += 1
                    continue

                if element_version is None:
                    floor_versions = workflow_repository.increment_floor_version(
                        connection, project_id, floor_id, "element_version"
                    )
                    element_version = int(floor_versions["element_version"])
                workflow_repository.upsert_element_property(
                    connection,
                    project_id=project_id,
                    floor_id=floor_id,
                    element_id=element_id,
                    property_name=property_name,
                    value=value,
                    unit=unit,
                    source=source,
                    source_priority=priority,
                    is_confirmed=False,
                    element_version=element_version,
                    created_by=created_by,
                )
                wall_ids = workflow_repository.related_wall_ids(connection, project_id, floor_id, element_id)
                workflow_repository.mark_element_dependents_stale(
                    connection, project_id=project_id, floor_id=floor_id, element_id=element_id, wall_ids=wall_ids
                )
                affected_elements.add(element_id)
                affected_walls.update(wall_ids)
                changed += 1

            versions = workflow_repository.get_versions(connection, project_id, floor_id)
            if changed or protected:
                event = workflow_repository.create_outbox_event(
                    connection,
                    project_id=project_id,
                    floor_id=floor_id,
                    event_type="element.properties.enriched",
                    entity_type="floor",
                    entity_id=floor_id,
                    dedupe_key=f"element.properties.enriched:{floor_id}:{versions.get('element_version', 0)}:{versions.get('review_version', 0)}",
                    payload={
                        "changed": changed,
                        "protected": protected,
                        "element_ids": sorted(affected_elements),
                    },
                )
            else:
                event = None

        jobs: list[dict] = []
        version_values = self._version_values(versions)
        if changed:
            task_type = "walls.calculate_areas" if affected_walls else "review.refresh"
            job, created = job_service.enqueue(
                task_type=task_type,
                project_id=project_id,
                floor_id=floor_id,
                entity_id=floor_id,
                payload={"entity_type": "floor", "element_ids": sorted(affected_elements)},
                input_versions=version_values,
                created_by=created_by,
            )
            jobs.append({**job, "created": created})
            if task_type == "review.refresh":
                boq_job, boq_created = job_service.enqueue(
                    task_type="boq.refresh", project_id=project_id, floor_id=floor_id,
                    payload={"entity_type": "floor"}, input_versions=version_values, created_by=created_by
                )
                jobs.append({**boq_job, "created": boq_created})
        elif protected:
            review_job, created = job_service.enqueue(
                task_type="review.refresh", project_id=project_id, floor_id=floor_id,
                payload={"entity_type": "floor"}, input_versions=version_values, created_by=created_by
            )
            jobs.append({**review_job, "created": created})
        if event:
            workflow_repository.mark_outbox_published(event["id"])
        return {
            "changed": changed,
            "protected": protected,
            "jobs": jobs,
            "versions": version_values,
        }

    def create_wall(self, *, project_id: str, payload: dict, created_by: str | None) -> dict:
        floor_id = payload["floor_id"]
        with get_connection() as connection:
            self._require_floor(connection, project_id, floor_id)
            versions = workflow_repository.increment_floor_version(connection, project_id, floor_id, "wall_version")
            wall = workflow_repository.create_wall(
                connection,
                project_id=project_id,
                floor_id=floor_id,
                payload=payload,
                wall_version=versions["wall_version"],
                created_by=created_by,
                source_versions=workflow_repository.get_versions(connection, project_id, floor_id),
            )
            event = workflow_repository.create_outbox_event(
                connection,
                project_id=project_id,
                floor_id=floor_id,
                event_type="wall.created",
                entity_type="wall",
                entity_id=wall["id"],
                dedupe_key=f"wall.created:{wall['id']}:{versions['wall_version']}",
                payload={"versions": self._version_values(versions)},
            )
        workflow_repository.mark_outbox_published(event["id"])
        return {"record": self._decode_record(wall), "protected": False, "changed": True, "versions": self._version_values(versions), "jobs": []}

    def create_relation(self, *, project_id: str, payload: dict, created_by: str | None) -> dict:
        floor_id = payload["floor_id"]
        planned_jobs: list[DependencyJob]
        with get_connection() as connection:
            self._require_floor(connection, project_id, floor_id)
            element = workflow_repository.get_element(connection, project_id, payload["source_element_id"])
            if not element or element["floor_id"] != floor_id:
                raise not_found("Element not found.")
            if payload["target_type"] == "wall":
                wall = connection.execute(
                    "SELECT id FROM walls WHERE id = ? AND project_id = ? AND floor_id = ?",
                    (payload["target_id"], project_id, floor_id),
                ).fetchone()
                if not wall:
                    raise not_found("Wall not found.")
            versions = workflow_repository.increment_floor_version(connection, project_id, floor_id, "element_version")
            relation = workflow_repository.create_relation(
                connection,
                project_id=project_id,
                floor_id=floor_id,
                source_element_id=payload["source_element_id"],
                target_type=payload["target_type"],
                target_id=payload["target_id"],
                relation_type=payload["relation_type"],
                created_by=created_by,
            )
            wall_ids = [payload["target_id"]] if payload["target_type"] == "wall" else []
            workflow_repository.mark_element_dependents_stale(
                connection,
                project_id=project_id,
                floor_id=floor_id,
                element_id=payload["source_element_id"],
                wall_ids=wall_ids,
            )
            planned_jobs = dependency_planner.for_element_relation(
                floor_id=floor_id,
                element_id=payload["source_element_id"],
                target_type=payload["target_type"],
                target_id=payload["target_id"],
            )
            event = workflow_repository.create_outbox_event(
                connection,
                project_id=project_id,
                floor_id=floor_id,
                event_type="element.relation.changed",
                entity_type="element",
                entity_id=payload["source_element_id"],
                dedupe_key=f"element.relation.changed:{relation['id']}:{versions['element_version']}",
                payload={"relation_id": relation["id"], "versions": self._version_values(versions)},
            )
            version_values = self._version_values(versions)
        jobs = self._enqueue_jobs(project_id=project_id, created_by=created_by, input_versions=version_values, jobs=planned_jobs)
        workflow_repository.mark_outbox_published(event["id"])
        return {"record": self._decode_record(relation), "protected": False, "changed": True, "versions": version_values, "jobs": jobs}
