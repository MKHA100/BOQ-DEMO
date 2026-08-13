from __future__ import annotations

from shapely.geometry import GeometryCollection, Polygon
from shapely.ops import unary_union


class FreeSpaceService:
    def calculate(self, envelope: Polygon, wall_footprints, exclusions=None, closures=None):
        result = envelope
        if wall_footprints is not None and not wall_footprints.is_empty:
            result = result.difference(wall_footprints)
        exclusion_geometry = self._union(exclusions)
        if not exclusion_geometry.is_empty:
            result = result.difference(exclusion_geometry)
        closure_geometry = self._union(closures)
        if not closure_geometry.is_empty:
            result = result.difference(closure_geometry)
        return result.buffer(0)

    @staticmethod
    def _union(value):
        if value is None:
            return GeometryCollection()
        if isinstance(value, (list, tuple)):
            items = [item for item in value if item is not None and not getattr(item, "is_empty", True)]
            return unary_union(items) if items else GeometryCollection()
        return value


free_space_service = FreeSpaceService()
