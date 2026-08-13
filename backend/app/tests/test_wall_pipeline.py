from __future__ import annotations


def _project_floor():
    from app.projects.project_service import project_service
    from app.workflow.service import workflow_service

    project = project_service.create_project("Automatic walls")
    floor = workflow_service.create_floor(
        project_id=project["id"], name="Ground Floor", level_index=0, created_by=None
    )
    return project, floor


def _wall_element(project_id: str, floor_id: str):
    from app.model_review.service import model_review_service

    return model_review_service.create(
        project_id=project_id,
        floor_id=floor_id,
        payload={
            "element_type": "wall",
            "geometry": {"x": 10, "y": 20, "width": 100, "height": 8, "rotation": 0},
        },
        created_by=None,
    )["record"]


def test_automatic_pipeline_creates_confirmed_walls_and_respects_deletion(foundation_db):
    from app.walls.service import walls_service

    project, floor = _project_floor()
    _wall_element(project["id"], floor["id"])

    first = walls_service.process_floor(project["id"], floor["id"])
    assert first["created"] == 1
    assert len(first["walls"]) == 1
    assert first["walls"][0]["status"] == "confirmed"
    # Automatic verification is distinct from an explicit user decision.
    assert first["walls"][0]["user_confirmed"] is False

    wall_id = first["walls"][0]["id"]
    removed = walls_service.delete(project["id"], floor["id"], wall_id, None)
    assert removed["suppressed"] is True

    rerun = walls_service.process_floor(project["id"], floor["id"])
    assert rerun["suppressed"] == 1
    assert rerun["walls"] == []


def test_automatic_pipeline_preserves_user_centerline_edit(foundation_db):
    from app.walls.service import walls_service

    project, floor = _project_floor()
    _wall_element(project["id"], floor["id"])
    generated = walls_service.process_floor(project["id"], floor["id"])["walls"][0]
    edited = {
        "start": dict(generated["centerline"]["start"]),
        "end": {
            "x": generated["centerline"]["end"]["x"],
            "y": generated["centerline"]["end"]["y"] + 12,
        },
    }
    walls_service.update(
        project_id=project["id"],
        floor_id=floor["id"],
        wall_id=generated["id"],
        payload={"centerline": edited},
        created_by=None,
    )

    rerun = walls_service.process_floor(project["id"], floor["id"])["walls"][0]
    assert rerun["centerline"] == edited


def test_regeneration_clears_legacy_confirmation_on_unedited_generated_wall(foundation_db):
    from app.walls.service import walls_service

    project, floor = _project_floor()
    _wall_element(project["id"], floor["id"])
    generated = walls_service.process_floor(project["id"], floor["id"])["walls"][0]
    walls_service.confirm_all(project["id"], floor["id"], None)

    rerun = walls_service.process_floor(project["id"], floor["id"])["walls"][0]

    assert rerun["id"] == generated["id"]
    assert rerun["status"] == "confirmed"
    assert rerun["user_confirmed"] is False


def test_wall_candidate_filter_rejects_dimension_strokes():
    from app.walls.service import walls_service

    assert walls_service._wall_candidate_is_plausible(
        {"geometry": {"width": 120, "height": 1}}, 30,
    ) is False
    assert walls_service._wall_candidate_is_plausible(
        {"geometry": {"width": 120, "height": 7}}, 30,
    ) is True
