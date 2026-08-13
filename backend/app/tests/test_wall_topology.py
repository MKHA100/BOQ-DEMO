from __future__ import annotations

from app.walls.rules import WallTopologyRules
from app.walls.topology_service import wall_topology_service
from app.walls.validation_service import wall_validation_service


def line(start_x: float, start_y: float, end_x: float, end_y: float) -> dict:
    return {
        "start": {"x": start_x, "y": start_y},
        "end": {"x": end_x, "y": end_y},
    }


def test_topology_straightens_snaps_and_merges_detector_lines():
    result = wall_topology_service.clean(
        [
            {"id": "one", "centerline": line(0, 1, 50, 0)},
            {"id": "two", "centerline": line(54, 0, 100, 1)},
            {"id": "corner", "centerline": line(101, 2, 100, 50)},
        ],
        200,
        200,
    )

    assert result["summary"]["straightened"] == 3
    assert result["summary"]["merged"] == 1
    assert result["merged_wall_ids"] == {"two": "one"}
    assert len(result["walls"]) == 2
    horizontal = next(item for item in result["walls"] if item["id"] == "one")
    assert horizontal["centerline"]["start"]["y"] == horizontal["centerline"]["end"]["y"]


def test_topology_derives_centerline_and_thickness_from_detection_bbox():
    result = wall_topology_service.clean(
        [{"id": "detected", "geometry": {"x": 10, "y": 20, "width": 80, "height": 8}}],
        200,
        200,
        mm_per_pixel=20,
    )

    wall = result["walls"][0]
    assert wall["centerline"] == {
        "start": {"x": 10.0, "y": 24.0},
        "end": {"x": 90.0, "y": 24.0},
    }
    assert wall["detected_thickness_px"] == 8
    assert wall["thickness_mm"] == 160


def test_topology_preserves_manual_walls_and_opening_gaps():
    rules = WallTopologyRules(endpoint_snap_px=12, merge_gap_px=15)
    manual = line(0, 2, 40, 3)
    result = wall_topology_service.clean(
        [
            {"id": "manual", "source": "manual", "centerline": manual},
            {"id": "generated", "centerline": line(50, 2, 100, 2)},
        ],
        200,
        200,
        openings=[
            {"id": "door", "geometry": {"x": 40, "y": -5, "width": 10, "height": 15}}
        ],
        rules=rules,
    )

    assert len(result["walls"]) == 2
    preserved = next(item for item in result["walls"] if item["id"] == "manual")
    assert preserved["centerline"] == {
        "start": {"x": 0.0, "y": 2.0},
        "end": {"x": 40.0, "y": 3.0},
    }
    assert result["summary"]["manual_preserved"] == 1


def test_topology_preserves_user_confirmed_wall_on_rerun():
    original = line(0, 2, 100, 4)
    result = wall_topology_service.clean(
        [{"id": "confirmed", "user_confirmed": True, "centerline": original}],
        200,
        200,
    )

    assert result["walls"][0]["centerline"] == {
        "start": {"x": 0.0, "y": 2.0},
        "end": {"x": 100.0, "y": 4.0},
    }
    assert result["summary"]["manual_preserved"] == 1


def test_validation_reports_blocking_duplicates_and_near_misses():
    result = wall_validation_service.validate(
        [
            {"id": "one", "centerline": line(0, 0, 100, 0)},
            {"id": "duplicate", "centerline": line(1, 1, 99, 1)},
            {"id": "near", "centerline": line(103, 0, 103, 50)},
        ],
        drawing_width=200,
        drawing_height=200,
    )

    codes = {item["code"] for item in result["warnings"]}
    assert "duplicate_wall" in codes
    assert "near_miss_endpoint" in codes
    assert result["is_valid"] is False
    assert result["summary"]["error_count"] >= 2
    assert result["warnings_by_wall"]["one"]


def test_validation_treats_opening_gap_endpoints_as_expected():
    result = wall_validation_service.validate(
        [
            {"id": "left", "centerline": line(0, 0, 40, 0)},
            {"id": "right", "centerline": line(60, 0, 100, 0)},
        ],
        openings=[
            {"id": "door", "geometry": {"x": 40, "y": -5, "width": 20, "height": 10}}
        ],
        drawing_width=200,
        drawing_height=200,
    )

    gap_warnings = [
        item
        for item in result["warnings"]
        if item["code"] == "unconnected_endpoint" and 35 <= item["point"]["x"] <= 65
    ]
    assert gap_warnings == []


def test_topology_snaps_small_t_junction_miss_to_segment():
    result = wall_topology_service.clean(
        [
            {"id": "vertical", "centerline": line(50, 0, 50, 100)},
            {"id": "branch", "centerline": line(0, 40, 47.5, 40)},
        ],
        200,
        200,
    )

    branch = next(item for item in result["walls"] if item["id"] == "branch")
    assert branch["centerline"]["end"] == {"x": 50.0, "y": 40.0}
    assert result["summary"]["snapped_to_segments"] + result["summary"]["extended_endpoints"] >= 1


def test_topology_cleanup_is_idempotent_for_orthogonal_network():
    first = wall_topology_service.clean(
        [
            {"id": "top", "centerline": line(0, 1, 100, 0)},
            {"id": "right", "centerline": line(99, 0, 100, 80)},
            {"id": "bottom", "centerline": line(100, 79, 0, 80)},
            {"id": "left", "centerline": line(1, 80, 0, 0)},
        ],
        200,
        200,
    )
    second = wall_topology_service.clean(first["walls"], 200, 200)

    assert {
        item["id"]: item["centerline"] for item in second["walls"]
    } == {
        item["id"]: item["centerline"] for item in first["walls"]
    }
