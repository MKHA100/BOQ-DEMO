from __future__ import annotations


def test_boq_ignores_unconfirmed_generated_floor_area(foundation_db):
    from app.projects.project_service import project_service
    from app.workflow.service import workflow_service
    from app.floors.repo import floors_repository
    from app.boq.quantity_resolver import boq_quantity_resolver

    project = project_service.create_project("Safe floor BOQ")
    floor = workflow_service.create_floor(project_id=project["id"], name=None, level_index=None, created_by=None)
    room = floors_repository.create_room(
        project_id=project["id"], floor_id=floor["id"],
        points=[{"x": 0, "y": 0}, {"x": 20, "y": 0}, {"x": 20, "y": 20}, {"x": 0, "y": 20}],
        generated=True, room_version=1, created_by=None, detection_source="model_only",
        floor_finish="Tile",
    )
    floors_repository.update_room(project["id"], floor["id"], room["id"], {"area_m2": 99.0}, 1, confirmed=False)
    groups, _ = boq_quantity_resolver.resolve(project["id"])
    assert all(room["id"] not in item["sources"] for item in groups)


def test_boq_rejects_room_area_from_raw_vector_boundaries(foundation_db):
    from app.projects.project_service import project_service
    from app.workflow.service import workflow_service
    from app.floors.repo import floors_repository
    from app.boq.quantity_resolver import boq_quantity_resolver

    project = project_service.create_project("Unsafe vector floor BOQ")
    floor = workflow_service.create_floor(project_id=project["id"], name=None, level_index=None, created_by=None)
    room = floors_repository.create_room(
        project_id=project["id"], floor_id=floor["id"],
        points=[{"x": 0, "y": 0}, {"x": 20, "y": 0}, {"x": 20, "y": 20}, {"x": 0, "y": 20}],
        generated=True, room_version=1, created_by=None, detection_source="wall_geometry",
        floor_finish="Tile",
    )
    floors_repository.update_room(
        project["id"], floor["id"], room["id"],
        {
            "area_m2": 25.0,
            "boundary_source": "vector_wall_faces",
            "measurement_status": "correct",
            "precision_status": "ready",
            "geometry_status": "ready",
            "include_in_boq": True,
        },
        1,
        confirmed=False,
    )

    groups, _ = boq_quantity_resolver.resolve(project["id"])
    assert all(room["id"] not in item["sources"] for item in groups)
