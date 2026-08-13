from __future__ import annotations

import hashlib
import json
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
from app.jobs.job_service import job_service
from app.pdf_upload.repo import pdf_upload_repository
from app.projects.project_service import project_service
from app.specifications.constants import CATEGORY_DEFINITIONS, CATEGORIES, EXTRACTION_SCHEMA_VERSION
from app.specifications.repo import specifications_repository
from app.storage import storage_paths
from app.storage.storage_service import storage_service
from app.workflow.repo import workflow_repository
from app.workflow.repo_base import now_iso

ALLOWED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg"}
ALLOWED_MIME_TYPES = {
    "application/pdf",
    "application/x-pdf",
    "application/octet-stream",
    "image/png",
    "image/jpeg",
    "image/jpg",
}
TASK_BY_CATEGORY = {
    "door_schedule": "extract.schedule.doors",
    "window_schedule": "extract.schedule.windows",
    "wall_schedule": "extract.schedule.walls",
    "floor_schedule": "extract.schedule.floors",
    "specification": "extract.schedule.specification",
    "other": "extract.schedule.other",
}


class SpecificationsService:
    def get_state(self, project: dict) -> dict:
        project_id = project["id"]
        floors = specifications_repository.list_floors(project_id)
        documents = specifications_repository.list_documents_with_pages(project_id)
        sources = specifications_repository.list_sources(project_id)
        category_states = specifications_repository.category_states(project_id)
        active_jobs = specifications_repository.active_jobs_by_source(project_id)
        for source in sources:
            job = active_jobs.get(source["id"])
            source["active_job"] = self._serialize_job(job) if job else None
            if job:
                source["display_status"] = "processing"
            else:
                source["display_status"] = self._display_status(source.get("extraction_status"), source.get("status"))
        categories = []
        for category in CATEGORIES:
            category_sources = [source for source in sources if source["category"] == category]
            status = self._category_status(category_states.get(category), category_sources)
            categories.append(
                {
                    "key": category,
                    "label": CATEGORY_DEFINITIONS[category]["label"],
                    "description": CATEGORY_DEFINITIONS[category]["description"],
                    "status": status,
                    "sources": [self._serialize_source(source, project_id) for source in category_sources],
                    "entry_count": sum(int(source.get("entry_count") or len(source.get("entries") or [])) for source in category_sources),
                }
            )
        return {
            "project_id": project_id,
            "project_name": project["name"],
            "categories": categories,
            "floors": floors,
            "documents": [self._serialize_document(document, project_id) for document in documents],
            "can_continue": True,
            "updated_at": max([project.get("updated_at") or now_iso()] + [source.get("updated_at") or "" for source in sources]),
        }

    async def upload_source(
        self,
        *,
        project_id: str,
        category: str,
        upload: UploadFile,
        scope_mode: str,
        floor_ids: list[str],
        created_by: str | None,
        replace_source_id: str | None = None,
    ) -> dict:
        self._validate_category(category)
        self._validate_scope(project_id, scope_mode, floor_ids)
        file_name, extension, mime_type = self._validate_upload(upload)
        temporary = storage_paths.temporary_upload_path(project_id, uuid4().hex)
        temporary.parent.mkdir(parents=True, exist_ok=True)
        try:
            size_bytes, content_hash = await self._stream_file(upload, temporary, extension)
            validation = self._inspect_file(temporary, extension)
        except Exception:
            temporary.unlink(missing_ok=True)
            raise
        finally:
            await upload.close()

        with get_connection() as connection:
            document = pdf_upload_repository.find_document_by_hash(connection, project_id, content_hash)
        if document:
            temporary.unlink(missing_ok=True)
        else:
            document_id = str(uuid4())
            destination = storage_paths.supporting_source_original_path(project_id, document_id, content_hash, extension)
            destination.parent.mkdir(parents=True, exist_ok=True)
            try:
                os.replace(temporary, destination)
                storage_service.upload_file(destination)
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
                        page_count=validation["page_count"],
                        version=int(versions["document_version"]),
                        validation=validation,
                        created_by=created_by,
                        document_type="supporting",
                        is_primary=False,
                    )
                    connection.execute(
                        "UPDATE documents SET manifest_status = 'ready', ingestion_status = 'ready' WHERE id = ?",
                        (document_id,),
                    )
            except Exception as exc:
                temporary.unlink(missing_ok=True)
                storage_service.delete_file(destination)
                raise service_unavailable("The file could not be saved. Please try again.") from exc

        source = self._create_source(
            project_id=project_id,
            category=category,
            document=document,
            source_type="file",
            page_number=None,
            crop=None,
            scope_mode=scope_mode,
            floor_ids=floor_ids,
            created_by=created_by,
            content_hash=content_hash,
            file_name=file_name,
            mime_type=mime_type,
            size_bytes=size_bytes,
        )
        if replace_source_id:
            previous = specifications_repository.get_source(project_id, replace_source_id)
            if previous:
                self.remove_source(project_id, replace_source_id)
        return source

    def create_crop_source(self, *, project_id: str, payload: dict, created_by: str | None) -> dict:
        category = str(payload["category"])
        self._validate_category(category)
        floor_ids = list(payload.get("floor_ids") or [])
        scope_mode = str(payload.get("scope_mode") or "all")
        self._validate_scope(project_id, scope_mode, floor_ids)
        document = pdf_upload_repository.get_document(project_id, payload["document_id"])
        page = pdf_upload_repository.get_page(project_id, payload["document_id"], int(payload["page_number"]))
        if not document or not page or str(page.get("id")) != str(payload["document_page_id"]):
            raise not_found("The selected PDF page is not available.")
        crop = {
            "page_number": int(payload["page_number"]),
            "page_id": payload["document_page_id"],
            "original_page_width": float(payload["original_page_width"]),
            "original_page_height": float(payload["original_page_height"]),
            "crop": payload["crop"],
        }
        hash_payload = json.dumps(
            {"document_hash": document.get("content_hash"), "page": payload["page_number"], "crop": payload["crop"]},
            sort_keys=True,
            separators=(",", ":"),
        )
        content_hash = hashlib.sha256(hash_payload.encode("utf-8")).hexdigest()
        return self._create_source(
            project_id=project_id,
            category=category,
            document=document,
            source_type="crop",
            page_number=int(payload["page_number"]),
            crop=crop,
            scope_mode=scope_mode,
            floor_ids=floor_ids,
            created_by=created_by,
            content_hash=content_hash,
            file_name=f"{document.get('file_name') or 'Project PDF'} · Page {payload['page_number']}",
            mime_type="application/pdf",
            size_bytes=0,
        )

    def update_scope(self, project_id: str, source_id: str, scope_mode: str, floor_ids: list[str]) -> dict:
        self._validate_scope(project_id, scope_mode, floor_ids)
        source = self._source(project_id, source_id)
        with get_connection() as connection:
            specifications_repository.update_scope(connection, source, scope_mode, floor_ids)
            self._increment_versions(connection, project_id, source["category"], floor_ids)
        return specifications_repository.get_source(project_id, source_id) or source

    def skip_category(self, project_id: str, category: str, skipped: bool) -> None:
        self._validate_category(category)
        with get_connection() as connection:
            specifications_repository.set_category_status(
                connection,
                project_id,
                category,
                "skipped" if skipped else "needs_review",
            )

    def remove_source(self, project_id: str, source_id: str) -> None:
        source = self._source(project_id, source_id)
        with get_connection() as connection:
            specifications_repository.deactivate_source(connection, source)
            self._increment_versions(connection, project_id, source["category"], source.get("floor_ids") or [])

    def source_asset_response(self, project_id: str, source_id: str):
        source = self._source(project_id, source_id)
        key = source.get("preview_asset_key") or source.get("asset_key")
        if not key:
            raise not_found("Preview is not ready.")
        return storage_service.download_response(storage_service.key_to_path(key), filename=source.get("file_name"))

    def _create_source(
        self,
        *,
        project_id: str,
        category: str,
        document: dict,
        source_type: str,
        page_number: int | None,
        crop: dict | None,
        scope_mode: str,
        floor_ids: list[str],
        created_by: str | None,
        content_hash: str,
        file_name: str,
        mime_type: str,
        size_bytes: int,
    ) -> dict:
        with get_connection() as connection:
            version = self._increment_versions(connection, project_id, category, floor_ids)
            source = specifications_repository.create_source(
                connection,
                project_id=project_id,
                category=category,
                document_id=document["id"],
                source_type=source_type,
                file_name=file_name,
                mime_type=mime_type,
                content_hash=content_hash,
                size_bytes=size_bytes,
                asset_key=document.get("storage_key"),
                page_number=page_number,
                crop=crop,
                scope_mode=scope_mode,
                floor_ids=floor_ids,
                version=version,
                schema_version=EXTRACTION_SCHEMA_VERSION,
                created_by=created_by,
            )
        job = self.enqueue_extraction(source, created_by=created_by)
        source["active_job"] = job
        source["display_status"] = "processing"
        return source

    def enqueue_extraction(self, source: dict, *, created_by: str | None) -> dict:
        task_type = TASK_BY_CATEGORY[source["category"]]
        job, created = job_service.enqueue(
            task_type=task_type,
            project_id=source["project_id"],
            payload={
                "source_id": source["id"],
                "category": source["category"],
                "floor_ids": source.get("floor_ids") or [],
            },
            input_versions={
                "extraction_version": int(source.get("schedule_version") or source.get("specification_version") or 1),
                "schema_version": int(source.get("extraction_schema_version") or EXTRACTION_SCHEMA_VERSION),
                "content_hash": source.get("content_hash") or "",
            },
            entity_id=source["id"],
            created_by=created_by,
        )
        return {**job, "created": created}

    def _increment_versions(self, connection: Any, project_id: str, category: str, floor_ids: list[str]) -> int:
        layer = "specification_version" if category in {"specification", "other"} else "schedule_version"
        project_versions = workflow_repository.increment_project_version(connection, project_id, layer)
        for floor_id in floor_ids:
            workflow_repository.increment_floor_version(connection, project_id, floor_id, "schedule_version")
        return int(project_versions[layer])

    def _validate_scope(self, project_id: str, scope_mode: str, floor_ids: list[str]) -> None:
        if scope_mode not in {"all", "selected"}:
            raise bad_request("Select a valid floor scope.")
        if scope_mode == "selected" and not floor_ids:
            raise bad_request("Select at least one floor.")
        if scope_mode == "all":
            return
        valid = {floor["id"] for floor in specifications_repository.list_floors(project_id)}
        if any(floor_id not in valid for floor_id in floor_ids):
            raise bad_request("One or more selected floors are not available.")

    @staticmethod
    def _validate_category(category: str) -> None:
        if category not in CATEGORY_DEFINITIONS:
            raise bad_request("Select a valid document category.")

    @staticmethod
    def _validate_upload(upload: UploadFile) -> tuple[str, str, str]:
        file_name = safe_filename(upload.filename or "")[:180]
        extension = Path(file_name).suffix.lower()
        if extension not in ALLOWED_EXTENSIONS:
            raise bad_request("Select a PDF, PNG or JPG file.")
        mime_type = (upload.content_type or "application/octet-stream").lower().split(";", 1)[0].strip()
        if mime_type not in ALLOWED_MIME_TYPES:
            raise bad_request("Select a valid PDF, PNG or JPG file.")
        normalized_mime = "image/jpeg" if extension in {".jpg", ".jpeg"} else "image/png" if extension == ".png" else "application/pdf"
        return file_name, extension, normalized_mime

    @staticmethod
    async def _stream_file(upload: UploadFile, destination: Path, extension: str) -> tuple[int, str]:
        max_bytes = settings.max_upload_mb * 1024 * 1024
        size = 0
        signature = bytearray()
        hasher = hashlib.sha256()
        with destination.open("wb") as target:
            while True:
                chunk = await upload.read(1024 * 1024)
                if not chunk:
                    break
                size += len(chunk)
                if size > max_bytes:
                    raise bad_request(f"The file must be {settings.max_upload_mb} MB or smaller.")
                if len(signature) < 16:
                    signature.extend(chunk[: 16 - len(signature)])
                hasher.update(chunk)
                target.write(chunk)
        if size == 0:
            raise bad_request("The selected file is empty.")
        raw = bytes(signature)
        if extension == ".pdf" and not raw.startswith(b"%PDF-"):
            raise bad_request("Select a valid PDF file.")
        if extension == ".png" and not raw.startswith(b"\x89PNG\r\n\x1a\n"):
            raise bad_request("Select a valid PNG file.")
        if extension in {".jpg", ".jpeg"} and not raw.startswith(b"\xff\xd8\xff"):
            raise bad_request("Select a valid JPG file.")
        return size, hasher.hexdigest()

    @staticmethod
    def _inspect_file(path: Path, extension: str) -> dict:
        try:
            with fitz.open(path) as document:
                if document.needs_pass:
                    raise bad_request("Password-protected PDFs are not supported.")
                if document.page_count < 1:
                    raise bad_request("The file does not contain a readable page.")
                return {"page_count": document.page_count, "format": extension.lstrip("."), "validated": True}
        except Exception as exc:
            if getattr(exc, "status_code", None):
                raise
            raise bad_request("The selected file could not be read.") from exc

    @staticmethod
    def _source(project_id: str, source_id: str) -> dict:
        source = specifications_repository.get_source(project_id, source_id)
        if not source:
            raise not_found("Supporting file not found.")
        return source

    @staticmethod
    def _display_status(extraction_status: str | None, status: str | None) -> str:
        value = extraction_status or status or "needs_review"
        if value in {"ready", "processing", "needs_review", "failed", "skipped"}:
            return value
        return "needs_review"

    @staticmethod
    def _category_status(saved: str | None, sources: list[dict]) -> str:
        if sources:
            statuses = [source.get("display_status") for source in sources]
            if "failed" in statuses:
                return "failed"
            if "processing" in statuses:
                return "processing"
            if "needs_review" in statuses:
                return "needs_review"
            return "ready"
        return saved if saved in {"ready", "processing", "needs_review", "failed", "skipped"} else "needs_review"

    def _serialize_source(self, source: dict, project_id: str) -> dict:
        return {
            "id": source["id"],
            "category": source["category"],
            "source_type": source["source_type"],
            "document_id": source["document_id"],
            "file_name": source.get("file_name"),
            "mime_type": source.get("mime_type"),
            "file_size": int(source.get("size_bytes") or 0),
            "page_number": source.get("source_page_number"),
            "crop": source.get("crop"),
            "scope_mode": source.get("scope_mode") or "all",
            "floor_ids": source.get("floor_ids") or [],
            "status": source.get("display_status") or "needs_review",
            "preview_url": f"/api/v1/projects/{project_id}/specifications/sources/{source['id']}/preview" if source.get("preview_asset_key") else None,
            "active_job": source.get("active_job"),
            "entry_count": int(source.get("entry_count") or len(source.get("entries") or [])),
            "entries": [
                {
                    "id": entry["id"],
                    "category": entry["category"],
                    "entity_key": entry["entity_key"],
                    "data": entry["data"],
                    "confidence": entry.get("confidence"),
                    "review_state": entry["review_state"],
                    "is_accepted": bool(entry.get("is_accepted")),
                }
                for entry in source.get("entries") or []
            ],
            "created_at": source["created_at"],
            "updated_at": source["updated_at"],
        }

    @staticmethod
    def _serialize_document(document: dict, project_id: str) -> dict:
        pages = []
        for page in document.get("pages") or []:
            pages.append(
                {
                    "id": page["id"],
                    "document_id": document["id"],
                    "page_number": int(page["page_number"]),
                    "page_label": page.get("page_label"),
                    "width": page.get("width_points"),
                    "height": page.get("height_points"),
                    "thumbnail_url": f"/api/v1/projects/{project_id}/floor-plans/documents/{document['id']}/pages/{page['page_number']}/thumbnail",
                    "preview_url": f"/api/v1/projects/{project_id}/floor-plans/documents/{document['id']}/pages/{page['page_number']}/preview",
                }
            )
        return {
            "id": document["id"],
            "file_name": document["file_name"],
            "page_count": document.get("page_count"),
            "is_primary": bool(document.get("is_primary")),
            "pages": pages,
        }

    @staticmethod
    def _serialize_job(job: dict | None) -> dict | None:
        if not job:
            return None
        return {
            "id": job["id"],
            "task_type": job["task_type"],
            "status": job["status"],
            "progress": int(job.get("progress") or 0),
        }


specifications_service = SpecificationsService()
