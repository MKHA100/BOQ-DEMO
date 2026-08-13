from __future__ import annotations


def test_model_seed_selects_the_containing_wall_bounded_room():
    from shapely.geometry import box
    from shapely.ops import unary_union
    from app.floors.room_seed_service import room_seed_service

    envelope = box(0, 0, 100, 80)
    walls = unary_union([
        box(0, 0, 100, 5), box(0, 75, 100, 80),
        box(0, 0, 5, 80), box(95, 0, 100, 80),
        box(48, 0, 52, 80),
    ])
    suggestion = {
        "id": "right-room", "status": "new", "confidence": 0.96,
        "polygon": {"points": [
            {"x": 55, "y": 8}, {"x": 92, "y": 8},
            {"x": 92, "y": 72}, {"x": 55, "y": 72},
        ]},
    }
    result = room_seed_service.refine(
        room_id=None,
        room_points=suggestion["polygon"]["points"],
        suggestions=[suggestion],
        prepared={"wall_footprints": walls, "door_closures": [], "typical_thickness_px": 4},
        envelope=envelope,
    )
    assert result is not None
    assert result.source == "model_seed_wall_faces"
    xs = [point["x"] for point in result.points]
    assert min(xs) >= 51.5
    assert max(xs) <= 95.5


def test_large_wall_cell_does_not_replace_one_model_room():
    from shapely.geometry import box
    from shapely.ops import unary_union
    from app.floors.room_seed_service import room_seed_service

    envelope = box(0, 0, 100, 100)
    walls = unary_union([
        box(0, 0, 100, 5), box(0, 95, 100, 100),
        box(0, 0, 5, 100), box(95, 0, 100, 100),
    ])
    points = [
        {"x": 10, "y": 10}, {"x": 30, "y": 10},
        {"x": 30, "y": 30}, {"x": 10, "y": 30},
    ]
    result = room_seed_service.refine(
        room_id=None,
        room_points=points,
        suggestions=[{
            "id": "one-room", "status": "new", "confidence": 0.95,
            "polygon": {"points": points},
        }],
        prepared={"wall_footprints": walls, "door_closures": [], "typical_thickness_px": 4},
        envelope=envelope,
    )

    assert result is not None
    assert result.source == "model_only"
    assert max(point["x"] for point in result.points) <= 31
