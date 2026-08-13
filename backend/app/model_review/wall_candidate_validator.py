from __future__ import annotations

from dataclasses import dataclass
import math
from statistics import median
from typing import Any

from app.core.config import settings
from app.model_review.prediction_processor import ProcessedPrediction


@dataclass(frozen=True)
class _WallBox:
    x: float
    y: float
    width: float
    height: float

    @property
    def horizontal(self) -> bool:
        return self.width >= self.height

    @property
    def length(self) -> float:
        return max(self.width, self.height)

    @property
    def thickness(self) -> float:
        return min(self.width, self.height)

    @property
    def center(self) -> tuple[float, float]:
        return self.x + self.width / 2, self.y + self.height / 2

    @property
    def endpoints(self) -> tuple[tuple[float, float], tuple[float, float]]:
        cx, cy = self.center
        if self.horizontal:
            return (self.x, cy), (self.x + self.width, cy)
        return (cx, self.y), (cx, self.y + self.height)


class WallCandidateValidator:
    """Allow recovery only where it repairs an existing wall network."""

    def validate(
        self,
        candidates: list[ProcessedPrediction],
        *,
        seed_walls: list[dict[str, Any]],
        crop_width: float,
        crop_height: float,
    ) -> list[ProcessedPrediction]:
        seeds = [
            box
            for item in seed_walls
            if (box := self._box(item.get("geometry") or {})) is not None
        ]
        if not seeds:
            return []
        typical_thickness = median(item.thickness for item in seeds)
        candidate_boxes = [
            self._box(item.geometry)
            for item in candidates
        ]
        output: list[ProcessedPrediction] = []
        for index, candidate in enumerate(candidates):
            box = candidate_boxes[index]
            if box is None:
                continue
            if not self._valid_shape(box, typical_thickness, crop_width, crop_height):
                continue
            if self._repeated_line_pattern(index, box, candidate_boxes):
                continue
            if not self._connected_to_network(box, seeds):
                continue
            output.append(candidate)
        return output

    @staticmethod
    def _box(geometry: dict[str, Any]) -> _WallBox | None:
        try:
            values = (
                float(geometry.get("x") or 0),
                float(geometry.get("y") or 0),
                float(geometry.get("width") or 0),
                float(geometry.get("height") or 0),
            )
        except (TypeError, ValueError):
            return None
        if not all(math.isfinite(value) for value in values):
            return None
        x, y, width, height = values
        if width <= 0 or height <= 0:
            return None
        return _WallBox(x=x, y=y, width=width, height=height)

    @staticmethod
    def _valid_shape(
        box: _WallBox,
        typical_thickness: float,
        crop_width: float,
        crop_height: float,
    ) -> bool:
        if box.length < settings.wall_recovery_min_length:
            return False
        if box.length / max(box.thickness, 1e-6) < settings.wall_recovery_min_aspect_ratio:
            return False
        if not (
            typical_thickness * settings.wall_recovery_min_thickness_ratio
            <= box.thickness
            <= typical_thickness * settings.wall_recovery_max_thickness_ratio
        ):
            return False
        # A line exactly on the crop rectangle is commonly a page/crop border.
        border = settings.wall_recovery_border_tolerance
        on_vertical_border = box.x <= border or box.x + box.width >= crop_width - border
        on_horizontal_border = box.y <= border or box.y + box.height >= crop_height - border
        if box.length >= max(crop_width, crop_height) * 0.65 and (
            on_vertical_border or on_horizontal_border
        ):
            return False
        return True

    def _connected_to_network(
        self, candidate: _WallBox, seeds: list[_WallBox]
    ) -> bool:
        max_gap = max(
            settings.wall_recovery_max_gap,
            candidate.thickness * settings.wall_recovery_gap_thickness_factor,
        )
        same_axis_support = any(
            candidate.horizontal == seed.horizontal
            and self._parallel_offset(candidate, seed)
            <= max(candidate.thickness, seed.thickness) * 1.5
            and self._axis_gap(candidate, seed) <= max_gap
            for seed in seeds
        )
        if same_axis_support:
            return True
        # A new partition must attach at both ends. This blocks furniture,
        # dimensions and isolated stair/grid strokes from becoming walls.
        return all(
            any(self._point_box_distance(endpoint, seed) <= max_gap for seed in seeds)
            for endpoint in candidate.endpoints
        )

    @staticmethod
    def _repeated_line_pattern(
        index: int,
        candidate: _WallBox,
        boxes: list[_WallBox | None],
    ) -> bool:
        similar = 0
        cx, cy = candidate.center
        for other_index, other in enumerate(boxes):
            if other_index == index or other is None:
                continue
            if candidate.horizontal != other.horizontal:
                continue
            if abs(other.length - candidate.length) > candidate.length * 0.22:
                continue
            if abs(other.thickness - candidate.thickness) > candidate.thickness * 0.6:
                continue
            ox, oy = other.center
            across = abs(oy - cy) if candidate.horizontal else abs(ox - cx)
            along = abs(ox - cx) if candidate.horizontal else abs(oy - cy)
            if (
                candidate.thickness * 1.1
                <= across
                <= candidate.length * 1.25
                and along <= candidate.length * 0.25
            ):
                similar += 1
        return similar >= settings.wall_recovery_repeated_line_limit

    @staticmethod
    def _parallel_offset(first: _WallBox, second: _WallBox) -> float:
        a = first.center
        b = second.center
        return abs(a[1] - b[1]) if first.horizontal else abs(a[0] - b[0])

    @staticmethod
    def _axis_gap(first: _WallBox, second: _WallBox) -> float:
        if first.horizontal:
            return max(0.0, max(first.x, second.x) - min(first.x + first.width, second.x + second.width))
        return max(0.0, max(first.y, second.y) - min(first.y + first.height, second.y + second.height))

    @staticmethod
    def _point_box_distance(point: tuple[float, float], box: _WallBox) -> float:
        px, py = point
        dx = max(box.x - px, 0.0, px - (box.x + box.width))
        dy = max(box.y - py, 0.0, py - (box.y + box.height))
        return math.hypot(dx, dy)


wall_candidate_validator = WallCandidateValidator()
