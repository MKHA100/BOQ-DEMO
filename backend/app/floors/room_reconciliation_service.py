from __future__ import annotations

from typing import Any

from app.floors.polygon_builder import room_polygon_builder


class RoomReconciliationService:
    """Deterministically match regenerated candidates to canonical rooms."""

    minimum_match_score = 0.15

    def match(
        self,
        rooms: list[dict[str, Any]],
        candidates: list[dict[str, Any]],
    ) -> dict[str, Any]:
        pairs: list[tuple[float, int, int]] = []
        for room_index, room in enumerate(rooms):
            current = room_polygon_builder.points_to_polygon(
                (room.get("geometry") or {}).get("points") or []
            )
            if current.is_empty:
                continue
            for candidate_index, candidate in enumerate(candidates):
                generated = room_polygon_builder.points_to_polygon(candidate.get("points") or [])
                if generated.is_empty:
                    continue
                score = room_polygon_builder.iou(current, generated)
                if current.buffer(2).contains(generated.representative_point()):
                    score += 0.08
                if generated.buffer(2).contains(current.representative_point()):
                    score += 0.04
                if score >= self.minimum_match_score:
                    pairs.append((score, room_index, candidate_index))
        pairs.sort(reverse=True)
        used_rooms: set[int] = set()
        used_candidates: set[int] = set()
        matches: dict[int, tuple[int, float]] = {}
        for score, room_index, candidate_index in pairs:
            if room_index in used_rooms or candidate_index in used_candidates:
                continue
            used_rooms.add(room_index)
            used_candidates.add(candidate_index)
            matches[room_index] = (candidate_index, score)
        return {
            "matches": matches,
            "unmatched_room_indexes": [index for index in range(len(rooms)) if index not in used_rooms],
            "unmatched_candidate_indexes": [index for index in range(len(candidates)) if index not in used_candidates],
        }


room_reconciliation_service = RoomReconciliationService()

