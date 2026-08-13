from __future__ import annotations

from collections import defaultdict
from typing import Any

from shapely.geometry import Point, Polygon

from app.floors.polygon_builder import room_polygon_builder
from app.floors.room_semantics import room_semantics
from app.floors.wall_cell_service import wall_cell_service


class RoomExceptionService:
    """Recover strongly labelled spaces without changing the model-first flow.

    Printed labels are semantic evidence, never geometry. A missed room is
    recovered only when an existing wall cell contains the label. Open-plan
    labels may share a cell; incompatible labels never create an artificial
    split when the wall network cannot support one.
    """

    minimum_match_iou = 0.45
    open_plan_labels = frozenset({
        "Dining Area", "Living Room", "Living Area", "Sitting Area",
        "Kitchen", "Kitchenette", "Pantry",
    })

    def recover(
        self,
        *,
        candidates: list[dict[str, Any]],
        wall_cells: list[dict[str, Any]],
        text_blocks: list[dict[str, Any]],
        minimum_label_confidence: float = 0.72,
    ) -> dict[str, Any]:
        observations = [
            item for item in self._observations(text_blocks)
            if float(item["confidence"]) >= minimum_label_confidence
        ]
        if not observations:
            return {"candidates": candidates, "recovered": 0, "labelled": 0, "ambiguous": 0}

        output = [dict(item) for item in candidates]
        labelled = self._label_existing(output, observations)
        cell_labels: dict[int, list[dict[str, Any]]] = defaultdict(list)
        cell_polygons: dict[int, Polygon] = {}
        for observation in observations:
            containing = wall_cell_service.smallest_containing(
                wall_cells, observation["point"]
            )
            if containing:
                index, polygon = containing
                cell_labels[index].append(observation)
                cell_polygons[index] = polygon

        recovered = 0
        ambiguous = 0
        for index, observations_in_cell in cell_labels.items():
            labels = self._unique_labels(observations_in_cell)
            if not self._compatible(labels):
                ambiguous += 1
                continue
            semantic = room_semantics.classify(labels)
            polygon = cell_polygons[index]
            match_index = self._matching_candidate(output, polygon)
            patch = self._semantic_patch(
                labels,
                semantic,
                confidence=max(float(item["confidence"]) for item in observations_in_cell),
                label_source=self._best_source(observations_in_cell),
            )
            if match_index is not None:
                output[match_index] = {
                    **output[match_index],
                    **patch,
                    "boundary_source": "label_seed_wall_cell",
                    "label_recovery": True,
                }
                continue

            cell = wall_cells[index]
            output.append({
                **cell,
                **patch,
                "points": room_polygon_builder.polygon_to_points(polygon),
                "raw_points": cell.get("points") or [],
                "model_points": [],
                "area_px": float(polygon.area),
                "perimeter_px": float(polygon.length),
                "geometry_hash": room_polygon_builder.geometry_hash(polygon),
                "shape_type": cell.get("shape_type") or "polygon",
                "geometry_status": "needs_review",
                "boundary_source": "label_seed_wall_cell",
                "measurement_authority": "wall_geometry",
                "label_recovery": True,
                "touches_crop_edge": bool(cell.get("touches_crop_edge")),
                "wall_ids": cell.get("wall_ids") or [],
                "opening_ids": cell.get("opening_ids") or [],
            })
            recovered += 1

        return {
            "candidates": output,
            "recovered": recovered,
            "labelled": labelled,
            "ambiguous": ambiguous,
        }

    def _label_existing(
        self,
        candidates: list[dict[str, Any]],
        observations: list[dict[str, Any]],
    ) -> int:
        assigned: dict[int, list[dict[str, Any]]] = defaultdict(list)
        for observation in observations:
            containing: list[tuple[float, int]] = []
            for index, candidate in enumerate(candidates):
                polygon = self._polygon(candidate)
                if not polygon.is_empty and polygon.buffer(1.0).contains(observation["point"]):
                    containing.append((float(polygon.area), index))
            if containing:
                _, index = min(containing, key=lambda item: item[0])
                assigned[index].append(observation)

        labelled = 0
        for index, items in assigned.items():
            labels = self._unique_labels(items)
            if not self._compatible(labels):
                continue
            semantic = room_semantics.classify(labels)
            candidates[index].update(self._semantic_patch(
                labels,
                semantic,
                confidence=max(float(item["confidence"]) for item in items),
                label_source=self._best_source(items),
            ))
            labelled += 1
        return labelled

    def _observations(self, text_blocks: list[dict[str, Any]]) -> list[dict[str, Any]]:
        output: list[dict[str, Any]] = []
        for block in text_blocks:
            labels = [
                label for label in room_semantics.match_known_labels(block.get("text"))
                if label in room_semantics.EXCEPTION_RECOVERY_LABELS
            ]
            if not labels:
                continue
            bbox = block.get("bbox") or {}
            try:
                point = Point(
                    (float(bbox["x0"]) + float(bbox["x1"])) / 2,
                    (float(bbox["y0"]) + float(bbox["y1"])) / 2,
                )
                confidence = float(block.get("confidence") or 0.95)
            except (KeyError, TypeError, ValueError):
                continue
            for label in labels:
                output.append({
                    "label": label,
                    "point": point,
                    "confidence": max(0.0, min(confidence, 1.0)),
                    "source": str(block.get("source") or "drawing"),
                })
        return output

    @staticmethod
    def _unique_labels(items: list[dict[str, Any]]) -> list[str]:
        output: list[str] = []
        for item in items:
            label = str(item["label"])
            if label not in output:
                output.append(label)
        return output

    def _compatible(self, labels: list[str]) -> bool:
        unique = set(labels)
        return len(unique) == 1 or unique.issubset(self.open_plan_labels)

    def _matching_candidate(
        self, candidates: list[dict[str, Any]], cell_polygon: Polygon
    ) -> int | None:
        best_index: int | None = None
        best_score = 0.0
        for index, candidate in enumerate(candidates):
            polygon = self._polygon(candidate)
            if polygon.is_empty:
                continue
            iou = room_polygon_builder.iou(cell_polygon, polygon)
            area_ratio = polygon.area / max(cell_polygon.area, 1e-9)
            score = iou if 0.55 <= area_ratio <= 1.80 else 0.0
            if score >= self.minimum_match_iou and score > best_score:
                best_index, best_score = index, score
        return best_index

    @staticmethod
    def _semantic_patch(
        labels: list[str],
        semantic: dict[str, object],
        *,
        confidence: float,
        label_source: str,
    ) -> dict[str, Any]:
        return {
            "label_hint": semantic.get("name") or labels[0],
            "room_type_hint": semantic.get("room_type") or labels[0],
            "label_candidates": labels,
            "label_source_hint": label_source,
            "label_confidence_hint": confidence,
            "space_kind": semantic.get("space_kind") or "internal",
            "include_in_boq": bool(semantic.get("include_in_boq", True)),
            "open_plan": bool(semantic.get("open_plan")),
            "semantic_type": semantic.get("semantic_type"),
            "confidence": max(confidence, 0.75),
        }

    @staticmethod
    def _best_source(items: list[dict[str, Any]]) -> str:
        priority = {"drawing": 3, "drawing_ocr": 2, "local_ocr": 2, "roboflow_class": 1}
        return max(
            (str(item.get("source") or "drawing") for item in items),
            key=lambda value: priority.get(value, 0),
            default="drawing",
        )

    @staticmethod
    def _polygon(item: dict[str, Any]) -> Polygon:
        return room_polygon_builder.points_to_polygon(item.get("points") or [])


room_exception_service = RoomExceptionService()
