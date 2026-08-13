from __future__ import annotations

import json

from app.core.config import settings
from app.floors.service import floors_service
from app.jobs.job_service import job_service
from app.jobs.worker import register_processor


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
    queued, created = job_service.enqueue(
        task_type=task_type,
        project_id=str(job["project_id"]),
        floor_id=str(job["floor_id"]),
        entity_id=str(job["floor_id"]),
        payload=payload or {"floor_id": str(job["floor_id"])},
        input_versions=_versions(job),
        created_by=job.get("created_by"),
    )
    return {"id": queued.get("id"), "created": created, "task_type": task_type}


def _enqueue_read_models(job: dict) -> list[dict]:
    return [
        _enqueue(job, "review.refresh", {"entity_type": "floor", "floor_id": str(job["floor_id"])}),
        _enqueue(job, "boq.refresh", {"entity_type": "floor", "floor_id": str(job["floor_id"])}),
    ]


def detect_rooms(job: dict) -> dict:
    project_id = str(job["project_id"])
    floor_id = str(job["floor_id"])
    result = floors_service.detect_room_suggestions(project_id, floor_id)
    # The model is optional. Local wall geometry must continue whether the
    # hosted model succeeds, is cached, is disabled, or temporarily fails.
    # Enqueueing here also repairs the race where the floor crop becomes ready
    # after the wall pipeline has already finished. Job-key deduplication keeps
    # this safe when Analyze Rooms already queued the same local task.
    # Analyze starts a local wall pass in parallel for fast feedback. Queue a
    # distinct second pass after detection as well, so late model suggestions
    # can never remain as raw measured rooms after the local pass has ended.
    queued, created = job_service.enqueue(
        task_type="rooms.prepare_lines",
        project_id=project_id,
        floor_id=floor_id,
        entity_id=floor_id,
        payload={**_payload(job), "after_detection": True},
        input_versions=_versions(job),
        created_by=job.get("created_by"),
        job_key=f"{job.get('job_key') or job.get('id')}:rooms.prepare_lines:final",
    )
    result["next_job"] = {
        "id": queued.get("id"), "created": created, "task_type": "rooms.prepare_lines"
    }
    if result.get("room_ids") or result.get("published") or result.get("suggestions"):
        # Kept as a separate fast-lane job even though the detection service
        # also publishes synchronously. The publisher is idempotent and this
        # durable step repairs interrupted workers without delaying geometry.
        result["publish_job"] = _enqueue(job, "rooms.publish_model_results")

    return {"message": "Room suggestions ready", **result}



def publish_model_results(job: dict) -> dict:
    result = floors_service.publish_model_results(str(job["project_id"]), str(job["floor_id"]))
    return {"message": "Model room results published", **result}

def prepare(job: dict) -> dict:
    result = floors_service.prepare_lines(str(job["project_id"]), str(job["floor_id"]))
    # Keep the persisted job result small; build_polygons deterministically
    # recomputes the line set so multiple workers remain safe.
    result.pop("prepared", None)
    result["next_job"] = _enqueue(job, "rooms.build_polygons")
    return {"message": "Room boundaries ready", **result}


def build(job: dict) -> dict:
    payload = _payload(job)
    target_ids = payload.get("room_ids") if isinstance(payload.get("room_ids"), list) else None
    result = floors_service.build_polygons(
        str(job["project_id"]),
        str(job["floor_id"]),
        target_room_ids=[str(item) for item in target_ids] if target_ids else None,
    )
    result["next_job"] = _enqueue(job, "rooms.reconcile", payload)
    return {"message": "Room polygons ready", **result}


def reconcile(job: dict) -> dict:
    payload = _payload(job)
    room_ids = payload.get("room_ids") if isinstance(payload.get("room_ids"), list) else None
    result = floors_service.reconcile(
        str(job["project_id"]),
        str(job["floor_id"]),
        [str(item) for item in room_ids] if room_ids else None,
    )
    result["next_job"] = _enqueue(job, "rooms.identify_labels", payload)
    return {"message": "Room results compared", **result}


def labels(job: dict) -> dict:
    result = floors_service.suggest_labels(str(job["project_id"]), str(job["floor_id"]))
    result["next_job"] = _enqueue(job, "rooms.assign_finishes", _payload(job))
    return {"message": "Room labels ready", **result}


def finishes(job: dict) -> dict:
    result = floors_service.assign_finishes(str(job["project_id"]), str(job["floor_id"]))
    if settings.room_llm_enabled and settings.room_llm_background_enabled:
        result["next_job"] = _enqueue(job, "rooms.interpret_floor", _payload(job))
    elif settings.room_precision_pass_enabled:
        result["next_job"] = _enqueue(
            job, "rooms.precision_refine", {**_payload(job), "interpretation_complete": True}
        )
    else:
        result["next_job"] = _enqueue(
            job, "rooms.calculate_areas", {**_payload(job), "precision_complete": True}
        )
    return {"message": "Floor finishes ready", **result}


def calculate(job: dict) -> dict:
    payload = _payload(job)
    room_id = payload.get("room_id") or (
        payload.get("entity_id") if payload.get("entity_type") == "room" else None
    )
    result = floors_service.calculate(
        str(job["project_id"]),
        str(job["floor_id"]),
        [str(room_id)] if room_id else None,
    )
    if settings.room_precision_pass_enabled and not payload.get("precision_complete"):
        result["precision_job"] = _enqueue(job, "rooms.precision_refine", {**payload, "precision_complete": True})
    else:
        result["read_model_jobs"] = _enqueue_read_models(job)
    return {"message": "Floor quantities ready", **result}


def precision(job: dict) -> dict:
    result = floors_service.precision_refine(
        str(job["project_id"]), str(job["floor_id"]), calculate_areas=False
    )
    result["next_job"] = _enqueue(
        job, "rooms.calculate_areas", {**_payload(job), "precision_complete": True}
    )
    return {"message": "Precision room geometry ready", **result}


def interpret_floor(job: dict) -> dict:
    result = floors_service.interpret_floor(str(job["project_id"]), str(job["floor_id"]))
    if settings.room_precision_pass_enabled:
        result["next_job"] = _enqueue(
            job,
            "rooms.precision_refine",
            {**_payload(job), "interpretation_complete": True},
        )
    else:
        result["next_job"] = _enqueue(
            job,
            "rooms.calculate_areas",
            {**_payload(job), "interpretation_complete": True, "precision_complete": True},
        )
    return {"message": "Floor room interpretation checked", **result}


def interpret_ambiguous(job: dict) -> dict:
    return interpret_floor(job)


def touching(job: dict) -> dict:
    payload = _payload(job)
    result = floors_service.recalculate_touching(
        str(job["project_id"]),
        str(job["floor_id"]),
        str(payload.get("wall_id") or payload.get("entity_id")) if payload.get("wall_id") or payload.get("entity_type") == "wall" else None,
        str(payload.get("element_id") or payload.get("entity_id")) if payload.get("element_id") or payload.get("entity_type") in {"door", "window", "element"} else None,
    )
    result["read_model_jobs"] = _enqueue_read_models(job)
    return {"message": "Touching rooms ready", **result}


def register_floors_processors() -> None:
    register_processor(
        "vision.detect_rooms",
        detect_rooms,
        category="vision",
        label="Room suggestions",
        retry_limit=2,
        floor_scoped=True,
    )
    register_processor("rooms.publish_model_results", publish_model_results, category="rooms", label="Publish detected rooms", floor_scoped=True)
    register_processor("rooms.prepare_lines", prepare, category="rooms", label="Room boundaries", floor_scoped=True)
    register_processor("rooms.build_polygons", build, category="rooms", label="Room polygons", floor_scoped=True)
    register_processor("rooms.reconcile", reconcile, category="rooms", label="Room comparison", floor_scoped=True)
    register_processor("rooms.identify_labels", labels, category="rooms", label="Room labels", floor_scoped=True)
    register_processor("rooms.assign_finishes", finishes, category="rooms", label="Floor finishes", floor_scoped=True)
    register_processor("rooms.calculate_areas", calculate, category="rooms", label="Floor quantities", floor_scoped=True)
    register_processor("rooms.precision_refine", precision, category="rooms", label="Precision room geometry", floor_scoped=True)
    register_processor("rooms.interpret_floor", interpret_floor, category="rooms", label="Floor room interpretation", floor_scoped=True)
    register_processor("rooms.interpret_ambiguous", interpret_ambiguous, category="rooms", label="Room label interpretation", floor_scoped=True)
    register_processor("rooms.prepare_geometry", prepare, category="rooms", label="Room geometry", floor_scoped=True)
    register_processor("rooms.build", build, category="rooms", label="Room calculation", floor_scoped=True)
    register_processor("rooms.measure", calculate, category="rooms", label="Room measurement", floor_scoped=True)
    register_processor("rooms.rebuild_touching", touching, category="rooms", label="Touching rooms", floor_scoped=True)
