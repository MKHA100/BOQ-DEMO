from __future__ import annotations

from typing import Any, Iterable

from shapely.geometry import MultiPolygon, Polygon

from app.floors.polygon_builder import room_polygon_builder


class RoomOverlapService:
    """Enforce the invariant that canonical physical rooms do not overlap."""

    duplicate_iou = 0.82
    material_overlap_ratio = 0.08

    @staticmethod
    def polygon(item: dict[str, Any]) -> Polygon:
        geometry = item.get("display_polygon") or item.get("geometry") or {}
        points = item.get("points") or geometry.get("points") or []
        return room_polygon_builder.points_to_polygon(points)

    def overlap_ratio(self, first: Polygon, second: Polygon) -> float:
        if first.is_empty or second.is_empty:
            return 0.0
        return float(first.intersection(second).area / max(min(first.area, second.area), 1e-9))

    def conflicts(
        self,
        candidate: dict[str, Any],
        rooms: Iterable[dict[str, Any]],
        *,
        ignore_room_id: str | None = None,
        ignore_room_ids: set[str] | None = None,
    ) -> list[dict[str, Any]]:
        polygon = self.polygon(candidate)
        conflicts: list[dict[str, Any]] = []
        ignored = {str(item) for item in (ignore_room_ids or set())}
        if ignore_room_id:
            ignored.add(str(ignore_room_id))
        for room in rooms:
            if str(room.get("id") or "") in ignored:
                continue
            if room.get("excluded") or room.get("is_finish_zone"):
                continue
            other = self.polygon(room)
            ratio = self.overlap_ratio(polygon, other)
            if ratio > self.material_overlap_ratio:
                conflicts.append(
                    {
                        "room_id": room.get("id"),
                        "name": room.get("name") or room.get("friendly_number") or "Room",
                        "overlap_ratio": round(ratio, 6),
                    }
                )
        return conflicts

    @staticmethod
    def largest_polygon(value: Any) -> Polygon:
        if isinstance(value, Polygon):
            return value
        if isinstance(value, MultiPolygon):
            return max(value.geoms, key=lambda item: item.area, default=Polygon())
        if hasattr(value, "geoms"):
            polygons = [item for item in value.geoms if isinstance(item, Polygon)]
            return max(polygons, key=lambda item: item.area, default=Polygon())
        return Polygon()


room_overlap_service = RoomOverlapService()
