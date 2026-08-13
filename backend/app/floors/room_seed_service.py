from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Iterable

from shapely.geometry import GeometryCollection, MultiPolygon, Polygon
from shapely.ops import unary_union

from app.floors.polygon_builder import room_polygon_builder
from app.floors.polygon_regularizer import polygon_regularizer


@dataclass(frozen=True)
class SeededRoomResult:
    points: list[dict[str, float]]
    model_points: list[dict[str, float]]
    source: str
    score: float
    suggestion_id: str | None
    model_overlap: float
    current_overlap: float


class RoomSeedService:
    """Make the room model the discovery priority and walls the boundary authority.

    The room instance-segmentation result is always considered first.  When a
    clean wall-bounded cell contains the model seed, that cell becomes the
    corrected proposal.  When wall topology is incomplete, a regularized model
    polygon remains visible as a provisional room instead of disappearing.
    """

    minimum_wall_face_support = 0.58

    def closed_free_space(self, prepared: dict[str, Any], envelope: Polygon):
        footprints = prepared.get("wall_footprints")
        barriers: list[Any] = []
        if footprints is not None and not getattr(footprints, "is_empty", True):
            barriers.append(footprints)

        typical = max(float(prepared.get("typical_thickness_px") or 8.0), 1.0)
        for item in prepared.get("door_closures") or []:
            line = item.get("line")
            if line is None or getattr(line, "is_empty", True):
                continue
            barriers.append(line.buffer(max(1.0, typical * 0.58), cap_style=2, join_style=2))

        barrier = unary_union(barriers) if barriers else GeometryCollection()
        free = envelope.difference(barrier) if not barrier.is_empty else envelope
        if not free.is_valid:
            free = free.buffer(0)
        return free

    def regions(self, prepared: dict[str, Any], envelope: Polygon) -> list[Polygon]:
        free = self.closed_free_space(prepared, envelope)
        typical = max(float(prepared.get("typical_thickness_px") or 8.0), 1.0)
        minimum = max(36.0, typical * typical * 0.8)
        cleaned: list[Polygon] = []
        for polygon in self._parts(free):
            if polygon.area < minimum:
                continue
            noise = min(2.5, max(0.45, typical * 0.10))
            candidate = polygon.buffer(noise, join_style=2).buffer(-noise, join_style=2)
            parts = self._parts(candidate)
            selected = max(parts, key=lambda item: item.area) if parts else polygon
            if selected.area >= minimum:
                cleaned.append(selected)
        return cleaned

    def provisional(self, suggestion: dict[str, Any], *, wall_thickness_px: float = 0.0) -> dict[str, Any] | None:
        model_points = (suggestion.get("polygon") or {}).get("points") or suggestion.get("points") or []
        model = room_polygon_builder.points_to_polygon(model_points)
        if model.is_empty:
            return None
        regularized = polygon_regularizer.regularize(model_points, wall_thickness_px=wall_thickness_px)
        points = regularized.get("points") or room_polygon_builder.polygon_to_points(model)
        polygon = room_polygon_builder.points_to_polygon(points)
        if polygon.is_empty:
            return None
        return {
            "points": points,
            "model_points": room_polygon_builder.polygon_to_points(model),
            "shape_type": regularized.get("shape_type") or "irregular",
            "geometry_hash": room_polygon_builder.geometry_hash(polygon),
            "confidence": float(suggestion.get("confidence") or 0),
            "suggestion_id": str(suggestion.get("id") or "") or None,
            "source": "model_only",
        }

    def best_suggestion(
        self,
        room_id: str | None,
        room_polygon: Polygon,
        suggestions: Iterable[dict[str, Any]],
    ) -> tuple[dict[str, Any] | None, Polygon]:
        best: dict[str, Any] | None = None
        best_polygon = Polygon()
        best_score = -1.0
        current_seed = room_polygon.representative_point() if not room_polygon.is_empty else None
        for suggestion in suggestions:
            if suggestion.get("status") in {"rejected", "superseded"}:
                continue
            polygon = room_polygon_builder.points_to_polygon(
                (suggestion.get("polygon") or {}).get("points") or suggestion.get("points") or []
            )
            if polygon.is_empty:
                continue
            matched = bool(room_id and str(suggestion.get("matched_room_id") or "") == room_id)
            iou = room_polygon_builder.iou(room_polygon, polygon) if not room_polygon.is_empty else 0.0
            model_contains_current = bool(current_seed and polygon.buffer(2).contains(current_seed))
            current_contains_model = bool(not room_polygon.is_empty and room_polygon.buffer(2).contains(polygon.representative_point()))
            score = (
                (1.2 if matched else 0.0)
                + iou * 0.8
                + (0.32 if model_contains_current else 0.0)
                + (0.22 if current_contains_model else 0.0)
                + float(suggestion.get("confidence") or 0) * 0.12
            )
            if score > best_score:
                best = suggestion
                best_polygon = polygon
                best_score = score
        return best, best_polygon

    def refine(
        self,
        *,
        room_id: str | None,
        room_points: list[dict[str, float]],
        suggestions: Iterable[dict[str, Any]],
        prepared: dict[str, Any],
        envelope: Polygon,
    ) -> SeededRoomResult | None:
        current = room_polygon_builder.points_to_polygon(room_points)
        suggestion, model = self.best_suggestion(room_id, current, suggestions)
        if model.is_empty:
            return None

        # Preserve the model's room instance and only move nearby vertices to
        # wall faces.  This is deliberately attempted before selecting a free
        # space region: a single open wall cell can contain several real rooms
        # when a doorway or one short wall segment is missing.
        model_points = room_polygon_builder.polygon_to_points(model)
        face_points, face_alignment = self._snap_to_wall_faces(model_points, prepared)
        face_polygon = room_polygon_builder.points_to_polygon(face_points)
        if not face_polygon.is_empty:
            face_iou = room_polygon_builder.iou(model, face_polygon)
            face_area_ratio = face_polygon.area / max(model.area, 1e-9)
            if (
                face_alignment >= self.minimum_wall_face_support
                and face_iou >= 0.65
                and 0.65 <= face_area_ratio <= 1.45
            ):
                return SeededRoomResult(
                    points=face_points,
                    model_points=model_points,
                    source="model_seed_wall_faces",
                    score=round(face_alignment, 5),
                    suggestion_id=str(suggestion.get("id")) if suggestion else None,
                    model_overlap=round(face_iou, 5),
                    current_overlap=round(
                        room_polygon_builder.iou(current, face_polygon) if not current.is_empty else 0.0,
                        5,
                    ),
                )

        regions = self.regions(prepared, envelope)
        model_seed = model.representative_point()
        current_seed = current.representative_point() if not current.is_empty else None
        best_region: Polygon | None = None
        best_score = -1.0
        best_model_overlap = 0.0
        best_current_overlap = 0.0
        best_iou = 0.0
        best_area_ratio = 0.0
        best_contains_model = False

        for region in regions:
            model_overlap = float(region.intersection(model).area / max(model.area, 1e-9))
            current_overlap = (
                float(region.intersection(current).area / max(current.area, 1e-9)) if not current.is_empty else 0.0
            )
            contains_model = region.buffer(1.5).contains(model_seed)
            contains_current = bool(current_seed and region.buffer(1.5).contains(current_seed))
            ratio = region.area / max(model.area, 1e-9)
            region_iou = room_polygon_builder.iou(region, model)
            oversize_penalty = max(0.0, math.log(max(ratio, 1.0)) - math.log(3.2)) * 0.22
            undersize_penalty = max(0.0, 0.45 - ratio) * 0.45
            score = (
                model_overlap * 0.66
                + current_overlap * 0.16
                + (0.24 if contains_model else 0.0)
                + (0.04 if contains_current else 0.0)
                - oversize_penalty
                - undersize_penalty
            )
            if score > best_score:
                best_region = region
                best_score = score
                best_model_overlap = model_overlap
                best_current_overlap = current_overlap
                best_iou = region_iou
                best_area_ratio = ratio
                best_contains_model = contains_model

        # Replace the model outline with a complete wall-bounded region only
        # when both shapes clearly describe the same room.  A much larger
        # region is usually an apartment/open-plan cell, not a room correction.
        region_is_same_room = bool(
            best_region is not None
            and best_contains_model
            and best_model_overlap >= 0.78
            and best_iou >= 0.55
            and 0.60 <= best_area_ratio <= 1.65
        )
        if not region_is_same_room:
            provisional = polygon_regularizer.regularize(
                model_points, wall_thickness_px=float(prepared.get("typical_thickness_px") or 0)
            )
            return SeededRoomResult(
                points=provisional.get("points") or model_points,
                model_points=model_points,
                source="model_only",
                score=round(max(best_score, 0.0), 5),
                suggestion_id=str(suggestion.get("id")) if suggestion else None,
                model_overlap=round(max(best_model_overlap, 0.0), 5),
                current_overlap=round(max(best_current_overlap, 0.0), 5),
            )

        return SeededRoomResult(
            points=room_polygon_builder.polygon_to_points(best_region),
            model_points=model_points,
            source="model_seed_wall_region",
            score=round(best_score, 5),
            suggestion_id=str(suggestion.get("id")) if suggestion else None,
            model_overlap=round(best_model_overlap, 5),
            current_overlap=round(best_current_overlap, 5),
        )

    def candidates(
        self,
        *,
        suggestions: Iterable[dict[str, Any]],
        prepared: dict[str, Any],
        envelope: Polygon,
    ) -> list[dict[str, Any]]:
        output: list[dict[str, Any]] = []
        used_hashes: set[str] = set()
        for suggestion in suggestions:
            if suggestion.get("status") in {"rejected", "superseded"}:
                continue
            provisional = self.provisional(
                suggestion, wall_thickness_px=float(prepared.get("typical_thickness_px") or 0)
            )
            if not provisional:
                continue
            seeded = self.refine(
                room_id=str(suggestion.get("matched_room_id") or "") or None,
                room_points=provisional["points"],
                suggestions=[suggestion],
                prepared=prepared,
                envelope=envelope,
            )
            points = seeded.points if seeded else provisional["points"]
            boundary_source = seeded.source if seeded else "model_only"
            wall_alignment = (
                float(seeded.score)
                if seeded and seeded.source == "model_seed_wall_faces"
                else 0.0
            )
            polygon = room_polygon_builder.points_to_polygon(points)
            if polygon.is_empty:
                continue
            geometry_hash = room_polygon_builder.geometry_hash(polygon)
            if geometry_hash in used_hashes:
                continue
            used_hashes.add(geometry_hash)
            output.append({
                "points": points,
                "model_points": provisional["model_points"],
                "suggestion_id": provisional["suggestion_id"],
                "confidence": provisional["confidence"],
                "seed_score": max(seeded.score if seeded else 0.0, wall_alignment),
                "geometry_hash": geometry_hash,
                "boundary_source": boundary_source,
                "wall_alignment": round(wall_alignment, 5),
            })
        return output

    def _snap_to_wall_faces(
        self,
        points: list[dict[str, float]],
        prepared: dict[str, Any],
    ) -> tuple[list[dict[str, float]], float]:
        """Use a model outline only when most edges are supported by wall faces."""
        polygon = room_polygon_builder.points_to_polygon(points)
        footprints = prepared.get("wall_footprints")
        if polygon.is_empty or polygon.length <= 0 or footprints is None or footprints.is_empty:
            return points, 0.0

        typical = max(float(prepared.get("typical_thickness_px") or 0.0), 2.0)
        snapped_points = room_polygon_builder.snap_polygon_to_walls(
            points,
            prepared,
            tolerance=max(4.0, typical * 2.25),
        )
        snapped = room_polygon_builder.points_to_polygon(snapped_points)
        if snapped.is_empty or snapped.length <= 0:
            return points, 0.0

        support_lines: list[Any] = [footprints.boundary]
        for closure in prepared.get("door_closures") or []:
            line = closure.get("line")
            if line is not None and not getattr(line, "is_empty", True):
                support_lines.append(line)
        wall_faces = unary_union(support_lines)
        supported_length = snapped.boundary.intersection(
            wall_faces.buffer(max(1.5, typical * 0.45))
        ).length
        alignment = max(0.0, min(1.0, float(supported_length) / float(snapped.length)))
        return snapped_points, alignment

    @staticmethod
    def _parts(geometry: Any) -> list[Polygon]:
        if geometry is None or getattr(geometry, "is_empty", True):
            return []
        if isinstance(geometry, Polygon):
            return [geometry]
        if isinstance(geometry, MultiPolygon):
            return list(geometry.geoms)
        if hasattr(geometry, "geoms"):
            return [item for item in geometry.geoms if isinstance(item, Polygon)]
        return []


room_seed_service = RoomSeedService()
