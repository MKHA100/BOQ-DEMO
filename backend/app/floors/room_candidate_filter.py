from __future__ import annotations

from typing import Any

from shapely.geometry import Polygon

from app.floors.polygon_builder import room_polygon_builder
from app.floors.room_overlap_service import room_overlap_service


class RoomCandidateFilter:
    """Reject outer masks, duplicates, suppressed detections and overlaps."""

    maximum_envelope_ratio = 0.72
    contained_room_ratio = 0.72
    duplicate_iou = 0.82
    minimum_room_area_m2 = 0.50
    minimum_room_width_m = 0.30

    def filter(
        self,
        candidates: list[dict[str, Any]],
        *,
        envelope: Polygon | None,
        mm_per_pixel: float | None,
        rejected_rooms: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        minimum_area = 36.0
        if mm_per_pixel and mm_per_pixel > 0:
            minimum_area = self.minimum_room_area_m2 * 1_000_000 / (mm_per_pixel**2)

        prepared: list[tuple[dict[str, Any], Polygon]] = []
        rejected: list[dict[str, Any]] = []
        for candidate in candidates:
            polygon = room_polygon_builder.points_to_polygon(candidate.get("points") or [])
            if polygon.is_empty or polygon.area < minimum_area:
                rejected.append(self._rejection(candidate, "below_minimum_room_area"))
                continue
            if self._is_scale_sliver(polygon, mm_per_pixel):
                rejected.append(self._rejection(candidate, "below_minimum_room_width"))
                continue
            if envelope is not None and not envelope.is_empty:
                inside = polygon.intersection(envelope)
                overlap = inside.area / max(polygon.area, 1e-9)
                source = str(candidate.get("boundary_source") or "")
                model_backed = source in {
                    "model_only", "roboflow", "model_seed_wall_faces", "model_seed_wall_region"
                }
                confidence = float(candidate.get("confidence") or 0)
                # Exterior balconies and edge rooms legitimately extend beyond
                # the convex wall envelope. A credible model instance is the
                # discovery authority, so the envelope must neither clip nor
                # discard it. Wall-only fallback cells still require the hard
                # containment check.
                preserve_model = model_backed and confidence >= 0.65 and overlap > 0.01
                preserve_external_label = (
                    source == "label_seed_wall_cell"
                    and str(candidate.get("space_kind") or "") == "external"
                )
                if overlap < 0.68 and not preserve_model and not preserve_external_label:
                    rejected.append(self._rejection(candidate, "outside_building_envelope"))
                    continue
                if preserve_model or preserve_external_label:
                    inside = polygon
                polygon = room_overlap_service.largest_polygon(inside)
                if polygon.is_empty or polygon.area < minimum_area:
                    rejected.append(self._rejection(candidate, "outside_building_envelope"))
                    continue
                if self._is_scale_sliver(polygon, mm_per_pixel):
                    rejected.append(self._rejection(candidate, "below_minimum_room_width"))
                    continue
                candidate = {
                    **candidate,
                    "points": room_polygon_builder.polygon_to_points(polygon),
                    "geometry_hash": room_polygon_builder.geometry_hash(polygon),
                }
            if self._is_suppressed(polygon, rejected_rooms or []):
                rejected.append(self._rejection(candidate, "previously_rejected"))
                continue
            prepared.append((candidate, polygon))

        # A mask that encloses several smaller credible candidates is the
        # building/background envelope, never a measurable room.
        outer_indexes: set[int] = set()
        for index, (_, polygon) in enumerate(prepared):
            contained = 0
            for other_index, (other, other_polygon) in enumerate(prepared):
                if index == other_index or other_polygon.area >= polygon.area * 0.70:
                    continue
                covered = polygon.intersection(other_polygon).area / max(other_polygon.area, 1e-9)
                credible = (
                    bool(other.get("wall_ids"))
                    or "wall" in str(other.get("boundary_source") or "")
                    or float(other.get("confidence") or 0) >= 0.45
                )
                if covered >= self.contained_room_ratio and credible:
                    contained += 1
            envelope_ratio = (
                polygon.area / max(envelope.area, 1e-9)
                if envelope is not None and not envelope.is_empty
                else 0.0
            )
            if contained >= 2 or (envelope_ratio > self.maximum_envelope_ratio and len(prepared) > 1):
                outer_indexes.add(index)

        survivors: list[tuple[dict[str, Any], Polygon]] = []
        for index, pair in enumerate(prepared):
            if index in outer_indexes:
                rejected.append(self._rejection(pair[0], "outer_or_multi_room_boundary"))
            else:
                survivors.append(pair)

        # Prefer model-discovered room instances. Wall geometry may safely
        # correct their edges, while wall-only cells remain the fallback for
        # rooms the model did not find.
        survivors.sort(key=lambda pair: self._priority(pair[0]), reverse=True)
        accepted: list[dict[str, Any]] = []
        accepted_polygons: list[Polygon] = []
        for candidate, polygon in survivors:
            duplicate = any(
                room_polygon_builder.iou(polygon, other) >= self.duplicate_iou
                for other in accepted_polygons
            )
            if duplicate:
                rejected.append(self._rejection(candidate, "duplicate_room"))
                continue
            for other in accepted_polygons:
                if room_overlap_service.overlap_ratio(polygon, other) <= room_overlap_service.material_overlap_ratio:
                    continue
                polygon = room_overlap_service.largest_polygon(polygon.difference(other))
                if polygon.is_empty:
                    break
            if polygon.is_empty or polygon.area < minimum_area:
                rejected.append(self._rejection(candidate, "overlaps_accepted_room"))
                continue
            candidate = {
                **candidate,
                "points": room_polygon_builder.polygon_to_points(polygon),
                "area_px": float(polygon.area),
                "perimeter_px": float(polygon.length),
                "geometry_hash": room_polygon_builder.geometry_hash(polygon),
            }
            accepted.append(candidate)
            accepted_polygons.append(polygon)

        accepted.sort(key=lambda item: self._centroid(item))
        return {"accepted": accepted, "rejected": rejected}

    @staticmethod
    def _priority(candidate: dict[str, Any]) -> tuple[float, float, float]:
        source = str(candidate.get("boundary_source") or "")
        if source == "label_seed_wall_cell":
            # Strong printed semantics plus an actual wall cell are the safest
            # authority for model-missed toilets, balconies and small rooms.
            authority = 5.0
        elif source in {"model_seed_wall_faces", "model_seed_wall_region"}:
            authority = 4.0
        elif source in {"model_only", "roboflow"}:
            authority = 3.0
        elif source in {"wall_cell", "wall_only"}:
            authority = 2.0
        else:
            authority = 2.5 if "wall" in source else 1.0
        return (
            authority + min(len(candidate.get("wall_ids") or []), 8) * 0.05,
            float(candidate.get("confidence") or 0),
            -float(candidate.get("area_px") or 0),
        )

    def _is_suppressed(self, polygon: Polygon, rejected_rooms: list[dict[str, Any]]) -> bool:
        for room in rejected_rooms:
            other = room_overlap_service.polygon(room)
            if other.is_empty:
                continue
            if room_polygon_builder.iou(polygon, other) >= 0.58:
                return True
            if room_overlap_service.overlap_ratio(polygon, other) >= 0.88:
                return True
        return False

    def _is_scale_sliver(self, polygon: Polygon, mm_per_pixel: float | None) -> bool:
        """Reject dimension-line strips without guessing when scale is absent."""
        if not mm_per_pixel or mm_per_pixel <= 0:
            return False
        width_px, _ = room_polygon_builder.oriented_dimensions(polygon)
        return float(width_px) * float(mm_per_pixel) < self.minimum_room_width_m * 1000.0

    @staticmethod
    def _rejection(candidate: dict[str, Any], reason: str) -> dict[str, Any]:
        return {
            "geometry_hash": candidate.get("geometry_hash"),
            "suggestion_id": candidate.get("seed_suggestion_id") or candidate.get("suggestion_id"),
            "reason": reason,
        }

    @staticmethod
    def _centroid(item: dict[str, Any]) -> tuple[float, float]:
        polygon = room_polygon_builder.points_to_polygon(item.get("points") or [])
        return (float(polygon.centroid.y), float(polygon.centroid.x)) if not polygon.is_empty else (0.0, 0.0)


room_candidate_filter = RoomCandidateFilter()
