from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import Any, Iterable
from uuid import uuid4

import fitz
from fastapi import UploadFile

from app.core.config import settings
from app.core.errors import bad_request, service_unavailable
from app.core.security import safe_filename
from app.database.session import get_connection
from app.jobs.job_service import job_service
from app.pdf_upload.repo import pdf_upload_repository
from app.storage import storage_paths
from app.storage.storage_service import storage_service
from app.workflow.repo import workflow_repository

PDF_MIME_TYPES = {"application/pdf", "application/x-pdf", "application/octet-stream"}
INGESTION_TASKS: tuple[str, ...] = (
    "ingest.page_metadata",
    "render.page_thumbnails",
    "render.page_previews",
    "extract.vector_text",
    "ingest.page_classification",
    "extract.doors",
    "extract.windows",
    "extract.walls",
    "extract.floors",
)

FLOOR_SOURCE_INGESTION_TASKS: tuple[str, ...] = (
    "ingest.page_metadata",
    "render.page_thumbnails",
    "render.page_previews",
    "extract.vector_text",
    "ingest.page_classification",
)

FLOOR_PLAN_PAGE_TASKS: tuple[str, ...] = (
    "ingest.page_metadata",
    "render.page_thumbnails",
    "render.page_previews",
)

_PAGE_TASK_READY_FIELD = {
    "ingest.page_metadata": "metadata_ready",
    "render.page_thumbnails": "thumbnails_ready",
    "render.page_previews": "previews_ready",
    "extract.vector_text": "text_ready",
    "ingest.page_classification": "classifications_ready",
}


class PdfUploadService:
    async def upload_main_pdf(
        self,
        *,
        project_id: str,
        upload: UploadFile,
        created_by: str | None,
    ) -> dict:
        file_name = self._validate_request_file(upload)
        upload_id = uuid4().hex
        temporary_path = storage_paths.temporary_upload_path(project_id, upload_id)
        temporary_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            size_bytes, content_hash = await self._stream_upload(upload, temporary_path)
            validation = self._inspect_pdf(temporary_path)
        except Exception:
            # PyMuPDF can briefly retain the failed file handle on Windows.
            # Cleanup is best-effort; the original validation error must still
            # be returned to the caller.
            try:
                temporary_path.unlink(missing_ok=True)
            except PermissionError:
                pass
            raise
        finally:
            await upload.close()

        with get_connection() as connection:
            existing = pdf_upload_repository.find_document_by_hash(connection, project_id, content_hash)
            if existing:
                existing = pdf_upload_repository.make_primary(connection, project_id, existing["id"])
                temporary_path.unlink(missing_ok=True)
                jobs = self.ensure_ingestion_jobs(existing, created_by=created_by)
                return {
                    "document": self._decode(existing),
                    "reused": True,
                    "duplicate": True,
                    "jobs": jobs,
                    "next_step": "floor-plans",
                }

        document_id = str(uuid4())
        destination = storage_paths.document_original_path(project_id, document_id, content_hash)
        destination.parent.mkdir(parents=True, exist_ok=True)
        try:
            os.replace(temporary_path, destination)
            storage_service.upload_file(destination)
        except Exception as exc:
            temporary_path.unlink(missing_ok=True)
            storage_service.delete_file(destination)
            raise service_unavailable("The PDF could not be saved. Please try again.") from exc

        try:
            with get_connection() as connection:
                versions = workflow_repository.increment_project_version(connection, project_id, "document_version")
                document = pdf_upload_repository.create_document(
                    connection,
                    document_id=document_id,
                    project_id=project_id,
                    file_name=file_name,
                    mime_type="application/pdf",
                    storage_key=storage_service.path_to_key(destination),
                    content_hash=content_hash,
                    size_bytes=size_bytes,
                    page_count=validation["page_count"],
                    version=int(versions["document_version"]),
                    validation=validation,
                    created_by=created_by,
                )
                event = workflow_repository.create_outbox_event(
                    connection,
                    project_id=project_id,
                    floor_id=None,
                    event_type="document.uploaded",
                    entity_type="document",
                    entity_id=document_id,
                    dedupe_key=f"document.uploaded:{document_id}:{versions['document_version']}",
                    payload={
                        "content_hash": content_hash,
                        "document_version": int(versions["document_version"]),
                        "page_count": validation["page_count"],
                    },
                )
                self._increment_storage_usage(connection, project_id, size_bytes)
        except Exception:
            with get_connection() as connection:
                existing = pdf_upload_repository.find_document_by_hash(connection, project_id, content_hash)
                if existing:
                    existing = pdf_upload_repository.make_primary(connection, project_id, existing["id"])
            storage_service.delete_file(destination)
            if existing:
                jobs = self.ensure_ingestion_jobs(existing, created_by=created_by)
                return {
                    "document": self._decode(existing),
                    "reused": True,
                    "duplicate": True,
                    "jobs": jobs,
                    "next_step": "floor-plans",
                }
            raise

        jobs = self.ensure_ingestion_jobs(document, created_by=created_by)
        workflow_repository.mark_outbox_published(event["id"])
        return {
            "document": self._decode(document),
            "reused": False,
            "duplicate": False,
            "jobs": jobs,
            "next_step": "floor-plans",
        }

    def list_documents(self, project_id: str) -> list[dict]:
        return [self._decode(document) for document in pdf_upload_repository.list_documents(project_id)]

    def ensure_ingestion_jobs(
        self,
        document: dict,
        *,
        created_by: str | None,
        tasks: Iterable[str] | None = None,
        repair_missing_outputs: bool = False,
        retry_failed: bool = False,
    ) -> list[dict]:
        from app.workflow.jobs import register_foundation_job_specs

        register_foundation_job_specs()
        input_versions = {
            "document_version": int(document.get("version") or 1),
            "content_hash": document.get("content_hash") or "",
        }
        payload = {
            "document_id": document["id"],
            "storage_key": document["storage_key"],
            "page_count": int(document.get("page_count") or 0),
        }
        expected_pages = max(1, int(document.get("page_count") or 0))
        snapshot = pdf_upload_repository.get_manifest_snapshot(document["project_id"], document["id"])
        jobs: list[dict] = []
        repaired_any = False
        for task_type in tuple(tasks or INGESTION_TASKS):
            job, created = job_service.enqueue(
                task_type=task_type,
                project_id=document["project_id"],
                payload=payload,
                input_versions=input_versions,
                entity_id=document["id"],
                created_by=created_by,
            )
            requeued = False
            if repair_missing_outputs and not self._task_output_ready(task_type, snapshot, expected_pages):
                status = str(job.get("status") or "")
                can_requeue = status in {"completed", "cancelled"} or (retry_failed and status == "failed")
                if not created and can_requeue:
                    repaired = job_service.requeue_job(str(job["id"]))
                    if repaired:
                        job = repaired
                        requeued = True
                        repaired_any = True
            jobs.append({**job, "created": created, "requeued": requeued})

        if repaired_any:
            pdf_upload_repository.update_document(
                document["project_id"],
                document["id"],
                ingestion_status="processing",
                manifest_status="processing",
            )
        return jobs

    def ensure_floor_plan_assets(
        self,
        document: dict,
        *,
        created_by: str | None,
        retry_failed: bool = False,
    ) -> list[dict]:
        return self.ensure_ingestion_jobs(
            document,
            created_by=created_by,
            tasks=FLOOR_PLAN_PAGE_TASKS,
            repair_missing_outputs=True,
            retry_failed=retry_failed,
        )

    @staticmethod
    def _task_output_ready(task_type: str, snapshot: dict[str, int], expected_pages: int) -> bool:
        field = _PAGE_TASK_READY_FIELD.get(task_type)
        if not field:
            return False
        return int(snapshot.get("page_rows") or 0) >= expected_pages and int(snapshot.get(field) or 0) >= expected_pages

    def refresh_ingestion_status(self, project_id: str, document_id: str) -> dict | None:
        document = pdf_upload_repository.refresh_document_manifest_status(project_id, document_id)
        if not document:
            return None
        jobs = job_service.list_project_jobs(project_id=project_id, active_only=False, limit=200)
        document_jobs = [job for job in jobs if f":entity:{document_id}:" in str(job.get("job_key") or "")]
        if not document_jobs:
            ingestion_status = "not_ready"
        elif any(job["status"] == "failed" for job in document_jobs):
            ingestion_status = "failed"
        elif any(job["status"] in {"pending", "running"} for job in document_jobs):
            ingestion_status = "processing"
        else:
            ingestion_status = "ready"
        return pdf_upload_repository.update_document(
            project_id,
            document_id,
            ingestion_status=ingestion_status,
        )

    @staticmethod
    def _validate_request_file(upload: UploadFile) -> str:
        file_name = safe_filename(upload.filename or "")
        if not file_name.lower().endswith(".pdf"):
            raise bad_request("Select a PDF file.")
        mime_type = (upload.content_type or "application/octet-stream").lower().split(";", 1)[0].strip()
        if mime_type not in PDF_MIME_TYPES:
            raise bad_request("Select a valid PDF file.")
        return file_name[:180]

    @staticmethod
    async def _stream_upload(upload: UploadFile, destination: Path) -> tuple[int, str]:
        max_bytes = settings.max_upload_mb * 1024 * 1024
        size_bytes = 0
        signature_buffer = bytearray()
        hasher = hashlib.sha256()
        with destination.open("wb") as target:
            while True:
                chunk = await upload.read(1024 * 1024)
                if not chunk:
                    break
                size_bytes += len(chunk)
                if size_bytes > max_bytes:
                    raise bad_request(f"The PDF must be {settings.max_upload_mb} MB or smaller.")
                if len(signature_buffer) < 1024:
                    signature_buffer.extend(chunk[: 1024 - len(signature_buffer)])
                hasher.update(chunk)
                target.write(chunk)
        if size_bytes == 0:
            raise bad_request("The selected PDF is empty.")
        if b"%PDF-" not in bytes(signature_buffer):
            raise bad_request("Select a valid PDF file.")
        return size_bytes, hasher.hexdigest()

    @staticmethod
    def _inspect_pdf(path: Path) -> dict[str, Any]:
        try:
            with fitz.open(path) as document:
                if document.needs_pass:
                    raise bad_request("Password-protected PDFs are not supported.")
                if document.page_count < 1:
                    raise bad_request("The PDF does not contain any pages.")
                first_page = document.load_page(0)
                metadata = document.metadata or {}
                return {
                    "page_count": int(document.page_count),
                    "pdf_version": str(metadata.get("format") or "PDF"),
                    "title": str(metadata.get("title") or "")[:300] or None,
                    "first_page_width_points": float(first_page.rect.width),
                    "first_page_height_points": float(first_page.rect.height),
                    "encrypted": False,
                    "signature_valid": True,
                }
        except Exception as exc:
            if getattr(exc, "status_code", None):
                raise
            message = str(exc).lower()
            if "password" in message or "encrypted" in message:
                raise bad_request("Password-protected PDFs are not supported.") from exc
            raise bad_request("The PDF could not be opened.") from exc

    @staticmethod
    def _increment_storage_usage(connection: Any, project_id: str, size_bytes: int) -> None:
        project = connection.execute(
            "SELECT organization_id FROM projects WHERE id = ?",
            (project_id,),
        ).fetchone()
        if not project or not project["organization_id"]:
            return
        from datetime import datetime, timezone

        period_key = datetime.now(timezone.utc).strftime("%Y-%m")
        connection.execute(
            """
            UPDATE usage_counters
            SET storage_used_mb = storage_used_mb + ?, updated_at = ?
            WHERE organization_id = ? AND period_key = ?
            """,
            (
                size_bytes / 1024 / 1024,
                datetime.now(timezone.utc).isoformat(),
                project["organization_id"],
                period_key,
            ),
        )

    @staticmethod
    def _decode(document: dict) -> dict:
        from app.workflow.repo import loads

        result = dict(document)
        for key in list(result):
            if key.endswith("_json"):
                result[key[:-5]] = loads(result.pop(key))
        for key in ("is_primary",):
            if key in result:
                result[key] = bool(result[key])
        return result


pdf_upload_service = PdfUploadService()
