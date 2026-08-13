from __future__ import annotations


def test_candidate_filter_returns_non_overlapping_rooms():
    from shapely.geometry import box
    from app.floors.room_candidate_filter import room_candidate_filter
    from app.floors.room_overlap_service import room_overlap_service

    values = [
        {"points": [{"x": 0, "y": 0}, {"x": 60, "y": 0}, {"x": 60, "y": 50}, {"x": 0, "y": 50}], "boundary_source": "wall_cell", "wall_ids": ["w1"], "confidence": 0.9, "area_px": 3000},
        {"points": [{"x": 40, "y": 0}, {"x": 100, "y": 0}, {"x": 100, "y": 50}, {"x": 40, "y": 50}], "boundary_source": "model_only", "wall_ids": [], "confidence": 0.8, "area_px": 3000},
    ]
    result = room_candidate_filter.filter(values, envelope=box(0, 0, 100, 60), mm_per_pixel=None)
    assert len(result["accepted"]) == 2
    first = room_overlap_service.polygon(result["accepted"][0])
    second = room_overlap_service.polygon(result["accepted"][1])
    assert first.intersection(second).area == 0

