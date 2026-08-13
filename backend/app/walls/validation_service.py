from __future__ import annotations

import math
from typing import Any

from app.walls.geometry import (
    angle_difference_degrees,
    bbox_center,
    collinear_overlap,
    endpoints,
    line_length,
    normalize_line,
    parallel_distance,
    point_distance,
    point_line_distance,
    point_line_projection,
    segment_intersection,
)
from app.walls.rules import WallTopologyRules, topology_rules


class WallValidationService:
    """Validate a canonical wall network and return UI-ready warning records."""

    def validate(
        self,
        walls: list[dict[str, Any]],
        openings: list[dict[str, Any]] | None = None,
        drawing_width: float | None = None,
        drawing_height: float | None = None,
        rules: WallTopologyRules | dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        resolved_rules = topology_rules(
            drawing_width=drawing_width,
            drawing_height=drawing_height,
            typical_thickness_px=self._typical_thickness(walls),
            overrides=rules,
        )
        valid: list[dict[str, Any]] = []
        warnings: list[dict[str, Any]] = []

        for index, source in enumerate(walls):
            wall_id = str(source.get("id") or f"wall:{index}")
            line = normalize_line(source.get("centerline"))
            if line is None:
                warnings.append(
                    self._warning(
                        "invalid_centerline",
                        "error",
                        "Wall centerline is missing, zero-length or contains invalid coordinates.",
                        [wall_id],
                    )
                )
                continue
            item = dict(source)
            item["id"] = wall_id
            item["centerline"] = line
            valid.append(item)
            if line_length(line) < resolved_rules.minimum_wall_length_px:
                warnings.append(
                    self._warning(
                        "short_wall",
                        "error",
                        "Wall segment is too short to use reliably.",
                        [wall_id],
                    )
                )
            warnings.extend(
                self._outside_warnings(
                    item,
                    drawing_width=drawing_width,
                    drawing_height=drawing_height,
                    rules=resolved_rules,
                )
            )

        warnings.extend(self._pair_warnings(valid, resolved_rules))
        endpoint_warnings, connected_endpoints = self._endpoint_warnings(
            valid, openings or [], resolved_rules
        )
        warnings.extend(endpoint_warnings)
        warnings.extend(self._opening_warnings(valid, openings or [], resolved_rules))

        warnings = self._deduplicate_warnings(warnings)
        warnings_by_wall: dict[str, list[dict[str, Any]]] = {
            str(item["id"]): [] for item in valid
        }
        for warning in warnings:
            for wall_id in warning.get("wall_ids") or []:
                warnings_by_wall.setdefault(str(wall_id), []).append(warning)

        error_count = sum(item["severity"] == "error" for item in warnings)
        warning_count = sum(item["severity"] == "warning" for item in warnings)
        total_endpoints = len(valid) * 2
        summary = {
            "wall_count": len(valid),
            "invalid_wall_count": len(walls) - len(valid),
            "opening_count": len(openings or []),
            "error_count": error_count,
            "warning_count": warning_count,
            "connected_endpoint_count": connected_endpoints,
            "unconnected_endpoint_count": sum(
                item["code"] == "unconnected_endpoint" for item in warnings
            ),
            "connection_ratio": round(connected_endpoints / total_endpoints, 4)
            if total_endpoints
            else 0.0,
            # Non-blocking endpoint notes are useful diagnostics, but they do
            # not make an otherwise usable wall network require user review.
            "requires_review": error_count > 0,
        }
        return {
            "is_valid": error_count == 0,
            "warnings_by_wall": warnings_by_wall,
            "warnings": warnings,
            "summary": summary,
            "rules": resolved_rules.as_dict(),
        }

    def _pair_warnings(
        self,
        walls: list[dict[str, Any]],
        rules: WallTopologyRules,
    ) -> list[dict[str, Any]]:
        warnings: list[dict[str, Any]] = []
        for first_index, first in enumerate(walls):
            for second in walls[first_index + 1 :]:
                angle = angle_difference_degrees(first["centerline"], second["centerline"])
                if angle <= rules.parallel_angle_degrees:
                    offset = parallel_distance(first["centerline"], second["centerline"])
                    overlap, _ = collinear_overlap(first["centerline"], second["centerline"])
                    overlap_ratio = overlap / max(
                        min(line_length(first["centerline"]), line_length(second["centerline"])),
                        1e-9,
                    )
                    if (
                        offset <= rules.duplicate_distance_px
                        and overlap_ratio >= rules.duplicate_overlap_ratio
                    ):
                        warnings.append(
                            self._warning(
                                "duplicate_wall",
                                "error",
                                "Two wall records describe the same wall segment.",
                                [str(first["id"]), str(second["id"])],
                            )
                        )
                    elif offset <= rules.collinear_distance_px and overlap > rules.intersection_tolerance_px:
                        warnings.append(
                            self._warning(
                                "overlapping_walls",
                                "error",
                                "Collinear wall segments overlap and should be merged.",
                                [str(first["id"]), str(second["id"])],
                            )
                        )
                    continue

                intersection = segment_intersection(
                    first["centerline"],
                    second["centerline"],
                    tolerance=rules.intersection_tolerance_px,
                )
                if intersection is None:
                    continue
                point, first_parameter, second_parameter = intersection
                first_margin = rules.intersection_tolerance_px / max(
                    line_length(first["centerline"]), 1.0
                )
                second_margin = rules.intersection_tolerance_px / max(
                    line_length(second["centerline"]), 1.0
                )
                if (
                    first_margin < first_parameter < 1.0 - first_margin
                    and second_margin < second_parameter < 1.0 - second_margin
                ):
                    warnings.append(
                        self._warning(
                            "unnoded_intersection",
                            "warning",
                            "Walls cross inside both segments; split them if separate editable pieces are required.",
                            [str(first["id"]), str(second["id"])],
                            point=point,
                        )
                    )
        return warnings

    def _endpoint_warnings(
        self,
        walls: list[dict[str, Any]],
        openings: list[dict[str, Any]],
        rules: WallTopologyRules,
    ) -> tuple[list[dict[str, Any]], int]:
        warnings: list[dict[str, Any]] = []
        connected_count = 0
        for wall_index, wall in enumerate(walls):
            for endpoint_name, point in zip(("start", "end"), endpoints(wall["centerline"])):
                if self._endpoint_is_opening_gap(point, openings, rules):
                    connected_count += 1
                    continue
                exact = False
                nearest: tuple[float, dict[str, float], str] | None = None
                for other_index, other in enumerate(walls):
                    if other_index == wall_index:
                        continue
                    projected, parameter = point_line_projection(
                        point, other["centerline"], clamp=True
                    )
                    distance = point_distance(point, projected)
                    if distance <= rules.intersection_tolerance_px:
                        exact = True
                        break
                    # A nearby point beyond either end is handled by the clamped
                    # projection as an endpoint-to-endpoint near miss.
                    if distance <= rules.endpoint_snap_px:
                        candidate = (distance, projected, str(other["id"]))
                        if nearest is None or candidate[0] < nearest[0]:
                            nearest = candidate
                if exact:
                    connected_count += 1
                    continue
                if nearest is not None:
                    warnings.append(
                        self._warning(
                            "near_miss_endpoint",
                            "error",
                            "Wall endpoint is close to another wall but is not connected.",
                            [str(wall["id"]), nearest[2]],
                            point=point,
                            endpoint=endpoint_name,
                            suggested_point=nearest[1],
                        )
                    )
                    continue
                severity = "error" if rules.block_on_unconnected else "warning"
                warnings.append(
                    self._warning(
                        "unconnected_endpoint",
                        severity,
                        "Wall endpoint is not connected to another wall.",
                        [str(wall["id"])],
                        point=point,
                        endpoint=endpoint_name,
                    )
                )
        return warnings, connected_count

    def _opening_warnings(
        self,
        walls: list[dict[str, Any]],
        openings: list[dict[str, Any]],
        rules: WallTopologyRules,
    ) -> list[dict[str, Any]]:
        warnings: list[dict[str, Any]] = []
        by_id = {str(item["id"]): item for item in walls}
        for index, opening in enumerate(openings):
            opening_id = str(opening.get("id") or f"opening:{index}")
            assigned_wall_id = str(opening.get("wall_id") or "")
            if assigned_wall_id and assigned_wall_id not in by_id:
                warnings.append(
                    self._warning(
                        "opening_wall_missing",
                        "error",
                        "Opening is assigned to a wall that no longer exists.",
                        [],
                        opening_id=opening_id,
                    )
                )
                continue
            geometry = opening.get("geometry") or {}
            try:
                center = bbox_center(geometry)
            except (TypeError, ValueError):
                warnings.append(
                    self._warning(
                        "invalid_opening_geometry",
                        "warning",
                        "Opening geometry is invalid and cannot be attached automatically.",
                        [assigned_wall_id] if assigned_wall_id else [],
                        opening_id=opening_id,
                    )
                )
                continue
            if not walls:
                warnings.append(
                    self._warning(
                        "opening_unattached",
                        "error",
                        "Opening cannot be attached because this floor has no walls.",
                        [],
                        opening_id=opening_id,
                    )
                )
                continue
            nearest = min(
                walls,
                key=lambda item: point_line_distance(center, item["centerline"]),
            )
            distance = point_line_distance(center, nearest["centerline"])
            attachment_distance = max(
                rules.opening_attachment_px,
                self._opening_extent(geometry) * 0.75,
            )
            if distance > attachment_distance:
                warnings.append(
                    self._warning(
                        "opening_unattached",
                        "error",
                        "Door or window is too far from every wall.",
                        [str(nearest["id"])],
                        opening_id=opening_id,
                    )
                )
        return warnings

    def _outside_warnings(
        self,
        wall: dict[str, Any],
        *,
        drawing_width: float | None,
        drawing_height: float | None,
        rules: WallTopologyRules,
    ) -> list[dict[str, Any]]:
        if not drawing_width or not drawing_height:
            return []
        width, height = float(drawing_width), float(drawing_height)
        margin = rules.drawing_margin_px
        for endpoint_name, point in zip(("start", "end"), endpoints(wall["centerline"])):
            if not (
                -margin <= point["x"] <= width + margin
                and -margin <= point["y"] <= height + margin
            ):
                return [
                    self._warning(
                        "wall_outside_drawing",
                        "warning",
                        "Wall extends outside the floor-plan drawing bounds.",
                        [str(wall["id"])],
                        point=point,
                        endpoint=endpoint_name,
                    )
                ]
        return []

    def _endpoint_is_opening_gap(
        self,
        point: dict[str, float],
        openings: list[dict[str, Any]],
        rules: WallTopologyRules,
    ) -> bool:
        padding = rules.opening_protection_padding_px + rules.endpoint_snap_px
        for opening in openings:
            rectangle = self._opening_rectangle(opening.get("geometry") or {}, padding)
            if rectangle is None:
                continue
            min_x, min_y, max_x, max_y = rectangle
            if min_x <= point["x"] <= max_x and min_y <= point["y"] <= max_y:
                return True
        return False

    @staticmethod
    def _opening_rectangle(
        geometry: dict[str, Any], padding: float
    ) -> tuple[float, float, float, float] | None:
        try:
            x = float(geometry.get("x") or 0)
            y = float(geometry.get("y") or 0)
            width = float(geometry.get("width") or 0)
            height = float(geometry.get("height") or 0)
        except (TypeError, ValueError):
            return None
        if width <= 0 or height <= 0:
            return None
        return x - padding, y - padding, x + width + padding, y + height + padding

    @staticmethod
    def _opening_extent(geometry: dict[str, Any]) -> float:
        try:
            return max(float(geometry.get("width") or 0), float(geometry.get("height") or 0))
        except (TypeError, ValueError):
            return 0.0

    @staticmethod
    def _typical_thickness(walls: list[dict[str, Any]]) -> float | None:
        values: list[float] = []
        for wall in walls:
            try:
                value = float(wall.get("detected_thickness_px") or 0)
            except (TypeError, ValueError):
                value = 0.0
            if value > 0 and math.isfinite(value):
                values.append(value)
        if not values:
            return None
        values.sort()
        middle = len(values) // 2
        return values[middle] if len(values) % 2 else (values[middle - 1] + values[middle]) / 2.0

    @staticmethod
    def _warning(
        code: str,
        severity: str,
        message: str,
        wall_ids: list[str],
        **details: Any,
    ) -> dict[str, Any]:
        return {
            "code": code,
            "severity": severity,
            "message": message,
            "wall_ids": [item for item in wall_ids if item],
            **details,
        }

    @staticmethod
    def _deduplicate_warnings(warnings: list[dict[str, Any]]) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        seen: set[tuple[Any, ...]] = set()
        for item in warnings:
            point = item.get("point") or {}
            key = (
                item.get("code"),
                tuple(sorted(item.get("wall_ids") or [])),
                item.get("endpoint"),
                item.get("opening_id"),
                round(float(point.get("x") or 0), 3),
                round(float(point.get("y") or 0), 3),
            )
            if key in seen:
                continue
            seen.add(key)
            result.append(item)
        return result


wall_validation_service = WallValidationService()
