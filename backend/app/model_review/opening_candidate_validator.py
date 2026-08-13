from __future__ import annotations

import math
from typing import Any

from app.core.config import settings
from app.model_review.prediction_processor import ProcessedPrediction


class OpeningCandidateValidator:
    """Reject implausible tiled door/window boxes while retaining small symbols."""

    def validate(
        self,
        candidates: list[ProcessedPrediction],
        *,
        seed_walls: list[dict[str, Any]],
        crop_width: float,
        crop_height: float,
    ) -> list[ProcessedPrediction]:
        wall_boxes = [
            self._bounds(item.get("geometry") or {})
            for item in seed_walls
            if self._bounds(item.get("geometry") or {}) is not None
        ]
        output: list[ProcessedPrediction] = []
        for candidate in candidates:
            bounds = self._bounds(candidate.geometry)
            if bounds is None:
                continue
            x1, y1, x2, y2 = bounds
            width, height = x2 - x1, y2 - y1
            major, minor = max(width, height), min(width, height)
            if major < settings.opening_recovery_min_size or minor <= 0:
                continue
            if major / minor > settings.opening_recovery_max_aspect_ratio:
                continue
            if width * height > crop_width * crop_height * 0.08:
                continue
            border = settings.wall_recovery_border_tolerance
            if (
                x1 <= border
                or y1 <= border
                or x2 >= crop_width - border
                or y2 >= crop_height - border
            ) and candidate.confidence < settings.opening_recovery_border_confidence:
                continue
            near_wall = any(
                self._box_distance(bounds, wall) <= max(
                    settings.opening_recovery_wall_distance,
                    major * settings.opening_recovery_wall_distance_factor,
                )
                for wall in wall_boxes
                if wall is not None
            )
            if not near_wall and candidate.confidence < settings.opening_recovery_independent_confidence:
                continue
            output.append(candidate)
        return output

    @staticmethod
    def _bounds(
        geometry: dict[str, Any],
    ) -> tuple[float, float, float, float] | None:
        try:
            x = float(geometry.get("x") or 0)
            y = float(geometry.get("y") or 0)
            width = float(geometry.get("width") or 0)
            height = float(geometry.get("height") or 0)
        except (TypeError, ValueError):
            return None
        if (
            not all(math.isfinite(value) for value in (x, y, width, height))
            or width <= 0
            or height <= 0
        ):
            return None
        return x, y, x + width, y + height

    @staticmethod
    def _box_distance(
        first: tuple[float, float, float, float],
        second: tuple[float, float, float, float],
    ) -> float:
        ax1, ay1, ax2, ay2 = first
        bx1, by1, bx2, by2 = second
        dx = max(bx1 - ax2, ax1 - bx2, 0.0)
        dy = max(by1 - ay2, ay1 - by2, 0.0)
        return math.hypot(dx, dy)


opening_candidate_validator = OpeningCandidateValidator()
