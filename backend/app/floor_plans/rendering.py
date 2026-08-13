from __future__ import annotations

from pathlib import Path

import fitz

from app.floor_plans.repo import floor_plans_repository
from app.pdf_upload.repo import pdf_upload_repository
from app.storage import storage_paths
from app.storage.storage_service import storage_service


def crop_clip(crop: dict) -> fitz.Rect:
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


def crop_source_path(project_id: str, crop: dict) -> Path:
    document = pdf_upload_repository.get_document(project_id, str(crop["document_id"]))
    if not document:
        raise RuntimeError("The floor source document is no longer available.")
    path = storage_service.ensure_local_file(storage_service.key_to_path(document["storage_key"]))
    if not path.exists():
        raise RuntimeError("The floor source file is not available.")
    return path


def render_preview(project_id: str, crop: dict, *, max_width: int = 900) -> tuple[str, int, int]:
    """Create a lightweight preview immediately after the crop is saved.

    The high-resolution crop and all extraction jobs remain in the worker. This
    small render lets Floor Plans and Scale open without waiting behind AI, BOQ,
    or old-project jobs.
    """
    source_path = crop_source_path(project_id, crop)
    clip = crop_clip(crop)
    page_number = int(crop.get("source_page_number") or 1)
    rotation = int(crop.get("rotation") or 0)
    crop_version = int(crop.get("crop_version") or 1)

    with fitz.open(source_path) as source:
        if source.needs_pass:
            raise RuntimeError("Password-protected source files are not supported.")
        if page_number < 1 or page_number > source.page_count:
            raise RuntimeError("The selected source page is not available.")
        page = source.load_page(page_number - 1)
        safe_clip = clip & page.rect
        if safe_clip.is_empty:
            raise RuntimeError("The crop does not overlap the selected source page.")
        scale = max(0.35, min(2.0, float(max_width) / max(float(safe_clip.width), 1.0)))
        pixmap = page.get_pixmap(
            matrix=fitz.Matrix(scale, scale).prerotate(rotation),
            clip=safe_clip, alpha=False, annots=False,
        )
        preview_path = storage_paths.floor_crop_preview_path(
            project_id, str(crop["floor_id"]), crop_version
        )
        preview_path.parent.mkdir(parents=True, exist_ok=True)
        pixmap.save(preview_path)
        storage_service.upload_file(preview_path)

    return storage_service.path_to_key(preview_path), int(pixmap.width), int(pixmap.height)
