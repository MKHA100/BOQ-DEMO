from __future__ import annotations

import math
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

from PIL import Image

from app.core.config import settings
from app.floors.vector_geometry_service import vector_floor_geometry_service
from app.model_review.prediction_processor import (
    ProcessedPrediction,
    automatic_status,
    process_predictions,
)
from app.model_review.opening_candidate_validator import opening_candidate_validator
from app.model_review.provider import detection_provider
from app.model_review.reconciliation_service import match_score
from app.model_review.wall_candidate_validator import wall_candidate_validator


class WallRecoveryService:
    """Recover only wall candidates supported by the existing wall network."""

    def detect(
        self,
        *,
        project_id: str,
        floor_id: str,
        image_path: Path,
        crop_width: float,
        crop_height: float,
        seed_walls: list[dict[str, Any]],
    ) -> dict[str, Any]:
        with ThreadPoolExecutor(max_workers=2) as executor:
            model_future = executor.submit(detection_provider.detect_precision_recovery, image_path)
            vector_future = (
                executor.submit(vector_floor_geometry_service.extract, project_id, floor_id)
                if settings.wall_vector_recovery_enabled
                else None
            )
            raw = model_future.result()
            vector_error: str | None = None
            if vector_future is not None:
                try:
                    vector_evidence = vector_future.result()
                except Exception as exc:
                    vector_evidence = {"wall_pairs": []}
                    vector_error = str(exc)
            else:
                vector_evidence = {"wall_pairs": []}
        with Image.open(image_path) as image:
            image_width, image_height = image.size
        groups = process_predictions(
            raw,
            image_width=image_width,
            image_height=image_height,
            crop_width=crop_width,
            crop_height=crop_height,
            threshold_overrides={
                "wall": settings.wall_recovery_min_confidence,
                "door": settings.door_recovery_min_confidence,
                "window": settings.window_recovery_min_confidence,
            },
        )
        walls = list(groups["wall"])
        vector_count = 0
        if settings.wall_vector_recovery_enabled:
            for pair in vector_evidence.get("wall_pairs") or []:
                prediction = self._vector_prediction(pair)
                if prediction is not None:
                    walls.append(prediction)
                    vector_count += 1
        walls = self._deduplicate(walls)
        walls = wall_candidate_validator.validate(
            walls,
            seed_walls=seed_walls,
            crop_width=crop_width,
            crop_height=crop_height,
        )
        doors = opening_candidate_validator.validate(
            self._deduplicate(list(groups["door"])),
            seed_walls=seed_walls,
            crop_width=crop_width,
            crop_height=crop_height,
        )
        windows = opening_candidate_validator.validate(
            self._deduplicate(list(groups["window"])),
            seed_walls=seed_walls,
            crop_width=crop_width,
            crop_height=crop_height,
        )
        return {
            "raw": {
                **raw,
                "vector_wall_count": vector_count,
                "vector_recovery_error": vector_error,
            },
            "groups": {"door": doors, "window": windows, "wall": walls},
            "door_count": len(doors),
            "window_count": len(windows),
            "wall_count": len(walls),
            "vector_wall_count": vector_count,
        }

    @staticmethod
    def _vector_prediction(pair: dict[str, Any]) -> ProcessedPrediction | None:
        line = pair.get("centerline") or {}
        start, end = line.get("start") or {}, line.get("end") or {}
        try:
            x1, y1 = float(start["x"]), float(start["y"])
            x2, y2 = float(end["x"]), float(end["y"])
            thickness = max(0.5, float(pair.get("thickness_px") or 0))
            confidence = float(pair.get("confidence") or 0.75)
        except (KeyError, TypeError, ValueError):
            return None
        dx, dy = abs(x2 - x1), abs(y2 - y1)
        if max(dx, dy) < 8 or min(dx, dy) > max(dx, dy) * 0.25:
            return None
        if dx >= dy:
            geometry = {
                "x": min(x1, x2),
                "y": (y1 + y2) / 2 - thickness / 2,
                "width": max(dx, 0.5),
                "height": thickness,
                "rotation": 0.0,
            }
        else:
            geometry = {
                "x": (x1 + x2) / 2 - thickness / 2,
                "y": min(y1, y2),
                "width": thickness,
                "height": max(dy, 0.5),
                "rotation": 0.0,
            }
        return ProcessedPrediction(
            element_type="wall",
            geometry=geometry,
            confidence=max(0.0, min(confidence, 1.0)),
            status=automatic_status("wall", confidence, geometry),
            raw={
                "class": "wall",
                "recovery_source": "pdf_vector",
                "vector_wall_id": pair.get("id"),
            },
        )

    @staticmethod
    def _deduplicate(
        predictions: list[ProcessedPrediction],
    ) -> list[ProcessedPrediction]:
        priority = {"original_tile": 2, "pdf_vector": 1}
        ordered = sorted(
            predictions,
            key=lambda item: (
                priority.get(str(item.raw.get("recovery_source") or ""), 0),
                item.confidence,
                max(item.geometry.get("width", 0), item.geometry.get("height", 0)),
            ),
            reverse=True,
        )
        kept: list[ProcessedPrediction] = []
        for candidate in ordered:
            if any(
                match_score(
                    {"geometry": existing.geometry},
                    candidate.geometry,
                ) >= 0.72
                for existing in kept
            ):
                continue
            if not all(math.isfinite(float(value)) for value in candidate.geometry.values()):
                continue
            kept.append(candidate)
        return kept


wall_recovery_service = WallRecoveryService()
