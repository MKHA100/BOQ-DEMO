from __future__ import annotations

import json
from typing import Any, Callable

from app.jobs.job_repository import job_repository
from app.specifications.extract import schedule_extraction_service
from app.specifications.repo import specifications_repository
from app.storage import storage_paths
from app.storage.storage_service import storage_service


def register_specification_processors() -> None:
    from app.jobs.worker import PROCESSORS, register_processor

    processors: tuple[tuple[str, Callable[[dict], dict], str], ...] = (
        ("extract.schedule.doors", _process, "Door schedule"),
        ("extract.schedule.windows", _process, "Window schedule"),
        ("extract.schedule.walls", _process, "Wall schedule"),
        ("extract.schedule.floors", _process, "Floor schedule"),
        ("extract.schedule.specification", _process, "Specification"),
        ("extract.schedule.other", _process, "Supporting file"),
    )
    for task_type, processor, label in processors:
        if task_type in PROCESSORS:
            continue
        register_processor(
            task_type,
            processor,
            category="extract",
            label=label,
            retry_limit=3,
            floor_scoped=False,
        )


def _payload(job: dict) -> dict[str, Any]:
    value = job.get("payload_json")
    if isinstance(value, dict):
        return value
    if not value:
        return {}
    parsed = json.loads(value)
    return parsed if isinstance(parsed, dict) else {}


def _progress(job: dict):
    def callback(progress: int, message: str, partial: dict | None = None) -> None:
        job_repository.update_progress(job["id"], progress=progress, message=message, partial_result=partial)

    return callback


def _process(job: dict) -> dict:
    payload = _payload(job)
    project_id = str(job.get("project_id") or payload.get("project_id") or "")
    source_id = str(payload.get("source_id") or "")
    if not project_id or not source_id:
        raise RuntimeError("Supporting document job scope is incomplete.")
    source = specifications_repository.get_source(project_id, source_id)
    if not source:
        raise RuntimeError("Supporting document is not available.")
    progress = _progress(job)
    progress(4, "Preparing supporting document", None)
    try:
        schema_version = int(source.get("extraction_schema_version") or 1)
        rows = specifications_repository.cache_get(source.get("content_hash"), source["category"], schema_version)
        cache_hit = rows is not None
        if rows is None:
            rows, extraction_method = schedule_extraction_service.extract(source, progress=progress)
            specifications_repository.cache_put(source.get("content_hash"), source["category"], schema_version, rows)
        else:
            extraction_method = "cached_structured"
        progress(94, "Saving extracted details", {"items": len(rows), "cached": cache_hit})
        count, conflicts = specifications_repository.replace_entries(
            source=source,
            rows=rows,
            method=extraction_method,
            extraction_version=int(source.get("schedule_version") or source.get("specification_version") or 1),
        )
        preview = storage_paths.supporting_source_preview_path(project_id, source_id)
        preview_path = schedule_extraction_service.render_preview(source, preview)
        status = "needs_review" if conflicts or count == 0 else "ready"
        specifications_repository.mark_source_status(
            source,
            status=status,
            extraction_status=status,
            extracted_data={"count": count, "category": source["category"]},
            preview_asset_key=storage_service.path_to_key(preview_path) if preview_path else None,
        )
        return {
            "project_id": project_id,
            "source_id": source_id,
            "category": source["category"],
            "record_count": count,
            "status": status,
            "cached": cache_hit,
            "message": "Ready" if status == "ready" else "Needs Review",
        }
    except Exception as exc:
        specifications_repository.mark_source_status(
            source,
            status="failed",
            extraction_status="failed",
            error_message=str(exc),
        )
        raise
