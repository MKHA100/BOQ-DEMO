from __future__ import annotations

import logging
from typing import Any

from app.core.errors import bad_request, not_found
from app.core.config import settings
from app.database.session import get_connection
from app.floor_plans.repo import floor_plans_repository
from app.jobs.job_service import job_service
from app.model_review.repo import model_review_repository
from app.workflow.repo import workflow_repository
from app.workflow.service import workflow_service


logger = logging.getLogger("autoboq.model_review")


class ModelReviewService:
    def enqueue_missing_wall_recoveries(self) -> dict[str, Any]:
        """Backfill automatic recovery for current crops analyzed before upgrade."""
        if not settings.wall_auto_recovery_enabled:
            return {"floors": 0, "scheduled": []}
        scheduled: list[dict[str, Any]] = []
        with get_connection() as connection:
            projects = connection.execute("SELECT id FROM projects").fetchall()
        for project_row in projects:
            project_id = str(project_row["id"])
            for floor in model_review_repository.floor_rows(project_id):
                floor_id = str(floor["id"])
                crop_version = int(floor.get("crop_version") or 0)
                crop_id = str(floor.get("crop_id") or "")
                if crop_version <= 0 or not crop_id or not floor.get("crop_asset_key"):
                    continue
                standard = model_review_repository.get_detection_run(
                    project_id=project_id, floor_id=floor_id, crop_version=crop_version,
                    model_id=settings.roboflow_model_id, analysis_mode="standard",
                )
                recovery = model_review_repository.get_detection_run(
                    project_id=project_id, floor_id=floor_id, crop_version=crop_version,
                    model_id=settings.roboflow_model_id, analysis_mode="wall_recovery",
                )
                if not standard or standard.get("status") != "ready":
                    continue
                if recovery and recovery.get("status") == "ready":
                    continue
                element_version = int(floor.get("element_version") or 0)
                queued, created = job_service.enqueue(
                    task_type="vision.recover_floor_walls",
                    project_id=project_id,
                    floor_id=floor_id,
                    entity_id=floor_id,
                    payload={
                        "floor_id": floor_id, "crop_id": crop_id,
                        "crop_version": crop_version, "analysis_mode": "wall_recovery",
                    },
                    input_versions={
                        "crop_version": crop_version, "element_version": element_version,
                        "model_id": settings.roboflow_model_id,
                        "analysis_mode": "wall_recovery",
                    },
                    created_by=None,
                )
                if created:
                    scheduled.append({"id": queued.get("id"), "floor_id": floor_id})
        return {"floors": len(scheduled), "scheduled": scheduled}

    def get_state(self, project: dict, floor_id: str | None = None) -> dict:
        """Return the last committed current-crop state without scheduling work."""
        project_id = project["id"]
        active_jobs = job_service.list_project_jobs(project_id=project_id, active_only=True, limit=300)
        counts = model_review_repository.floor_element_counts(project_id)
        model_tasks = {
            "vision.detect_floor_elements", "vision.recover_floor_walls",
            "vision.read_tags", "vision.match_schedules", "measure.elements"
        }
        floors: list[dict[str, Any]] = []
        for row in model_review_repository.floor_rows(project_id):
            crop_rect = ((row.get("coordinates") or {}).get("original_rect") or {})
            crop_version = int(row.get("crop_version") or 0)
            floor_jobs = [
                job for job in active_jobs
                if job.get("floor_id") == row["id"] and job.get("task_type") in model_tasks
            ]
            run = model_review_repository.get_detection_run(
                project_id=project_id, floor_id=row["id"], crop_version=crop_version,
                model_id=settings.roboflow_model_id,
                analysis_mode="standard",
            ) if crop_version else None
            count = counts.get(row["id"], {})
            results_available = bool(count.get("active", 0) or (run and run.get("status") == "ready"))
            if floor_jobs:
                detection_status = "results_available" if results_available else "processing"
            elif run and run.get("status") == "failed":
                detection_status = "failed"
            elif results_available:
                detection_status = "ready"
            else:
                detection_status = "not_ready"
            floors.append({
                "id": row["id"],
                "name": row["name"],
                "level_index": int(row["level_index"]),
                "crop_version": crop_version,
                "scale_version": int(row.get("scale_version") or 0),
                "element_version": int(row.get("element_version") or 0),
                "drawing_url": f"/api/v1/projects/{project_id}/floor-plans/floors/{row['id']}/crop-asset" if row.get("crop_asset_key") else None,
                "drawing_width": float(crop_rect.get("width") or 1),
                "drawing_height": float(crop_rect.get("height") or 1),
                "active_jobs": floor_jobs,
                "detection_status": detection_status,
                "results_available": results_available,
                "element_count": count.get("active", 0),
                "needs_review_count": count.get("needs_review", 0),
                "confirmed_count": count.get("confirmed", 0),
            })
        selected = floor_id or (floors[0]["id"] if floors else None)
        elements = model_review_repository.list_elements(project_id, selected) if selected else []
        return {
            "project_id": project_id,
            "floors": floors,
            "selected_floor_id": selected,
            "elements": elements,
            "schedule_entries": model_review_repository.list_schedule_entries(project_id),
        }

    def analyze_floor(self, *, project_id: str, floor_id: str, analysis_mode: str, created_by: str | None) -> dict:
        """Queue standard or explicit deep analysis for the current crop."""
        self._require_floor(project_id, floor_id)
        mode = str(analysis_mode or "standard").strip().lower()
        if mode not in {"standard", "deep"}:
            raise bad_request("Unknown model analysis mode.")
        if mode == "deep" and not settings.roboflow_deep_analysis_enabled:
            raise bad_request("Deep model analysis is disabled.")
        crop = floor_plans_repository.current_crop(project_id, floor_id)
        if not crop or not crop.get("crop_asset_key"):
            raise bad_request("The current floor crop is not ready.")
        crop_version = int(crop.get("crop_version") or 0)
        with get_connection() as connection:
            versions = connection.execute(
                "SELECT * FROM floor_versions WHERE project_id = ? AND floor_id = ?",
                (project_id, floor_id),
            ).fetchone()
        version_payload = {
            key: int(versions[key] or 0)
            for key in versions.keys()
            if key.endswith("_version")
        } if versions else {"crop_version": crop_version}
        version_payload["crop_version"] = crop_version
        job, created = job_service.enqueue(
            task_type="vision.detect_floor_elements",
            project_id=project_id,
            floor_id=floor_id,
            entity_id=f"{floor_id}:{mode}",
            payload={
                "floor_id": floor_id,
                "crop_id": crop.get("id"),
                "crop_version": crop_version,
                "analysis_mode": mode,
            },
            input_versions={**version_payload, "model_id": settings.roboflow_model_id, "analysis_mode": mode},
            created_by=created_by,
        )
        return {"job": job, "created": created, "analysis_mode": mode}

    def create(self, *, project_id: str, floor_id: str, payload: dict, created_by: str | None) -> dict:
        self._require_floor(project_id, floor_id)
        with get_connection() as connection:
            versions = workflow_repository.increment_floor_version(connection, project_id, floor_id, "element_version")
        record = model_review_repository.create_element(
            project_id=project_id,
            floor_id=floor_id,
            element_type=payload["element_type"],
            geometry=payload["geometry"],
            type_code=payload.get("type_code"),
            source="user_confirmed",
            confidence=1.0,
            detection_version=int(versions["element_version"]),
            is_manual=True,
            provider_name="manual",
            created_by=created_by,
        )
        record = model_review_repository.update_element(project_id, floor_id, record["id"], {"status":"confirmed"}, element_version=int(versions["element_version"]), user_confirmed=True)
        jobs = self._downstream(project_id, floor_id, record["id"], versions, created_by)
        return {"record": record, "jobs": jobs, "versions": self._versions(versions)}

    def update(self, *, project_id: str, floor_id: str, element_id: str, payload: dict, created_by: str | None) -> dict:
        current = model_review_repository.get_element(project_id, floor_id, element_id)
        if not current:
            raise not_found("Element not found.")
        updates: dict[str, Any] = {}
        if payload.get("geometry") is not None:
            updates["geometry_json"] = payload["geometry"]
        if "type_code" in payload and payload.get("type_code") is not None:
            updates["type_code"] = payload["type_code"].strip() or None
        if payload.get("review_status") is not None:
            updates["status"] = payload["review_status"]
        if payload.get("excluded") is not None:
            updates["excluded"] = 1 if payload["excluded"] else 0
        if "tag_text" in payload and payload.get("tag_text") is not None:
            updates["tag_text"] = payload["tag_text"].strip() or None
        if not updates:
            return {"record": current, "jobs": [], "versions": {}}
        with get_connection() as connection:
            versions = workflow_repository.increment_floor_version(connection, project_id, floor_id, "element_version")
        confirmed = payload.get("review_status") == "confirmed" or current.get("user_confirmed")
        record = model_review_repository.update_element(project_id, floor_id, element_id, updates, element_version=int(versions["element_version"]), user_confirmed=bool(confirmed))
        jobs = self._downstream(
            project_id, floor_id, element_id, versions, created_by,
            geometry_changed=payload.get("geometry") is not None and current.get("element_type") == "door",
        )
        return {"record": record, "jobs": jobs, "versions": self._versions(versions)}

    def update_property(self, *, project_id: str, floor_id: str, element_id: str, property_name: str, value: Any, unit: str | None, confirm: bool, created_by: str | None) -> dict:
        current = model_review_repository.get_element(project_id, floor_id, element_id)
        if not current:
            raise not_found("Element not found.")
        return workflow_service.update_element_property(
            project_id=project_id,
            element_id=element_id,
            property_name=property_name,
            value=value,
            unit=unit,
            source="user_confirmed" if confirm else "model",
            confirm=confirm,
            created_by=created_by,
        )

    def assign_schedule(self, *, project_id: str, floor_id: str, element_id: str, schedule_entry_id: str, created_by: str | None) -> dict:
        current = model_review_repository.get_element(project_id, floor_id, element_id)
        if not current:
            raise not_found("Element not found.")
        entry = next((item for item in model_review_repository.list_schedule_entries(project_id) if item["id"] == schedule_entry_id), None)
        if not entry:
            raise not_found("Schedule entry not found.")
        category = entry.get("category")
        if category != current.get("element_type"):
            raise bad_request("The selected schedule does not match this element.")
        data = entry.get("data") or {}
        for name, unit in (("width_mm","mm"),("height_mm","mm"),("material",None),("frame_material",None),("finish",None),("glass_type",None),("fire_rating",None)):
            if data.get(name) not in (None, ""):
                workflow_service.update_element_property(
                    project_id=project_id,
                    element_id=element_id,
                    property_name=name,
                    value=data[name],
                    unit=unit,
                    source="schedule",
                    confirm=False,
                    created_by=created_by,
                )
        with get_connection() as connection:
            versions = workflow_repository.increment_floor_version(connection, project_id, floor_id, "element_version")
        record = model_review_repository.update_element(
            project_id,
            floor_id,
            element_id,
            {"assigned_schedule_entry_id": schedule_entry_id, "type_code": (entry.get("data") or {}).get("type_code") or current.get("type_code")},
            element_version=int(versions["element_version"]),
            user_confirmed=current.get("user_confirmed"),
        )
        return {"record": record, "versions": self._versions(versions), "jobs": self._downstream(project_id,floor_id,element_id,versions,created_by)}

    def confirm_many(self, *, project_id: str, floor_id: str, element_ids: list[str], created_by: str | None) -> dict:
        self._require_floor(project_id, floor_id)
        unique_ids = list(dict.fromkeys(str(item) for item in element_ids if item))
        if not unique_ids:
            return {"items": [], "count": 0, "jobs": []}
        existing = {item["id"] for item in model_review_repository.list_elements(project_id, floor_id)}
        if any(item_id not in existing for item_id in unique_ids):
            raise not_found("One or more elements were not found.")
        with get_connection() as connection:
            versions = workflow_repository.increment_floor_version(
                connection, project_id, floor_id, "element_version"
            )
        updated = model_review_repository.confirm_elements(
            project_id, floor_id, unique_ids, element_version=int(versions["element_version"])
        )
        jobs = []
        for task_type in ("review.refresh", "boq.refresh"):
            job, created = job_service.enqueue(
                task_type=task_type, project_id=project_id, floor_id=floor_id,
                payload={"entity_type": "elements", "element_ids": unique_ids},
                input_versions=self._versions(versions), created_by=created_by,
            )
            jobs.append({**job, "created": created})
        return {"items": updated, "count": len(updated), "jobs": jobs}

    def _downstream(
        self,
        project_id: str,
        floor_id: str,
        element_id: str,
        versions: dict,
        created_by: str | None,
        geometry_changed: bool = False,
    ) -> list[dict]:
        jobs = []
        tasks = ["walls.recalculate_deduction"]
        if geometry_changed:
            tasks.append("rooms.rebuild_touching")
        else:
            tasks.extend(["review.refresh", "boq.refresh"])
        for task_type in tasks:
            payload = {"entity_type": "element", "entity_id": element_id, "element_id": element_id}
            job, created = job_service.enqueue(
                task_type=task_type,
                project_id=project_id,
                floor_id=floor_id,
                entity_id=element_id,
                payload=payload,
                input_versions=self._versions(versions),
                created_by=created_by,
            )
            jobs.append({**job, "created": created})
        return jobs

    @staticmethod
    def _versions(versions: dict) -> dict:
        return {key:int(value or 0) for key,value in versions.items() if key.endswith("_version")}

    @staticmethod
    def _require_floor(project_id: str, floor_id: str) -> None:
        with get_connection() as connection:
            row = connection.execute("SELECT id FROM floors WHERE project_id=? AND id=?", (project_id,floor_id)).fetchone()
        if not row:
            raise not_found("Floor not found.")


model_review_service = ModelReviewService()
