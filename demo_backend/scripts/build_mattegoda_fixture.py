"""Build the deterministic Mattegoda demo fixture from the archived harness run.

This is intentionally an offline build step. Runtime demo endpoints only read the
generated fixture and never call AI providers, workers, or the application DB.
"""

from __future__ import annotations

import json
import math
import re
import shutil
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
RUN = ROOT / "run-17685a72-7016-460b-85c9-3a13c2e6a195"
OUT = ROOT / "demo_backend/fixtures/mattegoda"
ASSET_URL = "/api/v1/demo/assets"
PROJECT_ID = "demo-mattegoda"
DOCUMENT_ID = "demo-mattegoda-source"
PAGE_WIDTH = 1820
PAGE_HEIGHT = 2573
PDF_TO_PX = PAGE_WIDTH / 1191.0
MM_PER_PIXEL = 33.8666666667 / PDF_TO_PX
NOW = "2026-08-13T04:00:00Z"


FLOOR_DEFS = [
    ("ground", "Ground Floor", 0, 17, "p017"),
    ("first", "First Floor", 1, 18, "p018"),
    ("second", "Second Floor", 2, 19, "p019"),
    ("third", "Third Floor", 3, 19, "p019"),
    ("fourth", "Fourth Floor", 4, 19, "p019"),
    ("fifth", "Fifth Floor", 5, 19, "p019"),
    ("sixth", "Sixth Floor", 6, 19, "p019"),
    ("roof-terrace", "Roof Terrace", 7, 20, "p020"),
    ("upper-roof", "Upper Roof", 8, 21, "p021"),
]

# Confirmed floor-to-floor/upper-storey dimensions from vertical-datum.json.
# Values are derived from L00→L09, including the accepted +80'-6" roof datum.
FLOOR_HEIGHT_MM = {
    "ground": 3962.4,       # 13'-0"
    "first": 3352.8,        # 11'-0"
    "second": 3352.8,
    "third": 3352.8,
    "fourth": 3352.8,
    "fifth": 3352.8,
    "sixth": 3657.6,        # 12'-0"
    "roof-terrace": 4267.2, # 14'-0"
    "upper-roof": 3048.0,   # 10'-0"
}
DEFAULT_WALL_HEIGHT_MM = 3352.8


def load(name: str) -> Any:
    return json.loads((RUN / name).read_text())


def dump(name: str, value: Any) -> None:
    (OUT / name).write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")


def asset(page_key: str) -> str:
    return f"{ASSET_URL}/{page_key}.png"


def floor_id(key: str) -> str:
    return f"demo-floor-{key}"


def px(value: float) -> float:
    return round(value * PDF_TO_PX, 3)


def parse_feet_inches(value: str | None) -> float | None:
    if not value:
        return None
    match = re.fullmatch(
        r"\s*(?:(\d+(?:\.\d+)?)\s*')?\s*(?:-\s*)?(?:(\d+(?:\.\d+)?)\s*\")?\s*",
        value,
    )
    if not match:
        return None
    feet = float(match.group(1) or 0)
    inches = float(match.group(2) or 0)
    return round((feet * 12 + inches) * 25.4, 1)


def opening_kind(type_code: str) -> str:
    return "door" if type_code.upper().startswith(("D", "GD", "FD")) else "window"


def plan_state() -> dict[str, Any]:
    pages = []
    for _, _, _, page, page_key in FLOOR_DEFS:
        if any(item["page_number"] == page for item in pages):
            continue
        pages.append({
            "id": f"demo-page-{page:03d}", "document_id": DOCUMENT_ID,
            "page_number": page, "page_label": str(page), "width": PAGE_WIDTH,
            "height": PAGE_HEIGHT, "rotation": 0, "thumbnail_status": "ready",
            "preview_status": "ready", "thumbnail_url": asset(page_key),
            "preview_url": asset(page_key),
        })
    floors = []
    for key, name, level, page, page_key in FLOOR_DEFS:
        fid = floor_id(key)
        height_mm = FLOOR_HEIGHT_MM[key]
        uses_default = height_mm == DEFAULT_WALL_HEIGHT_MM
        crop = {
            "id": f"demo-crop-{key}", "project_id": PROJECT_ID, "floor_id": fid,
            "document_id": DOCUMENT_ID, "document_page_id": f"demo-page-{page:03d}",
            "source_page_number": page, "original_page_width": PAGE_WIDTH,
            "original_page_height": PAGE_HEIGHT, "rotation": 0, "render_dpi": 216,
            "coordinates": {
                "original_rect": {"x": 0, "y": 0, "width": PAGE_WIDTH, "height": PAGE_HEIGHT},
                "normalized_display_rect": {"x": 0, "y": 0, "width": 1, "height": 1},
                "coordinate_space": "rendered_pixels",
            },
            "crop_version": 1, "status": "confirmed", "crop_asset_url": asset(page_key),
            "preview_asset_url": asset(page_key), "created_at": NOW, "updated_at": NOW,
        }
        floors.append({
            "id": fid, "project_id": PROJECT_ID, "name": name, "level_index": level,
            "status": "confirmed", "uses_default_height": uses_default,
            "wall_height_mm": None if uses_default else height_mm,
            "effective_wall_height_mm": height_mm, "is_custom_name": False,
            "source_document_id": DOCUMENT_ID, "source_page_number": page,
            "source_rotation": 0, "crop_version": 1, "crop": crop, "last_error": None,
            "active_jobs": [], "created_at": NOW, "updated_at": NOW,
        })
    return {
        "project_id": PROJECT_ID, "project_name": "Mattegoda Apartment Complex",
        "default_wall_height_mm": DEFAULT_WALL_HEIGHT_MM, "measurement_unit": "mm", "floors": floors,
        "documents": [{
            "id": DOCUMENT_ID, "project_id": PROJECT_ID, "document_type": "source",
            "file_name": "Mattegoda Apartment Drawings.pdf", "mime_type": "application/pdf",
            "page_count": 22, "status": "ready", "is_primary": True, "pages": pages,
        }],
        "can_continue": True, "updated_at": NOW,
    }


def specifications_state() -> dict[str, Any]:
    schedules = load("schedule-registry.json")
    specs = load("specification-registry.json")
    floor_ids = [floor_id(item[0]) for item in FLOOR_DEFS]
    opening_entries = []
    for index, row in enumerate(schedules["opening_types"], 1):
        kind = opening_kind(row["type"])
        width, height = (parse_feet_inches(part.strip()) for part in row["opening_size"].split("x", 1))
        opening_entries.append({
            "id": f"schedule-{row['type'].replace(chr(39), 'prime')}",
            "category": "door_schedule" if kind == "door" else "window_schedule",
            "entity_key": row["type"],
            "data": {**row, "element_type": kind, "width_mm": width, "height_mm": height},
            "confidence": 0.99, "review_state": "confirmed", "is_accepted": True,
        })
    wall_entries = [{
        "id": f"wall-spec-{row['type']}", "category": "wall_schedule", "entity_key": row["type"],
        "data": row, "confidence": 0.98 if row.get("verdict") == "CONFIRMED" else 0.78,
        "review_state": "confirmed" if row.get("verdict") == "CONFIRMED" else "needs_review",
        "is_accepted": row.get("verdict") == "CONFIRMED",
    } for row in specs["wall_types"]]
    floor_entries = [{
        "id": f"floor-spec-{index:02d}", "category": "floor_schedule", "entity_key": f"F{index:02d}",
        "data": row, "confidence": 0.97, "review_state": "confirmed", "is_accepted": True,
    } for index, row in enumerate(specs["finish_schedule"], 1)]
    general = [{
        "id": f"general-spec-{index:02d}", "category": "specification", "entity_key": key,
        "data": value if isinstance(value, dict) else {"value": value}, "confidence": 0.96,
        "review_state": "confirmed", "is_accepted": True,
    } for index, (key, value) in enumerate(specs.items(), 1) if key not in {"wall_types", "finish_schedule"}]

    page_source = {
        "door_schedule": (16, "Door schedule", [x for x in opening_entries if x["category"] == "door_schedule"]),
        "window_schedule": (16, "Window schedule", [x for x in opening_entries if x["category"] == "window_schedule"]),
        "wall_schedule": (7, "Wall type specifications", wall_entries),
        "floor_schedule": (3, "Internal finishes schedule", floor_entries),
        "specification": (1, "Preliminary specifications", general),
    }
    labels = {
        "door_schedule": ("Door Schedule", "Door types, structural openings and floor quantities"),
        "window_schedule": ("Window Schedule", "Window types, sizes, sills and floor quantities"),
        "wall_schedule": ("Wall Schedule", "Masonry wall types, thicknesses and performance notes"),
        "floor_schedule": ("Floor Schedule", "Room finish systems and locations"),
        "specification": ("Specifications", "General workmanship and measurement requirements"),
        "other": ("Other", "Additional supporting information"),
    }
    categories = []
    for category in ["door_schedule", "window_schedule", "wall_schedule", "floor_schedule", "specification", "other"]:
        sources = []
        entries = []
        if category in page_source:
            page, file_name, entries = page_source[category]
            sources = [{
                "id": f"source-{category}", "category": category, "source_type": "crop",
                "document_id": DOCUMENT_ID, "file_name": file_name, "mime_type": "image/png",
                "file_size": 1, "page_number": page,
                "crop": {"x": 0, "y": 0, "width": PAGE_WIDTH, "height": PAGE_HEIGHT},
                "scope_mode": "all", "floor_ids": floor_ids, "status": "ready",
                "preview_url": asset(f"p{page:03d}"), "active_job": None,
                "entry_count": len(entries), "entries": entries, "created_at": NOW, "updated_at": NOW,
            }]
        categories.append({
            "key": category, "label": labels[category][0], "description": labels[category][1],
            "status": "ready" if sources else "skipped", "sources": sources, "entry_count": len(entries),
        })
    return {
        "project_id": PROJECT_ID, "project_name": "Mattegoda Apartment Complex",
        "categories": categories,
        "floors": [{"id": floor_id(k), "name": n, "level_index": level} for k, n, level, _, _ in FLOOR_DEFS],
        "documents": [], "can_continue": True, "updated_at": NOW,
    }


def scale_state() -> dict[str, Any]:
    floors = []
    for key, name, level, page, page_key in FLOOR_DEFS:
        fid = floor_id(key)
        height_mm = FLOOR_HEIGHT_MM[key]
        height_m = height_mm / 1000
        a = {"x": 440.0, "y": 236.0}
        b = {"x": 782.0, "y": 236.0}
        pixel_distance = math.dist(a.values(), b.values())
        real_distance = round(pixel_distance * MM_PER_PIXEL, 2)
        floors.append({
            "id": fid, "project_id": PROJECT_ID, "name": name, "level_index": level,
            "crop_version": 1, "scale_version": 1, "source_document_id": DOCUMENT_ID,
            "source_page_number": page, "original_page_width": PAGE_WIDTH,
            "original_page_height": PAGE_HEIGHT, "rotation": 0, "drawing_url": asset(page_key),
            "status": "calibrated", "calibration": {
                "id": f"demo-calibration-{key}", "point_a": a, "point_b": b,
                "pixel_distance": round(pixel_distance, 3), "real_distance_mm": real_distance,
                "mm_per_pixel": round(MM_PER_PIXEL, 6), "verification_points": None,
                "verification_expected_mm": None, "verification_measured_mm": None,
                "verification_difference_percent": None, "input_unit": "mm",
                "crop_version": 1, "scale_version": 1, "status": "calibrated",
            }, "dimension_suggestions": [{
                "id": f"dimension-{key}", "label_text": "22'-0\"", "value_mm": 6705.6,
                "point_a": a, "point_b": b, "confidence": 0.99,
                "suggested_mm_per_pixel": round(MM_PER_PIXEL, 6),
            }],
        })
    return {"project_id": PROJECT_ID, "project_name": "Mattegoda Apartment Complex", "floors": floors, "can_continue": True}


def opening_geometry(item: dict[str, Any]) -> dict[str, float]:
    # The archived opening register is the single source of truth for demo
    # placement. Its bbox values are PDF display-space points (top-left origin).
    x1, y1, x2, y2 = item["mark_bbox"]
    return {"x": px(x1), "y": px(y1),
            "width": px(x2 - x1), "height": px(y2 - y1)}


def make_element(item: dict[str, Any], key: str, item_number: int, type_ordinal: int) -> dict[str, Any]:
    fid = floor_id(key)
    type_code = item["type"]
    kind = item["kind"]
    width_mm = round(item["width_m"] * 1000, 1)
    height_mm = round(item["height_m"] * 1000, 1)
    eid = f"demo-element-{key}-{item['instance_id']}"
    properties = []
    for prop, value, unit in [("type_code", type_code, None), ("width_mm", width_mm, "mm"), ("height_mm", height_mm, "mm"),
                              ("sill_height", round(item["sill_m"] * 1000, 1), "mm"),
                              ("description", item["description"], None)]:
        properties.append({
            "id": f"{eid}-{prop}", "property_name": prop, "value": value, "unit": unit,
            "source": "schedule", "is_confirmed": True,
        })
    display = f"{type_code}-{type_ordinal:02d}"
    resolved = {"type_code": type_code, "width_mm": width_mm, "height_mm": height_mm, "sill_height": round(item["sill_m"] * 1000, 1),
                "description": item["description"]}
    return {
        "id": eid, "project_id": PROJECT_ID, "floor_id": fid, "item_number": item_number,
        "display_number": display, "friendly_number": display, "element_type": kind,
        "type_code": type_code, "geometry": opening_geometry(item), "source": "model",
        "confidence": 0.96,
        "status": "confirmed", "excluded": False, "user_confirmed": True,
        "tag_text": type_code, "assigned_schedule_entry_id": f"schedule-{type_code.replace(chr(39), 'prime')}",
        "geometry_source": "opening_instance_register",
        "mark_bbox_pdf_points": item.get("mark_bbox"),
        "element_version": 1, "properties": properties, "resolved_data": resolved,
        "resolved_sources": {name: "schedule" for name in resolved},
        "confirmed_fields": {name: True for name in resolved}, "missing_fields": [],
        "detail_missing_fields": [], "schedule_match": {
            "id": f"schedule-{type_code.replace(chr(39), 'prime')}", "category": kind,
            "entity_key": type_code, "source_kind": "printed_schedule", "review_state": "confirmed",
        }, "drawing_detail": None,
    }


def elements_and_openings() -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, list[dict[str, Any]]]]:
    assignments = {item["instance_id"]: item for item in load("opening-hosts.json")["assignments"]}
    candidates = load("opening-instance-register.json")["candidates"]
    schedule = {item["type"]: item for item in load("schedule-registry.json")["opening_types"]}
    source_by_page = defaultdict(list)
    for candidate in candidates:
        type_code = candidate["normalized_type"]
        schedule_row = schedule.get(type_code, {})
        size = schedule_row.get("opening_size") or "3'-0\" x 7'-0\""
        width_mm, height_mm = (parse_feet_inches(part.strip()) or 0.0 for part in size.split("x", 1))
        sill_mm = parse_feet_inches(schedule_row.get("sill_height")) or 0.0
        source = {
            "instance_id": candidate["instance_id"], "type": type_code,
            "page": candidate["page"], "viewport_id": candidate["viewport_id"],
            "kind": opening_kind(type_code),
            "description": schedule_row.get("description") or f"PRINTED {type_code} OPENING",
            "width_m": width_mm / 1000.0, "height_m": height_mm / 1000.0,
            "sill_m": sill_mm / 1000.0, "lintel_m": (sill_mm + height_mm) / 1000.0,
            "mark_bbox": candidate["bbox"], "source_kind": candidate.get("source_kind", "PRINTED"),
            "verdict": candidate.get("verdict"), "review_state": candidate.get("review_state"),
        }
        assignment = assignments.get(candidate["instance_id"])
        if assignment:
            source.update(assignment)
            source["mark_bbox"] = candidate["bbox"]
        source_by_page[candidate["page"]].append(source)
    elements = []
    opening_elements = []
    by_floor = defaultdict(list)
    for key, _, _, page, _ in FLOOR_DEFS:
        source_page = 18 if page == 18 else 19 if page == 19 else page
        ordinals = defaultdict(int)
        for number, item in enumerate(source_by_page.get(source_page, []), 1):
            ordinals[item["type"]] += 1
            element = make_element(item, key, number, ordinals[item["type"]])
            elements.append(element)
            by_floor[key].append(element)
            opening_elements.append({
                "id": element["id"], "floor_id": element["floor_id"], "item_number": number,
                "display_number": element["display_number"], "friendly_number": element["friendly_number"],
                "element_type": element["element_type"], "type_code": element["type_code"],
                "wall_id": None, "geometry": element["geometry"], "dimensions": element["resolved_data"],
            })
    return elements, opening_elements, by_floor


def wall_states(opening_elements: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    source = {item["page"]: item for item in load("wall-register.json")["registers"]}
    corrected_geometry = ROOT / "demo_backend/fixtures/geometry/p018.json"
    human_corrections = []
    if corrected_geometry.exists():
        human_corrections = [
            item for item in json.loads(corrected_geometry.read_text())["walls"]
            if item.get("provenance", {}).get("annotation")
        ]
    walls = []
    wall_floors = []
    openings_by_floor = defaultdict(list)
    for item in opening_elements:
        openings_by_floor[item["floor_id"]].append(item)
    for key, name, level, page, page_key in FLOOR_DEFS:
        fid = floor_id(key)
        height_mm = FLOOR_HEIGHT_MM[key]
        height_m = height_mm / 1000
        source_page = 18 if page == 18 else 19 if page == 19 else None
        floor_walls = []
        if source_page:
            ordered = sorted(source[source_page]["walls"], key=lambda row: row["length_m"], reverse=True)
            for number, row in enumerate(ordered, 1):
                x1, y1, x2, y2 = row["coords"]
                thickness = row["nominal_thickness_mm"]
                length = row["length_m"] * 1000
                wid = f"demo-wall-{key}-{row['wall_id']}"
                centerline = {"start": {"x": px(x1), "y": px(y1)}, "end": {"x": px(x2), "y": px(y2)}}
                wall = {
                    "id": wid, "project_id": PROJECT_ID, "floor_id": fid, "item_number": number,
                    "display_number": f"WL{number:03d}", "friendly_number": f"Wall {number:03d}",
                    "source_element_id": None, "centerline": centerline, "generated_centerline": centerline,
                    "classification": "external" if thickness >= 200 else "internal",
                    "wall_type": "M01" if thickness >= 200 else "M03", "thickness_mm": thickness,
                    "height_mm": height_mm, "height_source": "vertical_datum", "height_override_mm": None,
                    "length_mm": round(length, 1), "gross_area_m2": round(length / 1000 * height_m, 3),
                    "deduction_area_m2": 0, "net_area_m2": round(length / 1000 * height_m, 3),
                    "side_1_finish": "W01 plaster and acrylic emulsion",
                    "side_2_finish": "W01 plaster and acrylic emulsion",
                    "boundary_role": "envelope" if thickness >= 200 else "partition",
                    "status": "confirmed", "source": "automatic", "confidence": 0.94,
                    "manually_edited": False, "user_confirmed": True, "validation_warnings": [], "openings": [],
                }
                floor_walls.append(wall)
                walls.append(wall)
            # Two omissions were explicitly marked during human review. They are
            # appended after the detector output, preserving evidence and IDs.
            if source_page == 18:
                for correction in human_corrections:
                    number = len(floor_walls) + 1
                    raw = correction["centerline"]
                    centerline = {
                        "start": {"x": px(raw["start"]["x"]), "y": px(raw["start"]["y"])},
                        "end": {"x": px(raw["end"]["x"]), "y": px(raw["end"]["y"])},
                    }
                    length_mm = math.dist(
                        (raw["start"]["x"], raw["start"]["y"]),
                        (raw["end"]["x"], raw["end"]["y"]),
                    ) * 33.8666666667
                    wall = {
                        "id": f"demo-wall-{key}-{correction['id']}", "project_id": PROJECT_ID,
                        "floor_id": fid, "item_number": number, "display_number": f"WL{number:03d}",
                        "friendly_number": f"Wall {number:03d}", "source_element_id": None,
                        "centerline": centerline, "generated_centerline": centerline,
                        "classification": "external", "wall_type": "M01", "thickness_mm": 225,
                        "height_mm": height_mm, "height_source": "vertical_datum", "height_override_mm": None,
                        "length_mm": round(length_mm, 1), "gross_area_m2": round(length_mm / 1000 * height_m, 3),
                        "deduction_area_m2": 0, "net_area_m2": round(length_mm / 1000 * height_m, 3),
                        "side_1_finish": "W01 plaster and acrylic emulsion",
                        "side_2_finish": "W01 plaster and acrylic emulsion", "boundary_role": "partition",
                        "status": "confirmed", "source": "manual_review_correction", "confidence": 1.0,
                        "manually_edited": True, "user_confirmed": True,
                        "validation_warnings": [], "openings": [],
                        "provenance": correction["provenance"],
                    }
                    floor_walls.append(wall); walls.append(wall)
        wall_floors.append({
            "id": fid, "name": name, "level_index": level, "crop_version": 1,
            "scale_version": 1, "element_version": 1, "wall_version": 1,
            "mm_per_pixel": round(MM_PER_PIXEL, 6), "drawing_url": asset(page_key),
            "drawing_width": PAGE_WIDTH, "drawing_height": PAGE_HEIGHT, "effective_height_mm": height_mm,
            "wall_status": "confirmed" if floor_walls else "ready", "walls_confirmed": bool(floor_walls),
            "validation_warning_count": 0, "active_jobs": [],
        })
    return walls, wall_floors


UNIT_POLYGONS = [
    ("Apartment Type A / Unit 01", [(335, 566), (699, 566), (699, 1025), (335, 1025)]),
    ("Apartment Type B / Unit 02", [(701, 592), (1188, 592), (1188, 959), (701, 959)]),
    ("Apartment Type C / Unit 03", [(1192, 567), (1510, 567), (1510, 1026), (1192, 1026)]),
    ("Apartment Type D / Unit 04", [(1190, 1147), (1511, 1147), (1511, 1641), (1190, 1641)]),
    ("Apartment Type E / Unit 05", [(703, 1225), (1187, 1225), (1187, 1605), (703, 1605)]),
    ("Apartment Type F / Unit 06", [(335, 1144), (700, 1144), (700, 1642), (335, 1642)]),
]


def polygon_metrics(points: list[dict[str, float]]) -> tuple[float, float]:
    area_px = abs(sum(points[i]["x"] * points[(i + 1) % len(points)]["y"] - points[(i + 1) % len(points)]["x"] * points[i]["y"] for i in range(len(points)))) / 2
    perimeter_px = sum(math.dist((points[i]["x"], points[i]["y"]), (points[(i + 1) % len(points)]["x"], points[(i + 1) % len(points)]["y"])) for i in range(len(points)))
    return round(area_px * MM_PER_PIXEL**2 / 1_000_000, 2), round(perimeter_px * MM_PER_PIXEL / 1000, 2)


def make_room(key: str, number: int, name: str, tuples: list[tuple[int, int]], finish: str = "F01 porcelain tile") -> dict[str, Any]:
    fid = floor_id(key)
    points = [{"x": float(x), "y": float(y)} for x, y in tuples]
    area, perimeter = polygon_metrics(points)
    geometry = {"points": points}
    rid = f"demo-room-{key}-{number:03d}"
    return {
        "id": rid, "project_id": PROJECT_ID, "floor_id": fid, "friendly_number": f"R{number:03d}",
        "name": name, "room_type": "apartment" if "Apartment" in name else "common_area",
        "geometry": geometry, "generated_geometry": geometry, "area_m2": area, "perimeter_m": perimeter,
        "floor_type_code": finish.split()[0], "floor_finish": finish, "status": "confirmed",
        "geometry_status": "confirmed", "user_confirmed": True, "room_version": 1,
        "wall_ids": [], "opening_ids": [], "detection_source": "hybrid", "confidence": 0.96,
        "model_verified": True, "comparison_status": "matched", "excluded": False,
        "exclusion_reason": None, "space_kind": "internal", "measurement_status": "correct",
        "measured_width_m": None, "measured_length_m": None, "printed_width_mm": None,
        "printed_length_mm": None, "dimension_difference_percent": None, "include_in_boq": True,
        "parent_room_id": None, "is_finish_zone": True, "open_plan": True,
        "label_candidates": [name], "raw_geometry": geometry, "wall_corrected_geometry": geometry,
        "regularized_geometry": geometry, "confirmed_geometry": geometry, "shape_type": "rectangle",
        "boundary_source": "curated_demo", "precision_status": "confirmed", "user_edited": False,
        "geometry_version": 1, "edit_revision": 0, "validation_details": {"status": "valid", "issues": []},
        "precision_updated_at": NOW, "model_polygon": geometry, "wall_corrected_polygon": geometry,
        "regularized_polygon": geometry, "confirmed_polygon": geometry, "display_polygon": geometry,
        "processing_stage": "confirmed", "interpretation_status": "confirmed",
        "interpretation_warnings": [], "interpretation_run_id": "demo-curated-v1",
        "dimension_status": "exact", "dimension_source": "drawing", "point_count": len(points), "cutouts": [],
    }


def floor_rooms_state() -> dict[str, Any]:
    zones = {row["scope"]: row["area_m2"] for row in load("floor-zone-register.json")["zones"]}
    rooms = []
    by_floor = defaultdict(list)
    for key, _, _, page, _ in FLOOR_DEFS:
        if page in {18, 19}:
            for number, (name, polygon) in enumerate(UNIT_POLYGONS, 1):
                room = make_room(key, number, name, polygon)
                rooms.append(room); by_floor[key].append(room)
            shared = [
                ("Shared Corridor", [(713, 969), (1206, 969), (1206, 1041), (1258, 1041), (1258, 1254), (713, 1254)]),
                ("Stair and Lift Core", [(713, 1041), (1258, 1041), (1258, 1254), (713, 1254)]),
            ]
            for number, (name, polygon) in enumerate(shared, 7):
                room = make_room(key, number, name, polygon, "F05 heavy-duty porcelain tile")
                rooms.append(room); by_floor[key].append(room)
        elif page == 17:
            ground = [
                ("Parking and Driveway", [(195, 560), (1510, 560), (1510, 1640), (195, 1640)], "F08 heavy-duty concrete"),
                ("Entrance Lobby", [(914, 1026), (1050, 1026), (1050, 1190), (914, 1190)], "F05 porcelain tile"),
                ("Garbage Room", [(701, 1027), (910, 1027), (910, 1155), (701, 1155)], "F09 epoxy coating"),
                ("Panel Room", [(1480, 1027), (1690, 1027), (1690, 1158), (1480, 1158)], "F09 epoxy coating"),
            ]
            for number, (name, polygon, finish) in enumerate(ground, 1):
                room = make_room(key, number, name, polygon, finish)
                rooms.append(room); by_floor[key].append(room)
        elif page == 20:
            roof = [
                ("Roof Terrace", [(195, 560), (1510, 560), (1510, 1640), (195, 1640)], "F10 exterior anti-slip tile"),
                ("Gymnasium", [(700, 780), (1120, 780), (1120, 1170), (700, 1170)], "F07 sports flooring"),
                ("Flower Troughs", [(330, 560), (1510, 560), (1510, 665), (330, 665)], "F12 drainage layer"),
            ]
            for number, (name, polygon, finish) in enumerate(roof, 1):
                room = make_room(key, number, name, polygon, finish)
                rooms.append(room); by_floor[key].append(room)
    summaries = []
    for key, name, level, _, page_key in FLOOR_DEFS:
        current = by_floor[key]
        summaries.append({
            "id": floor_id(key), "name": name, "level_index": level, "crop_version": 1,
            "scale_version": 1, "element_version": 1, "wall_version": 1, "room_version": 1,
            "mm_per_pixel": round(MM_PER_PIXEL, 6), "scale_verified": True, "room_count": len(current),
            "finish_zone_count": len(current), "dimension_suggestions": [], "needs_review_count": 0,
            "confirmed_count": len(current), "area_total_m2": round(sum(r["area_m2"] for r in current), 2),
            "drawing_url": asset(page_key), "drawing_width": PAGE_WIDTH, "drawing_height": PAGE_HEIGHT,
            "analysis_status": "ready", "interpretation_status": "ready", "active_jobs": [],
        })
    return {"project_id": PROJECT_ID, "floors": summaries, "selected_floor_id": floor_id("first"), "rooms": rooms, "suggestions": []}


def model_state(elements: list[dict[str, Any]]) -> dict[str, Any]:
    by_floor = defaultdict(list)
    for item in elements:
        by_floor[item["floor_id"]].append(item)
    floors = []
    for key, name, level, _, page_key in FLOOR_DEFS:
        current = by_floor[floor_id(key)]
        floors.append({
            "id": floor_id(key), "name": name, "level_index": level, "crop_version": 1,
            "scale_version": 1, "element_version": 1, "drawing_url": asset(page_key),
            "drawing_width": PAGE_WIDTH, "drawing_height": PAGE_HEIGHT, "element_count": len(current),
            "needs_review_count": 0, "confirmed_count": len(current), "active_jobs": [],
            "detection_status": "ready", "results_available": True,
        })
    schedule_entries = []
    for category in specifications_state()["categories"]:
        for source in category["sources"]:
            for entry in source["entries"]:
                if entry["category"] in {"door_schedule", "window_schedule"}:
                    schedule_entries.append({
                        "id": entry["id"], "category": entry["data"]["element_type"],
                        "entity_key": entry["entity_key"], "data": entry["data"], "review_state": entry["review_state"],
                    })
    return {"project_id": PROJECT_ID, "floors": floors, "selected_floor_id": floor_id("first"),
            "elements": elements, "schedule_entries": schedule_entries}


def review_state(elements: list[dict[str, Any]], walls: list[dict[str, Any]], rooms: list[dict[str, Any]]) -> dict[str, Any]:
    items = []
    source = elements[:60] + walls[:40] + rooms[:20]
    type_counts = defaultdict(int)
    for number, entity in enumerate(source, 1):
        entity_type = entity.get("element_type") or ("wall" if "centerline" in entity else "floor")
        type_counts[entity_type] += 1
        display = entity.get("display_number") or entity.get("friendly_number")
        items.append({
            "id": f"demo-review-{number:04d}", "project_id": PROJECT_ID, "floor_id": entity["floor_id"],
            "entity_type": entity_type, "entity_id": entity["id"], "display_number": display,
            "title": f"{display or entity_type.title()} measurements confirmed",
            "data": {"type_code": entity.get("type_code"), "area_m2": entity.get("area_m2"),
                     "length_mm": entity.get("length_mm"), "source": "curated demo fixture"},
            "status": "confirmed", "critical": False, "is_stale": False,
            "source_version": 1, "review_version": 1,
        })
    counts_by_floor = defaultdict(lambda: {"total": 0, "confirmed": 0, "ready": 0, "needs_review": 0})
    for item in items:
        row = counts_by_floor[item["floor_id"]]
        row["total"] += 1; row[item["status"]] += 1
    floors = [{"id": floor_id(key), "name": name, "level_index": level, **counts_by_floor[floor_id(key)]}
              for key, name, level, _, _ in FLOOR_DEFS]
    return {"project_id": PROJECT_ID, "floors": floors,
            "counts": {"all": len(items), "total": len(items),
                       "door": type_counts["door"], "window": type_counts["window"],
                       "wall": type_counts["wall"], "floor": type_counts["floor"],
                       "confirmed": len(items), "ready": 0, "needs_review": 0},
            "items": items, "stale": False, "active_jobs": []}


def boq_state() -> dict[str, Any]:
    source_rows = load("ui/boq.json")["rows"]
    rows = []
    section_names = {"door_set": "Doors", "window": "Windows", "wall": "Masonry walls",
                     "floor": "Floor finishes", "slab": "Concrete slabs"}
    for index, row in enumerate(source_rows, 1):
        element = row.get("element", "measurement")
        section = section_names.get(element, "Measured Works")
        quantity = float(row.get("qty") or 0)
        unit = row.get("unit") or "item"
        rate = None
        rows.append({
            "id": f"demo-boq-{index:03d}", "floor_id": None, "entity_type": element,
            "section": section, "item_code": row.get("nrm_ref"), "boq_item_number": f"{index:03d}",
            "bill_no": "1", "bill_name": "Measured Building Works", "subcategory_code": None,
            "subcategory_name": section, "description": row.get("description") or row["id"],
            "quantity": quantity, "unit": unit, "rate": rate, "amount": None,
            "status": "ready" if row.get("status") == "CONFIRMED" else "needs_review",
            "source_ids": [row["id"]], "source_items": [{
                "id": row["id"], "display_number": row["id"], "element_type": element,
                "quantity": quantity,
            }], "floor_ids": [], "floor_names": [],
            "missing_fields": [] if row.get("billable") else ["rate"], "manual": False,
            "protected_description": False, "protected_rate": False, "excluded": False, "sort_order": index,
        })
    template = {
        "id": "demo-template-nrm2", "name": "NRM2 Quantity Takeoff", "description": "Curated NRM2 demo template",
        "category": "construction", "version": 1, "is_default": True, "is_builtin": True,
        "is_active": True, "items": [],
    }
    setup = {
        "id": "demo-boq-setup", "project_id": PROJECT_ID, "project_name": "Mattegoda Apartment Complex",
        "client_name": "Prime Homes (Pvt) Ltd", "consultant_name": "ConcoLabs",
        "location": "Mattegoda, Sri Lanka", "boq_title": "Draft Bill of Quantities",
        "currency": "LKR", "vat_percentage": 18, "include_rates": True, "include_amounts": True,
        "include_preliminaries": True, "include_provisional_sums": True, "include_signature_section": True,
        "format_style": "quantity_takeoff", "item_numbering_format": "section_sequence",
        "measurement_unit_style": "metric", "description_style": "detailed",
        "section_order": ["Doors", "Windows", "Masonry walls", "Floor finishes", "Concrete slabs"],
        "setup_version": 1,
    }
    ready = sum(row["status"] == "ready" for row in rows)
    needs = len(rows) - ready
    return {
        "project_id": PROJECT_ID,
        "boq": {"id": "demo-boq", "name": "Mattegoda Draft BOQ", "status": "ready", "boq_version": 1,
                "template_version": 1, "setup_version": 1, "generated_at": NOW,
                "report_hash": "demo-mattegoda-v1"},
        "setup": setup, "template": template, "templates": [template], "rows": rows,
        "report": {"title": setup["boq_title"], "project_name": setup["project_name"],
                   "template_name": template["name"], "currency": "LKR", "vat_percentage": 18,
                   "summary": {"subtotal": 0, "vat": 0, "grand_total": 0, "bill_count": 1, "row_count": len(rows)}},
        "floors": [{"id": floor_id(k), "name": n, "level_index": level} for k, n, level, _, _ in FLOOR_DEFS],
        "stale": False,
        "summary": {"rows": len(rows), "ready": ready, "needs_review": needs, "manual": 0,
                    "doors": sum(r["entity_type"] == "door_set" for r in rows),
                    "windows": sum(r["entity_type"] == "window" for r in rows),
                    "walls": sum(r["entity_type"] == "wall" for r in rows),
                    "floors": sum(r["entity_type"] == "floor" for r in rows), "subtotal": 0},
        "active_jobs": [], "exports": [],
    }


def workflow_state(model: dict[str, Any], walls_state: dict[str, Any], floors_state: dict[str, Any]) -> dict[str, Any]:
    element_counts = defaultdict(int); wall_counts = defaultdict(int); room_counts = defaultdict(int)
    for row in model["elements"]: element_counts[row["floor_id"]] += 1
    for row in walls_state["walls"]: wall_counts[row["floor_id"]] += 1
    for row in floors_state["rooms"]: room_counts[row["floor_id"]] += 1
    summaries = []
    for key, name, level, _, _ in FLOOR_DEFS:
        fid = floor_id(key)
        summaries.append({
            "id": fid, "project_id": PROJECT_ID, "name": name, "level_index": level, "status": "confirmed",
            "versions": {"crop_version": 1, "schedule_version": 1, "scale_version": 1,
                         "element_version": 1, "wall_version": 1, "room_version": 1,
                         "review_version": 1, "boq_version": 1},
            "counts": {"elements": element_counts[fid], "walls": wall_counts[fid],
                       "rooms": room_counts[fid], "review_issues": 0},
        })
    return {
        "project": {"id": PROJECT_ID, "name": "Mattegoda Apartment Complex", "status": "ready",
                    "created_at": NOW, "updated_at": NOW},
        "project_versions": {"document_version": 1, "specification_version": 1, "crop_version": 1,
                             "schedule_version": 1, "scale_version": 1, "element_version": 1,
                             "wall_version": 1, "room_version": 1, "review_version": 1, "boq_version": 1},
        "floors": summaries,
        "counts": {"floors": len(summaries), "elements": len(model["elements"]),
                   "walls": len(walls_state["walls"]), "rooms": len(floors_state["rooms"])},
        "steps": [{"key": key, "label": label, "status": "confirmed"} for key, label in [
            ("upload", "Upload PDF"), ("floor-plans", "Floor Plans"),
            ("specifications", "Schedules & Specifications"), ("scale", "Scale"),
            ("model-review", "Model Review"), ("walls", "Walls"), ("floors", "Floors"),
            ("review", "Review"), ("boq", "BOQ")]],
        "active_jobs": [], "updated_at": NOW,
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "assets").mkdir(parents=True, exist_ok=True)
    for page in range(1, 23):
        source = RUN / f"renders/p{page:03d}.png"
        if source.exists():
            shutil.copy2(source, OUT / source.name)
            shutil.copy2(source, OUT / "assets" / source.name)
    plans = plan_state()
    specs = specifications_state()
    scales = scale_state()
    elements, openings, _ = elements_and_openings()
    walls, wall_floors = wall_states(openings)
    floors = floor_rooms_state()
    model = model_state(elements)
    walls_payload = {
        "project_id": PROJECT_ID, "floors": wall_floors, "selected_floor_id": floor_id("first"),
        "walls": walls, "openings": openings,
        "validation": {"is_valid": True, "blocking_issues": 0, "warning_count": 0, "warnings": []},
    }
    review = review_state(elements, walls, floors["rooms"])
    boq = boq_state()
    workflow = workflow_state(model, walls_payload, floors)
    fixture = {
        "meta": {
            "fixture_version": 1, "project_id": PROJECT_ID,
            "accepted_pdf_sha256": "5729d121d61fac727a38caa07d67e8658cf02b078ae006a4f9949185f1762f4e",
            "source_run": RUN.name, "generated_at": datetime.now(timezone.utc).isoformat(),
            "coordinate_space": "rendered_pixels", "drawing_width": PAGE_WIDTH,
            "drawing_height": PAGE_HEIGHT, "mm_per_pixel": MM_PER_PIXEL,
        },
        "floor_plans": plans, "specifications": specs, "scale": scales,
        "model_review": model, "walls": walls_payload, "floors": floors,
        "review": review, "boq": boq, "workflow": workflow,
        # Runtime-router aliases used by the upload/project shell endpoints.
        "project": {"id": PROJECT_ID, "project_id": PROJECT_ID,
                    "name": "Mattegoda Apartment Complex", "status": "active",
                    "created_at": NOW, "updated_at": NOW},
        "document": {**plans["documents"][0], "project_id": PROJECT_ID,
                     "original_file_name": "Mattegoda Apartment Drawings.pdf",
                     "content_hash": "5729d121d61fac727a38caa07d67e8658cf02b078ae006a4f9949185f1762f4e",
                     "size_bytes": (RUN / "source.pdf").stat().st_size,
                     "validation_status": "valid", "manifest_status": "ready",
                     "ingestion_status": "ready", "manifest_version": 1, "version": 1},
        "workflow_summary": workflow,
    }
    for name, payload in [("floor_plans.json", plans), ("specifications.json", specs),
                          ("scale.json", scales), ("model_review.json", model),
                          ("walls.json", walls_payload), ("floors.json", floors),
                          ("review.json", review), ("boq.json", boq), ("workflow.json", workflow)]:
        dump(name, payload)
    dump("fixture.json", fixture)
    print(json.dumps({
        "fixture": str(OUT / "fixture.json"), "floors": len(FLOOR_DEFS), "elements": len(elements),
        "walls": len(walls), "rooms": len(floors["rooms"]), "boq_rows": len(boq["rows"]),
    }, indent=2))


if __name__ == "__main__":
    main()
