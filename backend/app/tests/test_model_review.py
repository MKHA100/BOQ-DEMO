from __future__ import annotations


def _project_floors():
    from app.projects.project_service import project_service
    from app.workflow.service import workflow_service
    project=project_service.create_project("Review Tower")
    floors=[workflow_service.create_floor(project_id=project["id"],name=None,level_index=None,created_by=None) for _ in range(2)]
    return project,floors


def test_manual_elements_are_floor_isolated(foundation_db):
    from app.model_review.service import model_review_service
    project,floors=_project_floors()
    created=model_review_service.create(project_id=project["id"],floor_id=floors[0]["id"],payload={"element_type":"door","geometry":{"x":10,"y":10,"width":20,"height":30,"rotation":0},"type_code":"D1"},created_by=None)
    first=model_review_service.get_state(project,floors[0]["id"])
    second=model_review_service.get_state(project,floors[1]["id"])
    assert created["record"]["floor_id"]==floors[0]["id"]
    assert len(first["elements"])==1
    assert second["elements"]==[]


def test_geometry_edit_is_targeted_and_does_not_start_detection(foundation_db):
    from app.model_review.service import model_review_service
    from app.database.session import get_connection
    project,floors=_project_floors()
    element=model_review_service.create(project_id=project["id"],floor_id=floors[0]["id"],payload={"element_type":"window","geometry":{"x":1,"y":2,"width":10,"height":12,"rotation":0}},created_by=None)["record"]
    result=model_review_service.update(project_id=project["id"],floor_id=floors[0]["id"],element_id=element["id"],payload={"geometry":{"x":3,"y":4,"width":11,"height":13,"rotation":0}},created_by=None)
    assert result["record"]["geometry"]["x"]==3
    assert {job["task_type"] for job in result["jobs"]}=={"walls.recalculate_deduction","review.refresh","boq.refresh"}
    with get_connection() as connection:
        total=connection.execute("SELECT COUNT(*) AS total FROM job_runs WHERE project_id=? AND task_type LIKE 'vision.%'",(project["id"],)).fetchone()["total"]
    assert total==0


def test_confirmed_property_protected_from_schedule(foundation_db):
    from app.model_review.service import model_review_service
    from app.workflow.service import workflow_service
    project,floors=_project_floors()
    element=model_review_service.create(project_id=project["id"],floor_id=floors[0]["id"],payload={"element_type":"door","geometry":{"x":1,"y":2,"width":10,"height":12,"rotation":0}},created_by=None)["record"]
    model_review_service.update_property(project_id=project["id"],floor_id=floors[0]["id"],element_id=element["id"],property_name="width_mm",value=900,unit="mm",confirm=True,created_by=None)
    result=workflow_service.update_element_property(project_id=project["id"],element_id=element["id"],property_name="width_mm",value=850,unit="mm",source="schedule",confirm=False,created_by=None)
    assert result["protected"] is True
    assert result["record"]["value"]==900


def test_item_numbers_are_project_wide_and_stable_across_floors(foundation_db):
    from app.model_review.service import model_review_service

    project, floors = _project_floors()
    first = model_review_service.create(
        project_id=project["id"],
        floor_id=floors[0]["id"],
        payload={"element_type": "door", "geometry": {"x": 1, "y": 1, "width": 4, "height": 8, "rotation": 0}},
        created_by=None,
    )["record"]
    second = model_review_service.create(
        project_id=project["id"],
        floor_id=floors[1]["id"],
        payload={"element_type": "window", "geometry": {"x": 2, "y": 2, "width": 5, "height": 6, "rotation": 0}},
        created_by=None,
    )["record"]

    assert first["item_number"] == 1
    assert first["display_number"] == "Item 001"
    assert second["item_number"] == 2
    assert second["display_number"] == "Item 002"

    reloaded = model_review_service.get_state(project, floors[0]["id"])["elements"][0]
    assert reloaded["item_number"] == first["item_number"]
    assert reloaded["display_number"] == first["display_number"]


def test_generated_wall_keeps_source_element_item_number(foundation_db):
    from app.model_review.service import model_review_service
    from app.walls.service import walls_service

    project, floors = _project_floors()
    wall_element = model_review_service.create(
        project_id=project["id"],
        floor_id=floors[0]["id"],
        payload={"element_type": "wall", "geometry": {"x": 10, "y": 10, "width": 80, "height": 8, "rotation": 0}},
        created_by=None,
    )["record"]

    generated = walls_service.build_lines(project["id"], floors[0]["id"])["walls"][0]
    assert generated["source_element_id"] == wall_element["id"]
    assert generated["item_number"] == wall_element["item_number"]
    assert generated["display_number"] == wall_element["display_number"]


def test_state_resolves_available_schedule_values(foundation_db):
    from app.database.session import get_connection
    from app.model_review.service import model_review_service
    from app.workflow.repo_base import dumps, now_iso

    project, floors = _project_floors()
    element = model_review_service.create(
        project_id=project["id"],
        floor_id=floors[0]["id"],
        payload={"element_type": "door", "geometry": {"x": 1, "y": 1, "width": 4, "height": 8, "rotation": 0}, "type_code": "D1"},
        created_by=None,
    )["record"]
    now = now_iso()
    with get_connection() as connection:
        connection.execute(
            """
            INSERT INTO schedule_entries (
              id, project_id, source_id, source_kind, category, entity_key, data_json,
              source_location_json, extraction_method, confidence, review_state,
              is_accepted, source_priority, extraction_version, created_at, updated_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                "schedule-d1", project["id"], "source-d1", "schedule", "door", "D1",
                dumps({"type_code": "D1", "width_mm": 900, "height_mm": 2100, "material": "Timber"}),
                "{}", "test", 1.0, "ready", 1, 500, 1, now, now,
            ),
        )
    state = model_review_service.get_state(project, floors[0]["id"])
    resolved = next(item for item in state["elements"] if item["id"] == element["id"])
    assert resolved["resolved_data"]["width_mm"] == 900
    assert resolved["resolved_data"]["height_mm"] == 2100
    assert resolved["resolved_sources"]["width_mm"] == "schedule"


def test_confirm_many_uses_one_version_and_one_read_model_pair(foundation_db):
    from app.model_review.service import model_review_service
    from app.model_review.repo import model_review_repository
    from app.projects.project_service import project_service
    from app.workflow.service import workflow_service
    from app.database.session import get_connection
    project=project_service.create_project("Bulk confirm")
    floor=workflow_service.create_floor(project_id=project["id"],name=None,level_index=None,created_by=None)
    first=model_review_repository.create_element(project_id=project["id"],floor_id=floor["id"],element_type="door",geometry={"x":1,"y":1,"width":5,"height":5},type_code="D1",source="model",confidence=.9,detection_version=1,is_manual=False,provider_name="test",created_by=None)
    second=model_review_repository.create_element(project_id=project["id"],floor_id=floor["id"],element_type="window",geometry={"x":10,"y":1,"width":5,"height":5},type_code="W1",source="model",confidence=.9,detection_version=1,is_manual=False,provider_name="test",created_by=None)
    result=model_review_service.confirm_many(project_id=project["id"],floor_id=floor["id"],element_ids=[first["id"],second["id"]],created_by=None)
    assert result["count"] == 2
    assert {job["task_type"] for job in result["jobs"]} == {"review.refresh","boq.refresh"}
    with get_connection() as connection:
        rows=connection.execute("SELECT task_type,COUNT(*) total FROM job_runs WHERE project_id=? GROUP BY task_type",(project["id"],)).fetchall()
    assert {row["task_type"]:int(row["total"]) for row in rows} == {"review.refresh":1,"boq.refresh":1}
