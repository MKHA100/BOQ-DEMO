from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Any

import fitz

from app.database.session import get_connection
from app.floor_plans.repo import floor_plans_repository
from app.model_review.repo import model_review_repository
from app.pdf_upload.repo import pdf_upload_repository
from app.storage.storage_service import storage_service
from app.workflow.repo import workflow_repository
from app.workflow.service import workflow_service

DOOR_TAG = re.compile(r"^(?:D|GD)\d+[A-Z]*$")
WINDOW_TAG = re.compile(r"^(?:W\d+[A-Z]*|FG\d*|F\d+[A-Z]*)$")

PROPERTY_FIELDS: tuple[tuple[str, str | None], ...] = (
    ("width_mm", "mm"),
    ("height_mm", "mm"),
    ("material", None),
    ("frame_material", None),
    ("finish", None),
    ("glass_type", None),
    ("fire_rating", None),
)


@dataclass(frozen=True)
class TagCandidate:
    code: str
    element_type: str
    x: float
    y: float
    source_bbox: tuple[float, float, float, float]


def normalize_tag(value: str | None) -> str:
    return re.sub(r"[^A-Za-z0-9]", "", value or "").upper()


def tag_element_type(value: str | None) -> str | None:
    code = normalize_tag(value)
    if DOOR_TAG.fullmatch(code):
        return "door"
    if WINDOW_TAG.fullmatch(code):
        return "window"
    return None


def _point_to_rect_distance(x: float, y: float, geometry: dict[str, Any]) -> float:
    left = float(geometry.get("x") or 0)
    top = float(geometry.get("y") or 0)
    right = left + float(geometry.get("width") or 0)
    bottom = top + float(geometry.get("height") or 0)
    dx = max(left - x, 0.0, x - right)
    dy = max(top - y, 0.0, y - bottom)
    return math.hypot(dx, dy)


def _expanded_distance(candidate: TagCandidate, geometry: dict[str, Any]) -> float:
    width = max(float(geometry.get("width") or 0), 1.0)
    height = max(float(geometry.get("height") or 0), 1.0)
    expanded = {
        "x": float(geometry.get("x") or 0) - width * 1.5,
        "y": float(geometry.get("y") or 0) - height * 1.5,
        "width": width * 4.0,
        "height": height * 4.0,
    }
    edge_distance = _point_to_rect_distance(candidate.x, candidate.y, expanded)
    center_x = float(geometry.get("x") or 0) + width / 2
    center_y = float(geometry.get("y") or 0) + height / 2
    center_distance = math.hypot(candidate.x - center_x, candidate.y - center_y)
    return min(center_distance, edge_distance * 1.3)


def _candidate_score(candidate: TagCandidate, geometry: dict[str, Any]) -> float:
    """Return a scale-independent score; lower is a better tag-to-opening match."""
    width = max(float(geometry.get("width") or 0), 1.0)
    height = max(float(geometry.get("height") or 0), 1.0)
    left = float(geometry.get("x") or 0)
    top = float(geometry.get("y") or 0)
    right = left + width
    bottom = top + height
    inside = left <= candidate.x <= right and top <= candidate.y <= bottom
    edge = _point_to_rect_distance(candidate.x, candidate.y, geometry)
    center = math.hypot(candidate.x - (left + width / 2), candidate.y - (top + height / 2))
    diagonal = max(math.hypot(width, height), 1.0)
    aspect_penalty = 0.0
    if width > height * 4 and candidate.element_type == "door":
        aspect_penalty = 0.35
    if height > width * 4 and candidate.element_type == "window":
        aspect_penalty = 0.2
    return (-1.0 if inside else 0.0) + edge / diagonal * 0.72 + center / diagonal * 0.28 + aspect_penalty


def _rotate_normalized(u: float, v: float, rotation: int) -> tuple[float, float]:
    normalized = rotation % 360
    if normalized == 90:
        return 1.0 - v, u
    if normalized == 180:
        return 1.0 - u, 1.0 - v
    if normalized == 270:
        return v, 1.0 - u
    return u, v


class ModelReviewTagService:
    def read_tags(self, *, project_id: str, floor_id: str) -> dict[str, Any]:
        crop = floor_plans_repository.current_crop(project_id, floor_id)
        if not crop:
            raise RuntimeError("Floor crop is not ready.")
        decoded = floor_plans_repository.decode_crop(crop)
        coordinates = decoded.get("coordinates") or {}
        rect = coordinates.get("original_rect") or {}
        crop_x = float(rect.get("x") or 0)
        crop_y = float(rect.get("y") or 0)
        crop_width = float(rect.get("width") or 0)
        crop_height = float(rect.get("height") or 0)
        if crop_width <= 0 or crop_height <= 0:
            raise RuntimeError("Floor crop coordinates are invalid.")

        document = floor_plans_repository.get_document(project_id, str(crop["document_id"]))
        if not document:
            raise RuntimeError("The source document is no longer available.")
        source_path = storage_service.ensure_local_file(storage_service.key_to_path(document["storage_key"]))
        if not source_path.exists():
            raise RuntimeError("The source document file is not available.")

        rotation = int(crop.get("rotation") or 0) % 360
        display_width = crop_height if rotation in {90, 270} else crop_width
        display_height = crop_width if rotation in {90, 270} else crop_height
        clip = fitz.Rect(crop_x, crop_y, crop_x + crop_width, crop_y + crop_height)
        page_number = int(crop.get("source_page_number") or 1)

        candidates: list[TagCandidate] = []
        with fitz.open(source_path) as pdf:
            if page_number < 1 or page_number > pdf.page_count:
                raise RuntimeError("The selected source page is not available.")
            page = pdf.load_page(page_number - 1)
            for word in page.get_text("words", clip=clip, sort=True):
                code = normalize_tag(str(word[4] or ""))
                element_type = tag_element_type(code)
                if not element_type:
                    continue
                center_x = (float(word[0]) + float(word[2])) / 2
                center_y = (float(word[1]) + float(word[3])) / 2
                u = min(1.0, max(0.0, (center_x - crop_x) / crop_width))
                v = min(1.0, max(0.0, (center_y - crop_y) / crop_height))
                display_u, display_v = _rotate_normalized(u, v, rotation)
                candidates.append(
                    TagCandidate(
                        code=code,
                        element_type=element_type,
                        x=display_u * display_width,
                        y=display_v * display_height,
                        source_bbox=(float(word[0]), float(word[1]), float(word[2]), float(word[3])),
                    )
                )

        elements = [
            item
            for item in model_review_repository.list_elements(project_id, floor_id)
            if item.get("element_type") in {"door", "window"} and not item.get("excluded")
        ]
        if not elements:
            return {"message": "No door or window results need tags", "matched": 0, "candidates": len(candidates)}

        matched = 0
        conflicts = 0
        review_version: int | None = None

        # Build all compatible pairs first. This avoids the earlier element-order bias
        # where the first opening could consume a better tag belonging to another item.
        pairs: list[tuple[float, int, int]] = []
        for element_index, element in enumerate(elements):
            geometry = element.get("geometry") or {}
            existing_code = normalize_tag(element.get("type_code"))
            for candidate_index, candidate in enumerate(candidates):
                if candidate.element_type != element.get("element_type"):
                    continue
                score = _candidate_score(candidate, geometry)
                if existing_code and existing_code == candidate.code:
                    score -= 0.55
                pairs.append((score, element_index, candidate_index))

        assigned_elements: set[int] = set()
        assigned_candidates: set[int] = set()
        assignments: list[tuple[dict, TagCandidate]] = []
        for score, element_index, candidate_index in sorted(pairs, key=lambda value: value[0]):
            if element_index in assigned_elements or candidate_index in assigned_candidates:
                continue
            element = elements[element_index]
            geometry = element.get("geometry") or {}
            width = max(float(geometry.get("width") or 0), 1.0)
            height = max(float(geometry.get("height") or 0), 1.0)
            absolute_tolerance = max(90.0, math.hypot(width, height) * 7.0, math.hypot(display_width, display_height) * 0.08)
            if score > 7.5 and _expanded_distance(candidates[candidate_index], geometry) > absolute_tolerance:
                continue
            assigned_elements.add(element_index)
            assigned_candidates.add(candidate_index)
            assignments.append((element, candidates[candidate_index]))

        if assignments:
            with get_connection() as connection:
                versions = workflow_repository.increment_floor_version(connection, project_id, floor_id, "element_version")
            element_version = int(versions["element_version"])
        else:
            element_version = 0

        for element, candidate in assignments:
            current_type = normalize_tag(element.get("type_code"))
            current_tag = normalize_tag(element.get("tag_text"))
            updates: dict[str, Any] = {}
            if current_tag != candidate.code:
                updates["tag_text"] = candidate.code
            conflict = bool(current_type and current_type != candidate.code and element.get("user_confirmed"))
            if (not current_type or not element.get("user_confirmed")) and current_type != candidate.code:
                updates["type_code"] = candidate.code
            if conflict:
                conflicts += 1
                if review_version is None:
                    with get_connection() as connection:
                        values = workflow_repository.increment_floor_version(connection, project_id, floor_id, "review_version")
                    review_version = int(values["review_version"])
                with get_connection() as connection:
                    workflow_repository.upsert_review_issue(
                        connection,
                        project_id=project_id,
                        floor_id=floor_id,
                        entity_type="element",
                        entity_id=element["id"],
                        issue_type="conflicting_type_code",
                        title="Type code needs review",
                        detail=f"The drawing tag {candidate.code} conflicts with the confirmed type {current_type}.",
                        suggestion={"type_code": candidate.code, "source_bbox": list(candidate.source_bbox)},
                        source="drawing_note",
                        review_version=review_version,
                    )
            if updates:
                model_review_repository.update_element(
                    project_id,
                    floor_id,
                    element["id"],
                    updates,
                    element_version=element_version,
                    user_confirmed=element.get("user_confirmed"),
                )
            matched += 1

        return {
            "message": "Drawing tags ready",
            "matched": matched,
            "conflicts": conflicts,
            "candidates": len(candidates),
            "unmatched_candidates": [
                candidates[index].code
                for index in range(len(candidates))
                if index not in assigned_candidates
            ],
            "page_number": page_number,
        }

    def match_schedules(self, *, project_id: str, floor_id: str) -> dict[str, Any]:
        elements = [
            item
            for item in model_review_repository.list_elements(project_id, floor_id)
            if item.get("element_type") in {"door", "window"} and not item.get("excluded")
        ]
        explicit_entries = model_review_repository.list_schedule_entries(project_id)
        drawing_entries = self._drawing_entries(project_id)
        updates: list[dict[str, Any]] = []
        assignments: dict[str, str] = {}
        matched = 0

        for element in elements:
            code = normalize_tag(element.get("type_code") or element.get("tag_text"))
            if not code:
                continue
            candidates = [
                entry
                for entry in explicit_entries
                if entry.get("category") == element["element_type"]
                and normalize_tag((entry.get("data") or {}).get("type_code") or entry.get("entity_key")) == code
            ]
            source = "schedule"
            if candidates:
                entry = candidates[0]
                data = entry.get("data") or {}
                assigned_id = entry.get("id")
            else:
                data = drawing_entries.get((element["element_type"], code)) or {}
                source = "drawing_note"
                assigned_id = None
            if not data:
                continue
            for property_name, unit in PROPERTY_FIELDS:
                value = data.get(property_name)
                if value in (None, ""):
                    continue
                updates.append({
                    "element_id": element["id"],
                    "property_name": property_name,
                    "value": value,
                    "unit": unit,
                    "source": source,
                })
            if assigned_id:
                assignments[str(element["id"])] = str(assigned_id)
            matched += 1

        result = workflow_service.apply_generated_properties_bulk(
            project_id=project_id, floor_id=floor_id, updates=updates, created_by=None
        )
        assigned = 0
        if assignments:
            with get_connection() as connection:
                versions = workflow_repository.increment_floor_version(connection, project_id, floor_id, "element_version")
            assigned = model_review_repository.bulk_assign_schedule_entries(
                project_id, floor_id, assignments, element_version=int(versions["element_version"])
            )
        # Scale-based opening sizes and specification defaults are the final
        # automatic fallback. Keep low-confidence geometry in review; this
        # step enriches details but does not override the detector's status.
        fallback = self.reconcile_floor(
            project_id=project_id,
            floor_id=floor_id,
            auto_confirm=False,
        )
        completeness = self.completeness_audit(project_id=project_id)
        return {
            "message": "Schedule and drawing details matched",
            "matched": matched,
            "updated_properties": int(result.get("changed") or 0),
            "protected_values": int(result.get("protected") or 0),
            "assigned_schedules": assigned,
            "fallback_properties": int(fallback.get("updated_properties") or 0),
            "completeness": completeness,
            "jobs": [*(result.get("jobs") or []), *(fallback.get("jobs") or [])],
        }

    def completeness_audit(self, *, project_id: str) -> dict[str, Any]:
        """Compare optional schedule quantities with current tagged openings."""
        expected: dict[tuple[str, str], int] = {}
        known_types: set[tuple[str, str]] = set()
        entries = model_review_repository.list_schedule_entries(project_id)
        drawing_entries = self._drawing_entries(project_id)
        for entry in entries:
            category = str(entry.get("category") or "")
            data = entry.get("data") or {}
            code = normalize_tag(data.get("type_code") or entry.get("entity_key"))
            if category not in {"door", "window"} or not code:
                continue
            key = (category, code)
            known_types.add(key)
            quantity = data.get("quantity")
            if quantity not in (None, ""):
                try:
                    expected[key] = max(expected.get(key, 0), int(quantity))
                except (TypeError, ValueError):
                    pass
        for key, data in drawing_entries.items():
            known_types.add(key)
            quantity = data.get("quantity")
            if quantity not in (None, ""):
                try:
                    expected[key] = max(expected.get(key, 0), int(quantity))
                except (TypeError, ValueError):
                    pass

        detected: dict[tuple[str, str], int] = {}
        for floor in model_review_repository.floor_rows(project_id):
            for element in model_review_repository.list_elements(
                project_id, str(floor["id"])
            ):
                category = str(element.get("element_type") or "")
                if category not in {"door", "window"} or element.get("excluded"):
                    continue
                code = normalize_tag(element.get("type_code") or element.get("tag_text"))
                if not code:
                    continue
                key = (category, code)
                detected[key] = detected.get(key, 0) + 1

        missing = [
            {
                "element_type": key[0],
                "type_code": key[1],
                "expected": quantity,
                "detected": detected.get(key, 0),
                "missing": max(0, quantity - detected.get(key, 0)),
            }
            for key, quantity in sorted(expected.items())
            if detected.get(key, 0) < quantity
        ]
        return {
            "schedule_quantities_available": bool(expected),
            "expected_total": sum(expected.values()),
            "detected_scheduled_total": sum(
                min(detected.get(key, 0), quantity)
                for key, quantity in expected.items()
            ),
            "known_types": [
                {"element_type": key[0], "type_code": key[1]}
                for key in sorted(known_types)
            ],
            "missing": missing,
            "complete": bool(expected) and not missing,
        }

    def _measurement_context(self, project_id: str, floor_id: str) -> dict[str, float | None]:
        with get_connection() as connection:
            row = connection.execute(
                """
                SELECT f.wall_height_mm, p.default_wall_height_mm,
                       c.mm_per_pixel
                FROM floors f
                JOIN projects p ON p.id=f.project_id
                LEFT JOIN calibrations c ON c.id=(
                  SELECT c2.id FROM calibrations c2
                  WHERE c2.project_id=f.project_id AND c2.floor_id=f.id
                    AND c2.status IN ('confirmed','calibrated','needs_review')
                  ORDER BY c2.scale_version DESC, c2.updated_at DESC LIMIT 1
                )
                WHERE f.project_id=? AND f.id=?
                """,
                (project_id, floor_id),
            ).fetchone()
        if not row:
            return {"mm_per_pixel": None, "wall_height_mm": None}
        return {
            "mm_per_pixel": float(row["mm_per_pixel"]) if row["mm_per_pixel"] not in (None, "") else None,
            "wall_height_mm": float(row["wall_height_mm"] or row["default_wall_height_mm"] or 2700),
        }

    @staticmethod
    def _pixel_width_mm(element: dict[str, Any], mm_per_pixel: float | None) -> float | None:
        if not mm_per_pixel or mm_per_pixel <= 0:
            return None
        geometry = element.get("geometry") or {}
        width = abs(float(geometry.get("width") or 0))
        height = abs(float(geometry.get("height") or 0))
        pixel_span = max(width, height)
        if pixel_span <= 0:
            return None
        value = pixel_span * mm_per_pixel
        # Opening widths are normally reported in practical 5 mm increments.
        return max(100.0, round(value / 5.0) * 5.0)

    @staticmethod
    def _default_height_mm(element_type: str, wall_height_mm: float | None) -> float | None:
        if not wall_height_mm or wall_height_mm <= 0:
            return None
        if element_type == "door":
            return round(min(2100.0, wall_height_mm * 0.79) / 5.0) * 5.0
        if element_type == "window":
            return round(min(1750.0, wall_height_mm * 0.65) / 5.0) * 5.0
        return None

    def _specification_defaults(self, project_id: str) -> dict[str, Any]:
        defaults: dict[str, Any] = {}
        with get_connection() as connection:
            rows = connection.execute(
                "SELECT data_json FROM schedule_entries WHERE project_id=? AND category='specification' ORDER BY source_priority DESC, created_at",
                (project_id,),
            ).fetchall()
        from app.workflow.repo_base import loads
        for row in rows:
            data = loads(row["data_json"]) or {}
            if not isinstance(data, dict):
                continue
            for key in ("door_material", "window_material", "frame_material", "door_window_materials", "glazing", "glass_type", "joinery_finish", "paint_joinery", "finish"):
                if defaults.get(key) in (None, "") and data.get(key) not in (None, ""):
                    defaults[key] = data[key]
        return defaults

    def reconcile_floor(self, *, project_id: str, floor_id: str, auto_confirm: bool = True) -> dict[str, Any]:
        """Fill missing canonical values using one bulk enrichment write."""
        context = self._measurement_context(project_id, floor_id)
        specification = self._specification_defaults(project_id)
        elements = [
            item for item in model_review_repository.list_elements(project_id, floor_id)
            if item.get("element_type") in {"door", "window"} and not item.get("excluded")
        ]
        updates: list[dict[str, Any]] = []
        for element in elements:
            resolved = element.get("resolved_data") or {}
            element_type = str(element.get("element_type") or "")
            fallbacks: list[tuple[str, Any, str, str | None]] = []
            if resolved.get("width_mm") in (None, ""):
                measured = self._pixel_width_mm(element, context.get("mm_per_pixel"))
                if measured is not None:
                    fallbacks.append(("width_mm", measured, "calculated", "mm"))
            if resolved.get("height_mm") in (None, ""):
                estimated = self._default_height_mm(element_type, context.get("wall_height_mm"))
                if estimated is not None:
                    fallbacks.append(("height_mm", estimated, "default", "mm"))
            if resolved.get("material") in (None, ""):
                material = specification.get("door_material") if element_type == "door" else specification.get("window_material")
                material = material or specification.get("frame_material") or specification.get("door_window_materials")
                if material not in (None, ""):
                    fallbacks.append(("material", material, "specification", None))
            if resolved.get("frame_material") in (None, ""):
                frame = specification.get("frame_material") or specification.get("door_window_materials")
                if frame not in (None, ""):
                    fallbacks.append(("frame_material", frame, "specification", None))
            if element_type == "window" and resolved.get("glass_type") in (None, ""):
                glass = specification.get("glass_type") or specification.get("glazing")
                if glass not in (None, ""):
                    fallbacks.append(("glass_type", glass, "specification", None))
            if resolved.get("finish") in (None, ""):
                finish = specification.get("joinery_finish") or specification.get("paint_joinery") or specification.get("finish")
                if finish not in (None, ""):
                    fallbacks.append(("finish", finish, "specification", None))
            for property_name, value, source, unit in fallbacks:
                updates.append({
                    "element_id": element["id"], "property_name": property_name,
                    "value": value, "source": source, "unit": unit,
                })

        result = workflow_service.apply_generated_properties_bulk(
            project_id=project_id, floor_id=floor_id, updates=updates, created_by=None
        )
        auto_confirmed = 0
        if auto_confirm:
            refreshed = [
                item for item in model_review_repository.list_elements(project_id, floor_id)
                if item.get("element_type") in {"door", "window"} and not item.get("excluded")
            ]
            complete_ids = [
                str(item["id"]) for item in refreshed
                if item.get("status") != "confirmed"
                and bool((item.get("type_code") or item.get("tag_text")))
                and (item.get("resolved_data") or {}).get("width_mm") not in (None, "")
                and (item.get("resolved_data") or {}).get("height_mm") not in (None, "")
            ]
            if complete_ids:
                with get_connection() as connection:
                    versions = workflow_repository.increment_floor_version(connection, project_id, floor_id, "element_version")
                auto_confirmed = len(model_review_repository.confirm_elements(
                    project_id, floor_id, complete_ids, element_version=int(versions["element_version"])
                ))
        return {
            "updated_properties": int(result.get("changed") or 0),
            "protected_values": int(result.get("protected") or 0),
            "auto_confirmed": auto_confirmed,
            "jobs": result.get("jobs") or [],
        }

    def ensure_floor_details(self, *, project_id: str, floor_id: str) -> dict[str, Any]:
        """Resolve drawing tags and schedule/detail values without rerunning detection."""
        elements = [
            item for item in model_review_repository.list_elements(project_id, floor_id)
            if item.get("element_type") in {"door", "window"} and not item.get("excluded")
        ]
        if not elements:
            return {"matched_tags": 0, "matched_details": 0}
        needs_tags = any(not item.get("tag_text") or not item.get("type_code") for item in elements)
        needs_details = any(
            any((item.get("resolved_data") or {}).get(field) in (None, "") for field in ("width_mm", "height_mm"))
            for item in elements
        )
        tag_result = {"matched": 0}
        detail_result = {"matched": 0}
        if needs_tags:
            tag_result = self.read_tags(project_id=project_id, floor_id=floor_id)
        if needs_tags or needs_details:
            detail_result = self.match_schedules(project_id=project_id, floor_id=floor_id)
        reconciliation = self.reconcile_floor(project_id=project_id, floor_id=floor_id, auto_confirm=True)
        return {
            "matched_tags": int(tag_result.get("matched") or 0),
            "matched_details": int(detail_result.get("matched") or 0),
            **reconciliation,
        }

    @staticmethod
    def _drawing_entries(project_id: str) -> dict[tuple[str, str], dict[str, Any]]:
        records = pdf_upload_repository.list_extraction_records(project_id)
        result: dict[tuple[str, str], dict[str, Any]] = {}
        for record in records:
            extraction_type = str(record.get("extraction_type") or "")
            if extraction_type not in {"door", "window"}:
                continue
            data = record.get("data") or {}
            code = normalize_tag(data.get("type_code"))
            if not code:
                continue
            key = (extraction_type, code)
            current = result.get(key)
            current_score = sum(value not in (None, "") for value in (current or {}).values())
            incoming_score = sum(value not in (None, "") for value in data.values())
            if current is None or incoming_score > current_score:
                result[key] = data
        return result


model_review_tag_service = ModelReviewTagService()
