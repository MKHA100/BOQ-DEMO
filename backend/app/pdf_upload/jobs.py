from __future__ import annotations

import json
from typing import Any, Callable

from app.jobs.job_repository import job_repository
from app.pdf_upload.extract import structured_extraction_service
from app.pdf_upload.pdf import pdf_asset_service


def register_pdf_upload_processors() -> None:
    from app.jobs.worker import PROCESSORS, register_processor

    processors: tuple[tuple[str, Callable[[dict], dict], str, str], ...] = (
        ("ingest.page_metadata", _metadata, "ingest", "Page information"),
        ("render.page_thumbnails", _thumbnails, "render", "Page thumbnails"),
        ("render.page_previews", _previews, "render", "Page previews"),
        ("extract.vector_text", _vector_text, "extract", "Drawing text"),
        ("ingest.page_classification", _classification, "ingest", "Page organization"),
        ("extract.doors", _extract_doors, "extract", "Door information"),
        ("extract.windows", _extract_windows, "extract", "Window information"),
        ("extract.walls", _extract_walls, "extract", "Wall information"),
        ("extract.floors", _extract_floors, "extract", "Floor information"),
    )
    for task_type, processor, category, label in processors:
        if task_type in PROCESSORS:
            continue
        register_processor(
            task_type,
            processor,
            category=category,
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


def _scope(job: dict) -> tuple[str, str]:
    payload = _payload(job)
    project_id = str(job.get("project_id") or payload.get("project_id") or "")
    document_id = str(payload.get("document_id") or "")
    if not project_id or not document_id:
        raise RuntimeError("Document job scope is incomplete.")
    return project_id, document_id


def _progress(job: dict):
    def callback(progress: int, message: str, partial: dict | None = None) -> None:
        job_repository.update_progress(
            job["id"],
            progress=progress,
            message=message,
            partial_result=partial,
        )

    return callback


def _metadata(job: dict) -> dict:
    project_id, document_id = _scope(job)
    return pdf_asset_service.ensure_metadata(
        project_id=project_id,
        document_id=document_id,
        progress=_progress(job),
    )


def _thumbnails(job: dict) -> dict:
    project_id, document_id = _scope(job)
    return pdf_asset_service.ensure_thumbnails(
        project_id=project_id,
        document_id=document_id,
        progress=_progress(job),
    )


def _previews(job: dict) -> dict:
    project_id, document_id = _scope(job)
    return pdf_asset_service.ensure_previews(
        project_id=project_id,
        document_id=document_id,
        progress=_progress(job),
    )


def _vector_text(job: dict) -> dict:
    project_id, document_id = _scope(job)
    return pdf_asset_service.ensure_vector_text(
        project_id=project_id,
        document_id=document_id,
        progress=_progress(job),
    )


def _classification(job: dict) -> dict:
    project_id, document_id = _scope(job)
    return pdf_asset_service.ensure_classifications(
        project_id=project_id,
        document_id=document_id,
        progress=_progress(job),
    )


def _extract_doors(job: dict) -> dict:
    return _extract(job, "door")


def _extract_windows(job: dict) -> dict:
    return _extract(job, "window")


def _extract_walls(job: dict) -> dict:
    return _extract(job, "wall")


def _extract_floors(job: dict) -> dict:
    return _extract(job, "floor")


def _extract(job: dict, extraction_type: str) -> dict:
    project_id, document_id = _scope(job)
    return structured_extraction_service.extract(
        project_id=project_id,
        document_id=document_id,
        extraction_type=extraction_type,
        progress=_progress(job),
    )
