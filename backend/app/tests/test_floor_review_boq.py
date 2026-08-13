from __future__ import annotations


def test_room_flows_to_review_and_boq_then_exclusion_removes_it(foundation_db):
    from app.projects.project_service import project_service
    from app.workflow.service import workflow_service
    from app.floors.service import floors_service
    from app.review.service import review_service
    from app.boq.service import boq_service
    from app.database.session import get_connection
    from app.workflow.repo import workflow_repository

    project = project_service.create_project("Floor review BOQ")
    floor = workflow_service.create_floor(project_id=project["id"], name=None, level_index=None, created_by=None)
    with get_connection() as connection:
        connection.execute("UPDATE floor_versions SET scale_version=1 WHERE floor_id=?", (floor["id"],))
        connection.execute(
            "INSERT INTO calibrations (id,project_id,floor_id,point_a_json,point_b_json,pixel_distance,real_distance,unit,units_per_pixel,source_crop_version,scale_version,status,created_at,updated_at,real_distance_mm,mm_per_pixel,crop_version) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            ("floor-review-cal", project["id"], floor["id"], "{}", "{}", 100, 1000, "mm", 10, 1, 1, "calibrated", "x", "x", 1000, 10, 1),
        )
        workflow_repository.increment_floor_version(connection, project["id"], floor["id"], "room_version")

    room = floors_service.create(
        project["id"], floor["id"],
        {
            "points": [{"x": 0, "y": 0}, {"x": 100, "y": 0}, {"x": 100, "y": 80}, {"x": 0, "y": 80}],
            "name": "Office", "room_type": "Office", "floor_type_code": "F1", "floor_finish": "Ceramic tile",
        },
        None,
    )["record"]
    floors_service.confirm(project["id"], floor["id"], room["id"], None)

    review_service.refresh(project["id"])
    review_item = next(item for item in review_service.state(project)["items"] if item["entity_id"] == room["id"])
    assert review_item["entity_type"] == "floor"
    assert review_item["data"]["floor_finish"] == "Ceramic tile"
    assert review_item["data"]["area_m2"] == 0.8

    boq = boq_service.refresh(project["id"])
    floor_row = next(item for item in boq["rows"] if room["id"] in item["source_ids"])
    assert floor_row["entity_type"] == "floor"
    assert floor_row["quantity"] == 0.8
    assert floor["id"] in floor_row["floor_ids"]

    floors_service.exclude(project["id"], floor["id"], room["id"], "Void", None)
    review_service.refresh(project["id"])
    assert all(item["entity_id"] != room["id"] for item in review_service.state(project)["items"])
    boq = boq_service.refresh(project["id"])
    assert all(room["id"] not in item["source_ids"] for item in boq["rows"])
