from __future__ import annotations

from typing import Any

from shapely.geometry import Polygon
from shapely.ops import unary_union

from app.core.errors import bad_request
from app.floors.polygon_builder import room_polygon_builder
from app.floors.polygon_regularizer import polygon_regularizer


class RoomEditService:
    def simplify(self, points: list[dict[str, float]]) -> list[dict[str, float]]:
        return polygon_regularizer.regularize(points)["points"]

    def make_rectangle(self, points: list[dict[str, float]]) -> list[dict[str, float]]:
        return polygon_regularizer.make_rectangle(points)

    def straighten(self, points: list[dict[str, float]]) -> list[dict[str, float]]:
        return polygon_regularizer.straighten(points)

    def add_point(self, points: list[dict[str, float]], edge_index: int, point: dict[str, float]) -> list[dict[str, float]]:
        if edge_index < 0 or edge_index >= len(points):
            raise bad_request("Select a valid room edge.")
        result = list(points)
        result.insert(edge_index + 1, {"x": float(point["x"]), "y": float(point["y"])})
        return result

    def delete_point(self, points: list[dict[str, float]], index: int) -> list[dict[str, float]]:
        if len(points) <= 3:
            raise bad_request("A room must keep at least three points.")
        if index < 0 or index >= len(points):
            raise bad_request("Select a valid room point.")
        return [item for item_index, item in enumerate(points) if item_index != index]

    def move_edge(self, points: list[dict[str, float]], edge_index: int, dx: float, dy: float) -> list[dict[str, float]]:
        if edge_index < 0 or edge_index >= len(points):
            raise bad_request("Select a valid room edge.")
        result = [dict(item) for item in points]
        next_index = (edge_index + 1) % len(result)
        for index in {edge_index, next_index}:
            result[index]["x"] = float(result[index]["x"]) + float(dx)
            result[index]["y"] = float(result[index]["y"]) + float(dy)
        return result

    def subtract_cutouts(self, polygon: Polygon, cutouts: list[dict[str, Any]]) -> Polygon:
        geometries = [room_polygon_builder.points_to_polygon((item.get("geometry") or {}).get("points") or []) for item in cutouts]
        geometries = [item for item in geometries if not item.is_empty]
        return polygon.difference(unary_union(geometries)).buffer(0) if geometries else polygon


room_edit_service = RoomEditService()
