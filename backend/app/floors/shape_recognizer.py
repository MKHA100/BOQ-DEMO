from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterable

from shapely.geometry import Polygon


@dataclass(frozen=True)
class ShapeRecognition:
    shape_type: str
    confidence: float
    corner_count: int
    rectangularity: float


class RoomShapeRecognizer:
    """Classify architectural room polygons after basic cleanup.

    Rectangularity is measured against the minimum rotated rectangle rather
    than only the axis-aligned bounding box. This lets slightly rotated plans
    and noisy model contours still resolve to four architectural corners.
    """

    def recognize(self, polygon: Polygon, points: Iterable[dict[str, float]] | None = None) -> ShapeRecognition:
        if polygon.is_empty:
            return ShapeRecognition("invalid", 0.0, 0, 0.0)
        source = list(points or [])
        corners = len(source) if source else max(0, len(list(polygon.exterior.coords)) - 1)
        rotated = polygon.minimum_rotated_rectangle
        rotated_area = max(rotated.area, 1e-9)
        rectangularity = min(1.0, float(polygon.area / rotated_area))
        convexity = float(polygon.area / max(polygon.convex_hull.area, 1e-9))
        if polygon.interiors:
            return ShapeRecognition("irregular", 0.65, corners, rectangularity)
        if rectangularity >= 0.94 and convexity >= 0.96:
            return ShapeRecognition("rectangle", min(0.995, (rectangularity + convexity) / 2), corners, rectangularity)
        if corners == 4 and convexity >= 0.91:
            return ShapeRecognition("trapezium", min(0.96, convexity), corners, rectangularity)
        if corners in {5, 6} and convexity < 0.94:
            return ShapeRecognition("l_shape", min(0.93, 1.0 - abs(corners - 6) * 0.08), corners, rectangularity)
        if corners in {7, 8} and convexity < 0.91:
            return ShapeRecognition("u_shape", 0.84, corners, rectangularity)
        if corners > 12:
            return ShapeRecognition("irregular", 0.78, corners, rectangularity)
        return ShapeRecognition("polygon", 0.72, corners, rectangularity)

    @staticmethod
    def angle_degrees(first: tuple[float, float], middle: tuple[float, float], last: tuple[float, float]) -> float:
        a = (first[0] - middle[0], first[1] - middle[1])
        b = (last[0] - middle[0], last[1] - middle[1])
        denom = max(math.hypot(*a) * math.hypot(*b), 1e-9)
        value = max(-1.0, min(1.0, (a[0] * b[0] + a[1] * b[1]) / denom))
        return math.degrees(math.acos(value))


room_shape_recognizer = RoomShapeRecognizer()
