from __future__ import annotations


def _candidate(name, points, *, source="wall_cell", confidence=0.9):
    from app.floors.polygon_builder import room_polygon_builder

    polygon = room_polygon_builder.points_to_polygon(points)
    return {
        "name": name,
        "points": points,
        "boundary_source": source,
        "confidence": confidence,
        "wall_ids": [f"wall-{name}"] if "wall" in source else [],
        "geometry_hash": room_polygon_builder.geometry_hash(polygon),
        "area_px": polygon.area,
    }


def test_outer_mask_containing_separate_wall_cells_is_rejected():
    from shapely.geometry import box
    from app.floors.room_candidate_filter import room_candidate_filter

    result = room_candidate_filter.filter(
        [
            _candidate("outer", [{"x": 0, "y": 0}, {"x": 100, "y": 0}, {"x": 100, "y": 100}, {"x": 0, "y": 100}], source="model_only"),
            _candidate("left", [{"x": 5, "y": 5}, {"x": 45, "y": 5}, {"x": 45, "y": 45}, {"x": 5, "y": 45}]),
            _candidate("right", [{"x": 55, "y": 5}, {"x": 95, "y": 5}, {"x": 95, "y": 45}, {"x": 55, "y": 45}]),
        ],
        envelope=box(0, 0, 100, 100),
        mm_per_pixel=None,
    )
    assert len(result["accepted"]) == 2
    assert any(item["reason"] == "outer_or_multi_room_boundary" for item in result["rejected"])


def test_scaled_dimension_line_sliver_is_rejected():
    from shapely.geometry import box
    from app.floors.room_candidate_filter import room_candidate_filter

    result = room_candidate_filter.filter(
        [
            _candidate(
                "sliver",
                [
                    {"x": 5, "y": 5},
                    {"x": 95, "y": 5},
                    {"x": 95, "y": 6.5},
                    {"x": 5, "y": 6.5},
                ],
                source="model_only",
            )
        ],
        envelope=box(0, 0, 100, 100),
        mm_per_pixel=100.0,
    )

    assert result["accepted"] == []
    assert result["rejected"][0]["reason"] == "below_minimum_room_width"


def test_model_room_is_kept_when_it_is_not_a_sliver():
    from shapely.geometry import box
    from app.floors.room_candidate_filter import room_candidate_filter

    result = room_candidate_filter.filter(
        [
            _candidate(
                "bedroom",
                [
                    {"x": 5, "y": 5},
                    {"x": 55, "y": 5},
                    {"x": 55, "y": 45},
                    {"x": 5, "y": 45},
                ],
                source="model_only",
            )
        ],
        envelope=box(0, 0, 100, 100),
        mm_per_pixel=50.0,
    )

    assert len(result["accepted"]) == 1


def test_credible_model_balcony_is_not_clipped_by_wall_envelope():
    from shapely.geometry import box
    from app.floors.room_candidate_filter import room_candidate_filter

    points = [
        {"x": 5, "y": 20},
        {"x": 35, "y": 20},
        {"x": 35, "y": 70},
        {"x": 5, "y": 70},
    ]
    result = room_candidate_filter.filter(
        [_candidate("balcony", points, source="model_only", confidence=0.82)],
        envelope=box(30, 0, 100, 100),
        mm_per_pixel=None,
    )

    assert len(result["accepted"]) == 1
    assert result["accepted"][0]["points"] == points
