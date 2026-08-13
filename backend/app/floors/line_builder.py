from __future__ import annotations

import math
from statistics import median
from typing import Any

from shapely.geometry import LineString, Point, Polygon
from shapely.ops import snap, unary_union


class RoomLineBuilder:
    """Prepare wall topology, exact wall footprints and temporary door closures.

    Canonical/model wall centerlines are authoritative. Vector PDF wall-edge
    pairs may corroborate them, but raw vectors do not create production room
    topology because architectural annotations use the same primitive lines.
    Door openings are closed only in temporary room topology.
    """

    def build(
        self,
        *,
        walls: list[dict[str, Any]],
        openings: list[dict[str, Any]],
        mm_per_pixel: float | None,
        vector_walls: list[dict[str, Any]] | None = None,
        vector_mode: str = "independent",
        snap_tolerance_px: float | None = None,
    ) -> dict[str, Any]:
        wall_segments: list[dict[str, Any]] = []
        thicknesses: list[float] = []
        wall_by_id: dict[str, dict[str, Any]] = {}

        for wall in walls:
            line = self._line_from_centerline(wall.get("centerline") or {})
            if line is None or line.length < 2:
                continue
            thickness_px = self._thickness_px(wall, mm_per_pixel)
            thicknesses.append(thickness_px)
            record = {
                "id": str(wall["id"]),
                "line": line,
                "thickness_px": thickness_px,
                "classification": wall.get("classification"),
                "source": "canonical",
                "footprint": line.buffer(thickness_px / 2.0, cap_style=2, join_style=2),
            }
            wall_segments.append(record)
            wall_by_id[str(wall["id"])] = record

        # Raw PDF vectors contain dimension strings, extension lines, leaders,
        # furniture and hatching as well as real wall edges.  Production room
        # geometry therefore uses them only to corroborate canonical walls.
        # ``independent`` remains available for explicit vector-only callers.
        vector_evidence_count = 0
        for item in vector_walls or []:
            line = self._line_from_centerline(item.get("centerline") or {})
            points = item.get("footprint") or []
            if line is None or line.length < 2 or len(points) < 3:
                continue
            try:
                footprint = Polygon([(float(point["x"]), float(point["y"])) for point in points])
            except (KeyError, TypeError, ValueError):
                continue
            if footprint.is_empty or not footprint.is_valid:
                footprint = footprint.buffer(0)
            if footprint.is_empty:
                continue
            thickness_px = float(item.get("thickness_px") or max(1.0, footprint.area / max(line.length, 1.0)))
            if vector_mode != "independent":
                if vector_mode == "refine" and any(
                    self._supports_canonical(line, footprint, canonical)
                    for canonical in wall_segments
                    if canonical.get("source") == "canonical"
                ):
                    vector_evidence_count += 1
                continue
            thicknesses.append(thickness_px)
            wall_segments.append(
                {
                    "id": str(item.get("id") or f"vector:{len(wall_segments)}"),
                    "line": line,
                    "thickness_px": thickness_px,
                    "classification": None,
                    "source": "vector",
                    "footprint": footprint,
                    "confidence": item.get("confidence"),
                }
            )

        typical_thickness = float(median(thicknesses)) if thicknesses else 8.0
        tolerance = float(snap_tolerance_px or max(2.0, min(14.0, typical_thickness * 0.55)))
        lines = [item["line"] for item in wall_segments]
        if lines:
            reference = unary_union(lines)
            for item in wall_segments:
                item["line"] = snap(item["line"], reference, tolerance)
                if item.get("source") != "vector":
                    item["footprint"] = item["line"].buffer(
                        float(item.get("thickness_px") or typical_thickness) / 2.0,
                        cap_style=2,
                        join_style=2,
                    )

        closures: list[dict[str, Any]] = []
        canonical_segments = [item for item in wall_segments if item.get("source") == "canonical"]
        for opening in openings:
            if str(opening.get("element_type") or "").lower() != "door":
                continue
            wall_id = str(opening.get("wall_id") or "")
            wall = wall_by_id.get(wall_id)
            if wall is None:
                wall = self._nearest_wall(opening, canonical_segments or wall_segments)
            if wall is None:
                continue
            closure = self._gap_closure(
                opening,
                canonical_segments or wall_segments,
                mm_per_pixel,
                typical_thickness,
                tolerance,
            )
            if closure is None:
                closure = self._door_closure(
                    opening, wall["line"], mm_per_pixel, typical_thickness
                )
            if closure is None:
                continue
            closures.append(
                {
                    "element_id": str(opening["id"]),
                    "wall_id": str(wall["id"]),
                    "line": closure,
                    "length_px": float(closure.length),
                }
            )

        all_lines = [item["line"] for item in wall_segments] + [item["line"] for item in closures]
        footprints = [item["footprint"] for item in wall_segments if item.get("footprint") is not None]
        return {
            "wall_segments": wall_segments,
            "door_closures": closures,
            "noded_lines": unary_union(all_lines) if all_lines else LineString(),
            "wall_footprints": unary_union(footprints) if footprints else Polygon(),
            "typical_thickness_px": typical_thickness,
            "snap_tolerance_px": tolerance,
            "vector_wall_count": sum(item.get("source") == "vector" for item in wall_segments),
            "vector_evidence_count": vector_evidence_count,
        }

    @staticmethod
    def serialize(prepared: dict[str, Any]) -> dict[str, Any]:
        return {
            "wall_segments": [
                {
                    "id": item["id"],
                    "points": RoomLineBuilder._line_points(item["line"]),
                    "thickness_px": item["thickness_px"],
                    "classification": item.get("classification"),
                    "source": item.get("source"),
                    "footprint": RoomLineBuilder._polygon_points(item.get("footprint")),
                }
                for item in prepared.get("wall_segments", [])
            ],
            "door_closures": [
                {
                    "element_id": item["element_id"],
                    "wall_id": item["wall_id"],
                    "points": RoomLineBuilder._line_points(item["line"]),
                    "length_px": item["length_px"],
                }
                for item in prepared.get("door_closures", [])
            ],
            "typical_thickness_px": prepared.get("typical_thickness_px"),
            "snap_tolerance_px": prepared.get("snap_tolerance_px"),
            "vector_wall_count": prepared.get("vector_wall_count", 0),
            "vector_evidence_count": prepared.get("vector_evidence_count", 0),
        }

    @staticmethod
    def deserialize(payload: dict[str, Any]) -> dict[str, Any]:
        walls: list[dict[str, Any]] = []
        for item in payload.get("wall_segments", []):
            if len(item.get("points", [])) < 2:
                continue
            line = LineString([(point["x"], point["y"]) for point in item.get("points", [])])
            footprint_points = item.get("footprint") or []
            footprint = (
                Polygon([(point["x"], point["y"]) for point in footprint_points])
                if len(footprint_points) >= 3
                else line.buffer(float(item.get("thickness_px") or 8) / 2.0, cap_style=2, join_style=2)
            )
            walls.append(
                {
                    "id": item["id"],
                    "line": line,
                    "thickness_px": float(item.get("thickness_px") or 0),
                    "classification": item.get("classification"),
                    "source": item.get("source") or "canonical",
                    "footprint": footprint,
                }
            )
        closures = [
            {
                "element_id": item["element_id"],
                "wall_id": item.get("wall_id"),
                "line": LineString([(point["x"], point["y"]) for point in item.get("points", [])]),
                "length_px": float(item.get("length_px") or 0),
            }
            for item in payload.get("door_closures", [])
            if len(item.get("points", [])) >= 2
        ]
        all_lines = [item["line"] for item in walls] + [item["line"] for item in closures]
        footprints = [item["footprint"] for item in walls]
        return {
            "wall_segments": walls,
            "door_closures": closures,
            "noded_lines": unary_union(all_lines) if all_lines else LineString(),
            "wall_footprints": unary_union(footprints) if footprints else Polygon(),
            "typical_thickness_px": float(payload.get("typical_thickness_px") or 8),
            "snap_tolerance_px": float(payload.get("snap_tolerance_px") or 4),
            "vector_wall_count": int(payload.get("vector_wall_count") or 0),
            "vector_evidence_count": int(payload.get("vector_evidence_count") or 0),
        }

    @staticmethod
    def _supports_canonical(line: LineString, footprint: Polygon, canonical: dict[str, Any]) -> bool:
        """Return true only when a vector pair follows an existing wall.

        This deliberately does not create topology.  It prevents a pair of
        parallel dimension/annotation strokes from inventing a room boundary.
        """
        other = canonical.get("line")
        other_footprint = canonical.get("footprint")
        if other is None or other.is_empty or other_footprint is None or other_footprint.is_empty:
            return False
        first = list(line.coords)
        second = list(other.coords)
        if len(first) < 2 or len(second) < 2:
            return False
        first_angle = math.degrees(math.atan2(first[-1][1] - first[0][1], first[-1][0] - first[0][0])) % 180
        second_angle = math.degrees(math.atan2(second[-1][1] - second[0][1], second[-1][0] - second[0][0])) % 180
        angle = abs(first_angle - second_angle)
        angle = min(angle, 180 - angle)
        if angle > 8:
            return False
        padding = max(
            3.0,
            float(canonical.get("thickness_px") or 0) * 0.75,
            float(footprint.area / max(line.length, 1.0)) * 0.75,
        )
        supported = line.intersection(other_footprint.buffer(padding)).length
        return supported / max(line.length, 1.0) >= 0.45

    @staticmethod
    def _line_from_centerline(centerline: dict[str, Any]) -> LineString | None:
        start, end = centerline.get("start"), centerline.get("end")
        if not isinstance(start, dict) or not isinstance(end, dict):
            return None
        try:
            return LineString(
                [(float(start["x"]), float(start["y"])), (float(end["x"]), float(end["y"]))]
            )
        except (KeyError, TypeError, ValueError):
            return None

    @staticmethod
    def _thickness_px(wall: dict[str, Any], mm_per_pixel: float | None) -> float:
        try:
            thickness_mm = float(wall.get("thickness_mm") or 0)
        except (TypeError, ValueError):
            thickness_mm = 0
        if thickness_mm > 0 and mm_per_pixel and mm_per_pixel > 0:
            return max(1.0, thickness_mm / mm_per_pixel)
        return 8.0

    def _nearest_wall(
        self, opening: dict[str, Any], walls: list[dict[str, Any]]
    ) -> dict[str, Any] | None:
        center = self._geometry_center(opening.get("geometry") or {})
        if center is None or not walls:
            return None
        point = Point(center)
        return min(walls, key=lambda item: item["line"].distance(point))

    def _gap_closure(
        self,
        opening: dict[str, Any],
        walls: list[dict[str, Any]],
        mm_per_pixel: float | None,
        typical_thickness_px: float,
        snap_tolerance_px: float,
    ) -> LineString | None:
        center = self._geometry_center(opening.get("geometry") or {})
        if center is None or len(walls) < 2:
            return None
        width_px = self._opening_width_px(opening, mm_per_pixel)
        search_radius = max(width_px * 1.25, typical_thickness_px * 6.0, snap_tolerance_px * 3.0)
        endpoints: list[tuple[str, tuple[float, float]]] = []
        center_point = Point(center)
        for wall in walls:
            coords = list(wall["line"].coords)
            for point in (coords[0], coords[-1]):
                if center_point.distance(Point(point)) <= search_radius:
                    endpoints.append((str(wall["id"]), (float(point[0]), float(point[1]))))

        best: tuple[float, tuple[float, float], tuple[float, float]] | None = None
        maximum_gap = max(width_px * 1.8, typical_thickness_px * 10.0, snap_tolerance_px * 5.0)
        minimum_gap = max(1.0, typical_thickness_px * 0.35)
        for index, (first_id, first) in enumerate(endpoints):
            for second_id, second in endpoints[index + 1 :]:
                if first_id == second_id:
                    continue
                distance = math.dist(first, second)
                if distance < minimum_gap or distance > maximum_gap:
                    continue
                midpoint = Point((first[0] + second[0]) / 2.0, (first[1] + second[1]) / 2.0)
                width_penalty = abs(distance - width_px) if width_px > 0 else 0.0
                score = midpoint.distance(center_point) + width_penalty * 0.35
                if best is None or score < best[0]:
                    best = (score, first, second)
        return LineString([best[1], best[2]]) if best is not None else None

    def _door_closure(
        self,
        opening: dict[str, Any],
        wall_line: LineString,
        mm_per_pixel: float | None,
        typical_thickness_px: float,
    ) -> LineString | None:
        center = self._geometry_center(opening.get("geometry") or {})
        if center is None:
            return None
        projected = wall_line.interpolate(wall_line.project(Point(center)))
        coords = list(wall_line.coords)
        if len(coords) < 2:
            return None
        dx = coords[-1][0] - coords[0][0]
        dy = coords[-1][1] - coords[0][1]
        length = math.hypot(dx, dy)
        if length <= 0:
            return None
        ux, uy = dx / length, dy / length

        width_px = self._opening_width_px(opening, mm_per_pixel)
        if width_px <= 0:
            width_px = max(typical_thickness_px * 3.0, 18.0)
        half = max(width_px / 2.0, typical_thickness_px)
        return LineString(
            [
                (projected.x - ux * half, projected.y - uy * half),
                (projected.x + ux * half, projected.y + uy * half),
            ]
        )

    @staticmethod
    def _opening_width_px(opening: dict[str, Any], mm_per_pixel: float | None) -> float:
        dimensions = opening.get("dimensions") or {}
        try:
            width_mm = float(dimensions.get("width_mm") or 0)
        except (TypeError, ValueError):
            width_mm = 0
        if width_mm > 0 and mm_per_pixel and mm_per_pixel > 0:
            return width_mm / mm_per_pixel
        geometry = opening.get("geometry") or {}
        try:
            return max(float(geometry.get("width") or 0), float(geometry.get("height") or 0))
        except (TypeError, ValueError):
            return 0.0

    @staticmethod
    def _geometry_center(geometry: dict[str, Any]) -> tuple[float, float] | None:
        try:
            x = float(geometry.get("x") or 0)
            y = float(geometry.get("y") or 0)
            width = float(geometry.get("width") or 0)
            height = float(geometry.get("height") or 0)
        except (TypeError, ValueError):
            return None
        if geometry.get("coordinate_mode") == "center":
            return x, y
        return x + width / 2.0, y + height / 2.0

    @staticmethod
    def _line_points(line: LineString) -> list[dict[str, float]]:
        return [{"x": float(x), "y": float(y)} for x, y in line.coords]

    @staticmethod
    def _polygon_points(polygon: Any) -> list[dict[str, float]]:
        if polygon is None or polygon.is_empty or not hasattr(polygon, "exterior"):
            return []
        coords = list(polygon.exterior.coords)
        if coords and coords[0] == coords[-1]:
            coords.pop()
        return [{"x": float(x), "y": float(y)} for x, y in coords]


room_line_builder = RoomLineBuilder()
