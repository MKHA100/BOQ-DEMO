from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import Any
from uuid import uuid4

import fitz
from fastapi import UploadFile

from app.core.config import settings
from app.core.errors import bad_request, not_found, service_unavailable
from app.core.security import safe_filename
from app.database.session import get_connection
from app.floor_plans.repo import floor_plans_repository
from app.floor_plans.rendering import render_preview
from app.jobs.job_repository import job_repository
from app.jobs.job_service import job_service
from app.pdf_upload.repo import pdf_upload_repository
from app.pdf_upload.service import FLOOR_SOURCE_INGESTION_TASKS, pdf_upload_service
from app.storage import storage_paths
from app.storage.storage_service import storage_service
from app.workflow.repo import loads, workflow_repository

ALLOWED_SOURCE_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg"}
ALLOWED_SOURCE_MIME_TYPES = {
    "application/pdf",
    "application/x-pdf",
    "application/octet-stream",
    "image/png",
    "image/jpeg",
    "image/jpg",
}

FLOOR_NAMES = {
    0: "Ground Floor",
    1: "First Floor",
    2: "Second Floor",
    3: "Third Floor",
    4: "Fourth Floor",
    5: "Fifth Floor",
    6: "Sixth Floor",
    7: "Seventh Floor",
    8: "Eighth Floor",
    9: "Ninth Floor",
    10: "Tenth Floor",
}


class FloorPlansService:
    def get_state(self, project: dict, *, created_by: str | None = None) -> dict:
        project_id = project["id"]
        floor_plans_repository.ensure_ground_floor(project_id, created_by)
        settings_row = floor_plans_repository.get_project_settings(project_id)
        if not settings_row:
            raise not_found("Project not found.")

        floors = floor_plans_repository.list_floors_with_crops(project_id)
        documents, pages = floor_plans_repository.list_documents_with_pages(project_id)
        for document in documents:
            if document.get("document_type") not in {"source", "floor_source"}:
                continue
            pdf_upload_service.ensure_floor_plan_assets(document, created_by=created_by)
        documents, pages = floor_plans_repository.list_documents_with_pages(project_id)
        active_jobs = job_service.list_project_jobs(project_id=project_id, active_only=True, limit=500)
        recent_jobs = job_service.list_project_jobs(project_id=project_id, active_only=False, limit=500)
        jobs_by_floor: dict[str, list[dict]] = {}
        failed_crop_by_floor: dict[str, str] = {}
        for job in active_jobs:
            floor_id = job.get("floor_id")
            if floor_id:
                jobs_by_floor.setdefault(str(floor_id), []).append(job)
        for job in recent_jobs:
            floor_id = str(job.get("floor_id") or "")
            if (floor_id and floor_id not in failed_crop_by_floor
                and job.get("task_type") == "render.floor_crop"
                and job.get("status") == "failed"):
                failed_crop_by_floor[floor_id] = str(
                    job.get("error_message") or "The saved floor preview could not be prepared."
                )

        page_groups: dict[str, list[dict]] = {}
        for page in pages:
            page_groups.setdefault(page["document_id"], []).append(self._serialize_page(project_id, page))

        serialized_documents = [
            {
                "id": document["id"],
                "project_id": document["project_id"],
                "document_type": document["document_type"],
                "file_name": document.get("original_file_name") or document["file_name"],
                "mime_type": document["mime_type"],
                "page_count": document.get("page_count"),
                "status": self._document_display_status(document),
                "is_primary": bool(document.get("is_primary")),
                "pages": page_groups.get(document["id"], []),
            }
            for document in documents
        ]

        default_height = float(settings_row.get("default_wall_height_mm") or 2700)
        serialized_floors = [
            self._serialize_floor(
                project_id,
                floor,
                default_height=default_height,
                jobs=jobs_by_floor.get(floor["id"], []),
                last_error=failed_crop_by_floor.get(floor["id"]),
            )
            for floor in floors
        ]
        can_continue = bool(serialized_floors) and all(floor["crop"] is not None for floor in serialized_floors)
        return {
            "project_id": project_id,
            "project_name": project["name"],
            "default_wall_height_mm": default_height,
            "measurement_unit": settings_row.get("measurement_unit") or "mm",
            "floors": serialized_floors,
            "documents": serialized_documents,
            "can_continue": can_continue,
            "updated_at": settings_row.get("updated_at") or project.get("updated_at"),
        }

    def prepare_document(
        self,
        project_id: str,
        document_id: str,
        *,
        created_by: str | None,
        retry_failed: bool = True,
    ) -> list[dict]:
        document = pdf_upload_repository.get_document(project_id, document_id)
        if not document or document.get("document_type") not in {"source", "floor_source"}:
            raise not_found("Source document not found.")
        return pdf_upload_service.ensure_floor_plan_assets(
            document,
            created_by=created_by,
            retry_failed=retry_failed,
        )

    @staticmethod
    def _document_display_status(document: dict) -> str:
        ingestion = str(document.get("ingestion_status") or "")
        manifest = str(document.get("manifest_status") or "")
        if ingestion == "failed":
            return "failed"
        if manifest == "ready":
            return "ready"
        if ingestion == "processing" or manifest == "processing":
            return "processing"
        return str(document.get("status") or "not_ready")

    def update_project_settings(self, project_id: str, *, height_mm: float, unit: str) -> dict:
        return floor_plans_repository.update_project_settings(project_id, height_mm, unit)

    def add_floor(self, project_id: str, *, created_by: str | None) -> dict:
        level_index = floor_plans_repository.next_floor_index(project_id)
        return floor_plans_repository.create_floor(
            project_id,
            self.default_floor_name(level_index),
            level_index,
            created_by,
        )

    def update_floor(self, project_id: str, floor_id: str, payload: dict[str, Any]) -> dict:
        floor = floor_plans_repository.get_floor(project_id, floor_id)
        if not floor:
            raise not_found("Floor not found.")
        updates: dict[str, Any] = {}
        if payload.get("name") is not None:
            clean_name = str(payload["name"]).strip()
            if not clean_name:
                raise bad_request("Floor name is required.")
            updates["name"] = clean_name
            updates["is_custom_name"] = int(clean_name != self.default_floor_name(int(floor["level_index"])))
        if payload.get("uses_default_height") is not None:
            uses_default = bool(payload["uses_default_height"])
            updates["uses_default_height"] = int(uses_default)
            if uses_default:
                updates["wall_height_mm"] = None
            else:
                updates["wall_height_mm"] = float(payload["wall_height_mm"])
        elif payload.get("wall_height_mm") is not None:
            updates["uses_default_height"] = 0
            updates["wall_height_mm"] = float(payload["wall_height_mm"])
        updated = floor_plans_repository.update_floor(project_id, floor_id, updates)
        if not updated:
            raise not_found("Floor not found.")
        return updated

    def delete_floor(self, project_id: str, floor_id: str) -> None:
        if not floor_plans_repository.get_floor(project_id, floor_id):
            raise not_found("Floor not found.")
        if floor_plans_repository.floor_count(project_id) <= 1:
            raise bad_request("At least one floor is required.")
        floor_plans_repository.delete_floor(project_id, floor_id)

    async def upload_floor_source(
        self,
        *,
        project_id: str,
        floor_id: str,
        upload: UploadFile,
        created_by: str | None,
    ) -> dict:
        if not floor_plans_repository.get_floor(project_id, floor_id):
            raise not_found("Floor not found.")
        file_name, extension, mime_type = self._validate_source_request(upload)
        upload_id = uuid4().hex
        temporary_path = storage_paths.temporary_upload_path(project_id, upload_id)
        temporary_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            size_bytes, content_hash = await self._stream_source(upload, temporary_path, extension)
            validation = self._inspect_source(temporary_path, extension)
        except Exception:
            temporary_path.unlink(missing_ok=True)
            raise
        finally:
            await upload.close()

        with get_connection() as connection:
            existing = pdf_upload_repository.find_document_by_hash(connection, project_id, content_hash)
        if existing:
            temporary_path.unlink(missing_ok=True)
            floor_plans_repository.update_floor(
                project_id,
                floor_id,
                {
                    "source_document_id": existing["id"],
                    "source_page_number": 1,
                    "source_rotation": 0,
                    "status": "not_ready",
                },
            )
            jobs = pdf_upload_service.ensure_ingestion_jobs(
                existing,
                created_by=created_by,
                tasks=FLOOR_SOURCE_INGESTION_TASKS,
            )
            document = self._single_document_state(project_id, existing["id"])
            return {"document": document, "reused": True, "duplicate": True, "jobs": jobs}

        document_id = str(uuid4())
        destination = storage_paths.document_source_path(project_id, document_id, content_hash, extension)
        destination.parent.mkdir(parents=True, exist_ok=True)
        try:
            os.replace(temporary_path, destination)
            storage_service.upload_file(destination)
        except Exception as exc:
            temporary_path.unlink(missing_ok=True)
            storage_service.delete_file(destination)
            raise service_unavailable("The floor source could not be saved. Please try again.") from exc

        try:
            with get_connection() as connection:
                versions = workflow_repository.increment_project_version(connection, project_id, "document_version")
                document = pdf_upload_repository.create_document(
                    connection,
                    document_id=document_id,
                    project_id=project_id,
                    file_name=file_name,
                    mime_type=mime_type,
                    storage_key=storage_service.path_to_key(destination),
                    content_hash=content_hash,
                    size_bytes=size_bytes,
                    page_count=int(validation["page_count"]),
                    version=int(versions["document_version"]),
                    validation=validation,
                    created_by=created_by,
                    document_type="floor_source",
                    is_primary=False,
                )
                event = workflow_repository.create_outbox_event(
                    connection,
                    project_id=project_id,
                    floor_id=floor_id,
                    event_type="floor.source.uploaded",
                    entity_type="document",
                    entity_id=document_id,
                    dedupe_key=f"floor.source.uploaded:{floor_id}:{document_id}:{versions['document_version']}",
                    payload={"floor_id": floor_id, "document_version": int(versions["document_version"])},
                )
        except Exception:
            storage_service.delete_file(destination)
            raise

        floor_plans_repository.update_floor(
            project_id,
            floor_id,
            {
                "source_document_id": document_id,
                "source_page_number": 1,
                "source_rotation": 0,
                "status": "not_ready",
            },
        )
        jobs = pdf_upload_service.ensure_ingestion_jobs(
            document,
            created_by=created_by,
            tasks=FLOOR_SOURCE_INGESTION_TASKS,
        )
        workflow_repository.mark_outbox_published(event["id"])
        return {
            "document": self._single_document_state(project_id, document_id),
            "reused": False,
            "duplicate": False,
            "jobs": jobs,
        }

    def save_crop(
        self,
        *,
        project_id: str,
        floor_id: str,
        payload: dict[str, Any],
        created_by: str | None,
    ) -> dict:
        floor = floor_plans_repository.get_floor(project_id, floor_id)
        if not floor:
            raise not_found("Floor not found.")
        document = floor_plans_repository.get_document(project_id, payload["document_id"])
        if not document:
            raise not_found("Source document not found.")
        page = floor_plans_repository.get_document_page(
            project_id,
            payload["document_id"],
            payload["document_page_id"],
        )
        if not page or int(page["page_number"]) != int(payload["source_page_number"]):
            raise not_found("Source page not found.")

        previous = floor_plans_repository.current_crop(project_id, floor_id)
        previous_coordinates = floor_plans_repository.decode_crop(previous).get("coordinates", {}) if previous else {}
        previous_rect = (previous_coordinates.get("original_rect") or {}) if previous else {}
        requested_rect = payload.get("original_rect") or {}
        source_changed = bool(
            previous
            and (
                previous["document_id"] != payload["document_id"]
                or previous["document_page_id"] != payload["document_page_id"]
                or int(previous.get("rotation") or 0) != int(payload["rotation"])
                or any(abs(float(previous_rect.get(key) or 0) - float(requested_rect.get(key) or 0)) > 0.01
                       for key in ("x", "y", "width", "height"))
            )
        )
        coordinates = {
            "original_rect": payload["original_rect"],
            "normalized_display_rect": payload["normalized_display_rect"],
            "coordinate_space": "original_source",
        }
        unchanged = bool(
            previous
            and not source_changed
            and int(previous.get("render_dpi") or 144) == int(payload.get("render_dpi") or 144)
        )
        if unchanged:
            decoded = floor_plans_repository.decode_crop(previous)
            return {
                "crop": self._serialize_crop(project_id, decoded),
                "jobs": [],
                "source_changed": False,
                "unchanged": True,
                "preview_ready": bool(previous.get("preview_asset_key")),
                "preview_error": None,
            }
        crop = floor_plans_repository.save_crop(
            project_id=project_id,
            floor_id=floor_id,
            document_id=payload["document_id"],
            document_page_id=payload["document_page_id"],
            source_page_number=int(payload["source_page_number"]),
            original_page_width=float(payload["original_page_width"]),
            original_page_height=float(payload["original_page_height"]),
            rotation=int(payload["rotation"]),
            render_dpi=int(payload.get("render_dpi") or 144),
            coordinates=coordinates,
            created_by=created_by,
            source_changed=source_changed,
        )
        # Cancel pending work for the previous crop version before creating the
        # new high-priority render job. Running old jobs self-cancel by version.
        job_repository.cancel_pending_floor_pipeline(project_id, floor_id)

        preview_error: str | None = None
        try:
            preview_key, _, _ = render_preview(project_id, crop)
            crop = floor_plans_repository.mark_crop_preview_ready(crop["id"], preview_key) or crop
        except Exception as exc:
            # High-resolution rendering still retries in the worker. Returning the
            # save response is more useful than leaving the crop unsaved.
            preview_error = str(exc)

        input_versions = {"crop_version": int(crop["crop_version"])}
        job, created = job_service.enqueue(
            task_type="render.floor_crop",
            project_id=project_id,
            floor_id=floor_id,
            payload={
                "crop_id": crop["id"],
                "document_id": document["id"],
                "document_page_id": page["id"],
                "page_number": int(page["page_number"]),
            },
            input_versions=input_versions,
            entity_id=crop["id"],
            created_by=created_by,
        )
        return {
            "crop": self._serialize_crop(project_id, floor_plans_repository.decode_crop(crop)),
            "jobs": [{**job, "created": created}],
            "source_changed": source_changed,
            "preview_ready": bool(crop.get("preview_asset_key")),
            "preview_error": preview_error,
            "unchanged": False,
        }

    def asset_response(self, project_id: str, *, document_id: str, page_number: int, asset: str):
        page = pdf_upload_repository.get_page(project_id, document_id, page_number)
        if not page:
            raise not_found("Page asset not found.")
        key_column = "thumbnail_key" if asset == "thumbnail" else "preview_key"
        storage_key = page.get(key_column)
        if not storage_key:
            raise not_found("Page asset is not ready.")
        return storage_service.download_response(storage_service.key_to_path(storage_key), media_type="image/png")

    def crop_asset_response(self, project_id: str, floor_id: str, asset: str):
        crop = floor_plans_repository.current_crop(project_id, floor_id)
        if not crop:
            raise not_found("Floor crop not found.")
        key = crop.get("preview_asset_key" if asset == "preview" else "crop_asset_key")
        if not key and asset == "crop":
            key = crop.get("preview_asset_key")
        if not key:
            raise not_found("Floor crop preview is not ready.")
        return storage_service.download_response(storage_service.key_to_path(key), media_type="image/png")

    def _single_document_state(self, project_id: str, document_id: str) -> dict:
        documents, pages = floor_plans_repository.list_documents_with_pages(project_id)
        document = next((item for item in documents if item["id"] == document_id), None)
        if not document:
            raise not_found("Document not found.")
        document_pages = [self._serialize_page(project_id, page) for page in pages if page["document_id"] == document_id]
        return {
            "id": document["id"],
            "project_id": document["project_id"],
            "document_type": document["document_type"],
            "file_name": document.get("original_file_name") or document["file_name"],
            "mime_type": document["mime_type"],
            "page_count": document.get("page_count"),
            "status": document.get("manifest_status") or document.get("status") or "not_ready",
            "is_primary": bool(document.get("is_primary")),
            "pages": document_pages,
        }

    @staticmethod
    def default_floor_name(level_index: int) -> str:
        return FLOOR_NAMES.get(level_index, f"Level {level_index} Floor")

    @staticmethod
    def _serialize_page(project_id: str, page: dict) -> dict:
        page_number = int(page["page_number"])
        document_id = page["document_id"]
        base = f"/api/v1/projects/{project_id}/floor-plans/documents/{document_id}/pages/{page_number}"
        return {
            "id": page["id"],
            "document_id": document_id,
            "page_number": page_number,
            "page_label": page.get("page_label"),
            "width": page.get("width_points"),
            "height": page.get("height_points"),
            "rotation": int(page.get("rotation") or 0),
            "thumbnail_status": page.get("thumbnail_status") or "not_ready",
            "preview_status": page.get("preview_status") or "not_ready",
            "thumbnail_url": f"{base}/thumbnail" if page.get("thumbnail_key") else None,
            "preview_url": f"{base}/preview" if page.get("preview_key") else None,
        }

    def _serialize_floor(
        self, project_id: str, floor: dict, *, default_height: float,
        jobs: list[dict], last_error: str | None = None,
    ) -> dict:
        crop = None
        if floor.get("crop_id"):
            crop = self._serialize_crop(
                project_id,
                {
                    "id": floor["crop_id"],
                    "project_id": project_id,
                    "floor_id": floor["id"],
                    "document_id": floor["crop_document_id"],
                    "document_page_id": floor["crop_document_page_id"],
                    "source_page_number": floor.get("crop_source_page_number") or floor.get("source_page_number") or 1,
                    "original_page_width": floor.get("original_page_width") or 1,
                    "original_page_height": floor.get("original_page_height") or 1,
                    "rotation": floor.get("crop_rotation") or 0,
                    "render_dpi": floor.get("render_dpi") or 144,
                    "coordinates": loads(floor.get("coordinates_json") or "{}"),
                    "crop_version": int(floor.get("crop_version") or 0),
                    "status": floor.get("crop_status") or "not_ready",
                    "crop_asset_key": floor.get("crop_asset_key"),
                    "preview_asset_key": floor.get("preview_asset_key"),
                    "created_at": floor.get("crop_created_at") or floor["created_at"],
                    "updated_at": floor.get("crop_updated_at") or floor["updated_at"],
                },
            )
        uses_default = bool(floor.get("uses_default_height", 1))
        wall_height = floor.get("wall_height_mm")
        effective = default_height if uses_default or wall_height is None else float(wall_height)
        return {
            "id": floor["id"],
            "project_id": project_id,
            "name": floor["name"],
            "level_index": int(floor["level_index"]),
            "status": floor.get("status") or "not_ready",
            "uses_default_height": uses_default,
            "wall_height_mm": float(wall_height) if wall_height is not None else None,
            "effective_wall_height_mm": float(effective),
            "is_custom_name": bool(floor.get("is_custom_name")),
            "source_document_id": floor.get("source_document_id"),
            "source_page_number": floor.get("source_page_number"),
            "source_rotation": int(floor.get("source_rotation") or 0),
            "crop_version": int(floor.get("crop_version") or 0),
            "crop": crop,
            "last_error": last_error if (floor.get("status") == "failed" or (crop and crop.get("status") == "failed")) else None,
            "active_jobs": [
                {
                    "id": job["id"],
                    "floor_id": job.get("floor_id"),
                    "task_type": job["task_type"],
                    "status": job["status"],
                    "progress": int(job.get("progress") or 0),
                }
                for job in jobs
            ],
            "created_at": floor["created_at"],
            "updated_at": floor["updated_at"],
        }

    @staticmethod
    def _serialize_crop(project_id: str, crop: dict) -> dict:
        floor_id = crop["floor_id"]
        return {
            "id": crop["id"],
            "project_id": project_id,
            "floor_id": floor_id,
            "document_id": crop["document_id"],
            "document_page_id": crop["document_page_id"],
            "source_page_number": int(crop.get("source_page_number") or 1),
            "original_page_width": float(crop.get("original_page_width") or crop.get("source_width") or 1),
            "original_page_height": float(crop.get("original_page_height") or crop.get("source_height") or 1),
            "rotation": int(crop.get("rotation") or 0),
            "render_dpi": int(crop.get("render_dpi") or 144),
            "coordinates": crop.get("coordinates") or loads(crop.get("coordinates_json") or "{}"),
            "crop_version": int(crop.get("crop_version") or 0),
            "status": crop.get("status") or "not_ready",
            "crop_asset_url": f"/api/v1/projects/{project_id}/floor-plans/floors/{floor_id}/crop-asset" if crop.get("crop_asset_key") else None,
            "preview_asset_url": f"/api/v1/projects/{project_id}/floor-plans/floors/{floor_id}/preview-asset" if crop.get("preview_asset_key") else None,
            "created_at": crop["created_at"],
            "updated_at": crop["updated_at"],
        }

    @staticmethod
    def _validate_source_request(upload: UploadFile) -> tuple[str, str, str]:
        file_name = safe_filename(upload.filename or "")[:180]
        extension = Path(file_name).suffix.lower()
        if extension not in ALLOWED_SOURCE_EXTENSIONS:
            raise bad_request("Select a PDF, PNG or JPG file.")
        mime_type = (upload.content_type or "application/octet-stream").lower().split(";", 1)[0].strip()
        if mime_type not in ALLOWED_SOURCE_MIME_TYPES:
            raise bad_request("Select a valid PDF, PNG or JPG file.")
        resolved_mime = "application/pdf" if extension == ".pdf" else ("image/png" if extension == ".png" else "image/jpeg")
        return file_name, extension, resolved_mime

    @staticmethod
    async def _stream_source(upload: UploadFile, destination: Path, extension: str) -> tuple[int, str]:
        max_bytes = settings.max_upload_mb * 1024 * 1024
        size_bytes = 0
        signature = bytearray()
        hasher = hashlib.sha256()
        with destination.open("wb") as target:
            while True:
                chunk = await upload.read(1024 * 1024)
                if not chunk:
                    break
                size_bytes += len(chunk)
                if size_bytes > max_bytes:
                    raise bad_request(f"The file must be {settings.max_upload_mb} MB or smaller.")
                if len(signature) < 16:
                    signature.extend(chunk[: 16 - len(signature)])
                hasher.update(chunk)
                target.write(chunk)
        if size_bytes == 0:
            raise bad_request("The selected file is empty.")
        header = bytes(signature)
        if extension == ".pdf" and not header.startswith(b"%PDF-"):
            raise bad_request("Select a valid PDF file.")
        if extension == ".png" and not header.startswith(b"\x89PNG\r\n\x1a\n"):
            raise bad_request("Select a valid PNG file.")
        if extension in {".jpg", ".jpeg"} and not header.startswith(b"\xff\xd8\xff"):
            raise bad_request("Select a valid JPG file.")
        return size_bytes, hasher.hexdigest()

    @staticmethod
    def _inspect_source(path: Path, extension: str) -> dict[str, Any]:
        try:
            with fitz.open(path) as document:
                if getattr(document, "needs_pass", False):
                    raise bad_request("Password-protected PDFs are not supported.")
                if document.page_count < 1:
                    raise bad_request("The file does not contain a readable page.")
                first = document.load_page(0)
                return {
                    "page_count": int(document.page_count),
                    "source_format": "pdf" if extension == ".pdf" else "image",
                    "first_page_width": float(first.rect.width),
                    "first_page_height": float(first.rect.height),
                }
        except Exception as exc:
            if hasattr(exc, "status_code"):
                raise
            message = "The PDF could not be opened." if extension == ".pdf" else "The image could not be opened."
            raise bad_request(message) from exc


floor_plans_service = FloorPlansService()
