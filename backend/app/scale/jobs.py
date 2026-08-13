from __future__ import annotations

from app.database.session import get_connection
from app.jobs.worker import register_processor
from app.workflow.repo_base import now_iso


def _mark_elements(job: dict) -> dict:
    floor_id = job.get("floor_id")
    project_id = job.get("project_id")
    with get_connection() as connection:
        connection.execute(
            "UPDATE elements SET measurement_status='ready', updated_at=? WHERE project_id=? AND floor_id=? AND excluded=0",
            (now_iso(), project_id, floor_id),
        )
        total = connection.execute(
            "SELECT COUNT(*) AS total FROM elements WHERE project_id=? AND floor_id=? AND excluded=0",
            (project_id, floor_id),
        ).fetchone()["total"]
    return {"message": "Measurements ready", "updated": int(total or 0)}


def _prepare(job: dict) -> dict:
    return {"message": "Ready", "floor_id": job.get("floor_id")}


def register_scale_processors() -> None:
    register_processor("measure.elements", _mark_elements, category="measure", label="Element measurements", floor_scoped=True)
    register_processor("walls.build_centerlines", _prepare, category="walls", label="Wall centerlines", floor_scoped=True)
    register_processor("walls.prepare_quantities", _prepare, category="walls", label="Wall quantities", floor_scoped=True)
    register_processor("rooms.prepare_geometry", _prepare, category="rooms", label="Room geometry", floor_scoped=True)
