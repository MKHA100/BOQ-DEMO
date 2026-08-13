from __future__ import annotations

import json
import re
from collections.abc import Callable
from pathlib import Path
from typing import Any

import fitz

from app.core.config import settings
from app.core.errors import not_found
from app.pdf_upload.repo import pdf_upload_repository
from app.storage import storage_paths
from app.storage.storage_service import storage_service

ProgressCallback = Callable[[int, str, dict | None], None]


class PdfAssetService:
    def ensure_metadata(
        self,
        *,
        project_id: str,
        document_id: str,
        progress: ProgressCallback | None = None,
    ) -> dict:
        document = self._require_document(project_id, document_id)
        local_path = self._local_document_path(document)
        with fitz.open(local_path) as pdf:
            if pdf.needs_pass:
                raise RuntimeError("Password-protected PDFs are not supported.")
            page_count = int(pdf.page_count)
            for index in range(page_count):
                page = pdf.load_page(index)
                rect = page.rect
                media_box = page.mediabox
                try:
                    page_label = page.get_label() or None
                except Exception:
                    page_label = None
                pdf_upload_repository.upsert_page_metadata(
                    project_id=project_id,
                    document_id=document_id,
                    page_number=index + 1,
                    page_label=page_label,
                    width_points=float(rect.width),
                    height_points=float(rect.height),
                    rotation=int(page.rotation or 0),
                    media_box={
                        "x0": float(media_box.x0),
                        "y0": float(media_box.y0),
                        "x1": float(media_box.x1),
                        "y1": float(media_box.y1),
                    },
                    version=int(document.get("version") or 1),
                )
                self._report(progress, index + 1, page_count, "Reading page information", {"page_number": index + 1})
        pdf_upload_repository.update_document(
            project_id,
            document_id,
            page_count=page_count,
            status="ready",
        )
        return {"document_id": document_id, "page_count": page_count, "message": "Page information ready"}

    def ensure_thumbnails(
        self,
        *,
        project_id: str,
        document_id: str,
        progress: ProgressCallback | None = None,
    ) -> dict:
        return self._render_pages(
            project_id=project_id,
            document_id=document_id,
            target_width=settings.pdf_thumbnail_width,
            asset="thumbnail",
            progress=progress,
        )

    def ensure_previews(
        self,
        *,
        project_id: str,
        document_id: str,
        progress: ProgressCallback | None = None,
    ) -> dict:
        return self._render_pages(
            project_id=project_id,
            document_id=document_id,
            target_width=settings.pdf_preview_width,
            asset="preview",
            progress=progress,
        )

    def ensure_vector_text(
        self,
        *,
        project_id: str,
        document_id: str,
        progress: ProgressCallback | None = None,
    ) -> dict:
        document = self._require_document(project_id, document_id)
        pages = pdf_upload_repository.list_pages(project_id, document_id)
        if not pages:
            self.ensure_metadata(project_id=project_id, document_id=document_id)
            pages = pdf_upload_repository.list_pages(project_id, document_id)
        local_path = self._local_document_path(document)
        extracted_pages = 0
        with fitz.open(local_path) as pdf:
            total = len(pages)
            for position, page_record in enumerate(pages, start=1):
                page_number = int(page_record["page_number"])
                existing_key = page_record.get("text_layer_key")
                if page_record.get("text_status") == "ready" and existing_key and storage_service.file_exists(storage_service.key_to_path(existing_key)):
                    self._report(progress, position, total, "Reading drawing text", {"page_number": page_number})
                    continue
                page = pdf.load_page(page_number - 1)
                blocks: list[dict[str, Any]] = []
                text_parts: list[str] = []
                for block in page.get_text("blocks", sort=True):
                    if len(block) < 7 or int(block[6]) != 0:
                        continue
                    text = str(block[4] or "").strip()
                    if not text:
                        continue
                    blocks.append(
                        {
                            "bbox": [float(block[0]), float(block[1]), float(block[2]), float(block[3])],
                            "text": text,
                            "block_number": int(block[5]),
                        }
                    )
                    text_parts.append(text)
                text = "\n".join(text_parts).strip()
                payload = {
                    "document_id": document_id,
                    "page_id": page_record["id"],
                    "page_number": page_number,
                    "text": text,
                    "blocks": blocks,
                }
                text_path = storage_paths.page_text_path(project_id, document_id, page_number)
                storage_service.write_bytes(
                    text_path,
                    json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8"),
                )
                pdf_upload_repository.update_page_text(
                    page_id=page_record["id"],
                    storage_key=storage_service.path_to_key(text_path),
                    text_char_count=len(text),
                    vector_text_available=bool(text),
                )
                extracted_pages += 1
                self._report(progress, position, total, "Reading drawing text", {"page_number": page_number})
        pdf_upload_repository.refresh_document_manifest_status(project_id, document_id)
        return {
            "document_id": document_id,
            "page_count": len(pages),
            "updated_pages": extracted_pages,
            "message": "Drawing text ready",
        }

    def ensure_classifications(
        self,
        *,
        project_id: str,
        document_id: str,
        progress: ProgressCallback | None = None,
    ) -> dict:
        self.ensure_vector_text(project_id=project_id, document_id=document_id)
        pages = pdf_upload_repository.list_pages(project_id, document_id)
        total = len(pages)
        for position, page in enumerate(pages, start=1):
            text_payload = self.read_page_text(page)
            classification, confidence = classify_page_text(
                str(text_payload.get("text") or ""),
                page_number=int(page["page_number"]),
            )
            pdf_upload_repository.update_page_classification(
                page_id=page["id"],
                classification=classification,
                confidence=confidence,
            )
            self._report(progress, position, total, "Organizing drawing pages", {"page_number": page["page_number"]})
        pdf_upload_repository.refresh_document_manifest_status(project_id, document_id)
        return {"document_id": document_id, "page_count": total, "message": "Drawing pages organized"}

    def read_page_text(self, page: dict) -> dict:
        key = page.get("text_layer_key")
        if not key:
            return {"text": "", "blocks": []}
        path = storage_service.ensure_local_file(storage_service.key_to_path(key))
        if not path.exists():
            return {"text": "", "blocks": []}
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError, json.JSONDecodeError):
            return {"text": "", "blocks": []}
        return value if isinstance(value, dict) else {"text": "", "blocks": []}

    def _render_pages(
        self,
        *,
        project_id: str,
        document_id: str,
        target_width: int,
        asset: str,
        progress: ProgressCallback | None,
    ) -> dict:
        document = self._require_document(project_id, document_id)
        pages = pdf_upload_repository.list_pages(project_id, document_id)
        if not pages:
            self.ensure_metadata(project_id=project_id, document_id=document_id)
            pages = pdf_upload_repository.list_pages(project_id, document_id)
        local_path = self._local_document_path(document)
        updated = 0
        with fitz.open(local_path) as pdf:
            total = len(pages)
            for position, page_record in enumerate(pages, start=1):
                page_number = int(page_record["page_number"])
                if asset == "thumbnail":
                    existing_key = page_record.get("thumbnail_key")
                    existing_status = page_record.get("thumbnail_status")
                    output_path = storage_paths.page_thumbnail_path(project_id, document_id, page_number)
                    key_column = "thumbnail_key"
                    status_column = "thumbnail_status"
                    width_column = "thumbnail_width"
                    height_column = "thumbnail_height"
                    message = "Creating page thumbnails"
                else:
                    existing_key = page_record.get("preview_key")
                    existing_status = page_record.get("preview_status")
                    output_path = storage_paths.page_preview_path(project_id, document_id, page_number)
                    key_column = "preview_key"
                    status_column = "preview_status"
                    width_column = "preview_width"
                    height_column = "preview_height"
                    message = "Creating page previews"
                if existing_status == "ready" and existing_key and storage_service.file_exists(storage_service.key_to_path(existing_key)):
                    self._report(progress, position, total, message, {"page_number": page_number})
                    continue
                page = pdf.load_page(page_number - 1)
                scale = max(float(target_width) / max(float(page.rect.width), 1.0), 0.1)
                pixmap = page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False, annots=False)
                output_path.parent.mkdir(parents=True, exist_ok=True)
                pixmap.save(output_path)
                storage_service.upload_file(output_path)
                pdf_upload_repository.update_page_asset(
                    page_id=page_record["id"],
                    key_column=key_column,
                    storage_key=storage_service.path_to_key(output_path),
                    status_column=status_column,
                    width_column=width_column,
                    height_column=height_column,
                    width=int(pixmap.width),
                    height=int(pixmap.height),
                )
                updated += 1
                self._report(progress, position, total, message, {"page_number": page_number})
        pdf_upload_repository.refresh_document_manifest_status(project_id, document_id)
        return {
            "document_id": document_id,
            "page_count": len(pages),
            "updated_pages": updated,
            "message": "Page thumbnails ready" if asset == "thumbnail" else "Page previews ready",
        }

    @staticmethod
    def _report(
        progress: ProgressCallback | None,
        current: int,
        total: int,
        message: str,
        partial: dict | None,
    ) -> None:
        if not progress:
            return
        percent = int(round((current / max(total, 1)) * 100))
        progress(max(1, min(percent, 99)), message, partial)

    @staticmethod
    def _local_document_path(document: dict) -> Path:
        return storage_service.ensure_local_file(storage_service.key_to_path(document["storage_key"]))

    @staticmethod
    def _require_document(project_id: str, document_id: str) -> dict:
        document = pdf_upload_repository.get_document(project_id, document_id)
        if not document:
            raise not_found("Document not found.")
        return document


PAGE_CLASSIFICATION_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("door_window_schedule", ("door and window details", "doors and windows details", "door and window schedule", "doors and windows schedule")),
    ("door_schedule", ("door schedule", "door type", "fire rating", "door finish")),
    ("window_schedule", ("window schedule", "window type", "glazing", "glass type")),
    ("wall_schedule", ("wall schedule", "wall type", "wall thickness", "masonry schedule")),
    ("floor_schedule", ("floor finish schedule", "floor schedule", "floor finish", "room finish schedule")),
    ("specification", ("specification", "general notes", "materials and workmanship", "construction notes")),
    ("elevation", ("elevation", "north elevation", "south elevation", "east elevation", "west elevation")),
    ("section", ("section a", "section b", "building section", "cross section")),
    ("floor_plan", ("floor plan", "ground floor", "first floor", "second floor", "roof plan")),
    ("detail", ("detail", "typical detail", "construction detail")),
)


def classify_page_text(text: str, *, page_number: int) -> tuple[str, float]:
    normalized = re.sub(r"\s+", " ", text.lower()).strip()
    if not normalized:
        return ("cover" if page_number == 1 else "other", 0.35)
    scored: list[tuple[int, str]] = []
    for classification, keywords in PAGE_CLASSIFICATION_RULES:
        score = sum(2 if keyword in normalized else 0 for keyword in keywords)
        if classification.endswith("schedule") and "schedule" in normalized:
            score += 1
        if score:
            scored.append((score, classification))
    if not scored:
        if page_number == 1 and any(word in normalized for word in ("project", "drawing", "architect")):
            return "cover", 0.65
        return "other", 0.45
    score, classification = max(scored, key=lambda item: item[0])
    confidence = min(0.95, 0.55 + score * 0.06)
    return classification, confidence


pdf_asset_service = PdfAssetService()
