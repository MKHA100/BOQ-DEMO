from __future__ import annotations


def _project_and_floor():
    from app.projects.project_service import project_service
    from app.workflow.service import workflow_service

    project = project_service.create_project("Tower")
    floor = workflow_service.create_floor(project_id=project["id"], name=None, level_index=None, created_by=None)
    return project, floor


def test_version_updates_and_floor_isolation(foundation_db):
    from app.database.session import get_connection
    from app.workflow.service import workflow_service

    project, ground = _project_and_floor()
    first = workflow_service.create_floor(project_id=project["id"], name=None, level_index=None, created_by=None)

    result = workflow_service.save_calibration(
        project_id=project["id"],
        floor_id=first["id"],
        point_a={"x": 0, "y": 0},
        point_b={"x": 100, "y": 0},
        real_distance=10,
        unit="m",
        source_crop_version=1,
        confirmed_by=None,
    )

    assert result["versions"]["scale_version"] == 1
    assert {job["floor_id"] for job in result["jobs"]} == {first["id"]}
    with get_connection() as connection:
        ground_versions = connection.execute("SELECT * FROM floor_versions WHERE floor_id = ?", (ground["id"],)).fetchone()
        first_versions = connection.execute("SELECT * FROM floor_versions WHERE floor_id = ?", (first["id"],)).fetchone()
    assert ground_versions["scale_version"] == 0
    assert first_versions["scale_version"] == 1


def test_confirmed_value_is_protected_and_conflict_becomes_review_issue(foundation_db):
    from app.database.session import get_connection
    from app.workflow.service import workflow_service

    project, floor = _project_and_floor()
    element = workflow_service.create_element(
        project_id=project["id"],
        payload={
            "floor_id": floor["id"],
            "element_type": "door",
            "type_code": "D1",
            "geometry": {},
            "source": "model",
            "confidence": 0.9,
            "status": "needs_review",
        },
        created_by=None,
    )["record"]

    confirmed = workflow_service.update_element_property(
        project_id=project["id"],
        element_id=element["id"],
        property_name="width_mm",
        value=900,
        unit="mm",
        source="user_confirmed",
        confirm=True,
        created_by=None,
    )
    suggested = workflow_service.update_element_property(
        project_id=project["id"],
        element_id=element["id"],
        property_name="width_mm",
        value=850,
        unit="mm",
        source="schedule",
        confirm=False,
        created_by=None,
    )

    assert confirmed["record"]["value"] == 900
    assert suggested["protected"] is True
    assert suggested["record"]["value"] == 900
    assert suggested["record"]["suggestion_value"] == 850
    with get_connection() as connection:
        issue = connection.execute(
            "SELECT * FROM review_issues WHERE entity_id = ? AND issue_type = 'conflicting_width_mm'",
            (element["id"],),
        ).fetchone()
    assert issue is not None
    assert issue["status"] == "needs_review"


def test_cross_page_dependencies_are_targeted(foundation_db):
    from app.database.session import get_connection
    from app.workflow.service import workflow_service

    project, floor = _project_and_floor()
    element = workflow_service.create_element(
        project_id=project["id"],
        payload={
            "floor_id": floor["id"],
            "element_type": "door",
            "type_code": "D1",
            "geometry": {},
            "source": "model",
            "confidence": 0.9,
            "status": "confirmed",
        },
        created_by=None,
    )["record"]
    wall = workflow_service.create_wall(
        project_id=project["id"],
        payload={
            "floor_id": floor["id"],
            "geometry": {},
            "wall_type": "W1",
            "classification": "internal",
            "thickness_mm": 100,
            "height_mm": 3000,
            "gross_area_m2": 12,
            "status": "ready",
        },
        created_by=None,
    )["record"]
    workflow_service.create_relation(
        project_id=project["id"],
        payload={
            "floor_id": floor["id"],
            "source_element_id": element["id"],
            "target_type": "wall",
            "target_id": wall["id"],
            "relation_type": "opening",
        },
        created_by=None,
    )

    result = workflow_service.update_element_property(
        project_id=project["id"],
        element_id=element["id"],
        property_name="height_mm",
        value=2100,
        unit="mm",
        source="user_confirmed",
        confirm=True,
        created_by=None,
    )
    tasks = {job["task_type"] for job in result["jobs"]}
    assert tasks == {"walls.recalculate_deduction", "review.refresh", "boq.refresh"}
    with get_connection() as connection:
        wall_row = connection.execute("SELECT is_stale, status FROM walls WHERE id = ?", (wall["id"],)).fetchone()
        unrelated = connection.execute(
            "SELECT COUNT(*) AS total FROM job_runs WHERE project_id = ? AND task_type IN ('rooms.build','vision.detect_elements')",
            (project["id"],),
        ).fetchone()
    assert wall_row["is_stale"] == 1
    assert wall_row["status"] == "not_ready"
    assert unrelated["total"] == 0


def test_room_geometry_only_invalidates_room_dependencies(foundation_db):
    from app.workflow.service import workflow_service

    project, floor = _project_and_floor()
    room = workflow_service.create_room(
        project_id=project["id"],
        payload={"floor_id": floor["id"], "name": "Office", "geometry": {}, "finish_code": "F1", "status": "ready"},
        created_by=None,
    )["record"]
    result = workflow_service.update_room_geometry(
        project_id=project["id"],
        room_id=room["id"],
        geometry={"points": [[0, 0], [5, 0], [5, 4], [0, 4]]},
        confirm=True,
        created_by=None,
    )
    assert {job["task_type"] for job in result["jobs"]} == {"rooms.measure"}


def test_saved_read_models_are_floor_scoped(foundation_db):
    from app.projects.project_service import project_service
    from app.workflow.read_service import workflow_read_service
    from app.workflow.service import workflow_service

    project = project_service.create_project("Campus")
    ground = workflow_service.create_floor(project_id=project["id"], name=None, level_index=None, created_by=None)
    first = workflow_service.create_floor(project_id=project["id"], name=None, level_index=None, created_by=None)
    workflow_service.create_element(
        project_id=project["id"],
        payload={
            "floor_id": ground["id"],
            "element_type": "door",
            "type_code": "D1",
            "geometry": {},
            "source": "model",
            "confidence": 0.8,
            "status": "needs_review",
        },
        created_by=None,
    )
    workflow_service.create_element(
        project_id=project["id"],
        payload={
            "floor_id": first["id"],
            "element_type": "window",
            "type_code": "W1",
            "geometry": {},
            "source": "model",
            "confidence": 0.8,
            "status": "needs_review",
        },
        created_by=None,
    )

    ground_items = workflow_read_service.list_elements(
        project["id"], ground["id"], element_type=None, status=None, limit=100, offset=0
    )
    first_items = workflow_read_service.list_elements(
        project["id"], first["id"], element_type=None, status=None, limit=100, offset=0
    )

    assert ground_items["total"] == 1
    assert ground_items["items"][0]["element_type"] == "door"
    assert first_items["total"] == 1
    assert first_items["items"][0]["element_type"] == "window"
