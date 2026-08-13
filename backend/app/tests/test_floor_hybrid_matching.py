from __future__ import annotations


def square(x0, y0, x1, y1):
    return [{"x": x0, "y": y0}, {"x": x1, "y": y0}, {"x": x1, "y": y1}, {"x": x0, "y": y1}]


def test_hybrid_matcher_verifies_close_room_and_keeps_model_only_suggestion():
    from app.floors.hybrid_matcher import hybrid_room_matcher

    result = hybrid_room_matcher.reconcile(
        [{"points": square(0, 0, 100, 100), "geometry_hash": "wall", "touches_crop_edge": False}],
        [
            {"id": "near", "polygon": {"points": square(2, 2, 98, 98)}, "confidence": 0.94, "status": "new"},
            {"id": "missing", "polygon": {"points": square(200, 0, 260, 60)}, "confidence": 0.90, "status": "new"},
        ],
    )
    assert result["canonical"][0]["detection_source"] == "hybrid"
    assert result["canonical"][0]["model_verified"] is True
    assert result["canonical"][0]["comparison_status"] == "verified"
    assert result["unmatched_suggestions"][0]["id"] == "missing"


def test_large_difference_keeps_wall_geometry_as_primary():
    from app.floors.hybrid_matcher import hybrid_room_matcher

    result = hybrid_room_matcher.reconcile(
        [{"points": square(0, 0, 100, 100), "geometry_hash": "wall", "touches_crop_edge": False}],
        [{"id": "far", "polygon": {"points": square(300, 300, 350, 350)}, "confidence": 0.99, "status": "new"}],
    )
    assert result["canonical"][0]["detection_source"] == "wall_geometry"
    assert result["canonical"][0]["comparison_status"] == "wall_only"
    assert len(result["unmatched_suggestions"]) == 1
