from __future__ import annotations

import asyncio
import io
import json

import fitz
from starlette.datastructures import Headers, UploadFile


def _tag_pdf() -> bytes:
    document = fitz.open()
    page = document.new_page(width=400, height=300)
    page.insert_text((88, 100), "D1", fontsize=14)
    page.insert_text((278, 105), "W2", fontsize=14)
    content = document.tobytes()
    document.close()
    return content



def _detail_pdf() -> bytes:
    document = fitz.open()
    page = document.new_page(width=1191, height=842)
    details = [
        ("D1", 167, 370, 1070, 54, 2590, 92, "Timber frame Timber Panel"),
        ("D2", 412, 370, 990, 93, 2130, 346, "Timber frame Timber Panel"),
        ("D3", 649, 370, 840, 93, 2130, 582, "Aluminium frame Aluminium Panel"),
        ("W1", 934, 370, 1830, 61, 2510, 820, "Timber frame Glass Panel"),
        ("W2", 212, 662, 1830, 422, 1750, 103, "Timber frame Glass Panel"),
        ("W3", 508, 662, 1220, 422, 1750, 428, "Timber frame Glass Panel"),
        ("F1", 762, 662, 910, 468, 910, 698, "Timber frame Glass Panel"),
        ("FG", 992, 662, 610, 468, 910, 941, "Timber frame Glass Panel"),
    ]
    for code, code_x, code_y, width, width_y, height, height_x, note in details:
        page.insert_text((code_x, code_y), code, fontsize=12)
        page.insert_text((code_x, width_y), str(width), fontsize=10)
        page.insert_text((height_x, (width_y + code_y) / 2), str(height), fontsize=10)
        page.insert_text((code_x, code_y - 80), note, fontsize=8)
    content = document.tobytes()
    document.close()
    return content

def _upload(content: bytes) -> UploadFile:
    return UploadFile(io.BytesIO(content), filename="tags.pdf", headers=Headers({"content-type": "application/pdf"}))


def _project_with_crop():
    from app.floor_plans.repo import floor_plans_repository
    from app.pdf_upload.pdf import pdf_asset_service
    from app.pdf_upload.service import pdf_upload_service
    from app.projects.project_service import project_service

    project = project_service.create_project("Tag matching")
    uploaded = asyncio.run(pdf_upload_service.upload_main_pdf(project_id=project["id"], upload=_upload(_tag_pdf()), created_by=None))
    document = uploaded["document"]
    pdf_asset_service.ensure_metadata(project_id=project["id"], document_id=document["id"])
    page = floor_plans_repository.list_documents_with_pages(project["id"])[1][0]
    floor = floor_plans_repository.ensure_ground_floor(project["id"], None)
    crop = floor_plans_repository.save_crop(
        project_id=project["id"], floor_id=floor["id"], document_id=document["id"], document_page_id=page["id"],
        source_page_number=1, original_page_width=400, original_page_height=300, rotation=0, render_dpi=144,
        coordinates={"original_rect": {"x": 0, "y": 0, "width": 400, "height": 300}}, created_by=None, source_changed=False,
    )
    return project, floor, crop


def test_vector_tags_match_only_elements_on_the_same_floor(foundation_db):
    from app.model_review.repo import model_review_repository
    from app.model_review.tag_service import model_review_tag_service

    project, floor, _crop = _project_with_crop()
    door = model_review_repository.create_element(
        project_id=project["id"], floor_id=floor["id"], element_type="door",
        geometry={"x": 68, "y": 70, "width": 50, "height": 55}, type_code=None,
        source="model", confidence=0.9, detection_version=1, is_manual=False, provider_name="test", created_by=None,
    )
    window = model_review_repository.create_element(
        project_id=project["id"], floor_id=floor["id"], element_type="window",
        geometry={"x": 255, "y": 75, "width": 60, "height": 55}, type_code=None,
        source="model", confidence=0.9, detection_version=1, is_manual=False, provider_name="test", created_by=None,
    )

    result = model_review_tag_service.read_tags(project_id=project["id"], floor_id=floor["id"])
    assert result["matched"] == 2
    saved_door = model_review_repository.get_element(project["id"], floor["id"], door["id"])
    saved_window = model_review_repository.get_element(project["id"], floor["id"], window["id"])
    assert saved_door["type_code"] == "D1"
    assert saved_window["type_code"] == "W2"
    assert saved_door["friendly_number"].startswith("DR-")
    assert saved_window["friendly_number"].startswith("WN-")


def test_confirmed_type_code_is_preserved_and_conflict_is_reviewed(foundation_db):
    from app.database.session import get_connection
    from app.model_review.repo import model_review_repository
    from app.model_review.tag_service import model_review_tag_service

    project, floor, _crop = _project_with_crop()
    door = model_review_repository.create_element(
        project_id=project["id"], floor_id=floor["id"], element_type="door",
        geometry={"x": 68, "y": 70, "width": 50, "height": 55}, type_code="D9",
        source="user_confirmed", confidence=1.0, detection_version=1, is_manual=True, provider_name="manual", created_by=None,
    )
    model_review_repository.update_element(
        project["id"], floor["id"], door["id"], {"status": "confirmed"}, element_version=2, user_confirmed=True,
    )

    result = model_review_tag_service.read_tags(project_id=project["id"], floor_id=floor["id"])
    assert result["conflicts"] == 1
    saved = model_review_repository.get_element(project["id"], floor["id"], door["id"])
    assert saved["type_code"] == "D9"
    assert saved["tag_text"] == "D1"
    with get_connection() as connection:
        issue = connection.execute(
            "SELECT * FROM review_issues WHERE project_id=? AND entity_id=? AND issue_type='conflicting_type_code'",
            (project["id"], door["id"]),
        ).fetchone()
    assert issue is not None
    assert json.loads(issue["suggestion_json"])["type_code"] == "D1"


def test_door_window_detail_layout_extracts_dimensions(foundation_db):
    from app.pdf_upload.extract import structured_extraction_service

    document = fitz.open(stream=_detail_pdf(), filetype="pdf")
    page = {"id": "page-1", "page_number": 1, "classification": "door_window_schedule"}
    doors = structured_extraction_service._parse_door_window_details(document, page, "door")
    windows = structured_extraction_service._parse_door_window_details(document, page, "window")
    document.close()

    door_map = {item["data"]["type_code"]: item["data"] for item in doors}
    window_map = {item["data"]["type_code"]: item["data"] for item in windows}
    assert door_map["D1"]["width_mm"] == 1070
    assert door_map["D3"]["height_mm"] == 2130
    assert door_map["D3"]["frame_material"] == "Aluminium"
    assert window_map["W1"]["width_mm"] == 1830
    assert window_map["W3"]["height_mm"] == 1750
    assert window_map["FG"]["width_mm"] == 610
