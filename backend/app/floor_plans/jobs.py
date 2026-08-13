from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

import fitz

from app.core.config import settings

from app.floor_plans.repo import floor_plans_repository
from app.jobs.job_repository import job_repository
from app.jobs.job_service import job_service
from app.pdf_upload.repo import pdf_upload_repository
from app.storage import storage_paths
from app.storage.storage_service import storage_service


def register_floor_plan_processors() -> None:
    from app.jobs.worker import PROCESSORS, register_processor

    processors: tuple[tuple[str, Callable[[dict], dict], str, str], ...] = (
        ("render.floor_crop", render_floor_crop, "render", "Floor crop preview"),
        ("extract.floor_crop_text", extract_floor_crop_text, "extract", "Floor drawing notes"),
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
            floor_scoped=True,
        )


def _payload(job: dict) -> dict[str, Any]:
    value = job.get("payload_json")
    if isinstance(value, dict):
        return value
    parsed = json.loads(value or "{}")
    return parsed if isinstance(parsed, dict) else {}


def _scope(job: dict) -> tuple[str, str, str]:
    payload = _payload(job)
    project_id = str(job.get("project_id") or payload.get("project_id") or "")
    floor_id = str(job.get("floor_id") or payload.get("floor_id") or "")
    crop_id = str(payload.get("crop_id") or "")
    if not project_id or not floor_id or not crop_id:
        raise RuntimeError("Floor crop job scope is incomplete.")
    return project_id, floor_id, crop_id


def _load_source(project_id: str, crop: dict) -> tuple[dict, Path]:
    document = pdf_upload_repository.get_document(project_id, str(crop["document_id"]))
    if not document:
        raise RuntimeError("The floor source document is no longer available.")
    path = storage_service.ensure_local_file(storage_service.key_to_path(document["storage_key"]))
    if not path.exists():
        raise RuntimeError("The floor source file is not available.")
    return document, path


def _clip(crop: dict) -> fitz.Rect:
    coordinates = floor_plans_repository.decode_crop(crop).get("coordinates") or {}
    rect = coordinates.get("original_rect") or {}
    clip = fitz.Rect(
        float(rect.get("x") or 0),
        float(rect.get("y") or 0),
        float(rect.get("x") or 0) + float(rect.get("width") or 0),
        float(rect.get("y") or 0) + float(rect.get("height") or 0),
    )
    if clip.is_empty or clip.width <= 0 or clip.height <= 0:
        raise RuntimeError("The saved floor crop is invalid.")
    return clip


def _report(job: dict, progress: int, message: str, partial: dict | None = None) -> None:
    job_repository.update_progress(
        job["id"],
        progress=max(1, min(int(progress), 99)),
        message=message,
        partial_result=partial,
    )


def render_floor_crop(job: dict) -> dict:
    project_id, floor_id, crop_id = _scope(job)
    crop = floor_plans_repository.get_crop(project_id, crop_id)
    if not crop or str(crop["floor_id"]) != floor_id:
        raise RuntimeError("The floor crop no longer exists.")
    if not bool(crop.get("is_current")):
        return {"crop_id": crop_id, "floor_id": floor_id, "message": "A newer floor crop is already saved"}

    _, source_path = _load_source(project_id, crop)
    clip = _clip(crop)
    page_number = int(crop.get("source_page_number") or 1)
    rotation = int(crop.get("rotation") or 0)
    crop_version = int(crop.get("crop_version") or 1)
    render_dpi = int(crop.get("render_dpi") or 144)

    _report(job, 10, "Preparing floor crop", {"floor_id": floor_id, "crop_version": crop_version})
    with fitz.open(source_path) as source:
        if source.needs_pass:
            raise RuntimeError("Password-protected source files are not supported.")
        if page_number < 1 or page_number > source.page_count:
            raise RuntimeError("The selected source page is not available.")
        page = source.load_page(page_number - 1)
        safe_clip = clip & page.rect
        if safe_clip.is_empty:
            raise RuntimeError("The crop does not overlap the selected source page.")

        crop_scale = max(render_dpi / 72.0, 0.5)
        crop_pixmap = page.get_pixmap(
            matrix=fitz.Matrix(crop_scale, crop_scale).prerotate(rotation),
            clip=safe_clip,
            alpha=False,
            annots=False,
        )
        crop_path = storage_paths.floor_crop_asset_path(project_id, floor_id, crop_version)
        crop_path.parent.mkdir(parents=True, exist_ok=True)
        crop_pixmap.save(crop_path)
        storage_service.upload_file(crop_path)

        preview_scale = min(1.0, 900.0 / max(float(crop_pixmap.width), 1.0))
        if preview_scale < 0.999:
            preview_dpi_scale = max(crop_scale * preview_scale, 0.15)
            preview_pixmap = page.get_pixmap(
                matrix=fitz.Matrix(preview_dpi_scale, preview_dpi_scale).prerotate(rotation),
                clip=safe_clip,
                alpha=False,
                annots=False,
            )
        else:
            preview_pixmap = crop_pixmap
        preview_path = storage_paths.floor_crop_preview_path(project_id, floor_id, crop_version)
        preview_path.parent.mkdir(parents=True, exist_ok=True)
        preview_pixmap.save(preview_path)
        storage_service.upload_file(preview_path)

    _report(job, 90, "Saving floor preview", {"floor_id": floor_id, "crop_version": crop_version})
    floor_plans_repository.mark_crop_ready(
        crop_id,
        storage_service.path_to_key(crop_path),
        storage_service.path_to_key(preview_path),
    )
    downstream_jobs: list[dict[str, Any]] = []
    for task_type in (
        "vision.detect_rooms",
        "extract.floor_crop_text",
        "vision.detect_floor_elements",
    ):
        task_versions = {"crop_version": crop_version}
        if task_type == "vision.detect_floor_elements":
            task_versions.update({"model_id": settings.roboflow_model_id, "analysis_mode": "standard"})
        elif task_type == "vision.detect_rooms":
            task_versions.update({"model_id": settings.roboflow_floor_model_id, "analysis_mode": "standard"})
        queued, created = job_service.enqueue(
            task_type=task_type, project_id=project_id, floor_id=floor_id,
            entity_id=floor_id,
            payload={
                "floor_id": floor_id, "crop_id": crop_id, "crop_version": crop_version,
                "analysis": "background", "analysis_mode": "standard",
            },
            input_versions=task_versions,
            created_by=job.get("created_by"),
        )
        downstream_jobs.append({"id": queued.get("id"), "task_type": task_type, "created": created})
    return {
        "crop_id": crop_id, "floor_id": floor_id, "crop_version": crop_version,
        "width": int(crop_pixmap.width), "height": int(crop_pixmap.height),
        "downstream_jobs": downstream_jobs, "message": "Floor crop ready",
    }


def extract_floor_crop_text(job: dict) -> dict:
    project_id, floor_id, crop_id = _scope(job)
    crop = floor_plans_repository.get_crop(project_id, crop_id)
    if not crop or str(crop["floor_id"]) != floor_id:
        raise RuntimeError("The floor crop no longer exists.")
    if not bool(crop.get("is_current")):
        return {"crop_id": crop_id, "floor_id": floor_id, "message": "A newer floor crop is already saved"}

    _, source_path = _load_source(project_id, crop)
    clip = _clip(crop)
    page_number = int(crop.get("source_page_number") or 1)
    crop_version = int(crop.get("crop_version") or 1)
    page_record = pdf_upload_repository.get_page(project_id, str(crop["document_id"]), page_number)
    if not page_record:
        raise RuntimeError("The selected source page metadata is not ready.")

    _report(job, 20, "Reading floor drawing notes", {"floor_id": floor_id})
    blocks: list[dict[str, Any]] = []
    text_parts: list[str] = []
    with fitz.open(source_path) as source:
        page = source.load_page(page_number - 1)
        for block in page.get_text("blocks", clip=clip, sort=True):
            if len(block) < 7 or int(block[6]) != 0:
                continue
            text = str(block[4] or "").strip()
            if not text:
                continue
            block_rect = {
                "x0": float(block[0]),
                "y0": float(block[1]),
                "x1": float(block[2]),
                "y1": float(block[3]),
            }
            blocks.append({"text": text, "bbox": block_rect})
            text_parts.append(text)

    text = "\n".join(text_parts).strip()
    records = []
    if text:
        records.append(
            {
                "floor_id": floor_id,
                "document_page_id": page_record["id"],
                "entity_key": f"floor:{floor_id}:crop:{crop_version}:notes",
                "data": {"text": text, "blocks": blocks, "crop_id": crop_id},
                "source_type": "floor_crop",
                "source_location": {
                    "page_number": page_number,
                    "crop_id": crop_id,
                    "rect": floor_plans_repository.decode_crop(crop).get("coordinates", {}).get("original_rect", {}),
                },
                "extraction_method": "vector_text_crop",
                "confidence": 1.0,
                "quality_signal": "vector_text" if blocks else "empty",
                "review_state": "needs_review",
            }
        )
    pdf_upload_repository.replace_extraction_records(
        project_id=project_id,
        document_id=str(crop["document_id"]),
        extraction_type="floor_crop_note",
        extraction_version=crop_version,
        records=records,
        floor_id=floor_id,
    )
    _report(job, 90, "Saving floor drawing notes", {"floor_id": floor_id, "records": len(records)})
    return {
        "crop_id": crop_id,
        "floor_id": floor_id,
        "crop_version": crop_version,
        "records": len(records),
        "message": "Floor drawing notes ready",
    }
