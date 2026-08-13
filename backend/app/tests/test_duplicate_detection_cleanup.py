from __future__ import annotations


def test_cleanup_supersedes_geometric_duplicates(foundation_db):
    from app.model_review.cleanup_service import detection_cleanup_service
    from app.model_review.repo import model_review_repository
    from app.projects.project_service import project_service
    from app.workflow.service import workflow_service

    project = project_service.create_project("Duplicate cleanup")
    floor = workflow_service.create_floor(project_id=project["id"], name=None, level_index=None, created_by=None)
    geometry = {"x": 10, "y": 10, "width": 20, "height": 30}
    for _ in range(2):
        model_review_repository.create_element(
            project_id=project["id"], floor_id=floor["id"], element_type="door", geometry=geometry,
            type_code=None, source="model", confidence=.9, detection_version=1, is_manual=False,
            provider_name="test", created_by=None,
        )
    result = detection_cleanup_service.repair_project(
        project["id"], floor["id"], enqueue_rebuild=False
    )
    assert result["kept"] == 1
    assert result["superseded"] == 1
    assert result["affected_floors"] == [floor["id"]]
    assert result["jobs"] == []
