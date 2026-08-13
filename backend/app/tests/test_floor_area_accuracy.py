from __future__ import annotations


def test_floor_area_comes_from_local_polygon_and_scale():
    from app.floors.room_area_resolver import room_area_resolver

    room = {"wall_corrected_geometry": {"points": [
        {"x": 0, "y": 0}, {"x": 100, "y": 0}, {"x": 100, "y": 80}, {"x": 0, "y": 80},
    ]}}
    result = room_area_resolver.resolve(room, 10)
    assert result["area_m2"] == 0.8
    assert result["source"] == "wall_corrected"

