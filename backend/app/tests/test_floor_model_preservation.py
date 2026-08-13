from __future__ import annotations


def _points(x0: float, y0: float, x1: float, y1: float):
    return [
        {"x": x0, "y": y0},
        {"x": x1, "y": y0},
        {"x": x1, "y": y1},
        {"x": x0, "y": y1},
    ]


def test_current_model_support_matches_raw_model_polygon():
    from app.floors.service import floors_service

    room = {
        "id": "room-1",
        "raw_geometry": {"points": _points(10, 10, 50, 50)},
    }
    suggestions = [
        {
            "id": "suggestion-1",
            "status": "new",
            "polygon": {"points": _points(11, 11, 51, 51)},
        }
    ]

    assert floors_service._has_current_model_support(room, suggestions) is True


def test_rejected_model_suggestion_is_not_current_support():
    from app.floors.service import floors_service

    room = {
        "id": "room-1",
        "raw_geometry": {"points": _points(10, 10, 50, 50)},
    }
    suggestions = [
        {
            "id": "suggestion-1",
            "status": "rejected",
            "matched_room_id": "room-1",
            "polygon": {"points": _points(10, 10, 50, 50)},
        }
    ]

    assert floors_service._has_current_model_support(room, suggestions) is False
