from __future__ import annotations

import json
from typing import Any

from app.jobs.job_service import job_service
from app.jobs.worker import register_processor
from app.model_review.detection_service import SupersededDetection, unified_floor_detection_service
from app.model_review.tag_service import model_review_tag_service


def _payload(job: dict) -> dict[str, Any]:
    value = job.get("payload_json")
    if isinstance(value, dict):
        return value
    try:
        parsed = json.loads(value or "{}")
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _versions(job: dict) -> dict[str, Any]:
    value = job.get("input_versions_json")
    if isinstance(value, dict):
        return value
    try:
        parsed = json.loads(value or "{}")
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def detect_floor_elements(job: dict) -> dict:
    try:
        return unified_floor_detection_service.run(job)
    except SupersededDetection:
        return {"message": "Superseded by a newer floor crop", "superseded": True}


def recover_floor_walls(job: dict) -> dict:
    try:
        return unified_floor_detection_service.run_wall_recovery(job)
    except SupersededDetection:
        return {"message": "Superseded by a newer floor crop", "superseded": True}


def legacy_detection_alias(job: dict) -> dict:
    """Drain old queued class-specific jobs without repeating model inference."""
    payload = _payload(job)
    versions = _versions(job)
    queued, created = job_service.enqueue(
        task_type="vision.detect_floor_elements",
        project_id=str(job.get("project_id") or ""),
        floor_id=str(job.get("floor_id") or ""),
        entity_id=str(job.get("floor_id") or ""),
        payload={
            "floor_id": job.get("floor_id"),
            "crop_id": payload.get("crop_id"),
            "analysis_mode": payload.get("analysis_mode") or "standard",
        },
        input_versions=versions,
        created_by=job.get("created_by"),
    )
    return {
        "message": "Replaced by unified floor detection",
        "unified_job_id": queued.get("id"),
        "created": created,
    }


def _wait_for(job: dict, task_types: set[str]) -> None:
    active = job_service.list_project_jobs(project_id=str(job["project_id"]), active_only=True, limit=300)
    waiting = [
        item for item in active
        if item.get("id") != job.get("id")
        and item.get("floor_id") == job.get("floor_id")
        and item.get("task_type") in task_types
    ]
    if waiting:
        raise RuntimeError("Waiting for earlier floor analysis tasks.")


def read_tags(job: dict) -> dict:
    _wait_for(job, {"vision.detect_floor_elements"})
    result = model_review_tag_service.read_tags(
        project_id=str(job["project_id"]),
        floor_id=str(job["floor_id"]),
    )
    queued, created = job_service.enqueue(
        task_type="vision.match_schedules", project_id=str(job["project_id"]),
        floor_id=str(job["floor_id"]), entity_id=str(job["floor_id"]),
        payload={"floor_id":str(job["floor_id"])}, input_versions=_versions(job),
        created_by=job.get("created_by"),
    )
    return {**result, "next_job":{"id":queued.get("id"),"created":created}}


def match_schedules(job: dict) -> dict:
    _wait_for(job, {"vision.detect_floor_elements", "vision.read_tags"})
    return model_review_tag_service.match_schedules(
        project_id=str(job["project_id"]),
        floor_id=str(job["floor_id"]),
    )


def register_model_review_processors() -> None:
    register_processor(
        "vision.detect_floor_elements",
        detect_floor_elements,
        category="vision",
        label="Floor element detection",
        retry_limit=2,
        floor_scoped=True,
    )
    register_processor(
        "vision.recover_floor_walls",
        recover_floor_walls,
        category="vision",
        label="Automatic wall recovery",
        retry_limit=2,
        floor_scoped=True,
    )
    # Compatibility registrations allow an existing database queue to drain
    # safely after upgrading from the three-task implementation.
    for legacy, label in (
        ("vision.detect_doors", "Legacy door detection"),
        ("vision.detect_windows", "Legacy window detection"),
        ("vision.detect_walls", "Legacy wall detection"),
    ):
        register_processor(legacy, legacy_detection_alias, category="vision", label=label, retry_limit=1, floor_scoped=True)
    register_processor("vision.read_tags", read_tags, category="vision", label="Tag reading", retry_limit=5, floor_scoped=True)
    register_processor("vision.match_schedules", match_schedules, category="vision", label="Schedule matching", retry_limit=5, floor_scoped=True)
