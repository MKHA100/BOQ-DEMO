from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

import fitz
import httpx
from shapely.geometry import Polygon

from app.core.config import settings
from app.floors.room_detection_merge_service import room_detection_merge_service
from app.floors.room_tile_service import RoomTile, room_tile_service


class RoomSegmentationError(RuntimeError):
    """Raised when the optional room model request cannot be completed."""


class RoomSegmentationProvider:
    """Call the configured room instance-segmentation model.

    The provider keeps the model polygon as evidence.  It validates and removes
    duplicate detections, but deliberately does not snap the polygon to walls;
    the deterministic room pipeline performs that correction afterwards.
    """

    name = "roboflow_room_segmentation"
    duplicate_iou = 0.88
    maximum_image_area_ratio = 0.78
    minimum_inside_ratio = 0.80

    def detect(self, image_path: Path, *, crop_version: int | None = None) -> dict[str, Any]:
        if not settings.roboflow_floor_enabled:
            return self._empty("disabled", image_path, crop_version)
        if not settings.roboflow_api_key:
            return self._empty("not_configured", image_path, crop_version)
        if not image_path.is_file():
            raise RoomSegmentationError(f"Floor crop is not available: {image_path}")

        width, height = self._image_size(image_path)
        tiles = room_tile_service.create(
            image_path,
            target_size=settings.room_tile_target_pixels,
            overlap=settings.room_tile_overlap,
            maximum_tiles=settings.room_tile_maximum,
        ) if getattr(settings, "room_tiled_detection_enabled", False) else []
        requests: list[tuple[str, bytes, int, int, int, int, RoomTile | None]] = [
            (image_path.name, image_path.read_bytes(), 0, 0, width, height, None)
        ]
        requests.extend(
            (f"room-tile-{tile.index}.png", tile.image, tile.x, tile.y, tile.width, tile.height, tile)
            for tile in tiles
        )
        responses: list[dict[str, Any]] = []
        failures: list[str] = []
        with ThreadPoolExecutor(
            max_workers=min(getattr(settings, "room_tile_concurrency", 1), len(requests))
        ) as executor:
            future_map = {
                executor.submit(self._request, name, content): (name, x, y, source_width, source_height, tile)
                for name, content, x, y, source_width, source_height, tile in requests
            }
            for future in as_completed(future_map):
                name, x, y, source_width, source_height, tile = future_map[future]
                try:
                    raw = future.result()
                    responses.append({
                        "name": name, "raw": raw, "x": x, "y": y,
                        "width": source_width, "height": source_height, "tile": tile,
                    })
                except RoomSegmentationError as exc:
                    failures.append(f"{name}: {exc}")
        if not responses:
            raise RoomSegmentationError("; ".join(failures) or "Room model returned no results.")

        normalized: list[dict[str, Any]] = []
        for item in responses:
            raw = item["raw"]
            response_width = float(raw.get("image", {}).get("width") or item["width"])
            response_height = float(raw.get("image", {}).get("height") or item["height"])
            for value in raw.get("predictions") or []:
                prediction = self._normalize_prediction(value)
                if prediction is None or not self._valid_for_image(
                    prediction, response_width, response_height,
                    maximum_area_ratio=0.96 if item["tile"] else self.maximum_image_area_ratio,
                ):
                    continue
                normalized.append(self._to_plan_coordinates(
                    prediction,
                    offset_x=float(item["x"]), offset_y=float(item["y"]),
                    source_width=float(item["width"]), source_height=float(item["height"]),
                    response_width=response_width, response_height=response_height,
                    tiled=item["tile"] is not None,
                ))
        predictions = room_detection_merge_service.merge(normalized)
        return {
            "provider": self.name,
            "model_id": settings.roboflow_floor_model_id,
            "crop_version": crop_version,
            "status": "ready",
            "image_width": float(width),
            "image_height": float(height),
            "predictions": predictions,
            "raw": {
                "mode": "full_plus_adaptive_tiles",
                "tile_count": len(tiles),
                "request_count": len(requests),
                "successful_requests": len(responses),
                "failures": failures,
                "responses": [
                    {
                        "name": item["name"],
                        "image": item["raw"].get("image"),
                        "prediction_count": len(item["raw"].get("predictions") or []),
                    }
                    for item in responses
                ],
            },
        }

    def _request(self, filename: str, content: bytes) -> dict[str, Any]:
        url = f"{settings.roboflow_api_base_url.rstrip('/')}/{settings.roboflow_floor_model_id}"
        params = {
            "api_key": settings.roboflow_api_key,
            "confidence": max(1, min(int(settings.roboflow_floor_confidence * 100), 99)),
        }
        try:
            response = httpx.post(
                url, params=params, files={"file": (filename, content, "image/png")},
                timeout=settings.roboflow_floor_timeout_seconds,
            )
            response.raise_for_status()
            raw = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise RoomSegmentationError(f"Room model request failed: {exc}") from exc
        if not isinstance(raw, dict):
            raise RoomSegmentationError("Room model returned an unexpected response.")
        return raw

    @staticmethod
    def _to_plan_coordinates(
        prediction: dict[str, Any], *, offset_x: float, offset_y: float,
        source_width: float, source_height: float,
        response_width: float, response_height: float, tiled: bool,
    ) -> dict[str, Any]:
        scale_x = source_width / max(response_width, 1.0)
        scale_y = source_height / max(response_height, 1.0)
        points = [
            {"x": offset_x + float(point["x"]) * scale_x, "y": offset_y + float(point["y"]) * scale_y}
            for point in prediction.get("points") or []
        ]
        polygon = Polygon([(point["x"], point["y"]) for point in points])
        min_x, min_y, max_x, max_y = polygon.bounds
        margin = max(3.0, min(source_width, source_height) * 0.012)
        touches_edge = tiled and (
            min_x <= offset_x + margin or min_y <= offset_y + margin
            or max_x >= offset_x + source_width - margin
            or max_y >= offset_y + source_height - margin
        )
        bbox = prediction.get("bounding_box") or {}
        return {
            **prediction,
            "points": points,
            "area": float(polygon.area),
            "bounding_box": {
                "x": offset_x + float(bbox.get("x") or 0) * scale_x,
                "y": offset_y + float(bbox.get("y") or 0) * scale_y,
                "width": float(bbox.get("width") or 0) * scale_x,
                "height": float(bbox.get("height") or 0) * scale_y,
            },
            "detection_pass": "tile" if tiled else "full",
            "touches_tile_edge": touches_edge,
        }

    def _normalize_prediction(self, prediction: Any) -> dict[str, Any] | None:
        if not isinstance(prediction, dict):
            return None
        try:
            confidence = float(prediction.get("confidence") or 0)
        except (TypeError, ValueError):
            confidence = 0.0
        if confidence < settings.roboflow_floor_confidence:
            return None

        raw_points = prediction.get("points") or prediction.get("polygon") or []
        points: list[dict[str, float]] = []
        for point in raw_points:
            if isinstance(point, dict):
                x, y = point.get("x"), point.get("y")
            elif isinstance(point, (list, tuple)) and len(point) >= 2:
                x, y = point[0], point[1]
            else:
                continue
            try:
                value = {"x": float(x), "y": float(y)}
            except (TypeError, ValueError):
                continue
            if not points or abs(points[-1]["x"] - value["x"]) > 1e-6 or abs(points[-1]["y"] - value["y"]) > 1e-6:
                points.append(value)
        if len(points) > 2 and points[0] == points[-1]:
            points.pop()
        if len(points) < 3:
            return None

        polygon = Polygon([(point["x"], point["y"]) for point in points])
        if not polygon.is_valid:
            polygon = polygon.buffer(0)
        if polygon.is_empty or polygon.area <= 1:
            return None
        if polygon.geom_type == "MultiPolygon":
            polygon = max(polygon.geoms, key=lambda item: item.area)
        clean_points = [{"x": float(x), "y": float(y)} for x, y in list(polygon.exterior.coords)[:-1]]

        def number(name: str) -> float:
            try:
                return float(prediction.get(name) or 0)
            except (TypeError, ValueError):
                return 0.0

        return {
            "class_name": str(prediction.get("class") or prediction.get("class_name") or "room"),
            "confidence": confidence,
            "points": clean_points,
            "bounding_box": {
                "x": number("x"),
                "y": number("y"),
                "width": number("width"),
                "height": number("height"),
            },
            "prediction_id": str(prediction.get("detection_id") or prediction.get("id") or "") or None,
        }

    def _deduplicate(self, predictions: list[dict[str, Any]]) -> list[dict[str, Any]]:
        kept: list[tuple[dict[str, Any], Polygon]] = []
        for prediction in sorted(predictions, key=lambda item: float(item.get("confidence") or 0), reverse=True):
            polygon = Polygon([(point["x"], point["y"]) for point in prediction["points"]])
            duplicate = False
            for _, existing in kept:
                union = polygon.union(existing).area
                iou = polygon.intersection(existing).area / union if union else 0.0
                centre_inside = existing.buffer(1).contains(polygon.representative_point())
                area_ratio = min(polygon.area, existing.area) / max(polygon.area, existing.area)
                if iou >= self.duplicate_iou or (centre_inside and area_ratio >= 0.92):
                    duplicate = True
                    break
            if not duplicate:
                kept.append((prediction, polygon))
        return [item for item, _ in kept]

    def _valid_for_image(
        self, prediction: dict[str, Any], width: float, height: float,
        *, maximum_area_ratio: float | None = None,
    ) -> bool:
        if width <= 0 or height <= 0:
            return True
        polygon = Polygon([(point["x"], point["y"]) for point in prediction["points"]])
        image = Polygon([(0, 0), (width, 0), (width, height), (0, height)])
        maximum = self.maximum_image_area_ratio if maximum_area_ratio is None else maximum_area_ratio
        if polygon.is_empty or polygon.area / max(image.area, 1.0) > maximum:
            return False
        return polygon.intersection(image).area / max(polygon.area, 1.0) >= self.minimum_inside_ratio

    def _empty(
        self, status: str, image_path: Path, crop_version: int | None = None
    ) -> dict[str, Any]:
        width, height = self._image_size(image_path) if image_path.exists() else (0, 0)
        return {
            "provider": self.name,
            "model_id": settings.roboflow_floor_model_id,
            "crop_version": crop_version,
            "status": status,
            "image_width": float(width),
            "image_height": float(height),
            "predictions": [],
            "raw": {},
        }

    @staticmethod
    def _image_size(path: Path) -> tuple[int, int]:
        try:
            pixmap = fitz.Pixmap(str(path))
            return int(pixmap.width), int(pixmap.height)
        except Exception:
            return 0, 0


room_segmentation_provider = RoomSegmentationProvider()
