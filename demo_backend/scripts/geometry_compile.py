"""Build deterministic demo geometry from the captured run artifacts.

The output coordinate system is the source PDF/display space (1190 x 1684), not
the 1820 x 2573 raster-pixel space.  Keeping that distinction explicit avoids
the offset/scaling error that made earlier overlays appear misplaced.

This script deliberately includes only hosted openings.  The run contains
printed door/window marks that could not be matched uniquely to wall gaps; a
small misplaced box is worse for a demo than an explicitly omitted proposal.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
RUN = ROOT / "run-17685a72-7016-460b-85c9-3a13c2e6a195"
OUT = ROOT / "demo_backend/fixtures/geometry"

DISPLAY_WIDTH = 1190
DISPLAY_HEIGHT = 1684
RASTER_WIDTH = 1820
RASTER_HEIGHT = 2573
MM_PER_POINT = 33.86666666666666
WALL_HEIGHT_MM = 2700.0


# Human review notes in ui/annotations.json identify exactly these two gaps.
# Their axes and endpoints are bounded by the accepted wall segments on either
# side, so these are substantially safer than extending to the annotation box.
HUMAN_WALL_CORRECTIONS: dict[int, list[dict[str, Any]]] = {
    18: [
        {
            "id": "demo-p018-wall-human-001",
            "coords": [566.26, 485.16, 566.26, 551.88],
            "thickness_mm": 225,
            "type_family": "M01_or_M02",
            "annotation": "225mm wall is not identifying",
            "annotation_bbox": [543.8486, 489.1142, 584.8512, 553.8382],
        },
        {
            "id": "demo-p018-wall-human-002",
            "coords": [317.80, 476.10, 384.52, 476.10],
            "thickness_mm": 225,
            "type_family": "M01_or_M02",
            "annotation": "Add this wall",
            "annotation_bbox": [311.2571, 464.9901, 365.5357, 487.6058],
        },
    ]
}


# These are apartment/space polygons, not speculative bedroom subdivisions.
# They follow the six coloured unit boundaries visible on the source plans and
# add the shared circulation/core as useful non-BOQ review zones.
ROOMS: dict[int, list[dict[str, Any]]] = {
    18: [
        {"name": "TYPE A (UNIT 03)", "kind": "internal", "boq": True,
         "points": [(220, 370), (466, 370), (466, 686), (220, 686)]},
        {"name": "TYPE B (UNIT 02)", "kind": "internal", "boq": True,
         "points": [(466, 392), (789, 392), (789, 634), (466, 634)]},
        {"name": "TYPE C (UNIT 01)", "kind": "internal", "boq": True,
         "points": [(789, 370), (1020, 370), (1020, 686), (789, 686)]},
        {"name": "TYPE F (UNIT 06)", "kind": "internal", "boq": True,
         "points": [(220, 764), (466, 764), (466, 1085), (220, 1085)]},
        {"name": "TYPE E (UNIT 05)", "kind": "internal", "boq": True,
         "points": [(466, 821), (789, 821), (789, 1066), (466, 1066)]},
        {"name": "TYPE D (UNIT 04)", "kind": "internal", "boq": True,
         "points": [(789, 764), (1020, 764), (1020, 1085), (789, 1085)]},
        {"name": "SHARED CORRIDOR", "kind": "circulation", "boq": False,
         "points": [(466, 634), (789, 634), (789, 681), (823, 681),
                    (823, 821), (466, 821)]},
        {"name": "STAIR / LIFT CORE", "kind": "circulation", "boq": False,
         "points": [(466, 681), (823, 681), (823, 821), (466, 821)]},
    ],
    19: [
        {"name": "TYPE A", "kind": "internal", "boq": True,
         "points": [(220, 370), (466, 370), (466, 686), (220, 686)]},
        {"name": "TYPE B", "kind": "internal", "boq": True,
         "points": [(466, 392), (789, 392), (789, 634), (466, 634)]},
        {"name": "TYPE C", "kind": "internal", "boq": True,
         "points": [(789, 370), (1020, 370), (1020, 686), (789, 686)]},
        {"name": "TYPE F", "kind": "internal", "boq": True,
         "points": [(220, 764), (466, 764), (466, 1085), (220, 1085)]},
        {"name": "TYPE E", "kind": "internal", "boq": True,
         "points": [(466, 821), (789, 821), (789, 1066), (466, 1066)]},
        {"name": "TYPE D", "kind": "internal", "boq": True,
         "points": [(789, 764), (1020, 764), (1020, 1085), (789, 1085)]},
        {"name": "SHARED CORRIDOR", "kind": "circulation", "boq": False,
         "points": [(466, 634), (789, 634), (789, 681), (823, 681),
                    (823, 821), (466, 821)]},
        {"name": "STAIR / LIFT CORE", "kind": "circulation", "boq": False,
         "points": [(466, 681), (823, 681), (823, 821), (466, 821)]},
    ],
}


def point(x: float, y: float) -> dict[str, float]:
    return {"x": round(float(x), 3), "y": round(float(y), 3)}


def polygon_area(points: list[dict[str, float]]) -> float:
    twice_area = 0.0
    for current, following in zip(points, points[1:] + points[:1]):
        twice_area += current["x"] * following["y"] - following["x"] * current["y"]
    area_points = abs(twice_area) / 2.0
    return area_points * MM_PER_POINT * MM_PER_POINT / 1_000_000.0


def polygon_perimeter(points: list[dict[str, float]]) -> float:
    distance_points = 0.0
    for current, following in zip(points, points[1:] + points[:1]):
        distance_points += math.hypot(
            following["x"] - current["x"], following["y"] - current["y"]
        )
    return distance_points * MM_PER_POINT / 1000.0


def wall_polygon(coords: list[float], thickness_mm: float) -> list[dict[str, float]]:
    x1, y1, x2, y2 = map(float, coords)
    half = thickness_mm / MM_PER_POINT / 2.0
    if abs(y2 - y1) <= abs(x2 - x1):
        left, right = sorted((x1, x2))
        return [point(left, y1 - half), point(right, y1 - half),
                point(right, y1 + half), point(left, y1 + half)]
    top, bottom = sorted((y1, y2))
    return [point(x1 - half, top), point(x1 + half, top),
            point(x1 + half, bottom), point(x1 - half, bottom)]


def classification(coords: list[float]) -> str:
    x1, y1, x2, y2 = coords
    midpoint_x = (x1 + x2) / 2.0
    midpoint_y = (y1 + y2) / 2.0
    if midpoint_x < 275 or midpoint_x > 965 or midpoint_y < 415 or midpoint_y > 1035:
        return "external"
    return "internal"


def make_wall(raw: dict[str, Any], page: int, index: int) -> dict[str, Any]:
    coords = [float(value) for value in raw["coords"]]
    x1, y1, x2, y2 = coords
    thickness = int(raw["nominal_thickness_mm"])
    length_mm = math.hypot(x2 - x1, y2 - y1) * MM_PER_POINT
    wall_id = raw.get("wall_id") or raw["id"]
    source = "human_correction" if wall_id.startswith("demo-") else "run_wall_register"
    centerline = {"start": point(x1, y1), "end": point(x2, y2)}
    return {
        "id": wall_id,
        "project_id": "demo-project",
        "floor_id": f"demo-floor-p{page:03d}",
        "item_number": index,
        "display_number": f"W-{index:03d}",
        "friendly_number": f"Wall {index}",
        "source_element_id": None,
        "centerline": centerline,
        "generated_centerline": centerline,
        "polygon": wall_polygon(coords, thickness),
        "classification": classification(coords),
        "wall_type": f"{thickness} mm masonry wall",
        "type_family": raw.get("type_family"),
        "thickness_mm": thickness,
        "height_mm": WALL_HEIGHT_MM,
        "height_source": "demo_default",
        "height_override_mm": None,
        "length_mm": round(length_mm, 1),
        "gross_area_m2": round(length_mm * WALL_HEIGHT_MM / 1_000_000.0, 3),
        "deduction_area_m2": 0.0,
        "net_area_m2": round(length_mm * WALL_HEIGHT_MM / 1_000_000.0, 3),
        "side_1_finish": None,
        "side_2_finish": None,
        "boundary_role": None,
        "status": "confirmed",
        "source": source,
        "confidence": 1.0 if source == "human_correction" else 0.96,
        "manually_edited": source == "human_correction",
        "user_confirmed": True,
        "validation_warnings": [],
        "openings": [],
        "provenance": {
            "source_wall_id": raw.get("wall_id"),
            "review_state": raw.get("review_state", "ACCEPTED"),
            "annotation": raw.get("annotation"),
            "annotation_bbox": raw.get("annotation_bbox"),
        },
    }


def make_opening(raw: dict[str, Any], page: int, index: int) -> dict[str, Any]:
    gap = raw["host_gap"]
    thickness_mm = float(gap["nominal_thickness_mm"])
    thickness_points = thickness_mm / MM_PER_POINT
    if gap["axis"] == "h":
        x = float(gap["start_pt"])
        y = float(gap["cross_pt"]) - thickness_points / 2.0
        width = float(gap["end_pt"]) - float(gap["start_pt"])
        height = thickness_points
    else:
        x = float(gap["cross_pt"]) - thickness_points / 2.0
        y = float(gap["start_pt"])
        width = thickness_points
        height = float(gap["end_pt"]) - float(gap["start_pt"])
    geometry = {
        "x": round(x, 3), "y": round(y, 3),
        "width": round(width, 3), "height": round(height, 3),
    }
    return {
        "id": raw["instance_id"],
        "floor_id": f"demo-floor-p{page:03d}",
        "item_number": index,
        "display_number": f"O-{index:03d}",
        "friendly_number": f"{raw['kind'].title()} {raw['type']} {index}",
        "element_type": raw["kind"],
        "type_code": raw["type"],
        "wall_id": gap.get("adjacent_wall_ids", [None])[0],
        "geometry": geometry,
        "dimensions": {
            "width_mm": round(float(raw["width_m"]) * 1000),
            "height_mm": round(float(raw["height_m"]) * 1000),
            "sill_mm": round(float(raw.get("sill_m", 0)) * 1000),
            "lintel_mm": round(float(raw.get("lintel_m", 0)) * 1000),
        },
        "host": {
            "axis": gap["axis"],
            "center": [round(float(v), 3) for v in gap["centre"]],
            "gap_id": gap["gap_id"],
            "adjacent_wall_ids": gap.get("adjacent_wall_ids", []),
            "method": raw.get("host_method"),
        },
        "label_bbox": [round(float(v), 3) for v in raw["mark_bbox"]],
        "source": "printed_schedule_mark+hosted_wall_gap",
        "status": "confirmed",
        "confidence": 0.94,
    }


def make_room(raw: dict[str, Any], page: int, index: int) -> dict[str, Any]:
    points = [point(x, y) for x, y in raw["points"]]
    geometry = {"points": points}
    return {
        "id": f"demo-p{page:03d}-room-{index:02d}",
        "project_id": "demo-project",
        "floor_id": f"demo-floor-p{page:03d}",
        "friendly_number": f"R-{index:02d}",
        "name": raw["name"],
        "room_type": "Apartment" if raw["kind"] == "internal" else "Circulation",
        "geometry": geometry,
        "generated_geometry": geometry,
        "display_polygon": geometry,
        "area_m2": round(polygon_area(points), 3),
        "perimeter_m": round(polygon_perimeter(points), 3),
        "floor_type_code": "FT-01" if raw["boq"] else None,
        "floor_finish": "Ceramic tile" if raw["boq"] else None,
        "status": "confirmed",
        "geometry_status": "confirmed",
        "user_confirmed": True,
        "room_version": 1,
        "wall_ids": [],
        "opening_ids": [],
        "detection_source": "demo_plan_boundary",
        "confidence": 0.88,
        "model_verified": False,
        "comparison_status": "demo_curated",
        "excluded": False,
        "exclusion_reason": None,
        "space_kind": raw["kind"],
        "measurement_status": "check",
        "include_in_boq": raw["boq"],
        "parent_room_id": None,
        "is_finish_zone": False,
        "open_plan": False,
        "label_candidates": [raw["name"]],
        "shape_type": "orthogonal_polygon",
        "boundary_source": "visually_traced_unit_boundary",
        "precision_status": "demo_approximate",
        "user_edited": True,
        "geometry_version": 1,
        "edit_revision": 1,
        "processing_stage": "confirmed",
        "interpretation_status": "confirmed",
        "interpretation_warnings": ["Apartment-level zone; not a room-by-room takeoff."],
        "dimension_status": "partial",
        "dimension_source": "drawing",
        "point_count": len(points),
        "cutouts": [],
    }


def build() -> list[Path]:
    wall_register = json.loads((RUN / "wall-register.json").read_text())
    opening_hosts = json.loads((RUN / "opening-hosts.json").read_text())
    generated: list[Path] = []
    page_summaries: list[dict[str, Any]] = []

    for page in (18, 19):
        wall_page = next(register for register in wall_register["registers"] if register["page"] == page)
        raw_walls = list(wall_page["walls"])
        for correction in HUMAN_WALL_CORRECTIONS.get(page, []):
            raw_walls.append({
                "id": correction["id"],
                "coords": correction["coords"],
                "nominal_thickness_mm": correction["thickness_mm"],
                "type_family": correction["type_family"],
                "annotation": correction["annotation"],
                "annotation_bbox": correction["annotation_bbox"],
            })
        walls = [make_wall(raw, page, index) for index, raw in enumerate(raw_walls, 1)]

        hosted = [item for item in opening_hosts["assignments"] if item["page"] == page]
        openings = [make_opening(raw, page, index) for index, raw in enumerate(hosted, 1)]
        rooms = [make_room(raw, page, index) for index, raw in enumerate(ROOMS[page], 1)]
        omitted = [item for item in opening_hosts["omitted"] if item["page"] == page]

        payload = {
            "schema_version": "demo-geometry-v1",
            "page": page,
            "page_id": f"p{page:03d}",
            "viewport_id": wall_page["viewport_id"],
            "coordinate_space": {
                "name": "pdf_display_points",
                "width": DISPLAY_WIDTH,
                "height": DISPLAY_HEIGHT,
                "units": "display_point",
                "mm_per_point": MM_PER_POINT,
                "source_raster": {
                    "width": RASTER_WIDTH,
                    "height": RASTER_HEIGHT,
                    "scale_x": RASTER_WIDTH / DISPLAY_WIDTH,
                    "scale_y": RASTER_HEIGHT / DISPLAY_HEIGHT,
                },
            },
            "walls": walls,
            "openings": openings,
            "rooms": rooms,
            "qa": {
                "human_wall_corrections": len(HUMAN_WALL_CORRECTIONS.get(page, [])),
                "omitted_unresolved_openings": omitted,
                "room_scope": "apartment units and shared circulation; not bedroom-level segmentation",
            },
        }
        output_path = OUT / f"p{page:03d}.json"
        output_path.write_text(json.dumps(payload, indent=2) + "\n")
        generated.append(output_path)
        page_summaries.append({
            "page": page,
            "path": output_path.name,
            "walls": len(walls),
            "wall_thickness_counts": {
                str(value): sum(wall["thickness_mm"] == value for wall in walls)
                for value in (115, 225)
            },
            "openings": len(openings),
            "doors": sum(item["element_type"] == "door" for item in openings),
            "windows": sum(item["element_type"] == "window" for item in openings),
            "rooms": len(rooms),
        })

    manifest = {
        "schema_version": "demo-geometry-v1",
        "source_run": RUN.name,
        "coordinate_space": "pdf_display_points",
        "pages": page_summaries,
    }
    manifest_path = OUT / "index.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    generated.append(manifest_path)
    return generated


if __name__ == "__main__":
    for path in build():
        print(path.relative_to(ROOT))
