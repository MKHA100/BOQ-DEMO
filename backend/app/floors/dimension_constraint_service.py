from __future__ import annotations

from typing import Any

from shapely.geometry import Point

from app.floors.polygon_builder import room_polygon_builder


class DimensionConstraintService:
    """Match printed drawing evidence to one room and verify it with scale."""

    evidence_tolerance = 0.12
    correction_tolerance_percent = 8.0

    def apply(
        self,
        points: list[dict[str, float]],
        observations: list[dict[str, Any]],
        mm_per_pixel: float,
        *,
        preferred_width_mm: float | None = None,
        preferred_length_mm: float | None = None,
        preferred_source: str | None = None,
    ) -> dict[str, Any]:
        return self.match(
            points,
            observations,
            mm_per_pixel,
            preferred_width_mm=preferred_width_mm,
            preferred_length_mm=preferred_length_mm,
            preferred_source=preferred_source,
        )

    def match(
        self,
        points: list[dict[str, float]],
        observations: list[dict[str, Any]],
        mm_per_pixel: float,
        *,
        preferred_width_mm: float | None = None,
        preferred_length_mm: float | None = None,
        preferred_source: str | None = None,
    ) -> dict[str, Any]:
        polygon = room_polygon_builder.points_to_polygon(points)
        if polygon.is_empty:
            return {
                "points": points,
                "printed_width_mm": None,
                "printed_length_mm": None,
                "difference_percent": None,
                "dimension_status": "unknown",
                "dimension_source": "unknown",
            }

        width_px, length_px = room_polygon_builder.oriented_dimensions(polygon)
        near = [item for item in observations if self._near_room(item, polygon)]
        candidates: list[tuple[float, str, float, dict[str, Any]]] = []
        for item in near:
            try:
                value = float(item.get("value_mm") or 0)
            except (TypeError, ValueError):
                continue
            if value <= 0:
                continue
            orientation = str(item.get("orientation") or "").lower()
            if orientation not in {"vertical", "horizontal"}:
                continue
            if mm_per_pixel > 0:
                pixels = width_px if orientation == "vertical" else length_px
                predicted = pixels * mm_per_pixel
                difference = abs(predicted - value) / max(value, 1.0) * 100
            else:
                # Printed drawing evidence remains useful before calibration.
                # Infinity keeps the sort stable without pretending that a
                # scale-to-drawing comparison has already been performed.
                difference = float("inf")
            candidates.append((difference, orientation, value, item))
        candidates.sort(key=lambda item: (item[0], -float(item[3].get("confidence") or 0)))

        vertical = next((item for item in candidates if item[1] == "vertical"), None)
        horizontal = next((item for item in candidates if item[1] == "horizontal"), None)
        width_evidence = self._preferred_evidence(preferred_width_mm, candidates)
        length_evidence = self._preferred_evidence(preferred_length_mm, candidates)
        if width_evidence is not None:
            vertical = min(
                (item for item in candidates if item[2] == width_evidence),
                default=vertical,
                key=lambda item: item[0],
            )
        if length_evidence is not None:
            horizontal = min(
                (item for item in candidates if item[2] == length_evidence),
                default=horizontal,
                key=lambda item: item[0],
            )

        printed_width = width_evidence if width_evidence is not None else (vertical[2] if vertical else None)
        printed_length = length_evidence if length_evidence is not None else (horizontal[2] if horizontal else None)
        vertical_difference = (
            abs(width_px * mm_per_pixel - printed_width) / max(printed_width, 1.0) * 100
            if printed_width is not None and mm_per_pixel > 0
            else None
        )
        horizontal_difference = (
            abs(length_px * mm_per_pixel - printed_length) / max(printed_length, 1.0) * 100
            if printed_length is not None and mm_per_pixel > 0
            else None
        )
        target_width = (
            printed_width / mm_per_pixel
            if printed_width is not None and vertical_difference is not None and vertical_difference <= self.correction_tolerance_percent
            else None
        )
        target_length = (
            printed_length / mm_per_pixel
            if printed_length is not None and horizontal_difference is not None and horizontal_difference <= self.correction_tolerance_percent
            else None
        )
        corrected = room_polygon_builder.correct_rectangular_dimensions(
            points,
            target_width_px=target_width,
            target_length_px=target_length,
            max_change_ratio=0.08,
        ) if mm_per_pixel > 0 else points
        diffs = [
            value
            for value in (vertical_difference, horizontal_difference)
            if value is not None
        ]
        status = (
            "exact"
            if printed_width is not None and printed_length is not None
            else "partial"
            if printed_width is not None or printed_length is not None
            else "unknown"
        )
        source = (
            "llm_verified"
            if preferred_source and preferred_source.startswith("llm") and status != "unknown"
            else "drawing"
            if status != "unknown"
            else "unknown"
        )
        return {
            "points": corrected,
            "printed_width_mm": printed_width,
            "printed_length_mm": printed_length,
            "difference_percent": sum(diffs) / len(diffs) if diffs else None,
            "dimension_status": status,
            "dimension_source": source,
        }

    def _preferred_evidence(
        self, value: float | None, candidates: list[tuple[float, str, float, dict[str, Any]]]
    ) -> float | None:
        if value is None:
            return None
        try:
            expected = float(value)
        except (TypeError, ValueError):
            return None
        for _, _, actual, _ in candidates:
            if abs(actual - expected) / max(actual, 1.0) <= self.evidence_tolerance:
                return actual
        return None

    @staticmethod
    def _near_room(item: dict[str, Any], polygon: Any) -> bool:
        a, b = item.get("point_a") or {}, item.get("point_b") or {}
        try:
            point = Point(
                (float(a["x"]) + float(b["x"])) / 2,
                (float(a["y"]) + float(b["y"])) / 2,
            )
        except (KeyError, TypeError, ValueError):
            # Evidence without coordinates remains usable for a conservative
            # floor-level match, particularly on raster-only drawings.
            return True
        span = max(polygon.bounds[2] - polygon.bounds[0], polygon.bounds[3] - polygon.bounds[1], 1.0)
        return polygon.buffer(span * 0.35).contains(point)


dimension_constraint_service = DimensionConstraintService()

__all__ = ["DimensionConstraintService", "dimension_constraint_service"]
