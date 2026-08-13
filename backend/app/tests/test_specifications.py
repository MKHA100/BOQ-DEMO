from __future__ import annotations

import asyncio
import io
import json

import fitz
import pytest
from fastapi import HTTPException
from starlette.datastructures import Headers, UploadFile


def _pdf_bytes(lines: list[str]) -> bytes:
    document = fitz.open()
    page = document.new_page(width=700, height=900)
    page.insert_textbox(fitz.Rect(40, 40, 660, 860), "\n".join(lines), fontsize=12)
    content = document.tobytes()
    document.close()
    return content


def _upload(content: bytes, name: str = "schedule.pdf", mime: str = "application/pdf") -> UploadFile:
    return UploadFile(io.BytesIO(content), filename=name, headers=Headers({"content-type": mime}))


def _project():
    from app.projects.project_service import project_service

    return project_service.create_project("Schedule Project")


def _main_pdf(project_id: str):
    from app.pdf_upload.pdf import pdf_asset_service
    from app.pdf_upload.repo import pdf_upload_repository
    from app.pdf_upload.service import pdf_upload_service

    document = asyncio.run(
        pdf_upload_service.upload_main_pdf(
            project_id=project_id,
            upload=_upload(_pdf_bytes(["DOOR SCHEDULE", "D1 900 x 2100 timber Qty 2"]), "main.pdf"),
            created_by=None,
        )
    )["document"]
    pdf_asset_service.ensure_metadata(project_id=project_id, document_id=document["id"])
    pdf_asset_service.ensure_thumbnails(project_id=project_id, document_id=document["id"])
    pdf_asset_service.ensure_previews(project_id=project_id, document_id=document["id"])
    return document, pdf_upload_repository.list_pages(project_id, document["id"])[0]


def _add_floor(project_id: str):
    from app.floor_plans.service import floor_plans_service

    floor_plans_service.get_state({"id": project_id, "name": "Schedule Project", "updated_at": ""})
    return floor_plans_service.add_floor(project_id, created_by=None)


def test_each_category_creates_only_its_own_job_and_multiple_files(foundation_db):
    from app.specifications.service import specifications_service

    project = _project()
    first = asyncio.run(
        specifications_service.upload_source(
            project_id=project["id"],
            category="door_schedule",
            upload=_upload(_pdf_bytes(["D1 900 x 2100 timber Qty 2"]), "doors-a.pdf"),
            scope_mode="all",
            floor_ids=[],
            created_by=None,
        )
    )
    second = asyncio.run(
        specifications_service.upload_source(
            project_id=project["id"],
            category="door_schedule",
            upload=_upload(_pdf_bytes(["D2 1000 x 2100 steel Qty 1"]), "doors-b.pdf"),
            scope_mode="all",
            floor_ids=[],
            created_by=None,
        )
    )
    assert first["id"] != second["id"]
    assert first["active_job"]["task_type"] == "extract.schedule.doors"
    assert second["active_job"]["task_type"] == "extract.schedule.doors"
    state = specifications_service.get_state(project)
    category = next(item for item in state["categories"] if item["key"] == "door_schedule")
    assert len(category["sources"]) == 2


def test_crop_input_skip_and_selected_floor_scope(foundation_db):
    from app.specifications.service import specifications_service

    project = _project()
    first_floor = _add_floor(project["id"])
    document, page = _main_pdf(project["id"])
    source = specifications_service.create_crop_source(
        project_id=project["id"],
        payload={
            "category": "door_schedule",
            "document_id": document["id"],
            "document_page_id": page["id"],
            "page_number": 1,
            "original_page_width": 700,
            "original_page_height": 900,
            "crop": {"x": 20, "y": 20, "width": 650, "height": 850},
            "scope_mode": "selected",
            "floor_ids": [first_floor["id"]],
        },
        created_by=None,
    )
    assert source["source_type"] == "crop"
    assert source["floor_ids"] == [first_floor["id"]]
    specifications_service.skip_category(project["id"], "other", True)
    state = specifications_service.get_state(project)
    other = next(item for item in state["categories"] if item["key"] == "other")
    assert other["status"] == "skipped"


def test_worker_extracts_typed_rows_and_uses_cache(foundation_db):
    from app.jobs.worker import process_one
    from app.specifications.service import specifications_service

    project = _project()
    source = asyncio.run(
        specifications_service.upload_source(
            project_id=project["id"],
            category="window_schedule",
            upload=_upload(_pdf_bytes(["W1 1200 x 1500 aluminium frame clear glass Qty 3"]), "windows.pdf"),
            scope_mode="all",
            floor_ids=[],
            created_by=None,
        )
    )
    completed = process_one("spec-test", ["extract.schedule.windows"])
    assert completed and completed["status"] == "completed"
    saved = specifications_service.get_state(project)
    category = next(item for item in saved["categories"] if item["key"] == "window_schedule")
    assert category["status"] == "ready"
    entry = category["sources"][0]["entries"][0]
    assert entry["data"]["type_code"] == "W1"
    assert entry["data"]["width_mm"] == 1200
    assert entry["data"]["quantity"] == 3
    assert source["id"] == category["sources"][0]["id"]


def test_conflicts_create_review_issue_and_keep_accepted_value(foundation_db):
    from app.database.session import get_connection
    from app.jobs.worker import process_one
    from app.specifications.service import specifications_service

    project = _project()
    for name, text in (("doors-1.pdf", "D1 900 x 2100 timber Qty 1"), ("doors-2.pdf", "D1 1000 x 2100 steel Qty 1")):
        asyncio.run(
            specifications_service.upload_source(
                project_id=project["id"],
                category="door_schedule",
                upload=_upload(_pdf_bytes([text]), name),
                scope_mode="all",
                floor_ids=[],
                created_by=None,
            )
        )
        process_one("conflict-test", ["extract.schedule.doors"])
    with get_connection() as connection:
        accepted = connection.execute(
            "SELECT data_json FROM schedule_entries WHERE project_id = ? AND entity_key = 'D1' AND is_accepted = 1",
            (project["id"],),
        ).fetchone()
        issue = connection.execute(
            "SELECT * FROM review_issues WHERE project_id = ? AND issue_type = 'source_conflict'",
            (project["id"],),
        ).fetchone()
    assert json.loads(accepted["data_json"])["width_mm"] == 900
    assert issue is not None


def test_confirmed_element_value_is_not_overwritten(foundation_db):
    from app.database.session import get_connection
    from app.jobs.worker import process_one
    from app.specifications.service import specifications_service
    from app.workflow.repo_base import now_iso
    from uuid import uuid4

    project = _project()
    from app.floor_plans.service import floor_plans_service
    floor = floor_plans_service.get_state(project)["floors"][0]
    with get_connection() as connection:
        now = now_iso()
        element_id = str(uuid4())
        connection.execute(
            """INSERT INTO elements(id, project_id, floor_id, element_type, type_code, geometry_json, source, status,
               excluded, user_confirmed, measurement_status, element_version, source_versions_json, created_at, updated_at)
               VALUES (?, ?, ?, 'door', 'D1', '{}', 'user', 'confirmed', 0, 1, 'not_ready', 1, '{}', ?, ?)""",
            (element_id, project["id"], floor["id"], now, now),
        )
        connection.execute(
            """INSERT INTO element_properties(id, project_id, floor_id, element_id, property_name, value_json,
               source, source_priority, is_confirmed, element_version, created_at, updated_at)
               VALUES (?, ?, ?, ?, 'width_mm', '850', 'user', 600, 1, 1, ?, ?)""",
            (str(uuid4()), project["id"], floor["id"], element_id, now, now),
        )
    asyncio.run(
        specifications_service.upload_source(
            project_id=project["id"],
            category="door_schedule",
            upload=_upload(_pdf_bytes(["D1 1000 x 2100 steel Qty 1"]), "confirmed-conflict.pdf"),
            scope_mode="all",
            floor_ids=[],
            created_by=None,
        )
    )
    process_one("confirmed-test", ["extract.schedule.doors"])
    with get_connection() as connection:
        prop = connection.execute("SELECT value_json, is_confirmed FROM element_properties WHERE element_id = ?", (element_id,)).fetchone()
    assert json.loads(prop["value_json"]) == 850
    assert prop["is_confirmed"] == 1


def test_remove_replace_and_saved_state(foundation_db):
    from app.specifications.service import specifications_service

    project = _project()
    first = asyncio.run(
        specifications_service.upload_source(
            project_id=project["id"], category="specification",
            upload=_upload(_pdf_bytes(["Walls: painted plaster finish"]), "spec-a.pdf"),
            scope_mode="all", floor_ids=[], created_by=None,
        )
    )
    replacement = asyncio.run(
        specifications_service.upload_source(
            project_id=project["id"], category="specification",
            upload=_upload(_pdf_bytes(["Floors: ceramic tile finish"]), "spec-b.pdf"),
            scope_mode="all", floor_ids=[], created_by=None, replace_source_id=first["id"],
        )
    )
    state = specifications_service.get_state(project)
    category = next(item for item in state["categories"] if item["key"] == "specification")
    assert [item["id"] for item in category["sources"]] == [replacement["id"]]
    specifications_service.remove_source(project["id"], replacement["id"])
    refreshed = specifications_service.get_state(project)
    category = next(item for item in refreshed["categories"] if item["key"] == "specification")
    assert category["sources"] == []


def test_project_ownership_on_route(foundation_db):
    from app.auth.auth_service import auth_service
    from app.projects.project_service import project_service
    from app.specifications.routes import get_specifications

    owner = auth_service.register("spec-owner@example.com", "Password123!")["user"]
    other = auth_service.register("spec-other@example.com", "Password123!")["user"]
    project = project_service.create_project("Owned Schedules", user_id=owner["id"])
    with pytest.raises(HTTPException) as raised:
        get_specifications(project["id"], current_user={"id": other["id"]})
    assert raised.value.status_code == 404

@pytest.mark.parametrize(
    ("category", "task_type"),
    [
        ("door_schedule", "extract.schedule.doors"),
        ("window_schedule", "extract.schedule.windows"),
        ("wall_schedule", "extract.schedule.walls"),
        ("floor_schedule", "extract.schedule.floors"),
        ("specification", "extract.schedule.specification"),
        ("other", "extract.schedule.other"),
    ],
)
def test_category_specific_job_types(foundation_db, category, task_type):
    from app.specifications.service import specifications_service

    project = _project()
    source = asyncio.run(
        specifications_service.upload_source(
            project_id=project["id"],
            category=category,
            upload=_upload(_pdf_bytes(["General supporting information"]), f"{category}.pdf"),
            scope_mode="all",
            floor_ids=[],
            created_by=None,
        )
    )
    assert source["active_job"]["task_type"] == task_type


def test_worker_failure_marks_only_affected_source_failed(foundation_db, monkeypatch):
    from app.jobs.worker import process_one
    from app.specifications.extract import schedule_extraction_service
    from app.specifications.service import specifications_service

    project = _project()
    source = asyncio.run(
        specifications_service.upload_source(
            project_id=project["id"],
            category="wall_schedule",
            upload=_upload(_pdf_bytes(["WALL TYPE W1 200 mm blockwork"]), "walls.pdf"),
            scope_mode="all",
            floor_ids=[],
            created_by=None,
        )
    )
    monkeypatch.setattr(schedule_extraction_service, "extract", lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("processor unavailable")))
    failed = process_one("failure-test", ["extract.schedule.walls"])
    assert failed and failed["status"] == "pending"  # retry remains isolated to this source
    state = specifications_service.get_state(project)
    wall = next(item for item in state["categories"] if item["key"] == "wall_schedule")
    assert wall["sources"][0]["id"] == source["id"]
    assert wall["sources"][0]["status"] == "processing"  # active retry keeps the user-facing state non-blocking
    other = next(item for item in state["categories"] if item["key"] == "door_schedule")
    assert other["status"] == "needs_review"


def test_structured_provider_rows_are_validated_and_saved(foundation_db, monkeypatch):
    from app.database.session import get_connection
    from app.jobs.worker import process_one
    from app.specifications.openai_provider import openai_schedule_extraction_provider
    from app.specifications.service import specifications_service

    project = _project()
    source = asyncio.run(
        specifications_service.upload_source(
            project_id=project["id"],
            category="door_schedule",
            upload=_upload(_pdf_bytes(["Door schedule scan"]), "provider-doors.pdf"),
            scope_mode="all",
            floor_ids=[],
            created_by=None,
        )
    )
    monkeypatch.setattr(
        openai_schedule_extraction_provider,
        "extract",
        lambda category, pages: [
            {
                "type_code": "D7",
                "width_mm": 950,
                "height_mm": 2100,
                "material": "Timber",
                "frame_material": "Steel",
                "finish": "Painted",
                "fire_rating": "60 min",
                "quantity": 4,
                "source_page": 1,
                "source_text": "D7 950 x 2100 timber door, steel frame, FD60, Qty 4",
                "confidence": 0.96,
            }
        ],
    )
    completed = process_one("provider-test", ["extract.schedule.doors"])
    assert completed and completed["status"] == "completed"
    with get_connection() as connection:
        row = connection.execute(
            "SELECT data_json, extraction_method, confidence FROM schedule_entries WHERE source_id = ?",
            (source["id"],),
        ).fetchone()
    assert json.loads(row["data_json"])["type_code"] == "D7"
    assert row["extraction_method"] == "openai_structured"
    assert row["confidence"] == pytest.approx(0.96)


def test_identical_source_reuses_schema_version_cache(foundation_db):
    from app.database.session import get_connection
    from app.jobs.worker import process_one
    from app.specifications.service import specifications_service

    project = _project()
    content = _pdf_bytes(["F1 ceramic tile 600 x 600 screed skirting"])
    first = asyncio.run(
        specifications_service.upload_source(
            project_id=project["id"], category="floor_schedule",
            upload=_upload(content, "floor-a.pdf"), scope_mode="all", floor_ids=[], created_by=None,
        )
    )
    second = asyncio.run(
        specifications_service.upload_source(
            project_id=project["id"], category="floor_schedule",
            upload=_upload(content, "floor-b.pdf"), scope_mode="all", floor_ids=[], created_by=None,
        )
    )
    process_one("cache-test-a", ["extract.schedule.floors"])
    process_one("cache-test-b", ["extract.schedule.floors"])
    with get_connection() as connection:
        first_method = connection.execute(
            "SELECT extraction_method FROM schedule_entries WHERE source_id = ? LIMIT 1", (first["id"],)
        ).fetchone()
        second_method = connection.execute(
            "SELECT extraction_method FROM schedule_entries WHERE source_id = ? LIMIT 1", (second["id"],)
        ).fetchone()
    assert first_method["extraction_method"] == "structured_text"
    assert second_method["extraction_method"] == "cached_structured"


def test_openai_schema_is_strict_and_nullable(foundation_db):
    from app.specifications.openai_provider import openai_schedule_extraction_provider
    from app.specifications.schemas import extraction_model

    schema = openai_schedule_extraction_provider._strict_schema(
        extraction_model("door_schedule").model_json_schema()
    )
    assert schema["additionalProperties"] is False
    assert "rows" in schema["required"]
    door_definition = schema["$defs"]["DoorScheduleRow"]
    assert door_definition["additionalProperties"] is False
    assert set(door_definition["required"]) == set(door_definition["properties"])
