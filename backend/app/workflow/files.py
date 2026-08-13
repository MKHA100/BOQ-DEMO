from __future__ import annotations

from typing import Any

from app.core.errors import not_found


from app.database.session import get_connection
from app.jobs.job_service import job_service
from app.workflow.repo import workflow_repository


class WorkflowFileService:
    def save_floor_crop(self, *, project_id: str, payload: dict, created_by: str | None) -> dict:
        floor_id = payload["floor_id"]
        with get_connection() as connection:
            floor = workflow_repository.get_floor(connection, project_id, floor_id)
            if not floor:
                raise not_found("Floor not found.")
            document = workflow_repository.get_document(connection, project_id, payload["document_id"])
            if not document:
                raise not_found("Document not found.")
            page = connection.execute(
                "SELECT id FROM document_pages WHERE id = ? AND project_id = ? AND document_id = ?",
                (payload["document_page_id"], project_id, payload["document_id"]),
            ).fetchone()
            if not page:
                raise not_found("Document page not found.")
            versions = workflow_repository.increment_floor_version(connection, project_id, floor_id, "crop_version")
            crop = workflow_repository.save_floor_crop(
                connection,
                project_id=project_id,
                floor_id=floor_id,
                document_id=payload["document_id"],
                document_page_id=payload["document_page_id"],
                coordinates=payload["coordinates"],
                source_width=payload.get("source_width"),
                source_height=payload.get("source_height"),
                crop_asset_key=payload.get("crop_asset_key"),
                crop_version=versions["crop_version"],
                created_by=created_by,
            )
            event = workflow_repository.create_outbox_event(
                connection,
                project_id=project_id,
                floor_id=floor_id,
                event_type="floor.crop.changed",
                entity_type="floor_crop",
                entity_id=crop["id"],
                dedupe_key=f"floor.crop.changed:{floor_id}:{versions['crop_version']}",
                payload={"crop_version": versions["crop_version"], "document_page_id": payload["document_page_id"]},
            )
            version_input = {key: int(value or 0) for key, value in versions.items() if key.endswith("_version")}
        jobs = []
        for task_type in ("vision.detect_elements", "review.refresh", "boq.refresh"):
            job, created = job_service.enqueue(
                task_type=task_type,
                project_id=project_id,
                floor_id=floor_id,
                payload={"floor_id": floor_id, "floor_crop_id": crop["id"]},
                input_versions=version_input,
                entity_id=floor_id if task_type != "vision.detect_elements" else crop["id"],
                created_by=created_by,
            )
            jobs.append({**job, "created": created})
        workflow_repository.mark_outbox_published(event["id"])
        return {"record": self._decode(crop), "protected": False, "changed": True, "versions": version_input, "jobs": jobs}

    def create_schedule_file(self, *, project_id: str, payload: dict, created_by: str | None) -> dict:
        floor_id = payload.get("floor_id")
        with get_connection() as connection:
            document = workflow_repository.get_document(connection, project_id, payload["document_id"])
            if not document:
                raise not_found("Document not found.")
            if floor_id and not workflow_repository.get_floor(connection, project_id, floor_id):
                raise not_found("Floor not found.")
            project_versions = workflow_repository.increment_project_version(connection, project_id, "schedule_version")
            if floor_id:
                floor_versions = workflow_repository.increment_floor_version(connection, project_id, floor_id, "schedule_version")
                schedule_version = floor_versions["schedule_version"]
                input_versions = {key: int(value or 0) for key, value in floor_versions.items() if key.endswith("_version")}
            else:
                schedule_version = project_versions["schedule_version"]
                input_versions = {"schedule_version": int(schedule_version)}
            record = workflow_repository.create_schedule_file(
                connection,
                project_id=project_id,
                floor_id=floor_id,
                document_id=payload["document_id"],
                schedule_type=payload["schedule_type"],
                source_crop=payload.get("source_crop"),
                schedule_version=schedule_version,
                created_by=created_by,
            )
            event = workflow_repository.create_outbox_event(
                connection,
                project_id=project_id,
                floor_id=floor_id,
                event_type="schedule.file.added",
                entity_type="schedule_file",
                entity_id=record["id"],
                dedupe_key=f"schedule.file.added:{record['id']}:{schedule_version}",
                payload={"schedule_type": payload["schedule_type"], "schedule_version": schedule_version},
            )
        job, created = job_service.enqueue(
            task_type="extract.schedule",
            project_id=project_id,
            floor_id=floor_id,
            payload={"schedule_file_id": record["id"]},
            input_versions=input_versions,
            entity_id=record["id"],
            created_by=created_by,
        )
        workflow_repository.mark_outbox_published(event["id"])
        return {"record": self._decode(record), "protected": False, "changed": True, "versions": input_versions, "jobs": [{**job, "created": created}]}

    def create_specification_file(self, *, project_id: str, payload: dict, created_by: str | None) -> dict:
        floor_id = payload.get("floor_id")
        with get_connection() as connection:
            document = workflow_repository.get_document(connection, project_id, payload["document_id"])
            if not document:
                raise not_found("Document not found.")
            if floor_id and not workflow_repository.get_floor(connection, project_id, floor_id):
                raise not_found("Floor not found.")
            project_versions = workflow_repository.increment_project_version(connection, project_id, "specification_version")
            specification_version = project_versions["specification_version"]
            input_versions = {"specification_version": int(specification_version)}
            record = workflow_repository.create_specification_file(
                connection,
                project_id=project_id,
                floor_id=floor_id,
                document_id=payload["document_id"],
                specification_type=payload["specification_type"],
                source_crop=payload.get("source_crop"),
                specification_version=specification_version,
                created_by=created_by,
            )
            event = workflow_repository.create_outbox_event(
                connection,
                project_id=project_id,
                floor_id=floor_id,
                event_type="specification.file.added",
                entity_type="specification_file",
                entity_id=record["id"],
                dedupe_key=f"specification.file.added:{record['id']}:{specification_version}",
                payload={"specification_version": specification_version},
            )
        job, created = job_service.enqueue(
            task_type="extract.specification",
            project_id=project_id,
            floor_id=floor_id,
            payload={"specification_file_id": record["id"]},
            input_versions=input_versions,
            entity_id=record["id"],
            created_by=created_by,
        )
        workflow_repository.mark_outbox_published(event["id"])
        return {"record": self._decode(record), "protected": False, "changed": True, "versions": input_versions, "jobs": [{**job, "created": created}]}

    @staticmethod
    def _decode(record: dict) -> dict:
        result = dict(record)
        for key in list(result):
            if key.endswith("_json"):
                from app.workflow.repo import loads

                result[key[:-5]] = loads(result.pop(key))
        for key in ("is_current",):
            if key in result:
                result[key] = bool(result[key])
        return result


workflow_file_service = WorkflowFileService()
