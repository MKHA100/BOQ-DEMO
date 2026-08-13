from __future__ import annotations

import asyncio
import io

import fitz
from starlette.datastructures import Headers, UploadFile


def pdf_bytes(text: str = "GROUND FLOOR\nD1 W1") -> bytes:
    document = fitz.open()
    page = document.new_page(width=600, height=800)
    page.insert_textbox(fitz.Rect(40, 40, 560, 760), text, fontsize=14)
    content = document.tobytes()
    document.close()
    return content


def upload(content: bytes, name: str = "plan.pdf") -> UploadFile:
    return UploadFile(io.BytesIO(content), filename=name, headers=Headers({"content-type": "application/pdf"}))


def project_with_crop(*, rect: dict | None = None):
    from app.floor_plans.service import floor_plans_service
    from app.pdf_upload.pdf import pdf_asset_service
    from app.pdf_upload.repo import pdf_upload_repository
    from app.pdf_upload.service import pdf_upload_service
    from app.projects.project_service import project_service

    project = project_service.create_project("Unified detection")
    document = asyncio.run(
        pdf_upload_service.upload_main_pdf(project_id=project["id"], upload=upload(pdf_bytes()), created_by=None)
    )["document"]
    pdf_asset_service.ensure_metadata(project_id=project["id"], document_id=document["id"])
    pdf_asset_service.ensure_thumbnails(project_id=project["id"], document_id=document["id"])
    pdf_asset_service.ensure_previews(project_id=project["id"], document_id=document["id"])
    page = pdf_upload_repository.list_pages(project["id"], document["id"])[0]
    floor = floor_plans_service.get_state(project)["floors"][0]
    selected = rect or {"x": 60, "y": 80, "width": 480, "height": 640}
    result = floor_plans_service.save_crop(
        project_id=project["id"],
        floor_id=floor["id"],
        payload={
            "document_id": document["id"],
            "document_page_id": page["id"],
            "source_page_number": 1,
            "original_page_width": 600,
            "original_page_height": 800,
            "rotation": 0,
            "render_dpi": 144,
            "original_rect": selected,
            "normalized_display_rect": {"x": 0.1, "y": 0.1, "width": 0.8, "height": 0.8},
        },
        created_by=None,
    )
    return project, floor, result


def render_crop():
    from app.jobs.worker import process_one

    result = process_one("unified-render", ["render.floor_crop"])
    assert result is not None
    return result


def prediction_payload():
    return {
        "predictions": [
            {"class": "door", "confidence": 0.91, "x": 100, "y": 100, "width": 30, "height": 50},
            {"class": "window", "confidence": 0.88, "x": 220, "y": 100, "width": 60, "height": 20},
            {"class": "wall", "confidence": 0.94, "x": 250, "y": 300, "width": 300, "height": 20},
        ]
    }
