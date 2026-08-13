from __future__ import annotations

from typing import Any

from shapely.geometry import Point, Polygon

from app.floors.llm_room_schema import FloorRoomInterpretation, RoomInterpretation
from app.floors.polygon_builder import room_polygon_builder
from app.floors.room_semantics import room_semantics


class RoomResultValidator:
    """Validate semantic output against supplied, coordinate-grounded evidence."""

    dimension_tolerance = 0.12
    minimum_envelope_overlap = 0.65
    maximum_envelope_ratio = 0.72
    duplicate_iou = 0.86

    def validate(
        self,
        response: FloorRoomInterpretation | dict[str, Any],
        context: dict[str, Any],
    ) -> dict[str, Any]:
        parsed = (
            response
            if isinstance(response, FloorRoomInterpretation)
            else FloorRoomInterpretation.model_validate(response)
        )
        floor_id = str(context.get("floor_id") or "")
        if parsed.floor_id != floor_id:
            raise ValueError("Interpretation floor_id does not match the selected floor.")

        suggestion_map = {
            str(item.get("id")): item
            for item in context.get("room_suggestions") or []
            if item.get("id")
        }
        valid_wall_ids = {
            str(item.get("id")) for item in context.get("walls") or [] if item.get("id")
        }
        valid_door_ids = {
            str(item.get("id"))
            for item in context.get("openings") or []
            if item.get("id") and str(item.get("type") or item.get("element_type") or "").lower() == "door"
        }
        envelope = room_polygon_builder.points_to_polygon(
            (context.get("building_envelope") or {}).get("points") or []
        )
        observations = context.get("dimensions") or []

        accepted: list[dict[str, Any]] = []
        rejected: list[dict[str, Any]] = []
        warnings = list(parsed.warnings)
        used_ids: set[str] = set()
        accepted_polygons: list[tuple[str, Polygon]] = []
        wall_cells = [
            room_polygon_builder.points_to_polygon(
                (item.get("wall_corrected_polygon") or {}).get("points") or []
            )
            for item in context.get("rooms") or []
        ]
        wall_cells = [item for item in wall_cells if not item.is_empty]

        for value in parsed.rooms:
            item = value.model_copy(deep=True)
            item_warnings = list(item.warnings)
            suggestion = suggestion_map.get(item.room_suggestion_id)
            reason: str | None = None
            polygon = Polygon()
            if item.room_suggestion_id in used_ids:
                reason = "duplicate room_suggestion_id"
            elif suggestion is None:
                reason = "unknown room_suggestion_id"
            else:
                polygon = room_polygon_builder.points_to_polygon(
                    (suggestion.get("polygon") or {}).get("points")
                    or suggestion.get("points")
                    or []
                )
                if polygon.is_empty:
                    reason = "room suggestion has no valid polygon"
                elif not envelope.is_empty:
                    overlap = polygon.intersection(envelope).area / max(polygon.area, 1e-9)
                    ratio = polygon.area / max(envelope.area, 1e-9)
                    if overlap < self.minimum_envelope_overlap:
                        reason = "room lies outside the building envelope"
                    elif ratio > self.maximum_envelope_ratio and len(suggestion_map) > 1:
                        reason = "room resembles a large background mask"
                if reason is None:
                    covered_cells = sum(
                        polygon.intersection(cell).area / max(cell.area, 1e-9) >= 0.20
                        for cell in wall_cells
                    )
                    if covered_cells > 1:
                        reason = "model suggestion covers several separate wall-bounded rooms"
                if reason is None:
                    for other_id, other in accepted_polygons:
                        union = polygon.union(other).area
                        iou = polygon.intersection(other).area / union if union else 0.0
                        if iou >= self.duplicate_iou:
                            reason = f"room duplicates suggestion {other_id}"
                            break
                if reason is None:
                    accepted_polygons.append((item.room_suggestion_id, polygon))

            invalid_walls = sorted(set(item.surrounding_wall_ids) - valid_wall_ids)
            if invalid_walls:
                item.surrounding_wall_ids = [
                    wall_id for wall_id in item.surrounding_wall_ids if wall_id in valid_wall_ids
                ]
                item_warnings.append("Unsupported surrounding wall references were removed.")
            invalid_doors = sorted(set(item.door_ids) - valid_door_ids)
            if invalid_doors:
                item.door_ids = [door_id for door_id in item.door_ids if door_id in valid_door_ids]
                item_warnings.append("Unsupported door references were removed.")

            width = self._ground_dimension(item.printed_width_mm, observations, polygon)
            length = self._ground_dimension(item.printed_length_mm, observations, polygon)
            if item.printed_width_mm is not None and width is None:
                item_warnings.append("Unverified printed width was removed.")
            if item.printed_length_mm is not None and length is None:
                item_warnings.append("Unverified printed length was removed.")
            item.printed_width_mm = width
            item.printed_length_mm = length
            item.dimension_status = (
                "exact" if width is not None and length is not None
                else "partial" if width is not None or length is not None
                else "unknown"
            )

            # The LLM may recognize a label correctly but return an
            # inconsistent area type. Ground the classification in the room
            # name/type so, for example, a Bedroom can never become a stair.
            raw_label = " ".join(
                value for value in (str(item.room_name or ""), str(item.room_type or "")) if value
            )
            known_labels = room_semantics.match_known_labels(raw_label)
            if known_labels:
                semantic = room_semantics.classify(known_labels)
                item.room_name = str(semantic.get("name") or "")
                item.room_type = str(semantic.get("room_type") or item.room_name)
            else:
                # Keep a genuine uncommon printed name as a fallback, but
                # strip dimensions, window/door tags and drawing symbols.
                fallback = room_semantics.clean(item.room_name) or room_semantics.clean(item.room_type)
                normalized = room_semantics.normalize(fallback) if fallback else ""
                item.room_name = normalized
                item.room_type = normalized
                semantic = room_semantics.classify(normalized)
                if not normalized:
                    item_warnings.append("Drawing annotations were removed from the room label.")
            if semantic.get("name"):
                expected_kind = str(semantic.get("space_kind") or "internal")
                expected_type = str(semantic.get("semantic_type") or "internal_room")
                if item.area_type != expected_kind:
                    item_warnings.append("Area type was corrected from the recognized room label.")
                item.area_type = expected_kind  # type: ignore[assignment]
                if expected_type in {
                    "internal_room", "external_area", "open_plan", "circulation",
                    "stair", "void", "shaft", "balcony", "verandah",
                }:
                    item.semantic_type = expected_type  # type: ignore[assignment]
            item.warnings = list(dict.fromkeys(item_warnings))

            if reason:
                rejected.append(
                    {
                        "room_suggestion_id": item.room_suggestion_id,
                        "reason": reason,
                        "validation_status": "rejected",
                    }
                )
                warnings.append(f"{item.room_suggestion_id}: {reason}")
                continue
            used_ids.add(item.room_suggestion_id)
            saved = item.model_dump(mode="json")
            saved["validation_status"] = "validated"
            accepted.append(saved)

        validated = FloorRoomInterpretation(
            floor_id=parsed.floor_id,
            rooms=[
                RoomInterpretation.model_validate(
                    {key: value for key, value in item.items() if key != "validation_status"}
                )
                for item in accepted
            ],
            warnings=list(dict.fromkeys(warnings)),
        )
        return {
            "response": validated.model_dump(mode="json"),
            "rooms": accepted,
            "rejected": rejected,
            "warnings": list(dict.fromkeys(warnings)),
        }

    def _ground_dimension(
        self,
        value: float | None,
        observations: list[dict[str, Any]],
        polygon: Polygon | None = None,
    ) -> float | None:
        if value is None:
            return None
        candidate = float(value)
        if candidate <= 0:
            return None
        for observation in observations:
            try:
                actual = float(observation.get("value_mm") or 0)
            except (TypeError, ValueError):
                continue
            if (
                actual > 0
                and abs(actual - candidate) / actual <= self.dimension_tolerance
                and self._observation_near_polygon(observation, polygon)
            ):
                # Save the exact drawing observation, not a rounded model echo.
                return actual
        return None

    @staticmethod
    def _observation_near_polygon(
        observation: dict[str, Any], polygon: Polygon | None
    ) -> bool:
        if polygon is None or polygon.is_empty:
            return True
        first, second = observation.get("point_a") or {}, observation.get("point_b") or {}
        try:
            midpoint = Point(
                (float(first["x"]) + float(second["x"])) / 2,
                (float(first["y"]) + float(second["y"])) / 2,
            )
        except (KeyError, TypeError, ValueError):
            return True
        span = max(
            polygon.bounds[2] - polygon.bounds[0],
            polygon.bounds[3] - polygon.bounds[1],
            1.0,
        )
        return polygon.buffer(span * 0.35).contains(midpoint)


room_result_validator = RoomResultValidator()

__all__ = ["RoomResultValidator", "room_result_validator"]
