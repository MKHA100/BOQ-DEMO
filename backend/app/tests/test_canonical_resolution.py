from __future__ import annotations


def _project_floor():
    from app.projects.project_service import project_service
    from app.workflow.service import workflow_service
    project = project_service.create_project("Canonical Resolution")
    floor = workflow_service.create_floor(project_id=project["id"], name=None, level_index=None, created_by=None)
    return project, floor


def test_schedule_values_auto_confirm_and_reach_review_boq(foundation_db):
    from app.database.session import get_connection
    from app.model_review.service import model_review_service
    from app.review.service import review_service
    from app.boq.service import boq_service
    from app.workflow.repo_base import dumps, now_iso

    project, floor = _project_floor()
    element = model_review_service.create(
        project_id=project["id"], floor_id=floor["id"],
        payload={"element_type": "door", "geometry": {"x": 0, "y": 0, "width": 20, "height": 4}, "type_code": "D2"},
        created_by=None,
    )["record"]
    now = now_iso()
    with get_connection() as connection:
        connection.execute(
            """
            INSERT INTO schedule_entries(id,project_id,source_id,source_kind,category,entity_key,data_json,
              source_location_json,extraction_method,confidence,review_state,is_accepted,source_priority,
              extraction_version,created_at,updated_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            ("d2-entry", project["id"], "d2-source", "schedule", "door", "D2",
             dumps({"type_code": "D2", "width_mm": 990, "height_mm": 2130, "material": "Timber"}),
             "{}", "test", 1.0, "ready", 1, 500, 1, now, now),
        )
    state = model_review_service.get_state(project, floor["id"])
    resolved = next(item for item in state["elements"] if item["id"] == element["id"])
    assert resolved["resolved_data"]["width_mm"] == 990
    assert resolved["resolved_data"]["height_mm"] == 2130
    assert resolved["status"] == "confirmed"

    review_service.refresh(project["id"])
    review = review_service.state(project)
    row = next(item for item in review["items"] if item["entity_id"] == element["id"])
    assert row["status"] == "confirmed"
    assert row["data"]["value_sources"]["width_mm"] == "schedule"

    boq = boq_service.refresh(project["id"])
    boq_row = next(item for item in boq["rows"] if element["id"] in item["source_ids"])
    assert boq_row["quantity"] == 1
    assert boq_row["status"] == "ready"


def test_boq_template_selection_is_persistent(foundation_db):
    from app.boq.repo import boq_repository
    from app.boq.service import boq_service

    project, _ = _project_floor()
    templates = boq_repository.ensure_templates(project["id"])
    selected = next(item for item in templates if item["name"] == "NRM2 Trade Format")
    result = boq_service.select_template(project["id"], selected["id"])
    state = boq_service.state(project)
    assert result["template"]["name"] == "NRM2 Trade Format"
    assert state["template"]["name"] == "NRM2 Trade Format"
    assert len(state["templates"]) >= 3
