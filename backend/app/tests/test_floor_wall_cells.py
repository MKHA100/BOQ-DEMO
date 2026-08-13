from __future__ import annotations


def test_wall_cell_builder_returns_inside_faces_with_relations():
    from shapely.geometry import LineString
    from shapely.ops import unary_union
    from app.floors.wall_cell_service import wall_cell_service

    segments = []
    for index, points in enumerate([[(0, 0), (100, 0)], [(100, 0), (100, 80)], [(100, 80), (0, 80)], [(0, 80), (0, 0)]]):
        line = LineString(points)
        segments.append({"id": f"w{index}", "line": line, "footprint": line.buffer(2, cap_style=2), "thickness_px": 4})
    prepared = {
        "noded_lines": unary_union([item["line"] for item in segments]),
        "wall_footprints": unary_union([item["footprint"] for item in segments]),
        "wall_segments": segments,
        "door_closures": [],
        "typical_thickness_px": 4,
    }
    cells = wall_cell_service.build(prepared, crop_width=120, crop_height=100, mm_per_pixel=11)
    assert len(cells) == 1
    assert cells[0]["boundary_source"] == "wall_cell"
    assert len(cells[0]["wall_ids"]) == 4


def test_open_wall_cell_is_partitioned_by_distinct_printed_room_labels():
    from app.floors.wall_cell_service import wall_cell_service

    cell = {
        "points": [
            {"x": 0, "y": 0}, {"x": 100, "y": 0},
            {"x": 100, "y": 60}, {"x": 0, "y": 60},
        ],
        "area_px": 6000,
        "wall_ids": ["w1"],
        "opening_ids": [],
    }
    blocks = [
        {"text": "DINING AREA", "bbox": {"x0": 20, "y0": 25, "x1": 30, "y1": 35}},
        {"text": "SITTING AREA", "bbox": {"x0": 70, "y0": 25, "x1": 80, "y1": 35}},
    ]
    parts = wall_cell_service.split_open_cells([cell], blocks)
    assert [item["label_hint"] for item in parts] == ["Dining Area", "Sitting Area"]
    assert all(item["boundary_source"] == "label_partition" for item in parts)
    assert round(sum(float(item["area_px"]) for item in parts), 5) == 6000
