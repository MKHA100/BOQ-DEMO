from __future__ import annotations

from typing import Any

from shapely.geometry import Polygon, box


class BuildingEnvelopeService:
    def build(self, prepared: dict[str, Any], crop_width: float, crop_height: float) -> Polygon:
        footprints = prepared.get("wall_footprints")
        if footprints is not None and not footprints.is_empty:
            # A floor sheet can contain several disconnected apartment wings,
            # stair/lift cores or wall groups. Selecting only the largest
            # buffered component silently discards valid model rooms in every
            # other group. The envelope is only a coarse containment guard, so
            # span all detected wall footprints and let the room/model filters
            # perform the fine-grained validation.
            geometry = footprints.buffer(
                max(3.0, float(prepared.get("typical_thickness_px") or 8) * 1.5),
                join_style=2,
            )
            envelope = geometry.convex_hull.buffer(-max(1.0, float(prepared.get("typical_thickness_px") or 8) * 0.25), join_style=2)
            if isinstance(envelope, Polygon) and not envelope.is_empty:
                return envelope
        return box(0, 0, max(crop_width, 1), max(crop_height, 1))

    def overlap_ratio(self, polygon: Polygon, envelope: Polygon) -> float:
        if polygon.is_empty or envelope.is_empty:
            return 0.0
        return float(polygon.intersection(envelope).area / max(polygon.area, 1e-9))


building_envelope_service = BuildingEnvelopeService()
