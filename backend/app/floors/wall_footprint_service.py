from __future__ import annotations

from typing import Any

from shapely.geometry import GeometryCollection


class WallFootprintService:
    def footprints(self, prepared: dict[str, Any]):
        value = prepared.get("wall_footprints")
        return value if value is not None else GeometryCollection()

    def inner_faces(self, prepared: dict[str, Any]):
        footprints = self.footprints(prepared)
        return footprints.boundary if not footprints.is_empty else GeometryCollection()


wall_footprint_service = WallFootprintService()
