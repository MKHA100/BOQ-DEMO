from __future__ import annotations


def _provisional_room():
    from app.database.session import get_connection
    from app.floors.repo import floors_repository
    from app.projects.project_service import project_service
    from app.workflow.repo import workflow_repository
    from app.workflow.service import workflow_service

    project = project_service.create_project("Room Review BOQ")
    floor = workflow_service.create_floor(project_id=project["id"], name=None, level_index=None, created_by=None)
    with get_connection() as connection:
        versions = workflow_repository.increment_floor_version(connection, project["id"], floor["id"], "room_version")
    points = [{"x": 0, "y": 0}, {"x": 100, "y": 0}, {"x": 100, "y": 80}, {"x": 0, "y": 80}]
    room = floors_repository.create_room(
        project_id=project["id"], floor_id=floor["id"], points=points,
        generated=True, room_version=versions["room_version"], created_by=None,
        name="Office", room_type="Office", floor_type_code="F1", floor_finish="Tile",
        detection_source="roboflow", comparison_status="model_provisional",
        space_kind="internal", include_in_boq=True,
    )
    floors_repository.update_room(
        project["id"], floor["id"], room["id"],
        {
            "area_m2": 80,
            "perimeter_m": 36,
            "measurement_status": "correct",
            "boundary_source": "model_only",
            "status": "ready",
            "wall_corrected_geometry": {},
        },
        versions["room_version"], confirmed=False,
    )
    return project, floor, room, points, versions


def test_provisional_model_only_room_stays_out_of_review_and_boq(foundation_db):
    from app.boq.quantity_resolver import boq_quantity_resolver
    from app.review.service import review_service

    project, _floor, room, _points, _versions = _provisional_room()
    groups, _ = boq_quantity_resolver.resolve(project["id"])
    assert all(room["id"] not in item["sources"] for item in groups)
    review_service.refresh(project["id"])
    assert all(item["entity_id"] != room["id"] for item in review_service.state(project)["items"])


def test_wall_corrected_room_appears_once_in_review_and_boq(foundation_db):
    from app.boq.quantity_resolver import boq_quantity_resolver
    from app.floors.repo import floors_repository
    from app.review.service import review_service

    project, floor, room, points, versions = _provisional_room()
    floors_repository.update_room(
        project["id"], floor["id"], room["id"],
        {
            "wall_corrected_geometry": {"points": points},
            "regularized_geometry": {"points": points},
            "boundary_source": "wall_corrected",
            "comparison_status": "wall_corrected",
            "interpretation_status": "ready",
            "dimension_status": "exact",
            "dimension_source": "llm_verified",
        },
        versions["room_version"], confirmed=False,
    )
    groups, _ = boq_quantity_resolver.resolve(project["id"])
    floor_groups = [item for item in groups if room["id"] in item["sources"]]
    assert len(floor_groups) == 1
    assert floor_groups[0]["quantity"] == 80
    review_service.refresh(project["id"])
    items = [item for item in review_service.state(project)["items"] if item["entity_id"] == room["id"]]
    assert len(items) == 1
    assert items[0]["data"]["dimension_source"] == "llm_verified"
