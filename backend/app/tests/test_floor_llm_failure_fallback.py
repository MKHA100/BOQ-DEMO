from __future__ import annotations

from types import SimpleNamespace

import pytest


def test_llm_http_failure_is_saved_and_returned_without_raising(monkeypatch):
    from app.floors import llm_room_interpreter as module

    monkeypatch.setattr(
        module,
        "settings",
        SimpleNamespace(
            room_llm_enabled=True,
            room_llm_background_enabled=True,
            room_llm_model="test-model",
            room_llm_timeout_seconds=60,
            room_llm_max_floor_calls=1,
            openai_api_key="test-key",
        ),
    )
    monkeypatch.setattr(
        module.llm_room_context_service,
        "build",
        lambda *_: {
            "versions": {"crop_version": 1, "wall_version": 1, "scale_version": 1},
            "context": {
                "floor_id": "floor-1",
                "room_suggestions": [
                    {
                        "id": "suggestion-1",
                        "polygon": {
                            "points": [
                                {"x": 0, "y": 0},
                                {"x": 10, "y": 0},
                                {"x": 10, "y": 10},
                                {"x": 0, "y": 10},
                            ]
                        },
                    }
                ],
                "rooms": [],
            },
            "image_url": "data:image/png;base64,AA==",
            "input_hash": "hash",
        },
    )
    monkeypatch.setattr(module.llm_room_cache, "get_exact", lambda **_: None)
    monkeypatch.setattr(module.llm_room_cache, "find_reusable", lambda **_: None)
    monkeypatch.setattr(module.llm_room_cache, "begin", lambda **_: {"id": "run-1", "claimed": True, "status": "processing"})
    failed = []
    monkeypatch.setattr(module.llm_room_cache, "fail", lambda run_id, message, raw=None: failed.append((run_id, message)))

    def unavailable(*_args, **_kwargs):
        raise module.httpx.ConnectError("offline")

    monkeypatch.setattr(module.httpx, "post", unavailable)
    result = module.LLMRoomInterpreter().interpret_floor("project-1", "floor-1")
    assert result["status"] == "failed"
    assert result["rooms"] == []
    assert failed and failed[0][0] == "run-1"


def test_failed_interpretation_still_queues_local_precision(monkeypatch):
    from app.floors import jobs as floor_jobs

    monkeypatch.setattr(
        floor_jobs.floors_service,
        "interpret_floor",
        lambda *_: {"status": "failed", "warning": "offline", "updated": 0},
    )
    calls = []
    monkeypatch.setattr(
        floor_jobs.job_service,
        "enqueue",
        lambda **kwargs: (calls.append(kwargs) or {"id": "precision", "status": "pending"}, True),
    )
    result = floor_jobs.interpret_floor(
        {
            "project_id": "project-1",
            "floor_id": "floor-1",
            "payload_json": {},
            "input_versions_json": {"crop_version": 1},
            "created_by": None,
        }
    )
    assert calls[0]["task_type"] == "rooms.precision_refine"
    assert result["status"] == "failed"


def test_rate_limit_gets_one_short_retry(monkeypatch):
    from app.floors import llm_room_interpreter as module

    monkeypatch.setattr(
        module,
        "settings",
        SimpleNamespace(openai_api_key="test-key", room_llm_timeout_seconds=60),
    )
    calls = []

    class RateLimited:
        status_code = 429
        headers = {"Retry-After": "0"}

    def post(*_args, **_kwargs):
        calls.append(True)
        if len(calls) == 1:
            return RateLimited()
        raise module.httpx.ConnectError("offline after retry")

    monkeypatch.setattr(module.httpx, "post", post)
    with pytest.raises(module.httpx.ConnectError):
        module.LLMRoomInterpreter()._request({}, "data:image/png;base64,AA==", "test-model")

    assert len(calls) == 2
