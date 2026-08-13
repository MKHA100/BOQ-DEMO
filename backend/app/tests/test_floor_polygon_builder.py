from __future__ import annotations

from shapely.geometry import LineString
from shapely.ops import unary_union


def _prepared():
    lines = [
        LineString([(0, 0), (100, 0)]),
        LineString([(100, 0), (100, 80)]),
        LineString([(100, 80), (0, 80)]),
        LineString([(0, 80), (0, 0)]),
    ]
    return {
        "noded_lines": unary_union(lines),
        "wall_segments": [{"id": f"w{i}", "line": line} for i, line in enumerate(lines)],
        "door_closures": [],
        "typical_thickness_px": 10,
    }


def test_polygon_builder_uses_inner_wall_faces_for_saved_crop():
    from app.floors.polygon_builder import room_polygon_builder

    result = room_polygon_builder.build(_prepared(), crop_width=100, crop_height=80)
    assert len(result) == 1
    assert round(result[0]["area_px"], 4) == 6300
    assert result[0]["geometry_status"] == "ready"


def test_split_and_merge_use_real_polygon_geometry():
    from app.floors.polygon_builder import room_polygon_builder

    points = [{"x": 0, "y": 0}, {"x": 100, "y": 0}, {"x": 100, "y": 80}, {"x": 0, "y": 80}]
    parts = room_polygon_builder.split_polygon(points, axis="vertical", ratio=0.5)
    assert len(parts) == 2
    merged = room_polygon_builder.merge_polygons(parts[0], parts[1])
    assert round(room_polygon_builder.points_to_polygon(merged).area, 4) == 8000
