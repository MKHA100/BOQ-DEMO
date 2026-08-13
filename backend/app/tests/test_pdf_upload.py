from __future__ import annotations

import asyncio
import io
import json
from dataclasses import replace
from pathlib import Path

import fitz
import pytest
from fastapi import HTTPException
from starlette.datastructures import Headers, UploadFile


def _pdf_bytes(text: str = "DOOR SCHEDULE\nD1 900 x 2100 Timber door") -> bytes:
    document = fitz.open()
    page = document.new_page(width=595, height=842)
    page.insert_textbox(fitz.Rect(72, 72, 520, 760), text, fontsize=12)
    content = document.tobytes()
    document.close()
    return content


def _upload(content: bytes, name: str = "main-drawings.pdf", mime_type: str = "application/pdf") -> UploadFile:
    return UploadFile(
        io.BytesIO(content),
        filename=name,
        headers=Headers({"content-type": mime_type}),
    )


def _project(name: str = "Upload Test") -> dict:
    from app.projects.project_service import project_service

    return project_service.create_project(name)


def _run_upload(project_id: str, content: bytes, name: str = "main-drawings.pdf", mime_type: str = "application/pdf"):
    from app.pdf_upload.service import pdf_upload_service

    return asyncio.run(
        pdf_upload_service.upload_main_pdf(
            project_id=project_id,
            upload=_upload(content, name=name, mime_type=mime_type),
            created_by=None,
        )
    )


def test_successful_upload_returns_before_background_processing(foundation_db):
    from app.database.session import get_connection

    project = _project()
    result = _run_upload(project["id"], _pdf_bytes())

    assert result["reused"] is False
    assert result["next_step"] == "floor-plans"
    assert result["document"]["page_count"] == 1
    assert result["document"]["validation_status"] == "ready"
    assert result["document"]["ingestion_status"] == "processing"
    assert len(result["jobs"]) == 9
    assert all(job["status"] == "pending" for job in result["jobs"])

    with get_connection() as connection:
        assert connection.execute("SELECT COUNT(*) AS total FROM document_pages").fetchone()["total"] == 0
        assert connection.execute("SELECT COUNT(*) AS total FROM job_runs").fetchone()["total"] == 9


def test_duplicate_upload_reuses_document_and_jobs(foundation_db):
    from app.database.session import get_connection

    project = _project()
    content = _pdf_bytes()
    first = _run_upload(project["id"], content)
    second = _run_upload(project["id"], content, name="duplicate.pdf")

    assert second["reused"] is True
    assert second["duplicate"] is True
    assert second["document"]["id"] == first["document"]["id"]
    assert all(job["created"] is False for job in second["jobs"])
    with get_connection() as connection:
        assert connection.execute("SELECT COUNT(*) AS total FROM documents").fetchone()["total"] == 1
        assert connection.execute("SELECT COUNT(*) AS total FROM job_runs").fetchone()["total"] == 9


@pytest.mark.parametrize(
    ("content", "name", "mime_type", "message"),
    [
        (b"not a pdf", "drawing.txt", "text/plain", "Select a PDF file."),
        (b"not a pdf", "drawing.pdf", "application/pdf", "Select a valid PDF file."),
        (b"%PDF-1.7\ninvalid", "drawing.pdf", "application/pdf", "The PDF could not be opened."),
    ],
)
def test_invalid_files_are_rejected(foundation_db, content, name, mime_type, message):
    project = _project()
    with pytest.raises(HTTPException) as raised:
        _run_upload(project["id"], content, name=name, mime_type=mime_type)
    assert raised.value.status_code == 400
    assert raised.value.detail == message


def test_large_file_is_rejected_before_pdf_processing(foundation_db, monkeypatch):
    import app.pdf_upload.service as service_module

    project = _project()
    monkeypatch.setattr(service_module, "settings", replace(service_module.settings, max_upload_mb=1))
    content = b"%PDF-1.7\n" + (b"0" * (1024 * 1024 + 10))
    with pytest.raises(HTTPException) as raised:
        _run_upload(project["id"], content)
    assert raised.value.status_code == 400
    assert "1 MB or smaller" in raised.value.detail


def test_storage_failure_does_not_create_document(foundation_db, monkeypatch):
    import app.pdf_upload.service as service_module
    from app.database.session import get_connection

    project = _project()

    def fail_upload(_path: Path):
        raise RuntimeError("storage unavailable")

    monkeypatch.setattr(service_module.storage_service, "upload_file", fail_upload)
    with pytest.raises(HTTPException) as raised:
        _run_upload(project["id"], _pdf_bytes())
    assert raised.value.status_code == 503
    assert raised.value.detail == "The PDF could not be saved. Please try again."
    with get_connection() as connection:
        assert connection.execute("SELECT COUNT(*) AS total FROM documents").fetchone()["total"] == 0


def test_project_ownership_is_checked_before_upload(foundation_db):
    from app.auth.auth_service import auth_service
    from app.projects.project_service import project_service
    from app.workflow.routes import upload_document

    owner = auth_service.register("owner@example.com", "Password123!")["user"]
    other = auth_service.register("other@example.com", "Password123!")["user"]
    project = project_service.create_project("Owned", user_id=owner["id"])
    with pytest.raises(HTTPException) as raised:
        asyncio.run(
            upload_document(
                project_id=project["id"],
                file=_upload(_pdf_bytes()),
                document_type="source",
                current_user={"id": other["id"]},
            )
        )
    assert raised.value.status_code == 404


def test_worker_persists_manifest_assets_and_typed_extraction(foundation_db):
    from app.database.session import get_connection
    from app.jobs.worker import process_one

    project = _project()
    result = _run_upload(
        project["id"],
        _pdf_bytes("DOOR SCHEDULE\nD1 900 x 2100 Timber door fire rated\nROOM FINISH Office Carpet F1"),
    )

    for _ in range(9):
        assert process_one("pdf-upload-test") is not None

    with get_connection() as connection:
        page = connection.execute("SELECT * FROM document_pages WHERE document_id = ?", (result["document"]["id"],)).fetchone()
        document = connection.execute("SELECT * FROM documents WHERE id = ?", (result["document"]["id"],)).fetchone()
        door = connection.execute(
            "SELECT * FROM extraction_records WHERE document_id = ? AND extraction_type = 'door' LIMIT 1",
            (result["document"]["id"],),
        ).fetchone()

    assert page is not None
    assert page["metadata_status"] == "ready"
    assert page["thumbnail_status"] == "ready"
    assert page["preview_status"] == "ready"
    assert page["text_status"] == "ready"
    assert page["classification_status"] == "ready"
    assert page["thumbnail_key"]
    assert page["preview_key"]
    assert page["text_layer_key"]
    assert document["manifest_status"] == "ready"
    assert document["ingestion_status"] == "ready"
    assert door is not None
    assert json.loads(door["source_location_json"])["page_number"] == 1
    assert door["extraction_method"] == "vector_text_rules"
    assert door["review_state"] == "needs_review"


def test_worker_failure_retries_then_marks_document_failed(foundation_db, monkeypatch):
    from app.database.session import get_connection
    from app.jobs.worker import process_one
    from app.pdf_upload.pdf import pdf_asset_service

    project = _project()
    result = _run_upload(project["id"], _pdf_bytes())

    def fail_metadata(_job):
        raise RuntimeError("render engine unavailable")

    monkeypatch.setattr(pdf_asset_service, "ensure_metadata", fail_metadata)
    last = None
    for _ in range(3):
        last = process_one("failure-test", ["ingest.page_metadata"])
        with get_connection() as connection:
            connection.execute(
                "UPDATE job_runs SET retry_at = NULL WHERE task_type = 'ingest.page_metadata' AND status = 'pending'"
            )
    assert last is not None
    assert last["status"] == "failed"
    with get_connection() as connection:
        document = connection.execute("SELECT ingestion_status FROM documents WHERE id = ?", (result["document"]["id"],)).fetchone()
    assert document["ingestion_status"] == "failed"


def test_floor_plans_requeues_completed_manifest_job_when_output_is_missing(foundation_db):
    from app.database.session import get_connection
    from app.floor_plans.service import floor_plans_service
    from app.jobs.worker import process_one

    project = _project("Manifest recovery")
    uploaded = _run_upload(project["id"], _pdf_bytes())
    document_id = uploaded["document"]["id"]

    with get_connection() as connection:
        metadata_job = connection.execute(
            "SELECT id FROM job_runs WHERE project_id = ? AND task_type = 'ingest.page_metadata'",
            (project["id"],),
        ).fetchone()
        connection.execute(
            "UPDATE job_runs SET status = 'completed', progress = 100, message = 'Ready', finished_at = updated_at WHERE id = ?",
            (metadata_job["id"],),
        )
        assert connection.execute(
            "SELECT COUNT(*) AS total FROM document_pages WHERE document_id = ?",
            (document_id,),
        ).fetchone()["total"] == 0

    state = floor_plans_service.get_state(project)
    assert state["documents"][0]["status"] == "processing"

    with get_connection() as connection:
        repaired = connection.execute("SELECT * FROM job_runs WHERE id = ?", (metadata_job["id"],)).fetchone()
    assert repaired["status"] == "pending"
    assert repaired["attempts"] == 0

    assert process_one("manifest-recovery-test", ["ingest.page_metadata"]) is not None
    state = floor_plans_service.get_state(project)
    assert len(state["documents"][0]["pages"]) == 1


def test_prepare_document_retries_failed_page_job(foundation_db):
    from app.database.session import get_connection
    from app.floor_plans.service import floor_plans_service

    project = _project("Failed manifest retry")
    uploaded = _run_upload(project["id"], _pdf_bytes())
    document_id = uploaded["document"]["id"]

    with get_connection() as connection:
        preview_job = connection.execute(
            "SELECT id FROM job_runs WHERE project_id = ? AND task_type = 'render.page_previews'",
            (project["id"],),
        ).fetchone()
        connection.execute(
            """
            UPDATE job_runs
            SET status = 'failed', progress = 0, attempts = max_attempts,
                message = 'Failed', error_message = 'preview failed'
            WHERE id = ?
            """,
            (preview_job["id"],),
        )

    floor_plans_service.get_state(project)
    with get_connection() as connection:
        unchanged = connection.execute("SELECT * FROM job_runs WHERE id = ?", (preview_job["id"],)).fetchone()
    assert unchanged["status"] == "failed"

    jobs = floor_plans_service.prepare_document(
        project["id"],
        document_id,
        created_by=None,
        retry_failed=True,
    )
    retried = next(job for job in jobs if job["task_type"] == "render.page_previews")
    assert retried["status"] == "pending"
    assert retried["requeued"] is True
    assert retried["attempts"] == 0
