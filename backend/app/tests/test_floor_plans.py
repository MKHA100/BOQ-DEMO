from __future__ import annotations

import asyncio
import io
from pathlib import Path

import fitz
import pytest
from fastapi import HTTPException
from starlette.datastructures import Headers, UploadFile


def _pdf_bytes(text: str = "GROUND FLOOR PLAN\nOFFICE\nD1") -> bytes:
    document = fitz.open()
    page = document.new_page(width=600, height=800)
    page.insert_textbox(fitz.Rect(50, 50, 550, 750), text, fontsize=14)
    content = document.tobytes()
    document.close()
    return content


def _upload(content: bytes, name: str = "main.pdf", mime: str = "application/pdf") -> UploadFile:
    return UploadFile(io.BytesIO(content), filename=name, headers=Headers({"content-type": mime}))


def _project():
    from app.projects.project_service import project_service

    return project_service.create_project("Multi-floor Project")


def _main_document(project_id: str):
    from app.pdf_upload.service import pdf_upload_service

    return asyncio.run(
        pdf_upload_service.upload_main_pdf(
            project_id=project_id,
            upload=_upload(_pdf_bytes()),
            created_by=None,
        )
    )["document"]


def _prepare_page(project_id: str, document_id: str):
    from app.pdf_upload.pdf import pdf_asset_service
    from app.pdf_upload.repo import pdf_upload_repository

    pdf_asset_service.ensure_metadata(project_id=project_id, document_id=document_id)
    pdf_asset_service.ensure_thumbnails(project_id=project_id, document_id=document_id)
    pdf_asset_service.ensure_previews(project_id=project_id, document_id=document_id)
    return pdf_upload_repository.list_pages(project_id, document_id)[0]


def test_ground_floor_and_automatic_floor_labels(foundation_db):
    from app.floor_plans.service import floor_plans_service

    project = _project()
    state = floor_plans_service.get_state(project)
    assert [floor["name"] for floor in state["floors"]] == ["Ground Floor"]

    floor_plans_service.add_floor(project["id"], created_by=None)
    floor_plans_service.add_floor(project["id"], created_by=None)
    floor_plans_service.add_floor(project["id"], created_by=None)
    state = floor_plans_service.get_state(project)
    assert [floor["name"] for floor in state["floors"]] == [
        "Ground Floor",
        "First Floor",
        "Second Floor",
        "Third Floor",
    ]


def test_project_height_floor_override_and_custom_name(foundation_db):
    from app.floor_plans.service import floor_plans_service

    project = _project()
    state = floor_plans_service.get_state(project)
    ground = state["floors"][0]
    floor_plans_service.update_project_settings(project["id"], height_mm=3000, unit="mm")
    floor_plans_service.update_floor(
        project["id"],
        ground["id"],
        {"name": "Basement", "uses_default_height": False, "wall_height_mm": 2400},
    )
    state = floor_plans_service.get_state(project)
    assert state["default_wall_height_mm"] == 3000
    assert state["floors"][0]["name"] == "Basement"
    assert state["floors"][0]["is_custom_name"] is True
    assert state["floors"][0]["effective_wall_height_mm"] == 2400


def test_separate_floor_source_upload_is_scoped_and_deduplicated(foundation_db):
    from app.database.session import get_connection
    from app.floor_plans.service import floor_plans_service

    project = _project()
    state = floor_plans_service.get_state(project)
    ground = state["floors"][0]
    first = floor_plans_service.add_floor(project["id"], created_by=None)
    content = _pdf_bytes("FIRST FLOOR PLAN")

    result = asyncio.run(
        floor_plans_service.upload_floor_source(
            project_id=project["id"],
            floor_id=first["id"],
            upload=_upload(content, "first-floor.pdf"),
            created_by=None,
        )
    )
    duplicate = asyncio.run(
        floor_plans_service.upload_floor_source(
            project_id=project["id"],
            floor_id=first["id"],
            upload=_upload(content, "same-first-floor.pdf"),
            created_by=None,
        )
    )

    assert result["document"]["document_type"] == "floor_source"
    assert len(result["jobs"]) == 5
    assert duplicate["duplicate"] is True
    assert all(job["created"] is False for job in duplicate["jobs"])
    state = floor_plans_service.get_state(project)
    ground_state = next(item for item in state["floors"] if item["id"] == ground["id"])
    first_state = next(item for item in state["floors"] if item["id"] == first["id"])
    assert ground_state["source_document_id"] is None
    assert first_state["source_document_id"] == result["document"]["id"]
    with get_connection() as connection:
        assert connection.execute("SELECT COUNT(*) AS total FROM documents WHERE project_id = ?", (project["id"],)).fetchone()["total"] == 1


def test_crop_persists_original_coordinates_and_creates_floor_jobs(foundation_db):
    from app.database.session import get_connection
    from app.floor_plans.service import floor_plans_service

    project = _project()
    document = _main_document(project["id"])
    page = _prepare_page(project["id"], document["id"])
    floor = floor_plans_service.get_state(project)["floors"][0]
    payload = {
        "document_id": document["id"],
        "document_page_id": page["id"],
        "source_page_number": 1,
        "original_page_width": 600,
        "original_page_height": 800,
        "rotation": 0,
        "render_dpi": 144,
        "original_rect": {"x": 60, "y": 80, "width": 480, "height": 640},
        "normalized_display_rect": {"x": 0.1, "y": 0.1, "width": 0.8, "height": 0.8},
    }
    result = floor_plans_service.save_crop(
        project_id=project["id"],
        floor_id=floor["id"],
        payload=payload,
        created_by=None,
    )
    repeated = floor_plans_service.save_crop(
        project_id=project["id"],
        floor_id=floor["id"],
        payload=payload,
        created_by=None,
    )

    assert result["crop"]["coordinates"]["original_rect"] == payload["original_rect"]
    assert result["crop"]["crop_version"] == 1
    assert repeated["crop"]["crop_version"] == 1
    assert repeated["unchanged"] is True
    assert repeated["jobs"] == []
    assert {job["task_type"] for job in result["jobs"]} == {"render.floor_crop"}
    assert {job["floor_id"] for job in result["jobs"]} == {floor["id"]}
    with get_connection() as connection:
        current = connection.execute("SELECT * FROM floor_crops WHERE floor_id = ? AND is_current = 1", (floor["id"],)).fetchone()
        old = connection.execute("SELECT * FROM floor_crops WHERE floor_id = ? AND crop_version = 1", (floor["id"],)).fetchone()
    assert current["crop_version"] == 1
    assert old["is_current"] == 1


def test_floor_crop_worker_saves_preview_and_crop_text(foundation_db):
    from app.database.session import get_connection
    from app.floor_plans.service import floor_plans_service
    from app.jobs.worker import process_one

    project = _project()
    document = _main_document(project["id"])
    page = _prepare_page(project["id"], document["id"])
    floor = floor_plans_service.get_state(project)["floors"][0]
    floor_plans_service.save_crop(
        project_id=project["id"],
        floor_id=floor["id"],
        payload={
            "document_id": document["id"],
            "document_page_id": page["id"],
            "source_page_number": 1,
            "original_page_width": 600,
            "original_page_height": 800,
            "rotation": 90,
            "render_dpi": 144,
            "original_rect": {"x": 40, "y": 40, "width": 520, "height": 700},
            "normalized_display_rect": {"x": 0.05, "y": 0.07, "width": 0.88, "height": 0.86},
        },
        created_by=None,
    )
    assert process_one("floor-crop-test", ["render.floor_crop"]) is not None
    assert process_one("floor-crop-test", ["extract.floor_crop_text"]) is not None

    with get_connection() as connection:
        crop = connection.execute("SELECT * FROM floor_crops WHERE floor_id = ? AND is_current = 1", (floor["id"],)).fetchone()
        record = connection.execute(
            "SELECT * FROM extraction_records WHERE floor_id = ? AND extraction_type = 'floor_crop_note'",
            (floor["id"],),
        ).fetchone()
    assert crop["status"] == "ready"
    assert crop["crop_asset_key"]
    assert crop["preview_asset_key"]
    assert (foundation_db["storage_path"] / crop["crop_asset_key"]).exists()
    assert record is not None


def test_floor_deletion_requires_confirmation_target_and_preserves_other_floor(foundation_db):
    from app.floor_plans.service import floor_plans_service

    project = _project()
    state = floor_plans_service.get_state(project)
    ground = state["floors"][0]
    with pytest.raises(HTTPException) as raised:
        floor_plans_service.delete_floor(project["id"], ground["id"])
    assert raised.value.status_code == 400

    first = floor_plans_service.add_floor(project["id"], created_by=None)
    floor_plans_service.delete_floor(project["id"], first["id"])
    state = floor_plans_service.get_state(project)
    assert [item["id"] for item in state["floors"]] == [ground["id"]]


def test_png_floor_source_upload(foundation_db):
    from app.floor_plans.service import floor_plans_service

    project = _project()
    floor = floor_plans_service.get_state(project)["floors"][0]
    pixmap = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 40, 30), False)
    content = pixmap.tobytes("png")
    result = asyncio.run(
        floor_plans_service.upload_floor_source(
            project_id=project["id"],
            floor_id=floor["id"],
            upload=_upload(content, "ground-floor.png", "image/png"),
            created_by=None,
        )
    )
    assert result["document"]["mime_type"] == "image/png"
    assert result["document"]["page_count"] == 1
    assert len(result["jobs"]) == 5


def test_main_pdf_second_page_can_be_selected(foundation_db):
    from app.floor_plans.service import floor_plans_service
    from app.pdf_upload.pdf import pdf_asset_service
    from app.pdf_upload.service import pdf_upload_service
    from app.pdf_upload.repo import pdf_upload_repository

    project = _project()
    document = fitz.open()
    for text in ("COVER", "FIRST FLOOR PLAN"):
        page = document.new_page(width=700, height=500)
        page.insert_text((60, 80), text, fontsize=14)
    content = document.tobytes()
    document.close()
    uploaded = asyncio.run(
        pdf_upload_service.upload_main_pdf(
            project_id=project["id"],
            upload=_upload(content, "two-pages.pdf"),
            created_by=None,
        )
    )["document"]
    pdf_asset_service.ensure_metadata(project_id=project["id"], document_id=uploaded["id"])
    pages = pdf_upload_repository.list_pages(project["id"], uploaded["id"])
    floor = floor_plans_service.get_state(project)["floors"][0]
    result = floor_plans_service.save_crop(
        project_id=project["id"],
        floor_id=floor["id"],
        payload={
            "document_id": uploaded["id"],
            "document_page_id": pages[1]["id"],
            "source_page_number": 2,
            "original_page_width": 700,
            "original_page_height": 500,
            "rotation": 0,
            "render_dpi": 144,
            "original_rect": {"x": 35, "y": 25, "width": 630, "height": 450},
            "normalized_display_rect": {"x": 0.05, "y": 0.05, "width": 0.9, "height": 0.9},
        },
        created_by=None,
    )
    assert result["crop"]["source_page_number"] == 2
    state = floor_plans_service.get_state(project)
    assert state["floors"][0]["crop"]["document_page_id"] == pages[1]["id"]


def test_floor_plans_route_enforces_project_ownership(foundation_db):
    from app.auth.auth_service import auth_service
    from app.floor_plans.routes import get_floor_plans
    from app.projects.project_service import project_service

    owner = auth_service.register("floor-owner@example.com", "Password123!")["user"]
    other = auth_service.register("floor-other@example.com", "Password123!")["user"]
    project = project_service.create_project("Owned Floor Project", user_id=owner["id"])
    with pytest.raises(HTTPException) as raised:
        get_floor_plans(project["id"], current_user={"id": other["id"]})
    assert raised.value.status_code == 404
