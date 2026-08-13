from __future__ import annotations


def test_door_gap_is_closed_and_window_is_ignored():
    from app.floors.line_builder import room_line_builder

    walls = [
        {"id": "top", "centerline": {"start": {"x": 0, "y": 0}, "end": {"x": 100, "y": 0}}, "thickness_mm": 100},
        {"id": "right", "centerline": {"start": {"x": 100, "y": 0}, "end": {"x": 100, "y": 80}}, "thickness_mm": 100},
        {"id": "bottom-right", "centerline": {"start": {"x": 100, "y": 80}, "end": {"x": 60, "y": 80}}, "thickness_mm": 100},
        {"id": "bottom-left", "centerline": {"start": {"x": 40, "y": 80}, "end": {"x": 0, "y": 80}}, "thickness_mm": 100},
        {"id": "left", "centerline": {"start": {"x": 0, "y": 80}, "end": {"x": 0, "y": 0}}, "thickness_mm": 100},
    ]
    openings = [
        {
            "id": "door-1", "element_type": "door",
            "geometry": {"x": 40, "y": 75, "width": 20, "height": 10},
            "dimensions": {"width_mm": 200},
        },
        {
            "id": "window-1", "element_type": "window",
            "geometry": {"x": 5, "y": 0, "width": 20, "height": 5},
        },
    ]

    result = room_line_builder.build(walls=walls, openings=openings, mm_per_pixel=10)
    assert len(result["door_closures"]) == 1
    closure = result["door_closures"][0]["line"]
    assert round(closure.length, 4) == 20
    assert set(tuple(point) for point in closure.coords) == {(40.0, 80.0), (60.0, 80.0)}


def test_production_vector_mode_does_not_create_independent_boundaries():
    from app.floors.line_builder import room_line_builder

    walls = [{
        "id": "canonical",
        "centerline": {"start": {"x": 0, "y": 0}, "end": {"x": 100, "y": 0}},
        "thickness_mm": 100,
    }]
    vectors = [{
        "id": "dimension-pair",
        "centerline": {"start": {"x": 0, "y": 40}, "end": {"x": 100, "y": 40}},
        "thickness_px": 4,
        "footprint": [
            {"x": 0, "y": 38}, {"x": 100, "y": 38},
            {"x": 100, "y": 42}, {"x": 0, "y": 42},
        ],
    }]

    result = room_line_builder.build(
        walls=walls, openings=[], mm_per_pixel=10,
        vector_walls=vectors, vector_mode="refine",
    )

    assert len(result["wall_segments"]) == 1
    assert result["vector_wall_count"] == 0
    assert result["vector_evidence_count"] == 0
