from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from io import BytesIO
import math
import mimetypes
from pathlib import Path
import sys
import tempfile
from threading import Lock
import time
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Request
from fastapi.responses import FileResponse, JSONResponse, Response
from PIL import Image

from demo_backend.loader import asset_path, load_fixture

# The demo intentionally reuses the production BOQ writers, so downloads have
# the same PDF, Excel, and CSV structure as the real application.
BACKEND_ROOT = Path(__file__).resolve().parents[1] / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))
from app.boq.export import filter_report_for_floor, write_csv, write_pdf, write_xlsx
from app.boq.report_builder import formal_boq_report_builder


router = APIRouter(tags=["demo"])
_started_at: dict[str, float] = {}
_crop_overrides: dict[tuple[str, str], dict[str, Any]] = {}
_crop_images: dict[tuple[str, str], bytes] = {}
_specification_overrides: dict[str, dict[str, Any]] = {}
_specification_crop_images: dict[tuple[str, str], bytes] = {}
_specification_crop_versions: dict[tuple[str, str], int] = {}
_model_overrides: dict[str, dict[str, Any]] = {}
_walls_overrides: dict[str, dict[str, Any]] = {}
_floors_overrides: dict[str, dict[str, Any]] = {}
_review_overrides: dict[str, dict[str, Any]] = {}
_room_revisions: dict[tuple[str, str], list[dict[str, Any]]] = {}
_workflow_reached: dict[str, int] = {}
_boq_exports: dict[tuple[str, str], dict[str, Any]] = {}
_boq_export_files: dict[tuple[str, str], bytes] = {}
_crop_lock = Lock()
_model_lock = Lock()

# The demo deliberately reveals plans one at a time.  The first useful result
# arrives after eight seconds and the complete nine-floor set is available at
# eighteen seconds.  Later phases use their own clocks, but cannot start until
# their prerequisite phase is complete.
PLAN_REVEAL_SECONDS = (8.0, 9.25, 10.5, 11.75, 13.0, 14.25, 15.5, 16.75, 18.0)
SPECIFICATION_SECONDS_PER_CATEGORY = 2.0
WORKFLOW_KEYS = (
    "upload", "floor-plans", "specifications", "scale", "model-review",
    "walls", "floors", "review", "boq",
)

# The drawings use imperial dimension strings. These points are the checked
# A–B grid-line endpoints for the rendered demo pages.
GROUND_FLOOR_DIMENSION = {
    "point_a": {"x": 395.8, "y": 234.6},
    "point_b": {"x": 702.3, "y": 234.6},
    "pixel_distance": 306.44,
}
UPPER_FLOOR_DIMENSION = {
    "point_a": {"x": 394.7, "y": 234.8},
    "point_b": {"x": 702.6, "y": 234.8},
    "pixel_distance": 307.85,
}
IMPERIAL_DIMENSION_MM = 6705.6  # 22 feet


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _mark_workflow_reached(project_id: str, step: str) -> None:
    if step not in WORKFLOW_KEYS:
        return
    _workflow_reached[project_id] = max(_workflow_reached.get(project_id, 0), WORKFLOW_KEYS.index(step))


def _project_id(path: str) -> str | None:
    parts = path.strip("/").split("/")
    try:
        return parts[parts.index("projects") + 1]
    except (ValueError, IndexError):
        return None


def _floor_id(path: str) -> str | None:
    parts = path.strip("/").split("/")
    try:
        return parts[parts.index("floors") + 1]
    except (ValueError, IndexError):
        return None


def _state(fixture: dict, key: str, project_id: str) -> dict:
    state = deepcopy(fixture.get(key) or {})
    state["project_id"] = project_id
    return state


def _model_state(fixture: dict, project_id: str) -> dict:
    with _model_lock:
        saved = deepcopy(_model_overrides.get(project_id))
    state = saved or _state(fixture, "model_review", project_id)
    state["project_id"] = project_id
    elements = state.get("elements") or []
    for floor in state.get("floors") or []:
        floor_elements = [item for item in elements if item.get("floor_id") == floor.get("id")]
        floor["element_count"] = len(floor_elements)
        floor["needs_review_count"] = sum(item.get("status") == "needs_review" for item in floor_elements)
        floor["confirmed_count"] = sum(item.get("status") == "confirmed" for item in floor_elements)
        floor["element_version"] = max(
            [int(item.get("element_version") or 0) for item in floor_elements] or [int(floor.get("element_version") or 0)]
        )
    return state


def _save_model_state(project_id: str, state: dict) -> None:
    with _model_lock:
        _model_overrides[project_id] = deepcopy(state)


def _path_value(path: str, segment: str) -> str | None:
    parts = path.strip("/").split("/")
    try:
        return parts[parts.index(segment) + 1]
    except (ValueError, IndexError):
        return None


def _nested_floor_tail(path: str, resource: str) -> tuple[str | None, list[str]]:
    """Return the floor id and remaining path below /{resource}/floors/{id}."""
    parts = path.strip("/").split("/")
    try:
        resource_index = parts.index(resource)
        floors_index = parts.index("floors", resource_index + 1)
        return parts[floors_index + 1], parts[floors_index + 2:]
    except (ValueError, IndexError):
        return None, []


def _new_model_element(state: dict, project_id: str, floor_id: str, payload: dict) -> dict:
    floor_elements = [item for item in state.get("elements", []) if item.get("floor_id") == floor_id]
    item_number = max([int(item.get("item_number") or 0) for item in floor_elements] or [0]) + 1
    element_type = str(payload.get("element_type") or "door")
    prefix = {"door": "D", "window": "W", "wall": "M"}.get(element_type, "E")
    type_code = payload.get("type_code")
    display_number = str(type_code or f"{prefix}{item_number:03d}")
    element_id = f"demo-user-element-{uuid4().hex[:12]}"
    return {
        "id": element_id,
        "project_id": project_id,
        "floor_id": floor_id,
        "item_number": item_number,
        "display_number": display_number,
        "friendly_number": display_number,
        "element_type": element_type,
        "type_code": type_code,
        "geometry": deepcopy(payload.get("geometry") or {"x": 0, "y": 0, "width": 20, "height": 20}),
        "source": "user",
        "confidence": 1.0,
        "status": "confirmed",
        "excluded": False,
        "user_confirmed": True,
        "tag_text": type_code,
        "assigned_schedule_entry_id": None,
        "element_version": 1,
        "properties": [],
        "resolved_data": {"type_code": type_code} if type_code else {},
        "resolved_sources": {"type_code": "user_confirmed"} if type_code else {},
        "confirmed_fields": {"type_code": True} if type_code else {},
        "missing_fields": [],
        "detail_missing_fields": [],
        "schedule_match": None,
        "drawing_detail": None,
        "geometry_source": "user_drawn",
        "updated_at": _now(),
    }


def _patch_model_element(state: dict, element_id: str, payload: dict) -> dict | None:
    element = next((item for item in state.get("elements", []) if item.get("id") == element_id), None)
    if element is None:
        return None
    for field in ("geometry", "type_code", "tag_text", "excluded"):
        if field in payload:
            element[field] = deepcopy(payload[field])
    if "type_code" in payload:
        element.setdefault("resolved_data", {})["type_code"] = payload["type_code"]
        element.setdefault("resolved_sources", {})["type_code"] = "user_confirmed"
        element.setdefault("confirmed_fields", {})["type_code"] = True
    if "review_status" in payload:
        element["status"] = payload["review_status"]
        element["user_confirmed"] = payload["review_status"] == "confirmed"
    element["element_version"] = int(element.get("element_version") or 0) + 1
    element["updated_at"] = _now()
    return element


def _model_openings(state: dict, floor_id: str | None) -> list[dict]:
    return [
        {
            "id": item["id"], "floor_id": item["floor_id"],
            "item_number": item["item_number"], "display_number": item["display_number"],
            "friendly_number": item.get("friendly_number"), "element_type": item["element_type"],
            "type_code": item.get("type_code"), "wall_id": None,
            "geometry": deepcopy(item["geometry"]), "dimensions": deepcopy(item.get("resolved_data") or {}),
        }
        for item in state.get("elements", [])
        if item.get("element_type") in {"door", "window"}
        and not item.get("excluded")
        and (floor_id is None or item.get("floor_id") == floor_id)
    ]


def _wall_state(fixture: dict, project_id: str) -> dict:
    with _model_lock:
        saved = deepcopy(_walls_overrides.get(project_id))
    state = saved or _state(fixture, "walls", project_id)
    state["project_id"] = project_id
    model = _model_state(fixture, project_id)
    openings = _model_openings(model, None)
    assignments = {
        opening.get("element_id"): wall.get("id")
        for wall in state.get("walls", [])
        for opening in wall.get("openings", [])
    }
    for opening in openings:
        opening["wall_id"] = assignments.get(opening["id"])
    state["openings"] = openings
    walls = state.get("walls") or []
    for floor in state.get("floors") or []:
        floor_walls = [wall for wall in walls if wall.get("floor_id") == floor.get("id")]
        floor["wall_version"] = max([int(wall.get("wall_version") or 1) for wall in floor_walls] or [int(floor.get("wall_version") or 0)])
        floor["wall_status"] = "confirmed" if floor_walls and all(wall.get("status") == "confirmed" for wall in floor_walls) else "ready"
        floor["walls_confirmed"] = bool(floor_walls) and all(wall.get("status") == "confirmed" for wall in floor_walls)
    state["validation"] = state.get("validation") or {"is_valid": True, "blocking_issues": 0, "warning_count": 0, "warnings": []}
    return state


def _save_wall_state(project_id: str, state: dict) -> None:
    with _model_lock:
        _walls_overrides[project_id] = deepcopy(state)


def _wall_floor(state: dict, floor_id: str) -> dict:
    return next((floor for floor in state.get("floors", []) if floor.get("id") == floor_id), {})


def _recalculate_wall(wall: dict, floor: dict) -> None:
    line = wall.get("centerline") or {}
    start, end = line.get("start") or {}, line.get("end") or {}
    pixel_length = math.hypot(float(end.get("x", 0)) - float(start.get("x", 0)), float(end.get("y", 0)) - float(start.get("y", 0)))
    mm_per_pixel = float(floor.get("mm_per_pixel") or 22.3297)
    wall["length_mm"] = round(pixel_length * mm_per_pixel, 1)
    height_mm = float(wall.get("height_override_mm") or floor.get("effective_height_mm") or wall.get("height_mm") or 3352.8)
    wall["height_mm"] = height_mm
    wall["height_source"] = "override" if wall.get("height_override_mm") else "floor"
    wall["gross_area_m2"] = round(wall["length_mm"] * height_mm / 1_000_000, 3)
    wall["deduction_area_m2"] = round(sum(float(item.get("deduction_area_m2") or 0) for item in wall.get("openings", [])), 3)
    wall["net_area_m2"] = round(max(0.0, wall["gross_area_m2"] - wall["deduction_area_m2"]), 3)
    wall["status"] = "confirmed"
    wall["user_confirmed"] = True
    wall["manually_edited"] = True
    wall["validation_warnings"] = []
    wall["wall_version"] = int(wall.get("wall_version") or 0) + 1
    wall["updated_at"] = _now()


def _new_wall(state: dict, project_id: str, floor_id: str, payload: dict) -> dict:
    floor_walls = [wall for wall in state.get("walls", []) if wall.get("floor_id") == floor_id]
    template = deepcopy(floor_walls[0] if floor_walls else (state.get("walls") or [{}])[0])
    number = max([int(wall.get("item_number") or 0) for wall in floor_walls] or [0]) + 1
    wall_id = f"demo-user-wall-{uuid4().hex[:12]}"
    line = deepcopy(payload.get("centerline") or {"start": {"x": 0, "y": 0}, "end": {"x": 50, "y": 0}})
    template.update({
        "id": wall_id, "project_id": project_id, "floor_id": floor_id,
        "item_number": number, "display_number": f"WL{number:03d}", "friendly_number": f"WL{number:03d}",
        "source_element_id": None, "centerline": line, "generated_centerline": deepcopy(line),
        "classification": payload.get("classification") or "internal", "wall_type": payload.get("wall_type") or "M03",
        "thickness_mm": payload.get("thickness_mm") or 115, "height_override_mm": None,
        "source": "manual", "confidence": 1.0, "openings": [], "side_1_finish": None, "side_2_finish": None,
    })
    _recalculate_wall(template, _wall_floor(state, floor_id))
    return template


def _room_points(room: dict) -> list[dict]:
    return deepcopy(((room.get("display_polygon") or {}).get("points") or (room.get("geometry") or {}).get("points") or []))


def _polygon_metrics(points: list[dict], mm_per_pixel: float) -> tuple[float, float]:
    if len(points) < 3:
        return 0.0, 0.0
    twice_area = sum(float(a["x"]) * float(b["y"]) - float(b["x"]) * float(a["y"]) for a, b in zip(points, points[1:] + points[:1]))
    perimeter_px = sum(math.hypot(float(a["x"]) - float(b["x"]), float(a["y"]) - float(b["y"])) for a, b in zip(points, points[1:] + points[:1]))
    return round(abs(twice_area) / 2 * mm_per_pixel * mm_per_pixel / 1_000_000, 3), round(perimeter_px * mm_per_pixel / 1000, 3)


def _set_room_points(room: dict, points: list[dict], floor: dict, source: str = "user") -> None:
    geometry = {"points": deepcopy(points)}
    area, perimeter = _polygon_metrics(points, float(floor.get("mm_per_pixel") or 22.3297))
    room.update({
        "geometry": geometry, "display_polygon": geometry, "confirmed_polygon": geometry,
        "confirmed_geometry": geometry, "regularized_polygon": geometry, "regularized_geometry": geometry,
        "area_m2": area, "perimeter_m": perimeter, "point_count": len(points),
        "geometry_status": "confirmed", "status": "confirmed", "user_confirmed": True,
        "user_edited": True, "boundary_source": source,
        "geometry_version": int(room.get("geometry_version") or 0) + 1,
        "edit_revision": int(room.get("edit_revision") or 0) + 1,
        "updated_at": _now(),
    })


def _floor_state(fixture: dict, project_id: str) -> dict:
    with _model_lock:
        saved = deepcopy(_floors_overrides.get(project_id))
    state = saved or _state(fixture, "floors", project_id)
    state["project_id"] = project_id
    rooms = state.get("rooms") or []
    for floor in state.get("floors") or []:
        current = [room for room in rooms if room.get("floor_id") == floor.get("id")]
        floor["room_count"] = len(current)
        floor["finish_zone_count"] = sum(bool(room.get("parent_room_id")) for room in current)
        floor["needs_review_count"] = sum(room.get("status") == "needs_review" for room in current)
        floor["confirmed_count"] = sum(room.get("status") == "confirmed" for room in current)
        floor["area_total_m2"] = round(sum(float(room.get("area_m2") or 0) for room in current if not room.get("excluded")), 2)
        floor["room_version"] = max([int(room.get("geometry_version") or 1) for room in current] or [int(floor.get("room_version") or 0)])
    return state


def _save_floor_state(project_id: str, state: dict) -> None:
    with _model_lock:
        _floors_overrides[project_id] = deepcopy(state)


def _record_room_revision(project_id: str, room: dict, action: str) -> None:
    key = (project_id, str(room.get("id")))
    with _model_lock:
        revisions = _room_revisions.setdefault(key, [])
        revisions.append({
            "id": f"demo-revision-{uuid4().hex[:12]}",
            "room_id": room.get("id"),
            "revision": len(revisions) + 1,
            "action": action,
            "geometry": {"points": _room_points(room)},
            "metadata": {},
            "created_at": _now(),
        })


def _new_room(state: dict, project_id: str, floor_id: str, payload: dict) -> dict:
    floor_rooms = [room for room in state.get("rooms", []) if room.get("floor_id") == floor_id]
    template = deepcopy(floor_rooms[0] if floor_rooms else (state.get("rooms") or [{}])[0])
    number = max([int(str(room.get("friendly_number") or "0").lstrip("R") or 0) for room in floor_rooms] or [0]) + 1
    room_id = f"demo-user-room-{uuid4().hex[:12]}"
    template.update({
        "id": room_id, "project_id": project_id, "floor_id": floor_id, "friendly_number": f"R{number:03d}",
        "name": payload.get("name") or f"Room {number}", "room_type": payload.get("room_type") or "room",
        "floor_type_code": payload.get("floor_type_code") or "F01", "floor_finish": payload.get("floor_finish") or "Floor finish",
        "excluded": False, "exclusion_reason": None, "source": "user", "cutouts": [], "parent_room_id": None,
    })
    points = deepcopy(payload.get("points") or [{"x": 0, "y": 0}, {"x": 80, "y": 0}, {"x": 80, "y": 80}, {"x": 0, "y": 80}])
    _set_room_points(template, points, next((floor for floor in state.get("floors", []) if floor.get("id") == floor_id), {}), "user")
    return template


def _review_state(fixture: dict, project_id: str) -> dict:
    with _model_lock:
        saved = deepcopy(_review_overrides.get(project_id))
    state = saved or _state(fixture, "review", project_id)
    state["project_id"] = project_id
    items = state.get("items") or []
    floor_names = {str(floor.get("id")): str(floor.get("name") or "—") for floor in state.get("floors") or []}
    # The source fixture contains the review-item identities but the original
    # export omitted the resolved fields used by the Review table and inspector.
    # Supply complete, consistent display data for the demo without changing an
    # item's review status or source identity.
    for item in items:
        data = item.setdefault("data", {})
        if not isinstance(data, dict):
            data = item["data"] = {}
        entity_type = item.get("entity_type")
        code = str(data.get("type_code") or item.get("display_number") or "—").split("-")[0]
        data.setdefault("floor", floor_names.get(str(item.get("floor_id")), "—"))
        data.setdefault("drawing_tag", item.get("display_number") or code)
        data.setdefault("value_sources", {})
        if entity_type in {"door", "window"}:
            size_by_code = {
                "GD": (1200, 2100), "D7": (900, 2100), "D6": (750, 2100),
                "D5": (1000, 2400), "D3": (825, 2100), "D2": (900, 2100),
                "D1": (1200, 2100), "FW2": (1200, 1200), "FW1": (900, 1200),
            }
            width, height = size_by_code.get(code, (1200, 2100 if entity_type == "door" else 1200))
            data.setdefault("width_mm", width)
            data.setdefault("height_mm", height)
            data.setdefault("material", "Powder-coated aluminium" if entity_type == "window" else "Timber")
            data.setdefault("frame_material", "Powder-coated aluminium" if entity_type == "window" else "Timber")
            data.setdefault("finish", "Clear glazing" if entity_type == "window" else "Painted finish")
            if entity_type == "window":
                data.setdefault("glass_type", "6 mm clear float glass")
            data["value_sources"] = {**data["value_sources"], "dimensions": "schedule", "material": "specification"}
        elif entity_type == "wall":
            length = float(data.get("length_mm") or 3600)
            data.setdefault("wall_type", "RC blockwork wall")
            data.setdefault("classification", "Internal partition")
            data.setdefault("thickness_mm", 150)
            data.setdefault("net_area_m2", round(length * 3000 / 1_000_000, 2))
            data.setdefault("side_1_finish", "Cement plaster and emulsion paint")
            data.setdefault("side_2_finish", "Cement plaster and emulsion paint")
            data["value_sources"] = {**data["value_sources"], "area": "calculated", "finish": "specification"}
        elif entity_type == "floor":
            data.setdefault("room_name", item.get("title") or "Room")
            data.setdefault("floor_type_code", "F01")
            data.setdefault("floor_finish", "Ceramic floor tiles")
            data["value_sources"] = {**data["value_sources"], "area": "calculated", "finish": "specification"}
        data["source"] = "Schedules, specifications and drawing evidence"
    type_counts = {kind: sum(item.get("entity_type") == kind for item in items) for kind in ("door", "window", "wall", "floor")}
    state["counts"] = {
        "all": len(items), "total": len(items), **type_counts,
        "ready": sum(item.get("status") == "ready" for item in items),
        "confirmed": sum(item.get("status") == "confirmed" for item in items),
        "needs_review": sum(item.get("status") == "needs_review" for item in items),
    }
    for floor in state.get("floors") or []:
        current = [item for item in items if item.get("floor_id") == floor.get("id")]
        floor.update({
            "total": len(current), "ready": sum(item.get("status") == "ready" for item in current),
            "confirmed": sum(item.get("status") == "confirmed" for item in current),
            "needs_review": sum(item.get("status") == "needs_review" for item in current),
        })
    return state


def _attach_review_evidence_to_boq(state: dict, fixture: dict, project_id: str) -> dict:
    """Carry reviewed dimensions and materials into BOQ source-item evidence."""
    evidence_by_type: dict[str, dict] = {}
    for review in _review_state(fixture, project_id).get("items") or []:
        data = review.get("data") or {}
        code = str(data.get("type_code") or "").strip()
        if not code or code in evidence_by_type:
            continue
        if any(data.get(field) is not None for field in ("width_mm", "height_mm", "material", "finish")):
            evidence_by_type[code] = data

    for row in state.get("rows") or []:
        for source in row.get("source_items") or []:
            source_id = str(source.get("id") or source.get("display_number") or "")
            code = source_id.removeprefix("opening-").replace("prime", "")
            evidence = evidence_by_type.get(code)
            if not evidence:
                continue
            source.update({
                "type_code": code,
                "floor": evidence.get("floor"),
                "width_mm": evidence.get("width_mm"),
                "height_mm": evidence.get("height_mm"),
                "material": evidence.get("material"),
                "finish": evidence.get("finish"),
            })
    return state


def _save_review_state(project_id: str, state: dict) -> None:
    with _model_lock:
        _review_overrides[project_id] = deepcopy(state)


def _apply_crop_overrides(state: dict, project_id: str) -> dict:
    with _crop_lock:
        overrides = {
            floor_id: deepcopy(crop)
            for (saved_project_id, floor_id), crop in _crop_overrides.items()
            if saved_project_id == project_id
        }
    for floor in state.get("floors", []):
        crop = overrides.get(str(floor.get("id")))
        if crop is None:
            continue
        floor.update({
            "crop": crop,
            "crop_version": crop["crop_version"],
            "source_document_id": crop["document_id"],
            "source_page_number": crop["source_page_number"],
            "source_rotation": crop["rotation"],
            "status": "ready",
            "active_jobs": [],
            "last_error": None,
            "updated_at": crop["updated_at"],
        })
    return state


def _base_floor(fixture: dict, floor_id: str) -> dict:
    floors = (fixture.get("floor_plans") or {}).get("floors") or []
    return next((floor for floor in floors if str(floor.get("id")) == floor_id), {})


def _specification_state(fixture: dict, project_id: str) -> dict:
    with _crop_lock:
        saved = deepcopy(_specification_overrides.get(project_id))
    state = saved or _state(fixture, "specifications", project_id)
    state["project_id"] = project_id
    if state.get("documents"):
        return state

    base_documents = (fixture.get("floor_plans") or {}).get("documents") or []
    base_document = deepcopy(base_documents[0] if base_documents else {})
    document_id = str(base_document.get("id") or "demo-mattegoda-source")
    pages = []
    for page_number in range(1, 23):
        width, height = ((935, 1210) if page_number <= 12 else (1820, 2573))
        pages.append({
            "id": f"demo-page-{page_number:03d}",
            "document_id": document_id,
            "page_number": page_number,
            "page_label": str(page_number),
            "width": width,
            "height": height,
            "thumbnail_url": f"/api/v1/demo/assets/p{page_number:03d}.png",
            "preview_url": f"/api/v1/demo/assets/p{page_number:03d}.png",
        })
    state["documents"] = [{
        "id": document_id,
        "file_name": base_document.get("file_name") or "Mattegoda Apartment Drawings.pdf",
        "page_count": 22,
        "is_primary": True,
        "pages": pages,
    }]
    return state


def _render_crop_preview(payload: dict) -> bytes:
    page_number = int(payload.get("source_page_number") or 0)
    source = asset_path(f"p{page_number:03d}.png")
    if source is None:
        raise ValueError("The selected demo drawing page is not available.")

    rect = payload.get("original_rect") or {}
    original_width = max(1.0, float(payload.get("original_page_width") or 1))
    original_height = max(1.0, float(payload.get("original_page_height") or 1))
    with Image.open(source) as image:
        scale_x = image.width / original_width
        scale_y = image.height / original_height
        left = max(0, min(image.width - 1, round(float(rect.get("x") or 0) * scale_x)))
        top = max(0, min(image.height - 1, round(float(rect.get("y") or 0) * scale_y)))
        right = max(left + 1, min(image.width, round((float(rect.get("x") or 0) + float(rect.get("width") or original_width)) * scale_x)))
        bottom = max(top + 1, min(image.height, round((float(rect.get("y") or 0) + float(rect.get("height") or original_height)) * scale_y)))
        preview = image.crop((left, top, right, bottom))
        rotation = int(payload.get("rotation") or 0)
        if rotation:
            preview = preview.rotate(-rotation, expand=True)
        output = BytesIO()
        preview.save(output, format="PNG", optimize=True)
        return output.getvalue()


def _save_crop(fixture: dict, project_id: str, floor_id: str, payload: dict) -> dict:
    required = (
        "document_id", "document_page_id", "source_page_number",
        "original_page_width", "original_page_height", "rotation",
        "render_dpi", "original_rect", "normalized_display_rect",
    )
    missing = [field for field in required if field not in payload]
    if missing:
        raise ValueError(f"Missing crop fields: {', '.join(missing)}")

    key = (project_id, floor_id)
    base_floor = _base_floor(fixture, floor_id)
    with _crop_lock:
        previous = _crop_overrides.get(key) or base_floor.get("crop") or {}
        version = int(previous.get("crop_version") or base_floor.get("crop_version") or 0) + 1

    source_changed = bool(previous) and (
        previous.get("document_id") != payload["document_id"]
        or previous.get("document_page_id") != payload["document_page_id"]
    )
    updated_at = _now()
    preview_url = f"/api/v1/demo/crops/{project_id}/{floor_id}.png?v={version}"
    crop = {
        "id": previous.get("id") or f"demo-crop-{floor_id}",
        "project_id": project_id,
        "floor_id": floor_id,
        "document_id": payload["document_id"],
        "document_page_id": payload["document_page_id"],
        "source_page_number": int(payload["source_page_number"]),
        "original_page_width": float(payload["original_page_width"]),
        "original_page_height": float(payload["original_page_height"]),
        "rotation": int(payload["rotation"]),
        "render_dpi": int(payload["render_dpi"]),
        "coordinates": {
            "original_rect": deepcopy(payload["original_rect"]),
            "normalized_display_rect": deepcopy(payload["normalized_display_rect"]),
            "coordinate_space": "original_page_pixels",
        },
        "crop_version": version,
        "status": "ready",
        "crop_asset_url": preview_url,
        "preview_asset_url": preview_url,
        "created_at": previous.get("created_at") or updated_at,
        "updated_at": updated_at,
    }
    preview = _render_crop_preview(payload)
    with _crop_lock:
        _crop_overrides[key] = deepcopy(crop)
        _crop_images[key] = preview
    return {"crop": crop, "jobs": [], "source_changed": source_changed, "unchanged": False}


def _save_specification_crop(fixture: dict, project_id: str, payload: dict) -> dict:
    required = (
        "category", "document_id", "document_page_id", "page_number",
        "original_page_width", "original_page_height", "crop",
        "scope_mode", "floor_ids",
    )
    missing = [field for field in required if field not in payload]
    if missing:
        raise ValueError(f"Missing specification crop fields: {', '.join(missing)}")

    state = _specification_state(fixture, project_id)
    category = next(
        (item for item in state.get("categories", []) if item.get("key") == payload["category"]),
        None,
    )
    if category is None:
        raise ValueError("Specification category not found.")

    replace_source_id = payload.get("replace_source_id")
    existing = next(
        (source for source in category.get("sources", []) if source.get("id") == replace_source_id),
        None,
    )
    source_id = str(replace_source_id or f"demo-spec-source-{uuid4().hex[:10]}")
    preview_payload = {
        "source_page_number": payload["page_number"],
        "original_page_width": payload["original_page_width"],
        "original_page_height": payload["original_page_height"],
        "original_rect": payload["crop"],
        "rotation": 0,
    }
    preview = _render_crop_preview(preview_payload)
    key = (project_id, source_id)
    with _crop_lock:
        version = _specification_crop_versions.get(key, 0) + 1
        _specification_crop_versions[key] = version
        _specification_crop_images[key] = preview

    updated_at = _now()
    source = {
        **(deepcopy(existing) if existing else {}),
        "id": source_id,
        "category": payload["category"],
        "source_type": "crop",
        "document_id": payload["document_id"],
        "file_name": f"Project PDF · Page {int(payload['page_number'])} crop",
        "mime_type": "image/png",
        "file_size": len(preview),
        "page_number": int(payload["page_number"]),
        "crop": deepcopy(payload["crop"]),
        "scope_mode": payload["scope_mode"],
        "floor_ids": deepcopy(payload["floor_ids"]),
        "status": "ready",
        "preview_url": f"/api/v1/demo/specification-crops/{project_id}/{source_id}.png?v={version}",
        "active_job": None,
        "entry_count": int((existing or {}).get("entry_count") or 0),
        "entries": deepcopy((existing or {}).get("entries") or []),
        "created_at": (existing or {}).get("created_at") or updated_at,
        "updated_at": updated_at,
    }
    sources = category.setdefault("sources", [])
    if existing:
        sources[sources.index(existing)] = source
    else:
        sources.append(source)
    category["entry_count"] = sum(int(item.get("entry_count") or 0) for item in sources)
    category["status"] = "ready"
    state["updated_at"] = updated_at
    with _crop_lock:
        _specification_overrides[project_id] = deepcopy(state)
    # Saving an edit is a completed user action. Keep the updated source
    # visible instead of letting the initial demo streaming timeline hide it.
    _started_at[f"{project_id}:specifications"] = (
        time.monotonic() - _specification_total(fixture)
    )
    return {"source": source, "state": state}


def _floor_filter(state: dict, floor_id: str | None, fields: tuple[str, ...]) -> dict:
    selected = floor_id or state.get("selected_floor_id")
    if selected:
        state["selected_floor_id"] = selected
        for field in fields:
            if isinstance(state.get(field), list):
                state[field] = [item for item in state[field] if item.get("floor_id") == selected]
    return state


def _job(project_id: str, task: str, elapsed: float, total: float, floor_id: str | None = None) -> dict:
    progress = min(99, max(3, int(elapsed / total * 100)))
    return {
        "id": f"demo-{task}-{floor_id or project_id}", "project_id": project_id,
        "floor_id": floor_id, "category": task.split(".", 1)[0], "task_type": task,
        "job_type": task, "status": "running", "progress": progress,
        "message": "Analysing construction drawings", "attempts": 1, "max_attempts": 1,
        "created_at": _now(), "updated_at": _now(),
    }


def _project_elapsed(project_id: str) -> float:
    return time.monotonic() - _started_at.setdefault(project_id, time.monotonic())


def _plans_complete(fixture: dict, project_id: str) -> bool:
    floors = (fixture.get("floor_plans") or {}).get("floors") or []
    if not floors:
        return False
    final_index = min(len(floors), len(PLAN_REVEAL_SECONDS)) - 1
    return _project_elapsed(project_id) >= PLAN_REVEAL_SECONDS[final_index]


def _specification_total(fixture: dict) -> float:
    categories = (fixture.get("specifications") or {}).get("categories") or []
    return max(2.0, len(categories) * SPECIFICATION_SECONDS_PER_CATEGORY)


def _specification_elapsed(project_id: str, *, start: bool) -> float | None:
    key = f"{project_id}:specifications"
    if start:
        _started_at.setdefault(key, time.monotonic())
    started_at = _started_at.get(key)
    return None if started_at is None else time.monotonic() - started_at


def _specifications_complete(fixture: dict, project_id: str) -> bool:
    elapsed = _specification_elapsed(project_id, start=False)
    return elapsed is not None and elapsed >= _specification_total(fixture)


def _staged_floor_plans(state: dict, project_id: str, elapsed: float) -> dict:
    floors = state.get("floors", [])
    visible = []
    for index, floor in enumerate(floors):
        threshold = PLAN_REVEAL_SECONDS[min(index, len(PLAN_REVEAL_SECONDS) - 1)]
        if elapsed >= threshold:
            visible.append(floor)
    state["floors"] = visible
    complete = len(visible) == len(floors) and bool(floors)
    state["can_continue"] = complete
    for document in state.get("documents", []):
        document["status"] = "ready" if complete else "processing"
    if not complete:
        pending = floors[len(visible)] if len(visible) < len(floors) else None
        state["active_jobs"] = [
            _job(project_id, "render.floor_plans", elapsed, PLAN_REVEAL_SECONDS[-1], pending and pending.get("id"))
        ]
    else:
        state["active_jobs"] = []
    return state


def _staged_specifications(state: dict, project_id: str, elapsed: float) -> dict:
    categories = state.get("categories", [])
    visible_count = min(
        len(categories),
        max(0, int(elapsed // SPECIFICATION_SECONDS_PER_CATEGORY)),
    )
    total = max(2.0, len(categories) * SPECIFICATION_SECONDS_PER_CATEGORY)
    complete = visible_count >= len(categories) and bool(categories)
    for index, category in enumerate(categories):
        sources = category.get("sources", [])
        if index < visible_count:
            continue
        if index == visible_count and sources:
            category["status"] = "processing"
            category["entry_count"] = 0
            sources[0]["status"] = "processing"
            sources[0]["entries"] = []
            sources[0]["entry_count"] = 0
            sources[0]["active_job"] = _job(project_id, "extract.specifications", elapsed, total)
        else:
            category["sources"] = []
            category["entry_count"] = 0
            if category.get("status") != "skipped":
                category["status"] = "processing"
    state["can_continue"] = complete
    state["active_jobs"] = [] if complete else [_job(project_id, "extract.specifications", elapsed, total)]
    return state


def _waiting_specifications(state: dict, project_id: str, plan_elapsed: float) -> dict:
    for category in state.get("categories", []):
        category["sources"] = []
        category["entry_count"] = 0
        if category.get("status") != "skipped":
            category["status"] = "processing"
    state["can_continue"] = False
    state["active_jobs"] = [
        {
            **_job(project_id, "wait.floor_plans", plan_elapsed, PLAN_REVEAL_SECONDS[-1]),
            "message": "Waiting for floor plans to finish",
        }
    ]
    return state


def _locked_scale(state: dict) -> dict:
    # Keep the supplied demo calibrations visible while the preceding
    # specification phase is still staged.  The workflow itself remains
    # blocked, but users can inspect the saved points and scale evidence.
    state["can_continue"] = False
    return state


def _imperial_scale_state(state: dict) -> dict:
    """Normalise the demo's saved scale records to the printed imperial line."""
    for floor in state.get("floors", []):
        dimension = GROUND_FLOOR_DIMENSION if floor.get("id") == "demo-floor-ground" else UPPER_FLOOR_DIMENSION
        mm_per_pixel = IMPERIAL_DIMENSION_MM / dimension["pixel_distance"]
        calibration = floor.get("calibration")
        if isinstance(calibration, dict):
            calibration.update({
                "point_a": deepcopy(dimension["point_a"]),
                "point_b": deepcopy(dimension["point_b"]),
                "pixel_distance": dimension["pixel_distance"],
                "real_distance_mm": IMPERIAL_DIMENSION_MM,
                "mm_per_pixel": mm_per_pixel,
                "input_unit": "ft_in",
            })
        for suggestion in floor.get("dimension_suggestions", []):
            if isinstance(suggestion, dict):
                suggestion.update({
                    "point_a": deepcopy(dimension["point_a"]),
                    "point_b": deepcopy(dimension["point_b"]),
                    "value_mm": IMPERIAL_DIMENSION_MM,
                    "suggested_mm_per_pixel": mm_per_pixel,
                    "display_scale": "1:96",
                })
    return state


def _expected_boq_state(state: dict) -> dict:
    """Present the reviewed Preliminary Partial BOQ in the demo workspace."""
    source_rows = {row.get("id"): row for row in state.get("rows", [])}

    def row(
        number: str,
        section: str,
        reference: str,
        description: str,
        quantity: float | None,
        unit: str,
        status: str,
        source_id: str | None = None,
    ) -> dict:
        source = deepcopy(source_rows.get(source_id or "", {}))
        return {
            "id": f"demo-final-boq-{number.replace('.', '-').lower()}",
            "floor_id": None,
            "entity_type": source.get("entity_type") or "manual",
            "section": section,
            "item_code": reference,
            "boq_item_number": number,
            "bill_no": "1",
            "bill_name": "Measured Building Works",
            "subcategory_code": None,
            "subcategory_name": section,
            "description": description,
            "quantity": quantity or 0,
            "unit": unit,
            "rate": None,
            "amount": None,
            "status": status,
            "source_ids": deepcopy(source.get("source_ids") or []),
            "source_items": deepcopy(source.get("source_items") or []),
            "floor_ids": [],
            "floor_names": [],
            "missing_fields": ["rate"] if quantity is not None and status not in {"control", "tbc"} else [],
            "manual": False,
            "protected_description": False,
            "protected_rate": False,
            "excluded": False,
            "sort_order": len(final_rows) + 1,
        }

    final_rows: list[dict] = []
    opening_rows = [
        ("A.01", "Doors", "NRM2 24.2", "D1 - Timber panelled entrance door set, structural opening 4'-0\" x 7'-0\"; including frame, architraves, fixings, seals and finishing.", 36, "nr", "confirmed", "demo-boq-001"),
        ("A.02", "Doors", "NRM2 24.2", "D2 - Timber framed solid bedroom door set, structural opening 3'-0\" x 7'-0\"; including frame, architraves, fixings and finishing.", 72, "nr", "confirmed", "demo-boq-002"),
        ("A.03", "Doors", "NRM2 24.2", "D2' - Timber framed solid garbage-room door set, structural opening 3'-0\" x 8'-0\"; including frame, fixings, finishing and ironmongery.", 1, "nr", "unverified", "demo-boq-003"),
        ("A.04", "Doors", "NRM2 24.2", "D3 - Timber framed solid toilet door set, structural opening 2'-9\" x 7'-0\"; including moisture-resistant finishing, frame and architraves.", 72, "nr", "confirmed", "demo-boq-004"),
        ("A.05", "Doors", "NRM2 24.2", "D5 - Timber framed solid disabled-toilet door set, structural opening 3'-3\" x 8'-0\"; including accessible ironmongery.", 0, "nr", "confirmed", "demo-boq-005"),
        ("A.06", "Doors", "NRM2 24.2", "D6 - Aluminium framed composite-panel duct door set, structural opening 2'-0\" x 6'-0\"; including frame, fixings and seals.", 86, "nr", "confirmed", "demo-boq-006"),
        ("A.07", "Doors", "NRM2 24.2", "D7 - Aluminium framed composite-panel duct door set, structural opening 4'-0\" x 6'-0\"; including frame, fixings and seals.", 15, "nr", "disputed", "demo-boq-007"),
        ("A.08", "Doors", "NRM2 24.2", "D8 - Aluminium framed composite-panel duct door set, structural opening 2'-10\" x 6'-0\"; including frame, fixings and seals.", 1, "nr", "unverified", "demo-boq-008"),
        ("A.09", "Doors", "NRM2 24.2", "GD - G.I. gate to panel room, structural opening 4'-0\" x 8'-0\"; including frame, hinges, locking arrangement and protective coating.", 1, "nr", "confirmed", "demo-boq-018"),
        ("A.10", "Doors", "NRM2 24.2", "RD - Roller shutter door to transformer room, structural opening 8'-0\" x 8'-0\"; complete with guides, barrel, hood and operating gear.", 1, "nr", "unverified", "demo-boq-019"),
        ("B.01", "Windows", "NRM2 23.1", "FG - Aluminium framed glazed staircase window, structural opening 8'-0\" x 8'-0\"; including safety glazing, beads and gaskets.", 6, "nr", "disputed", "demo-boq-009"),
        ("B.02", "Windows", "NRM2 23.1", "FG1 - Aluminium framed glazed staircase-lobby window, structural opening 4'-0\" x 8'-0\"; including safety glazing, beads and gaskets.", 12, "nr", "confirmed", "demo-boq-010"),
        ("B.03", "Windows", "NRM2 23.1", "SL - Aluminium framed sliding lobby window, structural opening 6'-0\" x 8'-0\"; including glazing, sliding gear, locks and drainage.", 2, "nr", "disputed", "demo-boq-011"),
        ("B.04", "Windows", "NRM2 23.1", "SL1 - Aluminium framed sliding window to living/dining/pantry, structural opening 6'-2\" x 8'-0\"; including glazing, sliding gear and locks.", 12, "nr", "confirmed", "demo-boq-012"),
        ("B.05", "Windows", "NRM2 23.1", "SL2 - Aluminium framed sliding window to gym/condominium room, structural opening 10'-0\" x 8'-0\"; including glazing, sliding gear and locks.", 8, "nr", "confirmed", "demo-boq-013"),
        ("B.06", "Windows", "NRM2 23.1", "FW1 - Aluminium framed French window to living/dining/pantry, structural opening 5'-0\" x 8'-0\"; including glazing, hinges, stays and locks.", 24, "nr", "confirmed", "demo-boq-014"),
        ("B.07", "Windows", "NRM2 23.1", "FW2 - Aluminium framed French window to bedroom, structural opening 4'-3\" x 8'-0\"; including glazing, hinges, stays and locks.", 72, "nr", "disputed", "demo-boq-015"),
        ("B.08", "Windows", "NRM2 23.1", "LW - Aluminium framed louvered window to toilet, structural opening 2'-0\" x 8'-0\"; including louvre blades/panels and insect screening.", 72, "nr", "disputed", "demo-boq-016"),
        ("B.09", "Windows", "NRM2 23.1", "LW1 - Aluminium framed louvered window to water-tank area, structural opening 10'-3\" x 7'-0\"; including louvre blades/panels and frame.", 1, "nr", "disputed", "demo-boq-017"),
    ]
    for values in opening_rows:
        final_rows.append(row(*values))

    measured_rows = [
        ("C.01", "Masonry walls", "NRM2 14.1", "First-floor nominal 225 mm masonry walling (M01/M02 family), net of provisionally allocated openings.", 727.35051888, "m²", "provisional"),
        ("C.02", "Masonry walls", "NRM2 14.1", "First-floor nominal 115 mm masonry walling (M03/M04 family), net of provisionally allocated openings.", 295.83881904, "m²", "provisional"),
        ("C.03", "Masonry walls", "NRM2 14.1", "Second-to-sixth-floor nominal 225 mm masonry walling (M01/M02 family), net of provisionally allocated openings.", 3546.8304984, "m²", "provisional"),
        ("C.04", "Masonry walls", "NRM2 14.1", "Second-to-sixth-floor nominal 115 mm masonry walling (M03/M04 family), net of provisionally allocated openings.", 1424.9122632, "m²", "provisional"),
        ("D.01", "Floor finishes", "NRM2 28.2", "Heavy-duty homogeneous/porcelain tile finish to common corridors and entrance/lift lobbies (F04/F05 combined).", 387.96309504, "m²", "preliminary"),
        ("D.02", "Floor finishes", "NRM2 28.2", "Exterior anti-slip pavers/tiles to open roof terrace (F10) over protected insulated waterproofing system and screed to falls.", 356.7476736, "m²", "preliminary"),
        ("D.03", "Floor finishes", "NRM2 28.6", "Flower-trough drainage/protection finish (F12) over continuous root-resistant waterproofing.", 92.53142784, "m²", "preliminary"),
        ("D.C1", "Floor finishes", "Control", "Composite apartment-unit area requiring final split among F01 internal tile, F02 wet-area tile and F03 balcony finishes.", 2739.15323136, "m²", "control"),
        ("D.C2", "Floor finishes", "Control", "Ground-floor gross area requiring final split among F08 parking/driveway, F05 lobby and F09 service-room finishes.", 579.065, "m²", "control"),
        ("D.C3", "Floor finishes", "Control", "Roof enclosed/core gross area requiring final split among F07 gym, F01 management room and F05 lobby/circulation finishes.", 138.51843264, "m²", "control"),
        ("E.C1", "Wall finishes to masonry", "Control", "Control area for finishes to both faces of net first-to-sixth-floor masonry before allocation among wall finish types.", 11989.86419904, "m²", "control"),
        ("E.01", "Wall finishes to masonry", "NRM2 28", "W01/W02 internal wall finish: cement-sand plaster, skim where required, primer and two coats emulsion paint.", None, "m²", "tbc"),
        ("E.02", "Wall finishes to masonry", "NRM2 28", "W03 toilet/bathroom wall finish: glazed ceramic/porcelain tiles to full height on prepared backing.", None, "m²", "tbc"),
        ("E.03", "Wall finishes to masonry", "NRM2 28", "W05 external wall finish: weather-resistant cementitious render with mesh reinforcement and compatible external paint.", None, "m²", "tbc"),
    ]
    for values in measured_rows:
        final_rows.append(row(*values))
    state["rows"] = final_rows
    setup = state.get("setup")
    if isinstance(setup, dict):
        setup.update({
            "boq_title": "Preliminary Partial Bill of Quantities",
            "section_order": ["Doors", "Windows", "Masonry walls", "Floor finishes", "Wall finishes to masonry"],
        })
    return _attach_review_evidence_to_boq(state, load_fixture(), str(state.get("project_id") or "demo-mattegoda"))


def _demo_boq_exports(project_id: str, fixture: dict) -> list[dict[str, Any]]:
    with _crop_lock:
        generated = [
            deepcopy(record)
            for (saved_project_id, _), record in _boq_exports.items()
            if saved_project_id == project_id
        ]
    existing = deepcopy((fixture.get("boq") or {}).get("exports") or [])
    return sorted([*generated, *existing], key=lambda item: str(item.get("created_at") or ""), reverse=True)


def _create_demo_boq_export(project_id: str, fixture: dict, payload: dict) -> dict:
    format_name = str(payload.get("format") or "pdf").lower()
    if format_name not in {"pdf", "xlsx", "csv"}:
        raise ValueError("Unsupported export format.")
    floor_mode = str(payload.get("floor_mode") or "combined")
    if floor_mode not in {"combined", "floor_breakdown", "selected_floor"}:
        raise ValueError("Select a valid export layout.")
    floor_id = payload.get("floor_id") if floor_mode == "selected_floor" else None
    # Export the same normalized BOQ state served to the UI. This is the
    # reviewed/extracted dataset, not the raw fixture records it was derived
    # from, so descriptions, quantities, and setup metadata stay identical.
    boq_state = _expected_boq_state(_state(fixture, "boq", project_id))
    setup = deepcopy(boq_state.get("setup") or {})
    boq = deepcopy(boq_state.get("boq") or {})
    template = deepcopy(boq_state.get("template") or {})
    rows = deepcopy(boq_state.get("rows") or [])
    if not setup or not boq or not template:
        raise ValueError("The demo BOQ report is unavailable.")
    # Keep the export self-contained in every format. Excel also receives the
    # structured fields in its Element Properties sheet via source_items.
    for row in rows:
        source = next((item for item in row.get("source_items") or [] if item.get("width_mm") or item.get("height_mm") or item.get("material")), None)
        if source is None:
            continue
        dimensions = " × ".join(str(round(float(source[key]), 1)).rstrip("0").rstrip(".") for key in ("width_mm", "height_mm") if source.get(key) is not None)
        details = [f"size {dimensions} mm" if dimensions else None, source.get("material"), source.get("finish")]
        evidence = "; ".join(str(value) for value in details if value)
        if evidence:
            row["description"] = f"{row.get('description') or 'Description to confirm'} [Reviewed evidence: {evidence}]"
    report = formal_boq_report_builder.build(
        project={"id": project_id, "name": boq_state.get("project_name") or setup.get("project_name") or "Project"},
        setup=setup,
        template=template,
        boq=boq,
        rows=rows,
    )
    report["export_floor_mode"] = floor_mode
    if floor_mode == "selected_floor":
        floor = next((item for item in boq_state.get("floors") or [] if item.get("id") == floor_id), None)
        if floor is None:
            raise ValueError("Select a floor to export.")
        report = filter_report_for_floor(report, str(floor.get("name") or ""))
        report["export_floor_mode"] = "selected_floor"
        report["selected_floor_name"] = floor.get("name")

    export_id = str(uuid4())
    filename = f"Mattegoda-BOQ-{floor_mode}.{format_name}"
    writers = {"pdf": write_pdf, "xlsx": write_xlsx, "csv": write_csv}
    with tempfile.TemporaryDirectory(prefix="autoboq-demo-export-") as directory:
        output = Path(directory) / filename
        writers[format_name](output, report)
        content = output.read_bytes()
    record = {
        "id": export_id,
        "project_id": project_id,
        "format": format_name,
        "floor_mode": floor_mode,
        "floor_id": floor_id,
        "filename": filename,
        "status": "ready",
        "error_message": None,
        "boq_version": int((boq_state.get("boq") or {}).get("boq_version") or 1),
        "template_version": int((boq_state.get("boq") or {}).get("template_version") or 1),
        "setup_version": int((boq_state.get("boq") or {}).get("setup_version") or 1),
        "created_at": _now(),
    }
    with _crop_lock:
        _boq_exports[(project_id, export_id)] = deepcopy(record)
        _boq_export_files[(project_id, export_id)] = content
    return record


def _workflow_state(fixture: dict, project_id: str) -> dict:
    state = _state(fixture, "workflow", project_id)
    plan_elapsed = _project_elapsed(project_id)
    plans_done = _plans_complete(fixture, project_id)
    spec_elapsed = _specification_elapsed(project_id, start=False)
    specs_done = _specifications_complete(fixture, project_id)

    reached = _workflow_reached.get(project_id, 1 if plans_done else 0)
    for step in state.get("steps", []):
        key = step.get("key")
        index = WORKFLOW_KEYS.index(key) if key in WORKFLOW_KEYS else len(WORKFLOW_KEYS)
        if index > reached:
            step["status"] = "not_ready"
        elif key == "floor-plans" and not plans_done and reached <= 1:
            step["status"] = "processing"
        elif key == "specifications" and not specs_done and reached <= 2:
            step["status"] = "processing"
        else:
            # Visiting a workflow page makes its prerequisite data available;
            # it is not an explicit user approval.  Reserve "confirmed" for
            # real confirmation actions and show the navigation badge as ready.
            step["status"] = "ready"

    if reached <= 1 and not plans_done:
        state["active_jobs"] = [
            _job(project_id, "render.floor_plans", plan_elapsed, PLAN_REVEAL_SECONDS[-1])
        ]
    elif reached <= 2 and spec_elapsed is not None and not specs_done:
        state["active_jobs"] = [
            _job(project_id, "extract.specifications", spec_elapsed, _specification_total(fixture))
        ]
    else:
        state["active_jobs"] = []
    state["updated_at"] = _now()
    return state


async def _payload(request: Request) -> dict:
    if request.headers.get("content-type", "").startswith("application/json"):
        try:
            value = await request.json()
            return value if isinstance(value, dict) else {}
        except Exception:
            return {}
    return {}


def _mutation_response(path: str, payload: dict, fixture: dict, project_id: str) -> dict:
    record = {"id": str(uuid4()), **payload, "project_id": project_id, "updated_at": _now()}
    if "/scale/floors/" in path:
        return {"calibration": record, "jobs": [], "versions": {"scale_version": 1}}
    if "/model-review/" in path:
        return {"record": record, "jobs": [], "versions": {"element_version": 1}}
    if "/boq/setup" in path:
        return {"setup": {**(fixture.get("boq", {}).get("setup") or {}), **payload}, "job": None}
    if "/boq/exports" in path:
        return {"export": {**record, "status": "ready", "filename": "Mattegoda-BOQ.pdf"}, "job": None}
    if "/boq/rows" in path:
        return record
    if "/review/confirm" in path:
        return {"confirmed": len(payload.get("item_ids", [])), "jobs": []}
    if "/review/items/" in path:
        return {"record": record, "jobs": []}
    if "/walls/" in path or "/floors/" in path:
        return {"record": record, "jobs": [], "versions": {}}
    return {"record": record, "protected": False, "changed": False, "versions": {}, "jobs": []}


@router.api_route("/demo/assets/{name:path}", methods=["GET"], include_in_schema=False)
def demo_asset(name: str):
    path = asset_path(name)
    if path is None:
        return JSONResponse({"detail": "Demo asset not found."}, status_code=404)
    return FileResponse(path, media_type=mimetypes.guess_type(path.name)[0])


@router.get("/demo/crops/{project_id}/{floor_id}.png", include_in_schema=False)
def demo_crop(project_id: str, floor_id: str):
    with _crop_lock:
        content = _crop_images.get((project_id, floor_id))
    if content is None:
        return JSONResponse({"detail": "Demo crop preview not found."}, status_code=404)
    return Response(
        content=content,
        media_type="image/png",
        headers={"Cache-Control": "no-store"},
    )


@router.get("/demo/specification-crops/{project_id}/{source_id}.png", include_in_schema=False)
def demo_specification_crop(project_id: str, source_id: str):
    with _crop_lock:
        content = _specification_crop_images.get((project_id, source_id))
    if content is None:
        return JSONResponse({"detail": "Demo specification crop not found."}, status_code=404)
    return Response(
        content=content,
        media_type="image/png",
        headers={"Cache-Control": "no-store"},
    )


@router.api_route("/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"], include_in_schema=False)
async def demo_api(path: str, request: Request):
    fixture = load_fixture()
    full_path = f"/{path}"
    meta = fixture.get("meta") or {}
    workflow_project = (fixture.get("workflow") or {}).get("project") or {}
    fixture_project_id = meta.get("project_id") or workflow_project.get("id") or "demo-project"
    project_id = _project_id(full_path) or str(fixture_project_id)

    # The summary request is mounted beside the active page request. Use its
    # referrer as a race-free progress signal so badges are correct on the
    # first render after any Continue/Back navigation.
    if full_path.endswith("/workflow/summary"):
        active_step = request.query_params.get("active_step")
        if active_step:
            _mark_workflow_reached(project_id, active_step)
        referrer = request.headers.get("referer", "")
        for step in reversed(WORKFLOW_KEYS[1:]):
            if f"/{step}" in referrer:
                _mark_workflow_reached(project_id, step)
                break

    # Preserve login-free local behaviour and the project/upload entry flow.
    if request.method == "POST" and full_path == "/projects":
        payload = await _payload(request)
        return {**workflow_project, **payload, "id": project_id, "project_id": project_id, "status": "active", "created_at": _now(), "updated_at": _now()}
    if request.method == "GET" and full_path == "/projects":
        project = {**workflow_project, "id": project_id}
        return {"projects": [project], "total": 1, "limit": 50, "offset": 0}
    if request.method == "POST" and full_path.endswith("/workflow/documents"):
        _started_at[project_id] = time.monotonic()
        _started_at.pop(f"{project_id}:specifications", None)
        _workflow_reached[project_id] = 1
        with _crop_lock:
            for key in [key for key in _crop_overrides if key[0] == project_id]:
                _crop_overrides.pop(key, None)
                _crop_images.pop(key, None)
            _specification_overrides.pop(project_id, None)
            for key in [key for key in _specification_crop_images if key[0] == project_id]:
                _specification_crop_images.pop(key, None)
                _specification_crop_versions.pop(key, None)
        with _model_lock:
            _model_overrides.pop(project_id, None)
            _walls_overrides.pop(project_id, None)
            _floors_overrides.pop(project_id, None)
            _review_overrides.pop(project_id, None)
            for key in [key for key in _room_revisions if key[0] == project_id]:
                _room_revisions.pop(key, None)
        with _crop_lock:
            for key in [key for key in _boq_exports if key[0] == project_id]:
                _boq_exports.pop(key, None)
                _boq_export_files.pop(key, None)
        documents = (fixture.get("floor_plans") or {}).get("documents") or []
        document = deepcopy(documents[0] if documents else {})
        document.update({"id": document.get("id") or "demo-document", "project_id": project_id, "status": "processing", "created_at": _now(), "updated_at": _now()})
        return {"document": document, "reused": False, "duplicate": False, "jobs": [], "next_step": "floor-plans"}

    elapsed = _project_elapsed(project_id)
    floor_id = request.query_params.get("floor_id")
    if request.method == "GET":
        if full_path == "/auth/me":
            return {"id": "demo-user", "email": "demo@autoboq.local", "full_name": "Demo User", "role": "admin", "is_active": True}
        if full_path == "/platform/me":
            return {"user": {"id": "demo-user", "email": "demo@autoboq.local", "full_name": "Demo User", "role": "admin"}, "organization": None, "subscription": None}
        if full_path.endswith("/floor-plans"):
            _mark_workflow_reached(project_id, "floor-plans")
            state = _apply_crop_overrides(_state(fixture, "floor_plans", project_id), project_id)
            return _staged_floor_plans(state, project_id, elapsed)
        if full_path.endswith("/specifications"):
            _mark_workflow_reached(project_id, "specifications")
            if not _plans_complete(fixture, project_id):
                return _waiting_specifications(
                    _specification_state(fixture, project_id), project_id, elapsed
                )
            # The specification clock begins only after Plans is complete and
            # this phase is first opened/polled.
            spec_elapsed = _specification_elapsed(project_id, start=True) or 0.0
            return _staged_specifications(_specification_state(fixture, project_id), project_id, spec_elapsed)
        if full_path.endswith("/scale"):
            _mark_workflow_reached(project_id, "scale")
            state = _imperial_scale_state(_state(fixture, "scale", project_id))
            return state
        if full_path.endswith("/model-review"):
            _mark_workflow_reached(project_id, "model-review")
            return _floor_filter(_model_state(fixture, project_id), floor_id, ("elements",))
        if full_path.endswith("/walls"):
            _mark_workflow_reached(project_id, "walls")
            return _floor_filter(_wall_state(fixture, project_id), floor_id, ("walls", "openings"))
        if full_path.endswith("/floors"):
            _mark_workflow_reached(project_id, "floors")
            return _floor_filter(_floor_state(fixture, project_id), floor_id, ("rooms", "suggestions"))
        if full_path.endswith("/review"):
            _mark_workflow_reached(project_id, "review")
            state = _floor_filter(_review_state(fixture, project_id), floor_id, ("items",))
            category = request.query_params.get("category", "all")
            if category != "all" and isinstance(state.get("items"), list):
                state["items"] = [item for item in state["items"] if item.get("entity_type") == category]
            return state
        if full_path.endswith("/boq"):
            _mark_workflow_reached(project_id, "boq")
            return _expected_boq_state(_state(fixture, "boq", project_id))
        if full_path.endswith("/boq/setup"):
            return deepcopy(fixture.get("boq", {}).get("setup") or {})
        if full_path.endswith("/boq/templates"):
            boq = fixture.get("boq", {})
            return {"templates": deepcopy(boq.get("templates") or []), "selected_template_id": (boq.get("template") or {}).get("id")}
        if "/boq/exports/" in full_path and full_path.endswith("/download"):
            export_id = _path_value(full_path, "exports")
            with _crop_lock:
                record = deepcopy(_boq_exports.get((project_id, export_id or "")))
                content = _boq_export_files.get((project_id, export_id or ""))
            if not record or content is None:
                return JSONResponse({"detail": "Export is not ready."}, status_code=404)
            media_type = {
                "pdf": "application/pdf",
                "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                "csv": "text/csv; charset=utf-8",
            }[record["format"]]
            return Response(
                content=content,
                media_type=media_type,
                headers={
                    "Content-Disposition": f'attachment; filename="{record["filename"]}"',
                    "Cache-Control": "no-store",
                },
            )
        if full_path.endswith("/boq/exports"):
            return {"exports": _demo_boq_exports(project_id, fixture), "active_jobs": []}
        if full_path.endswith("/jobs"):
            return {"jobs": []}
        if full_path.endswith("/workflow/summary"):
            return _workflow_state(fixture, project_id)
        if full_path.endswith("/workflow/documents"):
            documents = (fixture.get("floor_plans") or {}).get("documents") or []
            document = deepcopy(documents[0] if documents else {})
            document["project_id"] = project_id
            return [document]
        if full_path.startswith("/projects/") and full_path.count("/") == 2:
            return {**workflow_project, "id": project_id}

    payload = await _payload(request)
    if full_path == "/auth/login":
        return {"access_token": "demo-token", "token_type": "bearer", "user": {"id": "demo-user", "email": "demo@autoboq.local", "full_name": "Demo User", "role": "admin", "is_active": True}}
    if full_path == "/auth/logout":
        return {"status": "signed_out"}
    if request.method == "POST" and full_path.endswith("/boq/exports"):
        try:
            record = _create_demo_boq_export(project_id, fixture, payload)
            return {"export": record, "job": None, "created": True}
        except (OSError, TypeError, ValueError) as error:
            return JSONResponse({"detail": str(error)}, status_code=422)
    if request.method == "PUT" and full_path.endswith("/crop") and "/floor-plans/floors/" in full_path:
        selected_floor_id = _floor_id(full_path)
        if selected_floor_id is None or not _base_floor(fixture, selected_floor_id):
            return JSONResponse({"detail": "Demo floor not found."}, status_code=404)
        try:
            return _save_crop(fixture, project_id, selected_floor_id, payload)
        except (TypeError, ValueError) as error:
            return JSONResponse({"detail": str(error)}, status_code=422)
    if request.method == "POST" and full_path.endswith("/specifications/sources/crop"):
        try:
            return _save_specification_crop(fixture, project_id, payload)
        except (TypeError, ValueError) as error:
            return JSONResponse({"detail": str(error)}, status_code=422)
    if "/model-review/floors/" in full_path:
        selected_floor_id = _floor_id(full_path)
        if selected_floor_id is None:
            return JSONResponse({"detail": "Demo floor not found."}, status_code=404)
        state = _model_state(fixture, project_id)

        if request.method == "POST" and full_path.endswith("/elements"):
            record = _new_model_element(state, project_id, selected_floor_id, payload)
            state.setdefault("elements", []).append(record)
            _save_model_state(project_id, state)
            return {"record": deepcopy(record), "jobs": [], "versions": {"element_version": record["element_version"]}}

        element_id = _path_value(full_path, "elements")
        if element_id:
            record = next((item for item in state.get("elements", []) if item.get("id") == element_id), None)
            if record is None:
                return JSONResponse({"detail": "Demo element not found."}, status_code=404)

            if request.method == "PATCH" and "/properties/" in full_path:
                property_name = _path_value(full_path, "properties")
                if property_name is None:
                    return JSONResponse({"detail": "Property name is required."}, status_code=422)
                properties = record.setdefault("properties", [])
                saved_property = next((item for item in properties if item.get("property_name") == property_name), None)
                value = payload.get("value")
                if saved_property is None:
                    saved_property = {
                        "id": f"{element_id}-{property_name}", "property_name": property_name,
                        "value": value, "unit": payload.get("unit"), "source": "user_confirmed", "is_confirmed": True,
                    }
                    properties.append(saved_property)
                else:
                    saved_property.update({"value": value, "unit": payload.get("unit"), "source": "user_confirmed", "is_confirmed": True})
                record.setdefault("resolved_data", {})[property_name] = value
                record.setdefault("resolved_sources", {})[property_name] = "user_confirmed"
                record.setdefault("confirmed_fields", {})[property_name] = True
                record["element_version"] = int(record.get("element_version") or 0) + 1
                record["updated_at"] = _now()
                _save_model_state(project_id, state)
                return {"record": deepcopy(record), "property": deepcopy(saved_property), "jobs": []}

            if request.method == "PUT" and full_path.endswith("/schedule"):
                schedule_id = payload.get("schedule_entry_id")
                schedule_entry = next((item for item in state.get("schedule_entries", []) if item.get("id") == schedule_id), None)
                record["assigned_schedule_entry_id"] = schedule_id
                record["schedule_match"] = deepcopy(schedule_entry)
                if schedule_entry:
                    schedule_data = schedule_entry.get("data") or {}
                    type_code = schedule_data.get("type_code") or schedule_data.get("type") or schedule_entry.get("entity_key")
                    if type_code:
                        record["type_code"] = type_code
                        record.setdefault("resolved_data", {})["type_code"] = type_code
                        record.setdefault("resolved_sources", {})["type_code"] = "schedule"
                    for field in ("width_mm", "height_mm", "sill_height"):
                        if schedule_data.get(field) is not None:
                            record.setdefault("resolved_data", {})[field] = schedule_data[field]
                            record.setdefault("resolved_sources", {})[field] = "schedule"
                    if schedule_data.get("description"):
                        record.setdefault("resolved_data", {})["description"] = schedule_data["description"]
                        record.setdefault("resolved_sources", {})["description"] = "schedule"
                record["element_version"] = int(record.get("element_version") or 0) + 1
                record["updated_at"] = _now()
                _save_model_state(project_id, state)
                return {"record": deepcopy(record), "jobs": []}

            if request.method == "PATCH" and full_path.endswith(f"/elements/{element_id}"):
                updated = _patch_model_element(state, element_id, payload)
                _save_model_state(project_id, state)
                return {"record": deepcopy(updated), "jobs": [], "versions": {"element_version": updated["element_version"]}}

        if request.method == "POST" and full_path.endswith("/confirm"):
            selected_ids = set(payload.get("element_ids") or [])
            updated = []
            for item in state.get("elements", []):
                if item.get("floor_id") == selected_floor_id and (not selected_ids or item.get("id") in selected_ids):
                    item["status"] = "confirmed"
                    item["user_confirmed"] = True
                    item["element_version"] = int(item.get("element_version") or 0) + 1
                    updated.append(item["id"])
            _save_model_state(project_id, state)
            return {"confirmed": len(updated), "element_ids": updated, "jobs": []}

    if "/walls/floors/" in full_path:
        selected_floor_id, tail = _nested_floor_tail(full_path, "walls")
        if selected_floor_id is None:
            return JSONResponse({"detail": "Demo floor not found."}, status_code=404)
        state = _wall_state(fixture, project_id)
        floor = _wall_floor(state, selected_floor_id)
        floor_walls = [wall for wall in state.get("walls", []) if wall.get("floor_id") == selected_floor_id]

        if request.method == "POST" and tail in (["regenerate"], ["auto-fix"]):
            for wall in floor_walls:
                wall["status"] = "confirmed"
                wall["user_confirmed"] = True
                wall["validation_warnings"] = []
                _recalculate_wall(wall, floor)
            state["validation"] = {"is_valid": True, "blocking_issues": 0, "warning_count": 0, "warnings": []}
            _save_wall_state(project_id, state)
            return {"state": _floor_filter(_wall_state(fixture, project_id), selected_floor_id, ("walls", "openings")), "jobs": []}

        if request.method == "POST" and tail == ["confirm-all"]:
            for wall in floor_walls:
                wall["status"] = "confirmed"
                wall["user_confirmed"] = True
                wall["validation_warnings"] = []
                wall["wall_version"] = int(wall.get("wall_version") or 0) + 1
            _save_wall_state(project_id, state)
            return {"confirmed": len(floor_walls), "jobs": [], "versions": {"wall_version": max([int(w.get("wall_version") or 1) for w in floor_walls] or [1])}}

        if request.method == "POST" and not tail:
            record = _new_wall(state, project_id, selected_floor_id, payload)
            state.setdefault("walls", []).append(record)
            _save_wall_state(project_id, state)
            return {"record": deepcopy(record), "jobs": [], "versions": {"wall_version": record["wall_version"]}}

        wall_id = tail[0] if tail else None
        wall = next((item for item in state.get("walls", []) if item.get("id") == wall_id and item.get("floor_id") == selected_floor_id), None)
        if wall_id and wall is None:
            return JSONResponse({"detail": "Demo wall not found."}, status_code=404)
        action = tail[1] if len(tail) > 1 else None

        if wall is not None and request.method == "PATCH" and action is None:
            for field in ("centerline", "classification", "wall_type", "thickness_mm", "height_override_mm", "side_1_finish", "side_2_finish"):
                if field in payload:
                    wall[field] = deepcopy(payload[field])
            if payload.get("use_floor_height"):
                wall["height_override_mm"] = None
            if payload.get("review_status"):
                wall["status"] = payload["review_status"]
            _recalculate_wall(wall, floor)
            _save_wall_state(project_id, state)
            return {"record": deepcopy(wall), "jobs": [], "versions": {"wall_version": wall["wall_version"]}}

        if wall is not None and request.method == "DELETE" and action is None:
            state["walls"] = [item for item in state.get("walls", []) if item.get("id") != wall_id]
            _save_wall_state(project_id, state)
            return {"deleted": True, "wall_id": wall_id, "jobs": [], "versions": {}}

        if wall is not None and request.method == "POST" and action == "restore":
            wall["centerline"] = deepcopy(wall.get("generated_centerline") or wall.get("centerline"))
            wall["manually_edited"] = False
            _recalculate_wall(wall, floor)
            _save_wall_state(project_id, state)
            return {"record": deepcopy(wall), "jobs": [], "versions": {"wall_version": wall["wall_version"]}}

        if wall is not None and request.method == "POST" and action == "openings":
            element_id = payload.get("element_id")
            element = next((item for item in _model_openings(_model_state(fixture, project_id), selected_floor_id) if item.get("id") == element_id), None)
            if element is None:
                return JSONResponse({"detail": "Demo opening not found."}, status_code=404)
            dimensions = element.get("dimensions") or {}
            width_mm = dimensions.get("width_mm")
            height_mm = dimensions.get("height_mm")
            opening_area = round(float(width_mm or 0) * float(height_mm or 0) / 1_000_000, 3)
            saved_opening = {
                "id": f"{wall_id}-{element_id}", "element_id": element_id,
                "element_number": element.get("friendly_number"), "element_item_number": element.get("item_number"),
                "element_display_number": element.get("display_number"), "element_type": element.get("element_type"),
                "type_code": element.get("type_code"), "width_mm": width_mm, "height_mm": height_mm,
                "opening_area_m2": opening_area, "deduction_area_m2": opening_area,
            }
            wall.setdefault("openings", [])[:] = [item for item in wall.get("openings", []) if item.get("element_id") != element_id]
            wall["openings"].append(saved_opening)
            # An opening belongs to one wall at a time.
            for other in state.get("walls", []):
                if other.get("id") != wall_id:
                    other["openings"] = [item for item in other.get("openings", []) if item.get("element_id") != element_id]
            _recalculate_wall(wall, floor)
            _save_wall_state(project_id, state)
            return {"record": deepcopy(wall), "opening": saved_opening, "jobs": [], "versions": {"wall_version": wall["wall_version"]}}

        if wall is not None and request.method == "POST" and action == "split":
            line = deepcopy(wall.get("centerline") or {})
            start, end = line.get("start") or {}, line.get("end") or {}
            ratio = min(0.9, max(0.1, float(payload.get("ratio") or 0.5)))
            midpoint = {"x": float(start.get("x", 0)) + (float(end.get("x", 0)) - float(start.get("x", 0))) * ratio,
                        "y": float(start.get("y", 0)) + (float(end.get("y", 0)) - float(start.get("y", 0))) * ratio}
            old_end = deepcopy(end)
            wall["centerline"]["end"] = midpoint
            _recalculate_wall(wall, floor)
            second = deepcopy(wall)
            second["id"] = f"demo-split-wall-{uuid4().hex[:12]}"
            second["item_number"] = max([int(item.get("item_number") or 0) for item in floor_walls] or [0]) + 1
            second["display_number"] = second["friendly_number"] = f"WL{second['item_number']:03d}"
            second["centerline"] = {"start": deepcopy(midpoint), "end": old_end}
            second["generated_centerline"] = deepcopy(second["centerline"])
            second["openings"] = []
            _recalculate_wall(second, floor)
            state.setdefault("walls", []).append(second)
            _save_wall_state(project_id, state)
            return {"record": deepcopy(wall), "created": deepcopy(second), "jobs": [], "versions": {"wall_version": second["wall_version"]}}

        if wall is not None and request.method == "POST" and action == "merge":
            other_id = payload.get("other_wall_id")
            other = next((item for item in state.get("walls", []) if item.get("id") == other_id and item.get("floor_id") == selected_floor_id), None)
            if other is None or other_id == wall_id:
                return JSONResponse({"detail": "Select another wall on the same floor."}, status_code=422)
            points = [
                (wall.get("centerline") or {}).get("start") or {}, (wall.get("centerline") or {}).get("end") or {},
                (other.get("centerline") or {}).get("start") or {}, (other.get("centerline") or {}).get("end") or {},
            ]
            # Use the farthest endpoints so merge is useful even if lines have a small detection gap.
            best = max(((a, b) for index, a in enumerate(points) for b in points[index + 1:]), key=lambda pair: math.hypot(float(pair[0].get("x", 0)) - float(pair[1].get("x", 0)), float(pair[0].get("y", 0)) - float(pair[1].get("y", 0))))
            wall["centerline"] = {"start": deepcopy(best[0]), "end": deepcopy(best[1])}
            existing = {item.get("element_id") for item in wall.get("openings", [])}
            wall.setdefault("openings", []).extend(deepcopy(item) for item in other.get("openings", []) if item.get("element_id") not in existing)
            state["walls"] = [item for item in state.get("walls", []) if item.get("id") != other_id]
            _recalculate_wall(wall, floor)
            _save_wall_state(project_id, state)
            return {"record": deepcopy(wall), "merged_wall_id": other_id, "jobs": [], "versions": {"wall_version": wall["wall_version"]}}

    if "/floors/floors/" in full_path:
        selected_floor_id, tail = _nested_floor_tail(full_path, "floors")
        if selected_floor_id is None:
            return JSONResponse({"detail": "Demo floor not found."}, status_code=404)
        state = _floor_state(fixture, project_id)
        floor = next((item for item in state.get("floors", []) if item.get("id") == selected_floor_id), {})
        floor_rooms = [room for room in state.get("rooms", []) if room.get("floor_id") == selected_floor_id]

        if request.method == "GET" and tail == ["interpretation-status"]:
            return {"project_id": project_id, "floor_id": selected_floor_id, "status": "ready", "run_id": "demo-run", "model": "demo-fixture", "prompt_version": "fixture-v1", "updated_at": _now(), "room_statuses": [{"room_id": room.get("id"), "status": room.get("interpretation_status") or "ready", "warnings": room.get("interpretation_warnings") or []} for room in floor_rooms]}
        if request.method == "GET" and tail == ["suggestions"]:
            return {"items": [item for item in state.get("suggestions", []) if item.get("floor_id") == selected_floor_id]}
        if request.method == "POST" and tail in (["analyze"], ["recalculate"], ["precision-refine"], ["interpret"]):
            for room in floor_rooms:
                room["processing_stage"] = "confirmed"
                room["interpretation_status"] = "ready"
                room["precision_status"] = "ready"
            floor["analysis_status"] = "ready"
            floor["interpretation_status"] = "ready"
            _save_floor_state(project_id, state)
            return {"state": _floor_filter(_floor_state(fixture, project_id), selected_floor_id, ("rooms", "suggestions")), "jobs": []}
        if request.method == "POST" and tail == ["confirm-all"]:
            for room in floor_rooms:
                room.update({"status": "confirmed", "user_confirmed": True, "interpretation_status": "confirmed"})
            _save_floor_state(project_id, state)
            return {"confirmed": len(floor_rooms), "jobs": [], "versions": {"room_version": max([int(room.get("geometry_version") or 1) for room in floor_rooms] or [1])}}
        if request.method == "POST" and tail == ["rooms"]:
            room = _new_room(state, project_id, selected_floor_id, payload)
            state.setdefault("rooms", []).append(room)
            _save_floor_state(project_id, state)
            return {"record": deepcopy(room), "jobs": [], "versions": {"room_version": room["geometry_version"]}}

        if len(tail) >= 2 and tail[0] == "suggestions":
            suggestion_id = tail[1]
            suggestion = next((item for item in state.get("suggestions", []) if item.get("id") == suggestion_id), None)
            action = tail[2] if len(tail) > 2 else None
            if suggestion is None:
                return JSONResponse({"detail": "Demo suggestion not found."}, status_code=404)
            if request.method == "POST" and action in {"accept", "correct-with-walls"}:
                room = _new_room(state, project_id, selected_floor_id, {"points": ((suggestion.get("polygon") or {}).get("points") or []), "name": "Suggested room"})
                state.setdefault("rooms", []).append(room)
                suggestion.update({"status": "accepted", "matched_room_id": room["id"]})
            elif request.method == "POST" and action == "reject":
                suggestion["status"] = "rejected"
            _save_floor_state(project_id, state)
            return {"record": deepcopy(suggestion), "jobs": []}

        room_id = tail[1] if len(tail) >= 2 and tail[0] == "rooms" else None
        room = next((item for item in state.get("rooms", []) if item.get("id") == room_id and item.get("floor_id") == selected_floor_id), None)
        if room_id and room is None:
            return JSONResponse({"detail": "Demo room not found."}, status_code=404)
        action_parts = tail[2:] if room_id else []

        if room is not None and request.method == "GET" and action_parts == ["revisions"]:
            with _model_lock:
                return {"items": deepcopy(_room_revisions.get((project_id, room_id), []))}
        if room is not None and request.method == "GET" and action_parts == ["auto-fix-preview"]:
            points = _room_points(room)
            return {"room_id": room_id, "original": {"points": points}, "proposed": {"points": points}, "changed": False, "shape_type": room.get("shape_type") or "polygon", "original_vertex_count": len(points), "proposed_vertex_count": len(points), "area_change_percent": 0, "source": "demo-fixture", "seed_score": 1, "model_overlap": 1, "warnings": []}
        if room is not None and request.method == "PATCH" and not action_parts:
            _record_room_revision(project_id, room, "edit")
            for field in ("name", "room_type", "floor_type_code", "floor_finish", "space_kind", "include_in_boq", "open_plan", "manual_area_override_m2"):
                if field in payload:
                    room[field] = deepcopy(payload[field])
            if payload.get("review_status"):
                room["status"] = payload["review_status"]
            if payload.get("points"):
                _set_room_points(room, payload["points"], floor, "user")
            _save_floor_state(project_id, state)
            return {"record": deepcopy(room), "jobs": [], "versions": {"room_version": room.get("geometry_version", 1)}}
        if room is not None and request.method == "DELETE" and not action_parts:
            state["rooms"] = [item for item in state.get("rooms", []) if item.get("id") != room_id and item.get("parent_room_id") != room_id]
            _save_floor_state(project_id, state)
            return {"deleted": True, "room_id": room_id, "jobs": [], "versions": {}}
        if room is not None and request.method == "POST" and action_parts == ["confirm"]:
            room.update({"status": "confirmed", "user_confirmed": True, "interpretation_status": "confirmed", "updated_at": _now()})
            _save_floor_state(project_id, state)
            return {"record": deepcopy(room), "jobs": []}
        if room is not None and request.method == "POST" and action_parts == ["exclude"]:
            room.update({"excluded": True, "exclusion_reason": payload.get("reason"), "include_in_boq": False, "status": "confirmed", "updated_at": _now()})
            _save_floor_state(project_id, state)
            return {"record": deepcopy(room), "jobs": []}
        if room is not None and request.method == "POST" and action_parts == ["restore"]:
            room.update({"excluded": False, "exclusion_reason": None, "include_in_boq": True, "status": "confirmed", "updated_at": _now()})
            _save_floor_state(project_id, state)
            return {"record": deepcopy(room), "jobs": []}
        if room is not None and request.method == "POST" and action_parts in (["split"], ["split-line"]):
            _record_room_revision(project_id, room, "split")
            points = _room_points(room)
            xs, ys = [float(point["x"]) for point in points], [float(point["y"]) for point in points]
            if not xs or not ys:
                return JSONResponse({"detail": "Room has no geometry."}, status_code=422)
            vertical = payload.get("axis", "vertical") == "vertical" if action_parts == ["split"] else abs(float((payload.get("points") or [{"x": 0}, {"x": 1}])[0].get("x", 0)) - float((payload.get("points") or [{"x": 0}, {"x": 1}])[-1].get("x", 1))) < abs(float((payload.get("points") or [{"y": 0}, {"y": 1}])[0].get("y", 0)) - float((payload.get("points") or [{"y": 0}, {"y": 1}])[-1].get("y", 1)))
            if vertical:
                mid = (min(xs) + max(xs)) / 2
                first_points = [{"x": min(xs), "y": min(ys)}, {"x": mid, "y": min(ys)}, {"x": mid, "y": max(ys)}, {"x": min(xs), "y": max(ys)}]
                second_points = [{"x": mid, "y": min(ys)}, {"x": max(xs), "y": min(ys)}, {"x": max(xs), "y": max(ys)}, {"x": mid, "y": max(ys)}]
            else:
                mid = (min(ys) + max(ys)) / 2
                first_points = [{"x": min(xs), "y": min(ys)}, {"x": max(xs), "y": min(ys)}, {"x": max(xs), "y": mid}, {"x": min(xs), "y": mid}]
                second_points = [{"x": min(xs), "y": mid}, {"x": max(xs), "y": mid}, {"x": max(xs), "y": max(ys)}, {"x": min(xs), "y": max(ys)}]
            _set_room_points(room, first_points, floor, "user_split")
            created = _new_room(state, project_id, selected_floor_id, {"points": second_points, "name": f"{room.get('name') or 'Room'} B", "room_type": room.get("room_type"), "floor_type_code": room.get("floor_type_code"), "floor_finish": room.get("floor_finish")})
            state.setdefault("rooms", []).append(created)
            _save_floor_state(project_id, state)
            return {"record": deepcopy(room), "created": deepcopy(created), "jobs": []}
        if room is not None and request.method == "POST" and action_parts == ["merge"]:
            other_id = payload.get("other_room_id")
            other = next((item for item in state.get("rooms", []) if item.get("id") == other_id and item.get("floor_id") == selected_floor_id), None)
            if other is None or other_id == room_id:
                return JSONResponse({"detail": "Select another room on the same floor."}, status_code=422)
            _record_room_revision(project_id, room, "merge")
            points = _room_points(room) + _room_points(other)
            xs, ys = [float(point["x"]) for point in points], [float(point["y"]) for point in points]
            merged = [{"x": min(xs), "y": min(ys)}, {"x": max(xs), "y": min(ys)}, {"x": max(xs), "y": max(ys)}, {"x": min(xs), "y": max(ys)}]
            _set_room_points(room, merged, floor, "user_merge")
            state["rooms"] = [item for item in state.get("rooms", []) if item.get("id") != other_id]
            _save_floor_state(project_id, state)
            return {"record": deepcopy(room), "merged_room_id": other_id, "jobs": []}
        if room is not None and request.method in {"POST", "PATCH"} and action_parts in (["snap"], ["auto-fix"], ["simplify"], ["make-rectangle"], ["straighten"], ["geometry"], ["reset-to-model"], ["reset-to-corrected"]):
            _record_room_revision(project_id, room, action_parts[0])
            points = deepcopy(payload.get("points") or ((payload.get("geometry") or {}).get("points") if isinstance(payload.get("geometry"), dict) else None) or _room_points(room))
            if action_parts == ["reset-to-model"]:
                points = deepcopy((room.get("model_polygon") or room.get("raw_geometry") or {}).get("points") or points)
            elif action_parts == ["reset-to-corrected"]:
                points = deepcopy((room.get("wall_corrected_polygon") or room.get("wall_corrected_geometry") or {}).get("points") or points)
            elif action_parts == ["make-rectangle"] and points:
                xs, ys = [float(point["x"]) for point in points], [float(point["y"]) for point in points]
                points = [{"x": min(xs), "y": min(ys)}, {"x": max(xs), "y": min(ys)}, {"x": max(xs), "y": max(ys)}, {"x": min(xs), "y": max(ys)}]
            _set_room_points(room, points, floor, f"user_{action_parts[0]}")
            _save_floor_state(project_id, state)
            return {"record": deepcopy(room), "jobs": []}
        if room is not None and action_parts and action_parts[0] == "finish-zones":
            zone_id = action_parts[1] if len(action_parts) > 1 else None
            zone = next((item for item in state.get("rooms", []) if item.get("id") == zone_id and item.get("parent_room_id") == room_id), None)
            if request.method == "POST" and zone_id is None:
                zone = _new_room(state, project_id, selected_floor_id, payload)
                zone.update({"parent_room_id": room_id, "is_finish_zone": True, "space_kind": room.get("space_kind")})
                state.setdefault("rooms", []).append(zone)
            elif request.method == "PATCH" and zone is not None:
                for field in ("name", "floor_type_code", "floor_finish"):
                    if field in payload:
                        zone[field] = payload[field]
                if payload.get("points"):
                    _set_room_points(zone, payload["points"], floor, "user_zone")
            elif request.method == "DELETE" and zone is not None:
                state["rooms"] = [item for item in state.get("rooms", []) if item.get("id") != zone_id]
            else:
                return JSONResponse({"detail": "Demo finish zone not found."}, status_code=404)
            _save_floor_state(project_id, state)
            return {"record": deepcopy(zone), "deleted": request.method == "DELETE", "jobs": []}
        if room is not None and action_parts and action_parts[0] == "cutouts":
            cutout_id = action_parts[1] if len(action_parts) > 1 else None
            if request.method == "POST" and cutout_id is None:
                points = deepcopy(payload.get("points") or [])
                area, _ = _polygon_metrics(points, float(floor.get("mm_per_pixel") or 22.3297))
                cutout = {"id": f"demo-cutout-{uuid4().hex[:12]}", "room_id": room_id, "name": payload.get("name"), "geometry": {"points": points}, "area_m2": area}
                room.setdefault("cutouts", []).append(cutout)
            elif request.method == "DELETE" and cutout_id:
                room["cutouts"] = [item for item in room.get("cutouts", []) if item.get("id") != cutout_id]
                cutout = {"id": cutout_id}
            else:
                return JSONResponse({"detail": "Demo cutout action not supported."}, status_code=422)
            _save_floor_state(project_id, state)
            return {"record": deepcopy(room), "cutout": cutout, "deleted": request.method == "DELETE", "jobs": []}
        if room is not None and len(action_parts) == 3 and action_parts[0] == "revisions" and action_parts[2] == "restore" and request.method == "POST":
            revision_id = action_parts[1]
            with _model_lock:
                revision = next((item for item in _room_revisions.get((project_id, room_id), []) if item.get("id") == revision_id), None)
            if revision is None:
                return JSONResponse({"detail": "Demo revision not found."}, status_code=404)
            _record_room_revision(project_id, room, "restore_revision")
            _set_room_points(room, deepcopy((revision.get("geometry") or {}).get("points") or []), floor, "revision")
            _save_floor_state(project_id, state)
            return {"record": deepcopy(room), "jobs": []}

    if "/review/items/" in full_path and request.method == "PATCH":
        state = _review_state(fixture, project_id)
        item_id = _path_value(full_path, "items")
        item = next((entry for entry in state.get("items", []) if entry.get("id") == item_id), None)
        if item is None:
            return JSONResponse({"detail": "Demo review item not found."}, status_code=404)
        field = payload.get("field")
        if field:
            item.setdefault("data", {})[str(field)] = deepcopy(payload.get("value"))
        item["status"] = "confirmed"
        item["review_version"] = int(item.get("review_version") or 0) + 1
        _save_review_state(project_id, state)
        return {"record": deepcopy(item), "jobs": []}

    if full_path.endswith("/review/confirm") and request.method == "POST":
        state = _review_state(fixture, project_id)
        selected_ids = set(payload.get("item_ids") or [])
        scope = payload.get("scope") or "selected"
        selected_floor_id = payload.get("floor_id")
        confirmed = []
        for item in state.get("items", []):
            matches = ((scope == "selected" and item.get("id") in selected_ids) or
                       (scope == "floor" and item.get("floor_id") == selected_floor_id) or
                       scope == "project")
            if matches:
                item["status"] = "confirmed"
                item["review_version"] = int(item.get("review_version") or 0) + 1
                confirmed.append(item.get("id"))
        _save_review_state(project_id, state)
        return {"confirmed": len(confirmed), "item_ids": confirmed, "jobs": []}

    if "/floor-plans" in full_path:
        state = _apply_crop_overrides(_state(fixture, "floor_plans", project_id), project_id)
        state["can_continue"] = True
        return state
    if "/specifications" in full_path:
        state = _specification_state(fixture, project_id)
        if "/sources/upload" in full_path or "/sources/crop" in full_path:
            return {"source_id": "demo-source", "state": state}
        return state
    return _mutation_response(full_path, payload, fixture, project_id)
