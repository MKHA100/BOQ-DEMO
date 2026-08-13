from __future__ import annotations

from typing import Any

from shapely.ops import unary_union

from app.floors.polygon_builder import room_polygon_builder


class RoomAreaResolver:
    """Resolve quantity geometry without trusting semantic-model measurements."""

    SOURCES: tuple[tuple[str, str], ...] = (
        ("wall_corrected_geometry", "wall_corrected"),
        ("regularized_geometry", "regularized"),
        ("raw_geometry", "model"),
        ("generated_geometry", "model"),
        ("geometry", "canonical"),
    )

    def geometry(self, room: dict[str, Any]) -> tuple[dict[str, Any], str]:
        confirmed = room.get("confirmed_geometry") or {}
        if (room.get("user_confirmed") or room.get("status") == "confirmed") and len(
            confirmed.get("points") or []
        ) >= 3:
            return confirmed, "confirmed"
        for key, source in self.SOURCES:
            value = room.get(key) or {}
            if len(value.get("points") or []) >= 3:
                return value, source
        return {}, "missing"

    def resolve(self, room: dict[str, Any], mm_per_pixel: float | None) -> dict[str, Any]:
        geometry, source = self.geometry(room)
        polygon = room_polygon_builder.points_to_polygon(geometry.get("points") or [])
        if polygon.is_empty:
            return {
                "geometry": geometry,
                "source": source,
                "area_m2": None,
                "perimeter_m": None,
                "measured_width_m": None,
                "measured_length_m": None,
            }

        cutout_polygons = [
            room_polygon_builder.points_to_polygon(
                ((item.get("geometry") or {}).get("points") or [])
            )
            for item in room.get("cutouts") or []
        ]
        cutout_polygons = [item for item in cutout_polygons if not item.is_empty]
        measurable = polygon
        if cutout_polygons:
            measurable = polygon.difference(unary_union(cutout_polygons)).buffer(0)

        scale = float(mm_per_pixel or 0)
        if scale <= 0:
            return {
                "geometry": geometry,
                "source": source,
                "area_m2": None,
                "perimeter_m": None,
                "measured_width_m": None,
                "measured_length_m": None,
            }

        width_px, length_px = room_polygon_builder.oriented_dimensions(polygon)
        mathematical_area = float(measurable.area) * scale * scale / 1_000_000
        manual = room.get("manual_area_override_m2")
        return {
            "geometry": geometry,
            "source": "manual_override" if manual is not None else source,
            "area_m2": round(float(manual) if manual is not None else mathematical_area, 4),
            "perimeter_m": round(float(polygon.length) * scale / 1000, 4),
            "measured_width_m": round(width_px * scale / 1000, 4),
            "measured_length_m": round(length_px * scale / 1000, 4),
        }


room_area_resolver = RoomAreaResolver()

__all__ = ["RoomAreaResolver", "room_area_resolver"]
