from __future__ import annotations


def test_floor_interpretation_cache_is_exact_and_scale_reusable(foundation_db):
    from app.floors.llm_room_cache import llm_room_cache
    from app.projects.project_service import project_service
    from app.workflow.service import workflow_service

    project = project_service.create_project("LLM Cache")
    floor = workflow_service.create_floor(
        project_id=project["id"], name=None, level_index=None, created_by=None
    )
    identity = {
        "project_id": project["id"],
        "floor_id": floor["id"],
        "crop_version": 1,
        "wall_version": 2,
        "scale_version": 3,
        "prompt_version": "p1",
        "model": "test-model",
    }
    run = llm_room_cache.begin(**identity, input_hash="abc")
    assert run["claimed"] is True
    llm_room_cache.complete(
        run["id"],
        raw_response={"id": "response-1"},
        validated_response={"floor_id": floor["id"], "rooms": [], "warnings": []},
        results=[],
    )
    exact = llm_room_cache.get_exact(**identity)
    assert exact and exact["status"] == "ready"
    assert exact["validated_response"]["floor_id"] == floor["id"]
    reused = llm_room_cache.find_reusable(
        project_id=project["id"],
        floor_id=floor["id"],
        crop_version=1,
        wall_version=2,
        prompt_version="p1",
        model="test-model",
    )
    assert reused and reused["id"] == run["id"]


def test_floor_interpretation_cache_claims_same_input_once(foundation_db):
    from app.floors.llm_room_cache import llm_room_cache
    from app.projects.project_service import project_service
    from app.workflow.service import workflow_service

    project = project_service.create_project("LLM Claim")
    floor = workflow_service.create_floor(project_id=project["id"], name=None, level_index=None, created_by=None)
    identity = dict(project_id=project["id"], floor_id=floor["id"], crop_version=1, wall_version=1, scale_version=1, prompt_version="p1", model="m1", input_hash="same")
    first = llm_room_cache.begin(**identity)
    second = llm_room_cache.begin(**identity)
    assert first["id"] == second["id"]
    assert first["claimed"] is True
    assert second["claimed"] is False
