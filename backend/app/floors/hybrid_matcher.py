from __future__ import annotations

from typing import Any

from app.floors.polygon_builder import room_polygon_builder


class HybridRoomMatcher:
    verified_threshold = 0.72
    review_threshold = 0.30

    def reconcile(
        self,
        wall_candidates: list[dict[str, Any]],
        model_suggestions: list[dict[str, Any]],
    ) -> dict[str, Any]:
        unused = {
            str(item["id"]): item
            for item in model_suggestions
            if item.get("status") not in {"rejected", "superseded"}
        }
        matches: list[dict[str, Any]] = []
        canonical: list[dict[str, Any]] = []

        for candidate in wall_candidates:
            wall_polygon = room_polygon_builder.points_to_polygon(candidate.get("points") or [])
            best_id: str | None = None
            best_score = 0.0
            for suggestion_id, suggestion in unused.items():
                model_polygon = room_polygon_builder.points_to_polygon(
                    (suggestion.get("polygon") or {}).get("points") or suggestion.get("points") or []
                )
                if wall_polygon.is_empty or model_polygon.is_empty:
                    continue
                iou = room_polygon_builder.iou(wall_polygon, model_polygon)
                seed_inside = wall_polygon.buffer(2).contains(model_polygon.representative_point())
                reverse_inside = model_polygon.buffer(2).contains(wall_polygon.representative_point())
                score = iou + (0.12 if seed_inside else 0.0) + (0.05 if reverse_inside else 0.0)
                matched_room_id = str(suggestion.get("matched_room_id") or "")
                candidate_room_id = str(candidate.get("room_id") or "")
                if matched_room_id and candidate_room_id and matched_room_id == candidate_room_id:
                    score += 0.35
                if score > best_score:
                    best_id, best_score = suggestion_id, score

            result = dict(candidate)
            if best_id and best_score >= self.review_threshold:
                suggestion = unused.pop(best_id)
                model_polygon = room_polygon_builder.points_to_polygon(
                    (suggestion.get("polygon") or {}).get("points") or []
                )
                iou = room_polygon_builder.iou(wall_polygon, model_polygon)
                verified = iou >= self.verified_threshold
                current_source = str(result.get("boundary_source") or "")
                corrected_source = (
                    current_source
                    if current_source in {"model_seed_wall_faces", "model_seed_wall_region"}
                    else "model_seed_wall_region"
                )
                result.update({
                    "detection_source": "hybrid",
                    "boundary_source": corrected_source,
                    "model_verified": verified,
                    "comparison_status": "verified" if verified else "wall_corrected",
                    "confidence": max(float(suggestion.get("confidence") or 0), min(max(iou, 0.0), 1.0)),
                    "suggestion_id": best_id,
                    "comparison_score": iou,
                    "geometry_status": "ready" if verified and not result.get("touches_crop_edge") else "needs_review",
                })
                matches.append({
                    "room_id": candidate.get("room_id"),
                    "suggestion_id": best_id,
                    "score": iou,
                    "verified": verified,
                })
            else:
                result.update({
                    "detection_source": result.get("detection_source") or "wall_geometry",
                    "boundary_source": result.get("boundary_source") or "wall_only",
                    "model_verified": False,
                    "comparison_status": "wall_only",
                    "confidence": float(result.get("confidence") or 0.65),
                    "geometry_status": "needs_review" if result.get("touches_crop_edge") else result.get("geometry_status", "ready"),
                })
            canonical.append(result)

        return {
            "canonical": canonical,
            "matches": matches,
            "unmatched_suggestions": list(unused.values()),
        }


hybrid_room_matcher = HybridRoomMatcher()
