from __future__ import annotations


def test_reset_to_model_restores_raw_model_geometry(monkeypatch):
    from app.floors.service import floors_service
    from app.floors import service as module

    room = {
        "id": "r1", "geometry_version": 2, "user_confirmed": True,
        "geometry": {"points": [{"x": 0, "y": 0}, {"x": 20, "y": 0}, {"x": 20, "y": 20}, {"x": 0, "y": 20}]},
        "model_polygon": {"points": [{"x": 2, "y": 2}, {"x": 18, "y": 2}, {"x": 18, "y": 18}, {"x": 2, "y": 18}]},
        "raw_geometry": {}, "generated_geometry": {},
    }
    saved = {}
    monkeypatch.setattr(module.floors_repository, "get_room", lambda *args: room if not saved else {**room, **saved})
    monkeypatch.setattr(module.edit_history_service, "record", lambda *args, **kwargs: None)
    monkeypatch.setattr(module.workflow_repository, "increment_floor_version", lambda *args, **kwargs: {"room_version": 4})
    monkeypatch.setattr(module.floors_repository, "update_room", lambda _p, _f, _r, patch, *_args, **_kwargs: saved.update(patch) or patch)
    monkeypatch.setattr(floors_service, "calculate", lambda *args, **kwargs: {"updated": 1})

    result = floors_service.reset_to_model("p", "f", "r1", None)
    assert result["record"]["boundary_source"] == "model_only"
    assert result["record"]["user_edited"] is False
    assert len(result["record"]["geometry"]["points"]) == 4
