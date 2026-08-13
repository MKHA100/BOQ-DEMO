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

class SummaryServiceMixin:
    def get_summary(self, *, project_id: str, project: dict) -> dict:
        with get_connection() as connection:
            project_versions = workflow_repository.ensure_project_versions(connection, project_id)
            floors = workflow_repository.list_floors(project_id)
            counts = {
                "documents": self._count(connection, "documents", project_id),
                "document_pages": self._count(connection, "document_pages", project_id),
                "extraction_records": self._count(connection, "extraction_records", project_id),
                "floors": self._count(connection, "floors", project_id),
                "floor_crops": self._count(connection, "floor_crops", project_id, "is_current = 1"),
                "schedule_files": self._count(connection, "schedule_files", project_id),
                "specification_files": self._count(connection, "specification_files", project_id),
                "elements": self._count(connection, "elements", project_id, "excluded = 0 AND (COALESCE(is_manual,0)=1 OR COALESCE(generated_status,'current')='current')"),
                "walls": self._count(connection, "walls", project_id, "COALESCE(generated_status,'current')='current'"),
                "rooms": self._count(connection, "rooms", project_id, "excluded = 0 AND COALESCE(generated_status,'current')='current'"),
                "review_issues": self._count(connection, "review_issues", project_id, "status = 'needs_review'"),
                "boq_rows": self._count(connection, "boq_rows", project_id),
            }
            active_rows = connection.execute(
                """
                SELECT id, project_id, floor_id, category, task_type, status, progress, message, created_at, updated_at
                FROM job_runs WHERE project_id = ? AND status IN ('pending', 'running')
                ORDER BY created_at ASC LIMIT 100
                """,
                (project_id,),
            ).fetchall()
            floor_summaries = [self._floor_summary(connection, floor) for floor in floors]
            steps = self._step_statuses(connection, project_id, counts, floor_summaries)
        return {
            "project": project,
            "project_versions": self._version_values(project_versions),
            "floors": floor_summaries,
            "counts": counts,
            "steps": steps,
            "active_jobs": [dict(row) for row in active_rows],
            "updated_at": max([project.get("updated_at") or "", project_versions.get("updated_at") or "", now_iso()]),
        }

    def _floor_summary(self, connection: Any, floor: dict) -> dict:
        floor_id = floor["id"]
        versions = workflow_repository.ensure_floor_versions(connection, floor["project_id"], floor_id)
        room_rows = connection.execute(
            """SELECT boundary_source,measurement_status,status FROM rooms
               WHERE project_id=? AND floor_id=? AND excluded=0
                 AND COALESCE(is_finish_zone,0)=0
                 AND COALESCE(generated_status,'current')='current'""",
            (floor["project_id"], floor_id),
        ).fetchall()
        room_tasks = {
            str(row["task_type"])
            for row in connection.execute(
                """SELECT task_type FROM job_runs WHERE project_id=? AND floor_id=?
                   AND status IN ('pending','running')""",
                (floor["project_id"], floor_id),
            ).fetchall()
        }
        if room_tasks.intersection({"rooms.interpret_floor", "rooms.interpret_ambiguous"}):
            room_analysis_status = "interpreting"
        elif any(
            task in room_tasks
            for task in {
                "rooms.prepare_lines",
                "rooms.build_polygons",
                "rooms.reconcile",
                "rooms.precision_refine",
                "rooms.calculate_areas",
            }
        ):
            room_analysis_status = "correcting"
        elif room_rows and all(
            row["measurement_status"] == "correct" and row["status"] in {"ready", "confirmed"}
            for row in room_rows
        ):
            room_analysis_status = "ready"
        elif room_rows and all(str(row["boundary_source"] or "") == "model_only" for row in room_rows):
            room_analysis_status = "detected"
        elif room_rows:
            room_analysis_status = "needs_review"
        else:
            room_analysis_status = "not_ready"
        return {
            "id": floor_id,
            "project_id": floor["project_id"],
            "name": floor["name"],
            "level_index": int(floor["level_index"]),
            "status": floor["status"],
            "room_analysis_status": room_analysis_status,
            "versions": self._version_values(versions),
            "counts": {
                "elements": self._count_floor(connection, "elements", floor["project_id"], floor_id, "excluded = 0 AND (COALESCE(is_manual,0)=1 OR COALESCE(generated_status,'current')='current')"),
                "walls": self._count_floor(connection, "walls", floor["project_id"], floor_id, "COALESCE(generated_status,'current')='current'"),
                "rooms": self._count_floor(connection, "rooms", floor["project_id"], floor_id, "excluded = 0 AND COALESCE(generated_status,'current')='current'"),
                "review_issues": self._count_floor(connection, "review_issues", floor["project_id"], floor_id, "status = 'needs_review'"),
            },
        }

    def _step_statuses(self, connection: Any, project_id: str, counts: dict, floors: list[dict]) -> list[dict]:
        floor_count = int(counts.get("floors") or 0)
        current_crops = connection.execute(
            """SELECT fc.floor_id,fc.crop_version,fc.status,fc.preview_asset_key,fc.crop_asset_key
               FROM floor_crops fc WHERE fc.project_id=? AND fc.is_current=1""",
            (project_id,),
        ).fetchall()
        crop_by_floor = {str(row["floor_id"]): row for row in current_crops}
        plans_ready = bool(floor_count) and len(crop_by_floor) >= floor_count and all(
            row["preview_asset_key"] or row["crop_asset_key"] for row in current_crops
        )

        category_rows = connection.execute(
            "SELECT category,status FROM specification_category_states WHERE project_id=?", (project_id,)
        ).fetchall()
        required_categories = {"door_schedule","window_schedule","wall_schedule","floor_schedule","specification","other"}
        category_status = {str(row["category"]): str(row["status"]) for row in category_rows}
        specifications_ready = required_categories.issubset(category_status) and all(
            category_status[key] in {"ready","skipped"} for key in required_categories
        )

        calibrated_floors = {
            str(row["floor_id"])
            for row in connection.execute(
                """SELECT c.floor_id FROM calibrations c
                   JOIN floor_crops fc ON fc.project_id=c.project_id AND fc.floor_id=c.floor_id AND fc.is_current=1
                   WHERE c.project_id=? AND c.status IN ('calibrated','confirmed')
                     AND c.source_crop_version=fc.crop_version""",
                (project_id,),
            ).fetchall()
        }
        scale_ready = bool(floor_count) and len(calibrated_floors) >= floor_count

        ready_detection_floors = {
            str(row["floor_id"])
            for row in connection.execute(
                """SELECT r.floor_id FROM floor_element_detection_runs r
                   JOIN floor_crops fc ON fc.id=r.crop_id AND fc.is_current=1
                   WHERE r.project_id=? AND r.crop_version=fc.crop_version
                     AND r.analysis_mode='standard' AND r.status='ready'""",
                (project_id,),
            ).fetchall()
        }
        active_element_count = int(connection.execute(
            """SELECT COUNT(*) AS total FROM elements e
               WHERE e.project_id=? AND e.excluded=0
                 AND (COALESCE(e.is_manual,0)=1 OR COALESCE(e.generated_status,'current')='current')
                 AND (e.crop_version IS NULL OR e.crop_version=(SELECT fc.crop_version FROM floor_crops fc
                    WHERE fc.project_id=e.project_id AND fc.floor_id=e.floor_id AND fc.is_current=1
                    ORDER BY fc.crop_version DESC LIMIT 1))""",
            (project_id,),
        ).fetchone()["total"] or 0)
        element_review_count = int(connection.execute(
            """SELECT COUNT(*) AS total FROM elements e
               WHERE e.project_id=? AND e.excluded=0 AND e.status='needs_review'
                 AND (COALESCE(e.is_manual,0)=1 OR COALESCE(e.generated_status,'current')='current')
                 AND (e.crop_version IS NULL OR e.crop_version=(SELECT fc.crop_version FROM floor_crops fc
                    WHERE fc.project_id=e.project_id AND fc.floor_id=e.floor_id AND fc.is_current=1
                    ORDER BY fc.crop_version DESC LIMIT 1))""",
            (project_id,),
        ).fetchone()["total"] or 0)
        model_ready = bool(floor_count) and len(ready_detection_floors) >= floor_count

        current_walls = int(connection.execute(
            """SELECT COUNT(*) AS total FROM walls w WHERE w.project_id=?
               AND COALESCE(w.generated_status,'current')='current'
               AND (w.source_crop_version IS NULL OR w.source_crop_version=(SELECT crop_version FROM floor_versions fv
                    WHERE fv.project_id=w.project_id AND fv.floor_id=w.floor_id))""",
            (project_id,),
        ).fetchone()["total"] or 0)
        ready_walls = int(connection.execute(
            """SELECT COUNT(*) AS total FROM walls w WHERE w.project_id=? AND w.is_stale=0
               AND w.status IN ('ready','confirmed') AND COALESCE(w.generated_status,'current')='current'
               AND (w.source_crop_version IS NULL OR w.source_crop_version=(SELECT crop_version FROM floor_versions fv
                    WHERE fv.project_id=w.project_id AND fv.floor_id=w.floor_id))""",
            (project_id,),
        ).fetchone()["total"] or 0)
        current_rooms = int(connection.execute(
            """SELECT COUNT(*) AS total FROM rooms r WHERE r.project_id=? AND r.excluded=0
               AND COALESCE(r.generated_status,'current')='current'
               AND (r.source_crop_version IS NULL OR r.source_crop_version=(SELECT crop_version FROM floor_versions fv
                    WHERE fv.project_id=r.project_id AND fv.floor_id=r.floor_id))""",
            (project_id,),
        ).fetchone()["total"] or 0)
        ready_rooms = int(connection.execute(
            """SELECT COUNT(*) AS total FROM rooms r WHERE r.project_id=? AND r.excluded=0
               AND COALESCE(r.is_finish_zone,0)=0 AND r.is_stale=0
               AND r.measurement_status='correct' AND r.status IN ('ready','confirmed')
               AND COALESCE(r.generated_status,'current')='current'
               AND (r.source_crop_version IS NULL OR r.source_crop_version=(SELECT crop_version FROM floor_versions fv
                    WHERE fv.project_id=r.project_id AND fv.floor_id=r.floor_id))""",
            (project_id,),
        ).fetchone()["total"] or 0)
        ready_boq = int(connection.execute(
            "SELECT COUNT(*) AS total FROM boqs WHERE project_id=? AND is_stale=0 AND status='ready'",
            (project_id,),
        ).fetchone()["total"] or 0)

        active_tasks = {
            str(row["task_type"])
            for row in connection.execute(
                "SELECT task_type FROM job_runs WHERE project_id=? AND status IN ('pending','running')",
                (project_id,),
            ).fetchall()
        }
        failed_tasks = {
            str(row["task_type"])
            for row in connection.execute(
                "SELECT task_type FROM job_runs WHERE project_id=? AND status='failed' ORDER BY updated_at DESC LIMIT 50",
                (project_id,),
            ).fetchall()
        }

        def activity_state(base: str, tasks: set[str], *, has_results: bool = False) -> str:
            if active_tasks.intersection(tasks):
                return "results_available" if has_results else "processing"
            if base == "not_ready" and failed_tasks.intersection(tasks):
                return "failed"
            return base

        plans_base = "ready" if plans_ready else "not_ready"
        specs_base = "ready" if specifications_ready else "not_ready"
        scale_base = "ready" if scale_ready else "not_ready"
        if model_ready:
            model_base = "needs_review" if element_review_count else "ready"
        elif active_element_count:
            model_base = "needs_review"
        else:
            model_base = "not_ready"
        walls_base = "ready" if ready_walls and ready_walls == current_walls else ("needs_review" if current_walls else "not_ready")
        rooms_base = "ready" if ready_rooms and ready_rooms == current_rooms else ("needs_review" if current_rooms else "not_ready")
        review_base = "needs_review" if counts["review_issues"] else ("ready" if active_element_count or current_walls or current_rooms else "not_ready")
        boq_base = "ready" if ready_boq else ("needs_review" if counts["boq_rows"] else "not_ready")

        steps = [
            ("upload", "Upload PDF", "ready" if counts["documents"] else "not_ready"),
            ("floor-plans", "Floor Plans", activity_state(plans_base,{"render.floor_crop"},has_results=plans_ready)),
            ("specifications", "Schedules & Specifications", activity_state(specs_base,{
                "extract.schedule","extract.specification","extract.doors","extract.windows","extract.walls"
            },has_results=specifications_ready)),
            ("scale", "Scale", activity_state(scale_base,{"measure.elements","rooms.calculate_areas"},has_results=scale_ready)),
            ("model-review", "Model Review", activity_state(model_base,{
                "vision.detect_floor_elements","vision.recover_floor_walls",
                "vision.read_tags","vision.match_schedules","measure.elements"
            },has_results=bool(active_element_count))),
            ("walls", "Walls", activity_state(walls_base,{task for task in active_tasks if task.startswith("walls.")},has_results=bool(current_walls))),
            ("floors", "Floors", activity_state(rooms_base,{task for task in active_tasks if task.startswith("rooms.") or task=="vision.detect_rooms"},has_results=bool(current_rooms))),
            ("review", "Review", activity_state(review_base,{"review.refresh"},has_results=bool(active_element_count or current_walls or current_rooms))),
            ("boq", "BOQ", activity_state(boq_base,{"boq.refresh","export.generate"},has_results=bool(counts["boq_rows"]))),
        ]
        return [{"key":key,"label":label,"status":state} for key,label,state in steps]
