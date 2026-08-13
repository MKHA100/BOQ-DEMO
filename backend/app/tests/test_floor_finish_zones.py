def test_finish_zone_is_clipped_to_parent():
    from app.floors.finish_zone_service import finish_zone_service
    parent = [{"x": 0, "y": 0}, {"x": 100, "y": 0}, {"x": 100, "y": 100}, {"x": 0, "y": 100}]
    zone = [{"x": 50, "y": 0}, {"x": 120, "y": 0}, {"x": 120, "y": 100}, {"x": 50, "y": 100}]
    clipped = finish_zone_service.validate(parent, zone)
    assert max(point["x"] for point in clipped) <= 100


def test_finish_zone_can_be_updated_and_deleted(foundation_db):
    from app.floors.service import floors_service
    from app.projects.project_service import project_service
    from app.workflow.service import workflow_service

    project = project_service.create_project("Finish Zone CRUD")
    floor = workflow_service.create_floor(project_id=project["id"], name=None, level_index=None, created_by=None)
    parent = floors_service.create(
        project["id"], floor["id"],
        {"points": [{"x": 0, "y": 0}, {"x": 100, "y": 0}, {"x": 100, "y": 100}, {"x": 0, "y": 100}], "name": "Open Plan"},
        None,
    )["record"]
    zone = floors_service.create_finish_zone(
        project["id"], floor["id"], parent["id"],
        {"points": [{"x": 0, "y": 0}, {"x": 50, "y": 0}, {"x": 50, "y": 100}, {"x": 0, "y": 100}], "name": "Dining"},
        None,
    )["record"]
    updated = floors_service.update_finish_zone(
        project["id"], floor["id"], parent["id"], zone["id"], {"floor_finish": "Tile"}, None
    )["record"]
    assert updated["floor_finish"] == "Tile"
    assert floors_service.delete_finish_zone(project["id"], floor["id"], parent["id"], zone["id"], None)["deleted"] is True
