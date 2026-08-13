from __future__ import annotations


def test_deleted_generated_room_is_hidden_and_persistently_rejected(foundation_db):
    from app.projects.project_service import project_service
    from app.workflow.service import workflow_service
    from app.floors.repo import floors_repository

    project = project_service.create_project("Durable room rejection")
    floor = workflow_service.create_floor(project_id=project["id"], name=None, level_index=None, created_by=None)
    room = floors_repository.create_room(
        project_id=project["id"], floor_id=floor["id"],
        points=[{"x": 0, "y": 0}, {"x": 20, "y": 0}, {"x": 20, "y": 20}, {"x": 0, "y": 20}],
        generated=True, room_version=1, created_by=None, detection_source="wall_geometry",
    )
    assert floors_repository.reject_room(project["id"], floor["id"], room["id"])
    assert floors_repository.list_rooms(project["id"], floor["id"]) == []
    rejected = floors_repository.list_room_records(project["id"], floor["id"], generated_status="rejected")
    assert [item["id"] for item in rejected] == [room["id"]]

