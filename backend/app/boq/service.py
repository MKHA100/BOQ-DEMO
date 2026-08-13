from __future__ import annotations

import hashlib
import json
from typing import Any

from app.boq.description_builder import boq_description_builder
from app.boq.quantity_resolver import boq_quantity_resolver
from app.boq.report_builder import formal_boq_report_builder
from app.boq.repo import boq_repository
from app.boq.section_mapper import map_bill
from app.boq.setup_repo import boq_setup_repository
from app.boq.template_repo import boq_template_repository
from app.core.errors import bad_request, not_found
from app.database.session import get_connection
from app.jobs.job_service import job_service
from app.model_review.repo import model_review_repository
from app.projects.project_service import project_service
from app.workflow.repo import workflow_repository


class BoqService:
    def _versions(self, project_id: str, template: dict | None = None, setup: dict | None = None) -> dict:
        with get_connection() as connection:
            project = workflow_repository.ensure_project_versions(connection, project_id)
            floors = connection.execute(
                "SELECT * FROM floor_versions WHERE project_id=? ORDER BY floor_id", (project_id,)
            ).fetchall()
        result = {
            "schedule_version": int(project.get("schedule_version") or 0),
            "specification_version": int(project.get("specification_version") or 0),
            "review_version": int(project.get("review_version") or 0),
            "floors": [
                {key: int(row[key] or 0) for key in (
                    "crop_version", "scale_version", "element_version", "wall_version", "room_version", "review_version"
                )} | {"floor_id": row["floor_id"]}
                for row in floors
            ],
        }
        if template:
            result["template_id"] = template["id"]
            result["template_version"] = int(template.get("version") or 1)
        if setup:
            result["setup_version"] = int(setup.get("setup_version") or 1)
        return result

    @staticmethod
    def _hash(value: Any) -> str:
        return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()).hexdigest()

    def refresh(self, project_id: str, created_by: str | None = None, grouping_mode: str = "item") -> dict:
        project = project_service.get_project(project_id, None)
        template = boq_template_repository.selected(project_id)
        setup = boq_setup_repository.ensure(project)
        boq = boq_repository.ensure_boq(project_id, template, created_by, int(setup["setup_version"]))
        versions = self._versions(project_id, template, setup)
        source_hash = self._hash(versions)
        with get_connection() as connection:
            next_version = workflow_repository.increment_project_version(connection, project_id, "boq_version")
            connection.execute(
                "UPDATE boqs SET grouping_mode=?,is_stale=1,status='processing',updated_at=? WHERE id=?",
                (grouping_mode, self._now(), boq["id"]),
            )
        boq = boq_repository.update_boq(
            boq["id"], version=int(next_version["boq_version"]), source_versions=versions,
            status="processing", setup_version=int(setup["setup_version"]),
            template_version=int(template["version"]), currency=setup.get("currency"),
            vat_percentage=float(setup.get("vat_percentage") or 0),
        )

        groups, _ = boq_quantity_resolver.resolve(project_id, grouping_mode)
        keys: set[str] = set()
        for group in groups:
            keys.add(group["group_key"])
            try:
                template_item = boq_template_repository.matching_item(
                    project_id, template["id"], group["kind"], group.get("keywords") or []
                )
            except ValueError:
                template_item = {
                    "section_code": "9A", "section_name": "Other items", "unit": group.get("unit") or "item",
                    "description_template": "[TYPE_CODE]", "sort_order": 900,
                    "conditional_rules": [],
                }
            rendered = boq_description_builder.build_details(template_item, group)
            description = rendered["description"]
            bill = map_bill(template_item.get("section_code"), group["kind"])
            status = "needs_review" if group.get("needs_review") or group.get("missing") else "ready"
            boq_repository.upsert_generated_row(
                boq=boq, group_key=group["group_key"], floor_id=group.get("floor_id"),
                entity_type=group["kind"], section=template_item.get("section_name") or "Other items",
                item_code=group.get("item_code"), description=description, quantity=group["quantity"],
                unit=rendered.get("unit") or template_item.get("unit") or group.get("unit") or "item",
                source_ids=group.get("sources") or [], floor_ids=group.get("floor_ids") or [],
                source_versions=versions, source_hash=source_hash,
                sort_order=int(template_item.get("sort_order") or 0), status=status,
                bill_no=bill["bill_no"], bill_name=bill["bill_name"],
                subcategory_code=template_item.get("section_code"),
                subcategory_name=template_item.get("section_name"),
            )
        boq_repository.delete_missing_generated(boq["id"], keys)
        rows = self._enrich_rows(project_id, boq_repository.rows(project_id, boq["id"]))
        report = formal_boq_report_builder.build(
            project=project, setup=setup, template=template, boq=boq, rows=rows
        )
        report_hash = self._hash(report)
        boq_repository.apply_report_numbers(boq["id"], report)
        boq = boq_repository.update_boq(
            boq["id"], version=int(next_version["boq_version"]), source_versions=versions,
            status="ready", setup_version=int(setup["setup_version"]),
            template_version=int(template["version"]), report=report, report_hash=report_hash,
            currency=setup.get("currency"), vat_percentage=float(setup.get("vat_percentage") or 0),
        )
        rows = self._enrich_rows(project_id, boq_repository.rows(project_id, boq["id"]))
        return {"boq": boq, "rows": rows, "report": report, "updated": len(groups)}

    def state(self, project: dict, floor_id: str | None = None, grouping_mode: str = "item") -> dict:
        templates = boq_template_repository.list_packages(project["id"])
        template = next((item for item in templates if item.get("is_default")), templates[0])
        setup = boq_setup_repository.ensure(project)
        boq = boq_repository.ensure_boq(project["id"], template, setup_version=int(setup["setup_version"]))
        versions = self._versions(project["id"], template, setup)
        current_hash = self._hash(versions)
        saved_hash = self._hash(boq.get("source_versions") or {})
        active = job_service.list_project_jobs(project_id=project["id"], active_only=True, limit=100)
        stale = bool(boq.get("is_stale")) or current_hash != saved_hash or str(boq.get("grouping_mode") or "item") != grouping_mode
        rows = self._enrich_rows(project["id"], boq_repository.rows(project["id"], boq["id"], floor_id))
        with get_connection() as connection:
            floors = [dict(row) for row in connection.execute(
                "SELECT id,name,level_index FROM floors WHERE project_id=? ORDER BY level_index", (project["id"],)
            ).fetchall()]
        summary = self._summary(rows)
        report = boq.get("report") or {}
        return {
            "project_id": project["id"], "boq": boq, "setup": setup,
            "template": template, "templates": templates, "rows": rows, "report": report,
            "floors": floors, "stale": stale, "summary": summary,
            "active_jobs": [job for job in active if job.get("category") in {"boq", "export"}],
            "exports": boq_repository.exports(project["id"], boq["id"]),
        }

    def select_template(self, project_id: str, template_id: str, created_by: str | None = None) -> dict:
        try:
            template = boq_template_repository.select(project_id, template_id)
        except ValueError:
            raise not_found("BOQ template not found.")
        project = project_service.get_project(project_id, created_by)
        setup = boq_setup_repository.ensure(project)
        versions = self._versions(project_id, template, setup)
        boq = boq_repository.ensure_boq(project_id, template, created_by, int(setup["setup_version"]))
        job, _ = job_service.enqueue(
            task_type="boq.refresh", project_id=project_id, payload={"grouping_mode": "item"},
            input_versions=versions, entity_id=boq["id"], created_by=created_by,
        )
        return {"template": template, "job": job}

    def add_manual(self, project_id: str, payload: dict, user_id: str | None) -> dict:
        project = project_service.get_project(project_id, user_id)
        template = boq_template_repository.selected(project_id)
        setup = boq_setup_repository.ensure(project)
        boq = boq_repository.ensure_boq(project_id, template, user_id, int(setup["setup_version"]))
        row = boq_repository.add_manual(
            project_id=project_id, boq_id=boq["id"], floor_id=payload.get("floor_id"),
            description=payload["description"], section=payload.get("section"),
            quantity=float(payload["quantity"]), unit=payload["unit"],
            version=int(boq["boq_version"]), rate=payload.get("rate"), item_code=payload.get("item_code"),
        )
        self._enqueue_refresh(project_id, boq, user_id, str(boq.get("grouping_mode") or "item"))
        return {"row": row}

    def update_row(self, project_id: str, row_id: str, payload: dict, user_id: str | None = None) -> dict:
        row = boq_repository.update_row(project_id, row_id, payload)
        if not row:
            raise not_found("BOQ row not found.")
        template = boq_template_repository.selected(project_id)
        project = project_service.get_project(project_id, user_id)
        setup = boq_setup_repository.ensure(project)
        boq = boq_repository.ensure_boq(project_id, template, user_id, int(setup["setup_version"]))
        self._enqueue_refresh(project_id, boq, user_id, str(boq.get("grouping_mode") or "item"))
        return {"row": row}

    def request_export(self, project_id: str, payload: dict, user_id: str | None) -> dict:
        project = project_service.get_project(project_id, user_id)
        template = boq_template_repository.selected(project_id)
        setup = boq_setup_repository.ensure(project)
        boq = boq_repository.ensure_boq(project_id, template, user_id, int(setup["setup_version"]))
        floor_id = payload.get("floor_id") if payload.get("floor_mode") == "selected_floor" else None
        if payload.get("floor_mode") == "selected_floor" and not floor_id:
            raise bad_request("Select a floor.")
        versions = self._versions(project_id, template, setup)
        snapshot_key = self._hash(versions)
        cache_key = (
            f"project:{project_id}:source:{snapshot_key}:template:{template['version']}:setup:{setup['setup_version']}:"
            f"format:{payload['format']}:mode:{payload['floor_mode']}:floor:{floor_id or 'all'}"
        )
        export, created = boq_repository.create_or_get_export(
            project_id=project_id, boq=boq, format=payload["format"],
            floor_mode=payload["floor_mode"], floor_id=floor_id, cache_key=cache_key,
            created_by=user_id,
        )
        if created:
            job, _ = job_service.enqueue(
                task_type="export.generate", project_id=project_id, payload={"export_id": export["id"]},
                input_versions=versions, entity_id=export["id"], created_by=user_id,
            )
            return {"export": export, "job": job, "created": True}
        return {"export": export, "created": False}

    def current_report(self, project_id: str, *, grouping_mode: str | None = None) -> tuple[dict, dict]:
        project = project_service.get_project(project_id, None)
        template = boq_template_repository.selected(project_id)
        setup = boq_setup_repository.ensure(project)
        boq = boq_repository.ensure_boq(project_id, template, setup_version=int(setup["setup_version"]))
        if boq.get("is_stale") or not boq.get("report") or (grouping_mode and str(boq.get("grouping_mode") or "item") != grouping_mode):
            result = self.refresh(project_id, grouping_mode=grouping_mode or str(boq.get("grouping_mode") or "item"))
            return result["boq"], result["report"]
        return boq, boq.get("report") or {}

    def _enqueue_refresh(self, project_id: str, boq: dict, user_id: str | None, grouping_mode: str) -> None:
        project = project_service.get_project(project_id, user_id)
        template = boq_template_repository.selected(project_id)
        setup = boq_setup_repository.ensure(project)
        job_service.enqueue(
            task_type="boq.refresh", project_id=project_id, payload={"grouping_mode": grouping_mode},
            input_versions=self._versions(project_id, template, setup), entity_id=boq["id"], created_by=user_id,
        )

    def _enrich_rows(self, project_id: str, rows: list[dict]) -> list[dict]:
        if not rows:
            return []
        with get_connection() as connection:
            floor_names = {row["id"]: row["name"] for row in connection.execute(
                "SELECT id,name FROM floors WHERE project_id=?", (project_id,)
            ).fetchall()}
            wall_rows = {row["id"]: dict(row) for row in connection.execute(
                """SELECT * FROM walls w WHERE project_id=? AND COALESCE(w.generated_status,'current')='current'
                   AND (w.source_crop_version IS NULL OR w.source_crop_version=(SELECT crop_version FROM floor_versions fv
                        WHERE fv.project_id=w.project_id AND fv.floor_id=w.floor_id))""", (project_id,)
            ).fetchall()}
            room_rows = {row["id"]: dict(row) for row in connection.execute(
                """SELECT * FROM rooms r WHERE project_id=? AND COALESCE(r.generated_status,'current')='current'
                   AND (r.source_crop_version IS NULL OR r.source_crop_version=(SELECT crop_version FROM floor_versions fv
                        WHERE fv.project_id=r.project_id AND fv.floor_id=r.floor_id))""", (project_id,)
            ).fetchall()}
            floor_ids = list(floor_names)
        elements: dict[str, dict] = {}
        for current_floor_id in floor_ids:
            for element in model_review_repository.list_elements(project_id, current_floor_id):
                elements[element["id"]] = element

        enriched: list[dict] = []
        for row in rows:
            source_items: list[dict] = []
            missing: set[str] = set()
            for source_id in row.get("source_ids") or []:
                if source_id in elements:
                    item = elements[source_id]; values = item.get("resolved_data") or {}
                    missing.update(item.get("missing_fields") or [])
                    source_items.append({
                        "id": source_id, "display_number": item.get("display_number"),
                        "item_number": item.get("item_number"), "element_type": item.get("element_type"),
                        "type_code": values.get("type_code") or item.get("type_code") or item.get("tag_text"),
                        "floor_id": item.get("floor_id"), "floor": floor_names.get(item.get("floor_id")),
                        "width_mm": values.get("width_mm"), "height_mm": values.get("height_mm"),
                        "material": values.get("material") or values.get("frame_material"),
                        "finish": values.get("finish"),
                    })
                elif source_id in wall_rows:
                    item = wall_rows[source_id]
                    source_items.append({
                        "id": source_id,
                        "display_number": f"Item {int(item['item_number']):03d}" if item.get("item_number") is not None else item.get("friendly_number"),
                        "item_number": item.get("item_number"), "element_type": "wall",
                        "type_code": item.get("wall_type"), "floor_id": item.get("floor_id"),
                        "floor": floor_names.get(item.get("floor_id")), "quantity": item.get("net_area_m2"),
                    })
                    for name in ("classification", "thickness_mm", "height_mm", "net_area_m2"):
                        if item.get(name) in (None, ""): missing.add(name)
                elif source_id in room_rows:
                    item = room_rows[source_id]
                    source_items.append({
                        "id": source_id, "display_number": item.get("friendly_number") or item.get("name"),
                        "element_type": "floor", "type_code": item.get("floor_type_code"),
                        "floor_id": item.get("floor_id"), "floor": floor_names.get(item.get("floor_id")),
                        "quantity": item.get("area_m2"), "finish": item.get("floor_finish") or item.get("finish_code"),
                    })
                    if not (item.get("floor_finish") or item.get("finish_code")): missing.add("floor_finish")
            next_row = dict(row)
            next_row["source_items"] = sorted(
                source_items, key=lambda item: (item.get("item_number") is None, item.get("item_number") or 0, str(item.get("display_number") or ""))
            )
            next_row["floor_names"] = [floor_names.get(value, value) for value in row.get("floor_ids") or []]
            next_row["missing_fields"] = sorted(missing)
            enriched.append(next_row)
        return enriched

    @staticmethod
    def _summary(rows: list[dict]) -> dict:
        visible = [row for row in rows if not row.get("excluded")]
        subtotal = sum(float(row.get("amount") or 0) for row in visible)
        return {
            "rows": len(visible), "ready": sum(row.get("status") == "ready" for row in visible),
            "needs_review": sum(row.get("status") == "needs_review" for row in visible),
            "manual": sum(bool(row.get("manual")) for row in visible),
            "doors": sum(row.get("entity_type") == "door" for row in visible),
            "windows": sum(row.get("entity_type") == "window" for row in visible),
            "walls": sum(str(row.get("entity_type") or "").startswith("wall_") for row in visible),
            "floors": sum(row.get("entity_type") == "floor" for row in visible),
            "subtotal": round(subtotal, 2),
        }

    @staticmethod
    def _now() -> str:
        from app.workflow.repo_base import now_iso
        return now_iso()


boq_service = BoqService()
