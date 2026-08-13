from __future__ import annotations

from typing import Any

from shapely.geometry import Polygon


class RoomDetectionMergeService:
    """Merge full-plan and overlapping-tile detections without joining rooms."""

    duplicate_iou = 0.72
    contained_ratio = 0.88

    def merge(self, predictions: list[dict[str, Any]]) -> list[dict[str, Any]]:
        ranked = sorted(predictions, key=self._score, reverse=True)
        kept: list[tuple[dict[str, Any], Polygon]] = []
        for prediction in ranked:
            polygon = self._polygon(prediction)
            if polygon.is_empty:
                continue
            duplicate_index: int | None = None
            for index, (_, existing) in enumerate(kept):
                intersection = polygon.intersection(existing).area
                union = polygon.union(existing).area
                iou = intersection / union if union else 0.0
                smaller = min(polygon.area, existing.area)
                contained = intersection / smaller if smaller else 0.0
                if iou >= self.duplicate_iou or contained >= self.contained_ratio:
                    duplicate_index = index
                    break
            if duplicate_index is None:
                kept.append((prediction, polygon))
            elif self._score(prediction) > self._score(kept[duplicate_index][0]):
                kept[duplicate_index] = (prediction, polygon)
        return [item for item, _ in kept]

    @staticmethod
    def _score(item: dict[str, Any]) -> tuple[float, float, float]:
        complete = 0.0 if item.get("touches_tile_edge") else 1.0
        full_plan = 0.2 if item.get("detection_pass") == "full" else 0.0
        return complete, float(item.get("confidence") or 0) + full_plan, float(item.get("area") or 0)

    @staticmethod
    def _polygon(item: dict[str, Any]) -> Polygon:
        polygon = Polygon([(float(p["x"]), float(p["y"])) for p in item.get("points") or []])
        if not polygon.is_valid:
            polygon = polygon.buffer(0)
        if polygon.geom_type == "MultiPolygon":
            polygon = max(polygon.geoms, key=lambda part: part.area)
        return polygon if isinstance(polygon, Polygon) else Polygon()


room_detection_merge_service = RoomDetectionMergeService()
