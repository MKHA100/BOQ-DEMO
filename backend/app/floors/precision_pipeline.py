from __future__ import annotations

from typing import Any

from app.floors.building_envelope_service import building_envelope_service
from app.floors.dimension_constraint_service import dimension_constraint_service
from app.floors.free_space_service import free_space_service
from app.floors.wall_footprint_service import wall_footprint_service
from app.floors.label_service import room_label_service
from app.floors.polygon_builder import room_polygon_builder
from app.floors.polygon_regularizer import polygon_regularizer
from app.floors.room_semantics import room_semantics
from app.floors.room_validation_service import room_validation_service
from app.floors.room_seed_service import room_seed_service


class PrecisionRoomPipeline:
    def refine(
        self,
        *,
        project_id: str,
        floor_id: str,
        floor: dict[str, Any],
        rooms: list[dict[str, Any]],
        prepared: dict[str, Any],
        evidence: dict[str, Any],
        suggestions: list[dict[str, Any]] | None = None,
    ) -> dict[str, dict[str, Any]]:
        crop_rect = ((floor.get("coordinates") or {}).get("original_rect") or {})
        envelope = building_envelope_service.build(
            prepared,
            float(crop_rect.get("width") or 1),
            float(crop_rect.get("height") or 1),
        )
        labels = room_label_service.suggestions(project_id, floor_id, rooms)
        free_space = free_space_service.calculate(envelope, wall_footprint_service.footprints(prepared))
        mm_per_pixel = float(floor.get("mm_per_pixel") or 0)
        scale_verified = bool(mm_per_pixel and int(floor.get("scale_version") or 0) > 0)
        output: dict[str, dict[str, Any]] = {}
        suggestions = suggestions or []
        for room in rooms:
            raw_points = (room.get("raw_geometry") or room.get("generated_geometry") or room.get("geometry") or {}).get("points") or []
            current_points = (room.get("geometry") or {}).get("points") or raw_points
            polygon = room_polygon_builder.points_to_polygon(current_points)
            if polygon.is_empty:
                output[str(room["id"])] = {"precision_status": "invalid", "validation_details": {"issues": ["Invalid polygon."]}}
                continue
            overlap = building_envelope_service.overlap_ratio(polygon, envelope)
            free_overlap = float(polygon.intersection(free_space).area / max(polygon.area, 1e-9)) if not free_space.is_empty else overlap
            semantic_hint = labels.get(str(room["id"]), {})
            semantic = room_semantics.classify(
                semantic_hint.get("label_candidates") or semantic_hint.get("name") or room.get("name") or room.get("room_type") or ""
            )
            external = semantic.get("space_kind") == "external"
            model_backed = bool(
                (room.get("raw_geometry") or room.get("generated_geometry") or {}).get("points")
                or str(room.get("boundary_source") or "") in {
                    "model_only", "roboflow", "model_seed_wall_region", "model_seed_wall_faces"
                }
            )
            if (overlap < 0.45 or free_overlap < 0.30) and not external and not model_backed:
                output[str(room["id"])] = {
                    "precision_status": "invalid",
                    "measurement_status": "invalid",
                    "validation_details": {"issues": ["Room is outside the usable building area."], "envelope_overlap": overlap, "free_space_overlap": free_overlap},
                }
                continue

            # build_polygons has already reconciled wall cells with model
            # seeds. Re-seeding those canonical cells can make several rooms
            # collapse onto the same suggestion. Only a raw model-only room
            # may seek a wall correction here.
            current_source = str(room.get("boundary_source") or "")
            seeded = (
                room_seed_service.refine(
                    room_id=str(room.get("id") or ""),
                    room_points=current_points,
                    suggestions=suggestions,
                    prepared=prepared,
                    envelope=envelope,
                )
                if current_source in {"model_only", "roboflow", "unknown", ""}
                else None
            )
            source_points = seeded.points if seeded is not None else current_points
            regularized = polygon_regularizer.regularize(
                source_points,
                wall_thickness_px=float(prepared.get("typical_thickness_px") or 0),
            )
            points = regularized["points"]
            dimension = dimension_constraint_service.apply(
                points,
                evidence.get("dimensions") or [],
                mm_per_pixel,
                preferred_width_mm=room.get("printed_width_mm"),
                preferred_length_mm=room.get("printed_length_mm"),
                preferred_source=room.get("dimension_source"),
            )
            grounded_source = seeded.source if seeded is not None else current_source
            if grounded_source in {
                "user", "wall_cell", "wall_only", "wall_geometry", "wall_corrected",
                "model_seed_wall_region", "model_seed_wall_faces", "label_seed_wall_cell",
            }:
                # Wall faces determine quantity geometry. Printed dimensions
                # remain comparison evidence and must not resize that polygon.
                dimension["points"] = points
            points = dimension["points"]
            refined_polygon = room_polygon_builder.points_to_polygon(points)
            # Wall correction is optional. Never replace a credible model
            # room with an invalid or materially unrelated polygon.
            model_polygon = room_polygon_builder.points_to_polygon(raw_points)
            used_model_fallback = False
            if model_backed and not model_polygon.is_empty:
                refined_iou = room_polygon_builder.iou(model_polygon, refined_polygon)
                area_ratio = refined_polygon.area / max(model_polygon.area, 1e-9)
                if (
                    refined_polygon.is_empty
                    or refined_iou < 0.45
                    or not 0.55 <= area_ratio <= 1.80
                ):
                    points = room_polygon_builder.polygon_to_points(model_polygon)
                    refined_polygon = model_polygon
                    seeded = None
                    used_model_fallback = True
            preserved_wall_source = current_source if current_source in {
                "wall_cell",
                "label_seed_wall_cell",
                "wall_geometry",
                "wall_corrected",
                "model_seed_wall_region",
                "model_seed_wall_faces",
            } else ""
            boundary_source = "user" if room.get("user_edited") or room.get("user_confirmed") else (
                seeded.source if seeded is not None else (
                    "model_only" if used_model_fallback else (preserved_wall_source or "wall_geometry")
                )
            )
            model_verified = bool(room.get("model_verified")) or bool(
                seeded is not None
                and seeded.source in {"model_seed_wall_region", "model_seed_wall_faces"}
                and seeded.model_overlap >= 0.55
            )
            validation = room_validation_service.validate(
                scale_verified=scale_verified,
                valid_geometry=not refined_polygon.is_empty and refined_polygon.is_valid,
                label=semantic_hint.get("name") or room.get("name"),
                difference_percent=dimension.get("difference_percent"),
                boundary_source=boundary_source,
                space_kind=str(semantic_hint.get("space_kind") or room.get("space_kind") or semantic.get("space_kind") or "internal"),
                model_verified=model_verified,
                shape_type=regularized.get("shape_type"),
                point_count=len(points),
                wall_aligned=boundary_source in {"user", "wall_cell", "label_seed_wall_cell", "model_seed_wall_region", "model_seed_wall_faces", "wall_geometry", "wall_corrected"},
            )
            patch: dict[str, Any] = {
                "regularized_geometry": {"points": points},
                "wall_corrected_geometry": {"points": points},
                "shape_type": regularized["shape_type"],
                "boundary_source": boundary_source,
                "precision_status": "ready" if validation["status"] == "correct" else "needs_review",
                "validation_details": {
                    **validation,
                    "envelope_overlap": round(overlap, 4),
                    "free_space_overlap": round(free_overlap, 4),
                    "regularizer_confidence": regularized["confidence"],
                    "original_vertex_count": regularized.get("original_vertex_count"),
                    "vertex_count": regularized.get("vertex_count"),
                    "regularizer_area_change_percent": regularized.get("area_change_percent"),
                    "seed_source": seeded.source if seeded else None,
                    "seed_score": seeded.score if seeded else None,
                    "seed_suggestion_id": seeded.suggestion_id if seeded else None,
                    "seed_model_overlap": seeded.model_overlap if seeded else None,
                },
                "measurement_status": validation["status"],
                "model_verified": model_verified,
                "detection_source": "hybrid" if seeded is not None and seeded.source in {
                    "model_seed_wall_region", "model_seed_wall_faces"
                } else ("roboflow" if seeded is not None else room.get("detection_source")),
                "comparison_status": "verified" if model_verified else ("model_provisional" if boundary_source == "model_only" else "wall_corrected"),
                "printed_width_mm": dimension.get("printed_width_mm"),
                "printed_length_mm": dimension.get("printed_length_mm"),
                "dimension_difference_percent": dimension.get("difference_percent"),
                "dimension_status": dimension.get("dimension_status") or "unknown",
                "dimension_source": dimension.get("dimension_source") or "unknown",
            }
            if not room.get("user_confirmed") and not room.get("user_edited"):
                patch.update({
                    "points": points,
                    "confirmed_geometry": {},
                    "geometry_hash": room_polygon_builder.geometry_hash(refined_polygon),
                    "geometry_status": "ready" if validation["status"] == "correct" else "needs_review",
                })
            # A user edit is the final authority. Vector text may supersede an
            # automated LLM/OCR label, but never a label the user saved.
            if semantic_hint and room.get("label_source") != "user":
                patch.update({
                    "name": semantic_hint.get("name") or room.get("name"),
                    "room_type": semantic_hint.get("room_type") or room.get("room_type"),
                    "label_source": semantic_hint.get("label_source") or room.get("label_source"),
                    "label_confidence": semantic_hint.get("label_confidence"),
                    "label_candidates": semantic_hint.get("label_candidates") or [],
                    "space_kind": semantic_hint.get("space_kind") or room.get("space_kind"),
                    "include_in_boq": semantic_hint.get("include_in_boq", room.get("include_in_boq")),
                    "open_plan": semantic_hint.get("open_plan", room.get("open_plan")),
                })
            output[str(room["id"])] = patch
        return output


precision_room_pipeline = PrecisionRoomPipeline()
