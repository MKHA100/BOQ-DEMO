from __future__ import annotations


def _job(payload=None):
    return {
        "project_id": "project-1",
        "floor_id": "floor-1",
        "payload_json": payload or {},
        "input_versions_json": {"crop_version": 1, "wall_version": 1, "scale_version": 1},
        "created_by": None,
    }


def test_model_publish_is_queued_before_background_interpretation(monkeypatch):
    from app.floors import jobs as floor_jobs

    monkeypatch.setattr(
        floor_jobs.floors_service,
        "detect_room_suggestions",
        lambda *_: {"status": "ready", "suggestions": 2, "published": 2, "room_ids": ["r1", "r2"]},
    )
    calls = []
    monkeypatch.setattr(
        floor_jobs.job_service,
        "enqueue",
        lambda **kwargs: (calls.append(kwargs) or {"id": f"job-{len(calls)}", "status": "pending"}, True),
    )
    result = floor_jobs.detect_rooms(_job())
    assert calls[0]["task_type"] == "rooms.prepare_lines"
    assert calls[1]["task_type"] == "rooms.publish_model_results"
    assert result["published"] == 2


def test_pipeline_runs_interpret_then_precision_then_area_and_one_read_refresh(monkeypatch):
    from app.floors import jobs as floor_jobs

    calls = []
    monkeypatch.setattr(
        floor_jobs.job_service,
        "enqueue",
        lambda **kwargs: (calls.append(kwargs) or {"id": f"job-{len(calls)}", "status": "pending"}, True),
    )
    monkeypatch.setattr(floor_jobs.floors_service, "assign_finishes", lambda *_: {"updated": 1})
    monkeypatch.setattr(floor_jobs.floors_service, "interpret_floor", lambda *_: {"status": "failed", "updated": 0})
    monkeypatch.setattr(floor_jobs.floors_service, "precision_refine", lambda *_args, **_kwargs: {"status": "ready", "updated": 1})
    monkeypatch.setattr(floor_jobs.floors_service, "calculate", lambda *_args, **_kwargs: {"updated": 1})

    floor_jobs.finishes(_job())
    assert calls[-1]["task_type"] == "rooms.interpret_floor"
    floor_jobs.interpret_floor(_job())
    assert calls[-1]["task_type"] == "rooms.precision_refine"
    floor_jobs.precision(_job({"interpretation_complete": True}))
    assert calls[-1]["task_type"] == "rooms.calculate_areas"
    floor_jobs.calculate(_job({"interpretation_complete": True, "precision_complete": True}))
    assert [item["task_type"] for item in calls].count("review.refresh") == 1
    assert [item["task_type"] for item in calls].count("boq.refresh") == 1


def test_scale_change_does_not_enqueue_model_or_llm():
    from app.workflow.dependencies import dependency_planner

    tasks = dependency_planner.for_scale_change(floor_id="floor-1")
    task_types = {item.task_type for item in tasks}
    assert "vision.detect_rooms" not in task_types
    assert "rooms.interpret_floor" not in task_types
    area = next(item for item in tasks if item.task_type == "rooms.calculate_areas")
    assert area.payload["precision_complete"] is True
