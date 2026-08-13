from __future__ import annotations

import math
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

import httpx
from PIL import Image

from app.core.config import settings
from app.model_review.wall_tile_service import wall_tile_service


class DetectionProvider:
    name = "roboflow"

    def detect(self, image_path: Path, *, analysis_mode: str = "standard") -> dict[str, Any]:
        """Run the shared multi-class floor model.

        Standard analysis uploads the floor crop once. Deep analysis is an
        explicit recovery mode: it keeps the full-image result, then adds
        overlapping high-resolution tiles and removes duplicate predictions
        locally. Deep analysis is never triggered by opening a page.
        """
        mode = str(analysis_mode or "standard").strip().lower()
        if mode not in {"standard", "deep"}:
            raise ValueError("analysis_mode must be 'standard' or 'deep'.")
        if mode == "deep" and not settings.roboflow_deep_analysis_enabled:
            raise RuntimeError("Deep model analysis is disabled.")
        if not settings.roboflow_api_key:
            return {
                "predictions": [],
                "provider": "not_configured",
                "model_id": settings.roboflow_model_id,
                "analysis_mode": mode,
                "request_count": 0,
            }

        full = self._request(image_path)
        predictions = list(full.get("predictions") or [])
        request_count = 1
        tile_count = 0
        if mode == "deep":
            tiled, tile_count = self._tiled_predictions(image_path)
            predictions = self._deduplicate([*predictions, *tiled])
            request_count += tile_count

        result = dict(full)
        result["predictions"] = predictions
        result["provider"] = self.name
        result["model_id"] = settings.roboflow_model_id
        result["analysis_mode"] = mode
        result["request_count"] = request_count
        result["tile_count"] = tile_count
        return result

    def _request(self, image_path: Path) -> dict[str, Any]:
        return self._request_content(image_path.name, image_path.read_bytes())

    def _request_content(self, filename: str, content: bytes) -> dict[str, Any]:
        url = f"{settings.roboflow_api_base_url.rstrip('/')}/{settings.roboflow_model_id}"
        response = httpx.post(
            url,
            params={"api_key": settings.roboflow_api_key},
            files={"file": (filename, content, "image/png")},
            timeout=settings.roboflow_timeout_seconds,
        )
        response.raise_for_status()
        payload = response.json()
        return payload if isinstance(payload, dict) else {"predictions": []}

    def detect_precision_recovery(self, image_path: Path) -> dict[str, Any]:
        """Scan original-colour tiles for walls, doors and windows."""
        if not settings.roboflow_api_key:
            return {
                "predictions": [], "provider": "not_configured",
                "model_id": settings.roboflow_model_id, "analysis_mode": "wall_recovery",
                "request_count": 0, "tile_count": 0,
            }
        tiles = wall_tile_service.tiles(
            image_path,
            target_pixels=settings.wall_recovery_tile_pixels,
            overlap=settings.wall_recovery_tile_overlap,
            maximum_tiles=settings.wall_recovery_max_tiles,
        )
        predictions: list[dict[str, Any]] = []
        failures: list[str] = []
        with ThreadPoolExecutor(
            max_workers=min(settings.wall_recovery_concurrency, len(tiles) or 1)
        ) as executor:
            pending = {
                executor.submit(
                    self._request_content, f"wall-recovery-{tile.index}.png", tile.content
                ): tile
                for tile in tiles
            }
            for future in as_completed(pending):
                tile = pending[future]
                try:
                    payload = future.result()
                except Exception as exc:
                    failures.append(f"tile-{tile.index}: {exc}")
                    continue
                for item in payload.get("predictions") or []:
                    class_name = str(
                        item.get("class") or item.get("class_name") or ""
                    ).lower()
                    if not any(name in class_name for name in ("wall", "door", "window")):
                        continue
                    shifted = self._shift_prediction(item, tile.x, tile.y)
                    if shifted:
                        shifted["detection_pass"] = "original_tile"
                        shifted["recovery_source"] = "original_tile"
                        predictions.append(shifted)
        return {
            "predictions": self._deduplicate(predictions),
            "provider": self.name,
            "model_id": settings.roboflow_model_id,
            "analysis_mode": "wall_recovery",
            "request_count": len(tiles),
            "tile_count": len(tiles),
            "failures": failures,
        }

    def detect_wall_recovery(self, image_path: Path) -> dict[str, Any]:
        """Compatibility alias for previously queued recovery jobs."""
        return self.detect_precision_recovery(image_path)

    def _tiled_predictions(self, image_path: Path) -> tuple[list[dict[str, Any]], int]:
        """Return predictions transformed into original-image coordinates."""
        overlap = float(settings.roboflow_deep_analysis_tile_overlap)
        with Image.open(image_path) as source:
            image = source.convert("RGB")
            width, height = image.size
            # Keep normal plans to a small, predictable request count. The
            # longer side is split into at most three tiles and each tile is
            # large enough to preserve wall context.
            target = max(640, min(1280, int(max(width, height) * 0.62)))
            tile_width = min(width, target)
            tile_height = min(height, target)
            x_positions = self._positions(width, tile_width, overlap)
            y_positions = self._positions(height, tile_height, overlap)
            predictions: list[dict[str, Any]] = []
            requests = 0
            with tempfile.TemporaryDirectory(prefix="autoboq-model-tiles-") as temp_dir:
                root = Path(temp_dir)
                for row, top in enumerate(y_positions):
                    for column, left in enumerate(x_positions):
                        right = min(width, left + tile_width)
                        bottom = min(height, top + tile_height)
                        # Skip a tile that is effectively the full image; the
                        # standard pass already covered it.
                        if left == 0 and top == 0 and right == width and bottom == height:
                            continue
                        tile_path = root / f"tile-{row}-{column}.png"
                        image.crop((left, top, right, bottom)).save(tile_path, format="PNG")
                        payload = self._request(tile_path)
                        requests += 1
                        for item in payload.get("predictions") or []:
                            shifted = self._shift_prediction(item, left, top)
                            if shifted:
                                predictions.append(shifted)
            return predictions, requests

    @staticmethod
    def _positions(total: int, tile: int, overlap: float) -> list[int]:
        if tile >= total:
            return [0]
        step = max(1, int(round(tile * (1.0 - overlap))))
        positions = list(range(0, max(1, total - tile + 1), step))
        last = total - tile
        if not positions or positions[-1] != last:
            positions.append(last)
        # Avoid excessive calls on unusually large drawings.
        if len(positions) > 3:
            positions = [0, int(round(last / 2)), last]
        return sorted(set(max(0, value) for value in positions))

    @staticmethod
    def _shift_prediction(item: Any, left: int, top: int) -> dict[str, Any] | None:
        if not isinstance(item, dict):
            return None
        shifted = dict(item)
        if item.get("x") is not None:
            shifted["x"] = float(item["x"]) + left
        if item.get("y") is not None:
            shifted["y"] = float(item["y"]) + top
        points = item.get("points")
        if isinstance(points, list):
            shifted["points"] = [
                {**point, "x": float(point["x"]) + left, "y": float(point["y"]) + top}
                for point in points
                if isinstance(point, dict) and point.get("x") is not None and point.get("y") is not None
            ]
        return shifted

    def _deduplicate(self, predictions: list[dict[str, Any]]) -> list[dict[str, Any]]:
        ordered = sorted(
            (item for item in predictions if isinstance(item, dict)),
            key=lambda item: float(item.get("confidence") or 0.0),
            reverse=True,
        )
        kept: list[dict[str, Any]] = []
        for candidate in ordered:
            candidate_class = str(candidate.get("class") or candidate.get("class_name") or "").lower()
            if any(
                candidate_class == str(existing.get("class") or existing.get("class_name") or "").lower()
                and self._iou(candidate, existing) >= 0.55
                for existing in kept
            ):
                continue
            kept.append(candidate)
        return kept

    @staticmethod
    def _iou(first: dict[str, Any], second: dict[str, Any]) -> float:
        def box(item: dict[str, Any]) -> tuple[float, float, float, float]:
            x = float(item.get("x") or 0.0)
            y = float(item.get("y") or 0.0)
            width = max(0.0, float(item.get("width") or 0.0))
            height = max(0.0, float(item.get("height") or 0.0))
            return x - width / 2.0, y - height / 2.0, x + width / 2.0, y + height / 2.0

        ax1, ay1, ax2, ay2 = box(first)
        bx1, by1, bx2, by2 = box(second)
        intersection = max(0.0, min(ax2, bx2) - max(ax1, bx1)) * max(0.0, min(ay2, by2) - max(ay1, by1))
        if intersection <= 0:
            return 0.0
        first_area = max(0.0, ax2 - ax1) * max(0.0, ay2 - ay1)
        second_area = max(0.0, bx2 - bx1) * max(0.0, by2 - by1)
        union = first_area + second_area - intersection
        return intersection / union if union > 0 and math.isfinite(union) else 0.0


detection_provider = DetectionProvider()
