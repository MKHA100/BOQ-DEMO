from __future__ import annotations

import json

from app.jobs.job_service import job_service
from app.jobs.worker import register_processor
from app.database.session import get_connection
from app.walls.service import walls_service
from app.workflow.repo import workflow_repository


def _payload(job: dict) -> dict:
    value = job.get("payload_json")
    if isinstance(value, dict):
        return value
    try:
        parsed = json.loads(value or "{}")
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _versions(job: dict) -> dict:
    value = job.get("input_versions_json")
    if isinstance(value, dict):
        return value
    try:
        parsed = json.loads(value or "{}")
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _enqueue(job: dict, task_type: str, payload: dict | None = None) -> dict:
    with get_connection() as connection:
        current_versions = workflow_repository.get_versions(
            connection, str(job["project_id"]), str(job["floor_id"])
        )
    queued, created = job_service.enqueue(
        task_type=task_type,
        project_id=str(job["project_id"]),
        floor_id=str(job["floor_id"]),
        entity_id=str(job["floor_id"]),
        payload=payload or {"floor_id": str(job["floor_id"])},
        input_versions=current_versions or _versions(job),
        created_by=job.get("created_by"),
    )
    return {"id": queued.get("id"), "task_type": task_type, "created": created}


def build(job: dict) -> dict:
    result = walls_service.process_floor(
        str(job["project_id"]),
        str(job["floor_id"]),
        created_by=job.get("created_by"),
    )
    result["next_job"] = _enqueue(job, "rooms.prepare_lines")
    return {"message": "Walls generated and connected", **result}


def boundary(job: dict) -> dict:
    result = walls_service.classify(str(job["project_id"]), str(job["floor_id"]))
    result["next_job"] = _enqueue(job, "walls.classify")
    return {"message": "Boundary ready", **result}


def classify(job: dict) -> dict:
    result = walls_service.classify(str(job["project_id"]), str(job["floor_id"]))
    result["next_job"] = _enqueue(job, "walls.assign_openings")
    return {"message": "Walls classified", **result}


def assign(job: dict) -> dict:
    result = walls_service.auto_assign_openings(str(job["project_id"]), str(job["floor_id"]))
    result["next_job"] = _enqueue(job, "walls.calculate_areas")
    return {"message": "Openings assigned", **result}


def calculate(job: dict) -> dict:
    payload = _payload(job)
    wall_id = payload.get("wall_id") or payload.get("entity_id")
    project_id = str(job["project_id"])
    floor_id = str(job["floor_id"])
    result = walls_service.calculate(project_id, floor_id, [str(wall_id)] if wall_id else None)
    if job.get("task_type") in {"walls.calculate_areas", "walls.prepare_quantities", "walls.build_centerlines"}:
        result["next_job"] = _enqueue(job, "rooms.prepare_lines")
    return {"message": "Wall quantities ready", **result}


def recalculate_deduction(job: dict) -> dict:
    payload = _payload(job)
    element_id = payload.get("element_id")
    if not element_id:
        return calculate(job)
    result = walls_service.refresh_opening_deduction(
        str(job["project_id"]),
        str(job["floor_id"]),
        str(element_id),
        str(payload["wall_id"]) if payload.get("wall_id") else None,
    )
    # A changed opening can alter adjacent room closure geometry.
    result["next_job"] = _enqueue(
        job,
        "rooms.rebuild_touching",
        {"entity_type": "element", "element_id": str(element_id)},
    )
    return {"message": "Wall opening deduction ready", **result}


def register_walls_processors() -> None:
    register_processor("walls.build_lines", build, category="walls", label="Wall lines", floor_scoped=True)
    register_processor("walls.find_boundary", boundary, category="walls", label="Building boundary", floor_scoped=True)
    register_processor("walls.classify", classify, category="walls", label="Wall classification", floor_scoped=True)
    register_processor("walls.assign_openings", assign, category="walls", label="Opening assignment", floor_scoped=True)
    register_processor("walls.calculate_areas", calculate, category="walls", label="Wall quantities", floor_scoped=True)
    register_processor("walls.recalculate_deduction", recalculate_deduction, category="walls", label="Wall opening deduction", floor_scoped=True)
    register_processor("walls.build_centerlines", build, category="walls", label="Wall centerlines", floor_scoped=True)
    register_processor("walls.prepare_quantities", calculate, category="walls", label="Wall quantities", floor_scoped=True)
