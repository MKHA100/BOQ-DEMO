from __future__ import annotations

import hashlib
import math
from typing import Any, Iterable

from shapely.geometry import LineString, MultiPolygon, Point, Polygon, box
from shapely import affinity
from shapely.ops import nearest_points, polygonize, split, unary_union

try:
    from shapely import make_valid as _make_valid
except ImportError:  # pragma: no cover
    _make_valid = None


class RoomPolygonBuilder:
    def build(
        self,
        prepared: dict[str, Any],
        *,
        crop_width: float | None = None,
        crop_height: float | None = None,
        minimum_area_px: float | None = None,
    ) -> list[dict[str, Any]]:
        linework = prepared.get("noded_lines")
        if linework is None or linework.is_empty:
            return []
        typical_thickness = max(float(prepared.get("typical_thickness_px") or 8), 1.0)
        min_area = float(minimum_area_px or max(50.0, typical_thickness * typical_thickness * 1.4))
        wall_footprints = prepared.get("wall_footprints")

        raw_polygons = [self._repair(item) for item in polygonize(linework)]
        raw_polygons = [item for item in raw_polygons if item is not None and item.area >= min_area]
        raw_polygons = self._remove_exterior_cycles(raw_polygons)

        candidates: list[dict[str, Any]] = []
        seen_hashes: set[str] = set()
        for raw in raw_polygons:
            inner_parts = self._inside_free_space(raw, wall_footprints, typical_thickness)
            for polygon in inner_parts:
                if polygon.area < min_area:
                    continue
                geometry_hash = self.geometry_hash(polygon)
                if geometry_hash in seen_hashes:
                    continue
                if any(self.iou(polygon, self.points_to_polygon(item["points"])) >= 0.985 for item in candidates):
                    continue
                seen_hashes.add(geometry_hash)
                wall_ids = self._boundary_wall_ids(polygon, prepared.get("wall_segments") or [], typical_thickness)
                opening_ids = self._boundary_opening_ids(polygon, prepared.get("door_closures") or [], typical_thickness)
                touches_edge = self._touches_crop_edge(polygon, crop_width, crop_height, typical_thickness)
                width_px, length_px = self.oriented_dimensions(polygon)
                candidates.append(
                    {
                        "points": self.polygon_to_points(polygon),
                        "wall_ids": wall_ids,
                        "opening_ids": opening_ids,
                        "area_px": float(polygon.area),
                        "perimeter_px": float(polygon.length),
                        "width_px": width_px,
                        "length_px": length_px,
                        "geometry_hash": geometry_hash,
                        "touches_crop_edge": touches_edge,
                        "geometry_status": "needs_review" if touches_edge else "ready",
                    }
                )
        return sorted(candidates, key=lambda item: (self._centroid(item)[1], self._centroid(item)[0]))[:250]

    def _inside_free_space(self, raw: Polygon, wall_footprints: Any, typical_thickness: float) -> list[Polygon]:
        """Move a centreline cycle to the actual inside wall faces.

        When exact vector footprints exist, subtracting them handles mixed wall
        thicknesses and junctions better than a uniform negative buffer.
        """
        if wall_footprints is not None and not getattr(wall_footprints, "is_empty", True):
            free = self._repair(raw.difference(wall_footprints))
            parts = self._polygon_parts(free)
            if parts:
                representative = raw.representative_point()
                containing = [item for item in parts if item.buffer(0.5).contains(representative)]
                selected = containing or sorted(parts, key=lambda item: item.area, reverse=True)[:1]
                cleaned = [self._repair(item.buffer(-0.15, join_style=2).buffer(0.15, join_style=2)) for item in selected]
                result = [part for item in cleaned for part in self._polygon_parts(item)]
                if result:
                    return result
        fallback = self._repair(raw.buffer(-typical_thickness / 2.0, join_style=2))
        return self._polygon_parts(fallback)

    def correct_rectangular_dimensions(
        self,
        points: list[dict[str, float]],
        *,
        target_width_px: float | None,
        target_length_px: float | None,
        max_change_ratio: float = 0.08,
    ) -> list[dict[str, float]]:
        polygon = self.points_to_polygon(points)
        if polygon.is_empty:
            return points
        min_x, min_y, max_x, max_y = polygon.bounds
        bbox_area = max((max_x - min_x) * (max_y - min_y), 1.0)
        if polygon.area / bbox_area < 0.90:
            return points
        current_width = max_x - min_x
        current_height = max_y - min_y
        desired_x = target_length_px if current_width >= current_height else target_width_px
        desired_y = target_width_px if current_width >= current_height else target_length_px
        x_factor = 1.0
        y_factor = 1.0
        if desired_x and current_width > 0 and abs(desired_x - current_width) / current_width <= max_change_ratio:
            x_factor = desired_x / current_width
        if desired_y and current_height > 0 and abs(desired_y - current_height) / current_height <= max_change_ratio:
            y_factor = desired_y / current_height
        if abs(x_factor - 1.0) < 0.003 and abs(y_factor - 1.0) < 0.003:
            return points
        corrected = affinity.scale(polygon, xfact=x_factor, yfact=y_factor, origin="center")
        return self.polygon_to_points(corrected)

    def split_polygon(
        self, points: list[dict[str, float]], *, axis: str, ratio: float
    ) -> list[list[dict[str, float]]]:
        polygon = self.points_to_polygon(points)
        if polygon.is_empty:
            return []
        min_x, min_y, max_x, max_y = polygon.bounds
        if axis == "vertical":
            cut = min_x + (max_x - min_x) * ratio
            cutter = LineString([(cut, min_y - 10), (cut, max_y + 10)])
        else:
            cut = min_y + (max_y - min_y) * ratio
            cutter = LineString([(min_x - 10, cut), (max_x + 10, cut)])
        return self._split_with_cutter(polygon, cutter)

    def split_polygon_with_line(
        self,
        points: list[dict[str, float]],
        line_points: list[dict[str, float]],
    ) -> list[list[dict[str, float]]]:
        polygon = self.points_to_polygon(points)
        if polygon.is_empty or len(line_points) < 2:
            return []
        line = LineString([(float(item["x"]), float(item["y"])) for item in line_points])
        if line.length <= 1:
            return []
        min_x, min_y, max_x, max_y = polygon.bounds
        extension = max(max_x - min_x, max_y - min_y) * 2 + 20
        coords = list(line.coords)
        dx, dy = coords[-1][0] - coords[0][0], coords[-1][1] - coords[0][1]
        length = math.hypot(dx, dy)
        if length <= 0:
            return []
        ux, uy = dx / length, dy / length
        cutter = LineString([
            (coords[0][0] - ux * extension, coords[0][1] - uy * extension),
            (coords[-1][0] + ux * extension, coords[-1][1] + uy * extension),
        ])
        return self._split_with_cutter(polygon, cutter)

    def _split_with_cutter(self, polygon: Polygon, cutter: LineString) -> list[list[dict[str, float]]]:
        try:
            result = split(polygon, cutter)
        except Exception:
            return []
        parts = [part for part in result.geoms if isinstance(part, Polygon) and part.area > 4]
        if len(parts) != 2:
            return []
        return [self.polygon_to_points(part) for part in sorted(parts, key=lambda item: (item.centroid.y, item.centroid.x))]

    def merge_polygons(
        self, first: list[dict[str, float]], second: list[dict[str, float]]
    ) -> list[dict[str, float]]:
        merged = self._repair(unary_union([self.points_to_polygon(first), self.points_to_polygon(second)]))
        parts = self._polygon_parts(merged)
        if len(parts) != 1:
            return []
        return self.polygon_to_points(parts[0])

    def snap_polygon_to_walls(
        self,
        points: list[dict[str, float]],
        prepared: dict[str, Any],
        *,
        tolerance: float | None = None,
    ) -> list[dict[str, float]]:
        polygon = self.points_to_polygon(points)
        footprints = prepared.get("wall_footprints")
        if polygon.is_empty or footprints is None or footprints.is_empty:
            return points
        boundary = footprints.boundary
        limit = float(tolerance or max(3.0, float(prepared.get("typical_thickness_px") or 8) * 1.5))
        snapped: list[tuple[float, float]] = []
        for x, y in list(polygon.exterior.coords)[:-1]:
            source = Point(x, y)
            nearest = nearest_points(source, boundary)[1]
            if source.distance(nearest) <= limit:
                snapped.append((nearest.x, nearest.y))
            else:
                snapped.append((x, y))
        candidate = self._repair(Polygon(snapped))
        parts = self._polygon_parts(candidate)
        if not parts:
            return points
        best = max(parts, key=lambda item: item.area)
        return self.polygon_to_points(best)

    @staticmethod
    def polygon_to_points(polygon: Polygon) -> list[dict[str, float]]:
        coords = list(polygon.exterior.coords)
        if coords and coords[0] == coords[-1]:
            coords.pop()
        return [{"x": round(float(x), 4), "y": round(float(y), 4)} for x, y in coords]

    def points_to_polygon(self, points: Iterable[dict[str, float]]) -> Polygon:
        try:
            polygon = Polygon([(float(point["x"]), float(point["y"])) for point in points])
        except (KeyError, TypeError, ValueError):
            return Polygon()
        repaired = self._repair(polygon)
        parts = self._polygon_parts(repaired)
        return max(parts, key=lambda item: item.area) if parts else Polygon()

    @staticmethod
    def geometry_hash(polygon: Polygon) -> str:
        normalized = polygon.normalize()
        return hashlib.sha256(normalized.wkb).hexdigest()[:32]

    @staticmethod
    def iou(first: Polygon, second: Polygon) -> float:
        if first.is_empty or second.is_empty:
            return 0.0
        union = first.union(second).area
        return float(first.intersection(second).area / union) if union > 0 else 0.0

    @staticmethod
    def oriented_dimensions(polygon: Polygon) -> tuple[float, float]:
        if polygon.is_empty:
            return 0.0, 0.0
        rectangle = polygon.minimum_rotated_rectangle
        coords = list(rectangle.exterior.coords)
        lengths = sorted(
            math.dist(coords[index], coords[index + 1])
            for index in range(min(4, len(coords) - 1))
        )
        if len(lengths) < 2:
            return 0.0, 0.0
        return float(lengths[0]), float(lengths[-1])

    def _repair(self, geometry: Any) -> Any:
        if geometry is None or geometry.is_empty:
            return None
        if geometry.is_valid:
            return geometry
        try:
            repaired = _make_valid(geometry) if _make_valid is not None else geometry.buffer(0)
        except Exception:
            repaired = geometry.buffer(0)
        return repaired if repaired is not None and not repaired.is_empty else None

    @staticmethod
    def _polygon_parts(geometry: Any) -> list[Polygon]:
        if geometry is None or geometry.is_empty:
            return []
        if isinstance(geometry, Polygon):
            return [geometry]
        if isinstance(geometry, MultiPolygon):
            return list(geometry.geoms)
        if hasattr(geometry, "geoms"):
            return [item for item in geometry.geoms if isinstance(item, Polygon)]
        return []

    def _remove_exterior_cycles(self, polygons: list[Polygon]) -> list[Polygon]:
        if len(polygons) < 3:
            return polygons
        output: list[Polygon] = []
        for polygon in polygons:
            contained = [
                other
                for other in polygons
                if other is not polygon and polygon.contains(other.representative_point()) and polygon.area > other.area * 1.25
            ]
            contained_area = sum(other.area for other in contained)
            if len(contained) >= 2 and polygon.area >= contained_area * 1.15:
                continue
            output.append(polygon)
        return output

    @staticmethod
    def _boundary_wall_ids(
        polygon: Polygon, walls: list[dict[str, Any]], thickness: float
    ) -> list[str]:
        tolerance = max(2.0, thickness * 0.8)
        return sorted(
            {
                str(item["id"])
                for item in walls
                if not str(item.get("id") or "").startswith("vector:")
                and item.get("line") is not None
                and polygon.boundary.distance(item["line"]) <= tolerance
            }
        )

    @staticmethod
    def _boundary_opening_ids(
        polygon: Polygon, closures: list[dict[str, Any]], thickness: float
    ) -> list[str]:
        tolerance = max(2.0, thickness)
        return sorted(
            {
                str(item["element_id"])
                for item in closures
                if item.get("line") is not None and polygon.boundary.distance(item["line"]) <= tolerance
            }
        )

    @staticmethod
    def _touches_crop_edge(
        polygon: Polygon,
        crop_width: float | None,
        crop_height: float | None,
        tolerance: float,
    ) -> bool:
        if not crop_width or not crop_height:
            return False
        frame = box(0, 0, float(crop_width), float(crop_height)).boundary
        return polygon.boundary.distance(frame) <= max(2.0, tolerance * 0.35)

    @staticmethod
    def _centroid(item: dict[str, Any]) -> tuple[float, float]:
        points = item.get("points") or []
        if not points:
            return 0.0, 0.0
        return (
            sum(float(point["x"]) for point in points) / len(points),
            sum(float(point["y"]) for point in points) / len(points),
        )


room_polygon_builder = RoomPolygonBuilder()
