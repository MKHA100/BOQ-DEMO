from __future__ import annotations

import math
from typing import Iterable

from shapely.geometry import Polygon

from app.core.config import settings
from app.floors.shape_recognizer import room_shape_recognizer


class PolygonRegularizer:
    def regularize(
        self,
        points: Iterable[dict[str, float]],
        *,
        force_rectangle: bool = False,
        preserve_curves: bool = True,
        wall_thickness_px: float | None = None,
    ) -> dict:
        original = self._dedupe(list(points), max(0.20, settings.room_min_edge_pixels * 0.10))
        if len(original) < 3:
            return {"points": original, "shape_type": "invalid", "confidence": 0.0, "changed": False}
        polygon = self._polygon(original)
        if polygon.is_empty:
            return {"points": original, "shape_type": "invalid", "confidence": 0.0, "changed": False}

        typical = max(float(wall_thickness_px or 0), 0.0)
        scale = math.sqrt(max(polygon.area, 1.0))
        tolerance = max(0.65, min(max(settings.room_min_edge_pixels, typical * 0.38), scale * 0.012))
        noise = min(max(0.45, typical * 0.10 if typical else tolerance * 0.45), 3.0)

        # Evaluate a few topology-preserving cleanup candidates. Architectural
        # room boundaries should not keep pixel-sized door-arc notches or model
        # stair-step noise along otherwise straight walls.
        geometry_candidates: list[Polygon] = [polygon]
        simplified = polygon.simplify(tolerance, preserve_topology=True)
        if isinstance(simplified, Polygon) and not simplified.is_empty:
            geometry_candidates.append(simplified)
        for candidate in (
            polygon.buffer(noise, join_style=2).buffer(-noise, join_style=2),
            polygon.buffer(-noise, join_style=2).buffer(noise, join_style=2),
        ):
            if isinstance(candidate, Polygon) and not candidate.is_empty and candidate.is_valid:
                change = abs(candidate.area - polygon.area) / max(polygon.area, 1e-9)
                if change <= 0.075:
                    geometry_candidates.append(candidate)

        ranked: list[tuple[int, float, Polygon, list[dict[str, float]]]] = []
        for geometry in geometry_candidates:
            candidate = self._points(geometry)
            candidate = self._dedupe(candidate, max(0.25, tolerance * 0.35))
            candidate = self._remove_short_noise(candidate, tolerance)
            candidate = self._remove_collinear(candidate)
            candidate = self._orthogonalize(candidate)
            candidate = self._remove_short_noise(candidate, tolerance)
            candidate = self._remove_collinear(candidate)
            candidate_polygon = self._polygon(candidate)
            if candidate_polygon.is_empty:
                continue
            area_change = abs(candidate_polygon.area - polygon.area) / max(polygon.area, 1e-9)
            ranked.append((len(candidate), area_change, candidate_polygon, candidate))

        if not ranked:
            candidate = original
            candidate_polygon = polygon
        else:
            # Prefer fewer real corners while strongly penalizing area drift.
            _, _, candidate_polygon, candidate = min(
                ranked,
                key=lambda item: (item[0] + item[1] * 120.0, item[1], item[0]),
            )

        recognition = room_shape_recognizer.recognize(candidate_polygon, candidate)
        rectangle = candidate_polygon.minimum_rotated_rectangle
        rectangle_difference = abs(rectangle.area - candidate_polygon.area) / max(candidate_polygon.area, 1e-9)
        convexity = candidate_polygon.area / max(candidate_polygon.convex_hull.area, 1e-9)

        # A noisy rectangular room may initially have many vertices. Vertex
        # count must not prevent it from being reduced to four architectural
        # corners when the area and convexity clearly support a rectangle.
        should_rectangle = force_rectangle or (
            recognition.rectangularity >= max(0.88, settings.room_rectangle_confidence - 0.08)
            and rectangle_difference <= 0.12
            and convexity >= 0.93
        )
        if should_rectangle:
            rectangular = self.make_rectangle(candidate)
            rectangular_polygon = self._polygon(rectangular)
            area_change = abs(rectangular_polygon.area - polygon.area) / max(polygon.area, 1e-9)
            if force_rectangle or area_change <= 0.13:
                candidate = rectangular
                candidate_polygon = rectangular_polygon
                recognition = room_shape_recognizer.recognize(candidate_polygon, candidate)

        # Genuinely irregular shapes retain necessary corners, but never keep
        # hundreds of nearly collinear points on straight wall faces.
        if len(candidate) > 32:
            reduced = candidate_polygon.simplify(tolerance * 1.6, preserve_topology=True)
            if isinstance(reduced, Polygon) and not reduced.is_empty:
                candidate = self._remove_collinear(
                    self._remove_short_noise(self._dedupe(self._points(reduced), tolerance * 0.6), tolerance)
                )
                candidate_polygon = self._polygon(candidate)
                recognition = room_shape_recognizer.recognize(candidate_polygon, candidate)

        area_change_percent = abs(candidate_polygon.area - polygon.area) / max(polygon.area, 1e-9) * 100.0
        return {
            "points": [{"x": round(float(item["x"]), 4), "y": round(float(item["y"]), 4)} for item in candidate],
            "shape_type": recognition.shape_type,
            "confidence": recognition.confidence,
            "rectangularity": recognition.rectangularity,
            "changed": self._signature(original) != self._signature(candidate),
            "original_vertex_count": len(original),
            "vertex_count": len(candidate),
            "area_change_percent": round(area_change_percent, 4),
        }

    def make_rectangle(self, points: Iterable[dict[str, float]]) -> list[dict[str, float]]:
        polygon = self._polygon(list(points))
        if polygon.is_empty:
            return list(points)
        rectangle = polygon.minimum_rotated_rectangle
        min_x, min_y, max_x, max_y = polygon.bounds
        bbox = Polygon([(min_x, min_y), (max_x, min_y), (max_x, max_y), (min_x, max_y)])
        overlap = rectangle.intersection(bbox).area / max(rectangle.union(bbox).area, 1e-9)
        target = bbox if overlap >= 0.88 else rectangle
        return self._points(target)

    def straighten(self, points: Iterable[dict[str, float]]) -> list[dict[str, float]]:
        result = self._dedupe(list(points), 0.25)
        result = self._orthogonalize(result)
        result = self._remove_short_noise(result, max(1.0, settings.room_min_edge_pixels))
        return self._remove_collinear(result)

    def _remove_short_noise(self, points: list[dict[str, float]], tolerance: float) -> list[dict[str, float]]:
        if len(points) <= 4:
            return points
        result = [dict(item) for item in points]
        minimum = max(float(settings.room_min_edge_pixels), tolerance * 0.85)
        changed = True
        while changed and len(result) > 4:
            changed = False
            for index, current in enumerate(result):
                previous = result[index - 1]
                following = result[(index + 1) % len(result)]
                before = math.dist((previous["x"], previous["y"]), (current["x"], current["y"]))
                after = math.dist((current["x"], current["y"]), (following["x"], following["y"]))
                triangle = abs(
                    (current["x"] - previous["x"]) * (following["y"] - previous["y"])
                    - (current["y"] - previous["y"]) * (following["x"] - previous["x"])
                ) / 2.0
                if min(before, after) <= minimum and triangle <= minimum * minimum * 1.3:
                    proposed = result[:index] + result[index + 1 :]
                    polygon = self._polygon(proposed)
                    current_polygon = self._polygon(result)
                    if not polygon.is_empty and abs(polygon.area - current_polygon.area) / max(current_polygon.area, 1e-9) <= 0.025:
                        result = proposed
                        changed = True
                        break
        return result

    def _remove_collinear(self, points: list[dict[str, float]]) -> list[dict[str, float]]:
        if len(points) <= 4:
            return points
        output: list[dict[str, float]] = []
        count = len(points)
        tolerance = settings.room_collinear_tolerance_degrees
        for index, current in enumerate(points):
            previous = points[index - 1]
            following = points[(index + 1) % count]
            angle = room_shape_recognizer.angle_degrees(
                (previous["x"], previous["y"]),
                (current["x"], current["y"]),
                (following["x"], following["y"]),
            )
            if abs(180.0 - angle) <= tolerance:
                continue
            output.append(current)
        return output if len(output) >= 3 else points

    def _orthogonalize(self, points: list[dict[str, float]]) -> list[dict[str, float]]:
        if len(points) < 3:
            return points
        result = [dict(item) for item in points]
        tolerance = settings.room_orthogonal_tolerance_degrees
        # Two passes allow a shared corner to settle after both adjacent edges
        # are inspected without repeatedly drifting the polygon.
        for _ in range(2):
            for index in range(len(result)):
                nxt = (index + 1) % len(result)
                dx = result[nxt]["x"] - result[index]["x"]
                dy = result[nxt]["y"] - result[index]["y"]
                angle = abs(math.degrees(math.atan2(dy, dx))) % 180
                if min(angle, abs(180 - angle)) <= tolerance:
                    shared = (result[index]["y"] + result[nxt]["y"]) / 2
                    result[index]["y"] = shared
                    result[nxt]["y"] = shared
                elif abs(angle - 90) <= tolerance:
                    shared = (result[index]["x"] + result[nxt]["x"]) / 2
                    result[index]["x"] = shared
                    result[nxt]["x"] = shared
        return result

    @staticmethod
    def _dedupe(points: list[dict[str, float]], tolerance: float) -> list[dict[str, float]]:
        output: list[dict[str, float]] = []
        for item in points:
            point = {"x": float(item["x"]), "y": float(item["y"])}
            if output and math.dist((output[-1]["x"], output[-1]["y"]), (point["x"], point["y"])) <= tolerance:
                continue
            output.append(point)
        if len(output) > 2 and math.dist((output[0]["x"], output[0]["y"]), (output[-1]["x"], output[-1]["y"])) <= tolerance:
            output.pop()
        return output

    @staticmethod
    def _polygon(points: list[dict[str, float]]) -> Polygon:
        try:
            polygon = Polygon([(float(item["x"]), float(item["y"])) for item in points])
        except (KeyError, TypeError, ValueError):
            return Polygon()
        if not polygon.is_valid:
            polygon = polygon.buffer(0)
        if isinstance(polygon, Polygon):
            return polygon
        if hasattr(polygon, "geoms"):
            parts = [item for item in polygon.geoms if isinstance(item, Polygon)]
            return max(parts, key=lambda item: item.area) if parts else Polygon()
        return Polygon()

    @staticmethod
    def _points(polygon: Polygon) -> list[dict[str, float]]:
        return [{"x": float(x), "y": float(y)} for x, y in list(polygon.exterior.coords)[:-1]]

    @staticmethod
    def _signature(points: list[dict[str, float]]) -> tuple[tuple[int, int], ...]:
        return tuple((round(item["x"] * 10), round(item["y"] * 10)) for item in points)


polygon_regularizer = PolygonRegularizer()
