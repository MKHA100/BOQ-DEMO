from __future__ import annotations

from app.core.errors import bad_request
from app.floors.polygon_builder import room_polygon_builder


class FinishZoneService:
    def validate(self, parent_points: list[dict], zone_points: list[dict]) -> list[dict]:
        parent = room_polygon_builder.points_to_polygon(parent_points)
        zone = room_polygon_builder.points_to_polygon(zone_points)
        if parent.is_empty or zone.is_empty:
            raise bad_request("Draw a valid finish zone.")
        clipped = zone.intersection(parent)
        if clipped.is_empty or clipped.area < 4:
            raise bad_request("The finish zone must be inside the open-plan room.")
        if hasattr(clipped, "geoms"):
            parts = [item for item in clipped.geoms if hasattr(item, "exterior")]
            clipped = max(parts, key=lambda item: item.area) if parts else clipped
        return room_polygon_builder.polygon_to_points(clipped)


finish_zone_service = FinishZoneService()
