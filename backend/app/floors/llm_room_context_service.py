from __future__ import annotations

import base64
import hashlib
import io
import json
import re
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw

from app.core.config import settings
from app.floors.building_envelope_service import building_envelope_service
from app.floors.label_service import room_label_service
from app.floors.line_builder import room_line_builder
from app.floors.polygon_builder import room_polygon_builder
from app.floors.repo import floors_repository
from app.floors.vector_geometry_service import vector_floor_geometry_service
from app.storage.storage_service import storage_service
from app.walls.repo import walls_repository


class LLMRoomContextService:
    """Build compact, selected-floor-only multimodal evidence."""

    max_image_dimension = 2400
    max_text_blocks = 500
    max_dimensions = 300

    def build(self, project_id: str, floor_id: str) -> dict[str, Any]:
        floor = floors_repository.get_floor_row(project_id, floor_id)
        if not floor or not floor.get("crop_asset_key"):
            raise ValueError("The selected floor crop is not ready.")

        image_path = storage_service.ensure_local_file(
            storage_service.key_to_path(str(floor["crop_asset_key"]))
        )
        if not image_path.is_file():
            raise ValueError("The selected floor crop image is unavailable.")

        try:
            evidence = vector_floor_geometry_service.extract(project_id, floor_id)
        except Exception:
            evidence = {"segments": [], "wall_pairs": [], "dimensions": []}
        dimensions = floors_repository.list_dimension_observations(
            project_id, floor_id, int(floor.get("crop_version") or 0)
        )
        if not dimensions and evidence.get("dimensions"):
            dimensions = evidence.get("dimensions") or []

        walls = walls_repository.list_walls(project_id, floor_id)
        openings = walls_repository.list_opening_elements(project_id, floor_id)
        prepared = room_line_builder.build(
            walls=walls,
            openings=openings,
            mm_per_pixel=float(floor.get("mm_per_pixel") or 0) or None,
            vector_walls=evidence.get("wall_pairs") or [],
        )
        image_width, image_height = self._image_size(image_path)
        crop_rect = ((floor.get("coordinates") or {}).get("original_rect") or {})
        width = float(crop_rect.get("width") or image_width)
        height = float(crop_rect.get("height") or image_height)
        envelope = building_envelope_service.build(prepared, width, height)
        serialized = room_line_builder.serialize(prepared)
        image_url, submitted_image_width, submitted_image_height = self._image_payload(
            image_path
        )

        suggestions = []
        for item in floors_repository.list_suggestions(project_id, floor_id):
            if item.get("status") in {"rejected", "superseded"}:
                continue
            suggestions.append(
                {
                    "id": str(item["id"]),
                    "polygon": item.get("polygon") or {},
                    "bounding_box": item.get("bounding_box") or {},
                    "confidence": item.get("confidence"),
                    "matched_room_id": item.get("matched_room_id"),
                }
            )

        rooms = [
            {
                "id": str(item["id"]),
                "name": item.get("name"),
                "room_type": item.get("room_type"),
                "model_polygon": item.get("model_polygon") or {},
                "wall_corrected_polygon": item.get("wall_corrected_polygon") or {},
                "wall_ids": item.get("wall_ids") or [],
                "opening_ids": item.get("opening_ids") or [],
            }
            for item in floors_repository.list_rooms(project_id, floor_id, include_excluded=False)
            if not item.get("is_finish_zone")
        ]
        room_crop_urls, room_crop_evidence = self._room_crop_payloads(
            image_path=image_path,
            rooms=rooms,
            suggestions=suggestions,
            coordinate_width=width,
            coordinate_height=height,
        )

        wall_items = [
            {
                "id": str(item.get("id")),
                "points": item.get("points") or [],
                "footprint": item.get("footprint") or [],
                "thickness_px": item.get("thickness_px"),
                "source": item.get("source"),
            }
            for item in serialized.get("wall_segments") or []
        ]
        opening_items = [
            {
                "id": str(item.get("id")),
                "type": item.get("element_type"),
                "wall_id": item.get("wall_id"),
                "geometry": item.get("geometry") or {},
                "width_mm": (item.get("dimensions") or {}).get("width_mm"),
            }
            for item in openings
        ]
        dimension_items = [self._dimension(item) for item in dimensions[: self.max_dimensions]]
        context = {
            "project_id": project_id,
            "floor_id": floor_id,
            "floor_name": floor.get("name"),
            "coordinate_space": {
                "width": width,
                "height": height,
                "image_width": image_width,
                "image_height": image_height,
                "submitted_image_width": submitted_image_width,
                "submitted_image_height": submitted_image_height,
                "coordinate_to_submitted_image": {
                    "scale_x": submitted_image_width / max(width, 1.0),
                    "scale_y": submitted_image_height / max(height, 1.0),
                },
                "origin": "top_left",
            },
            "versions": {
                "crop_version": int(floor.get("crop_version") or 0),
                "wall_version": int(floor.get("wall_version") or 0),
                "scale_version": int(floor.get("scale_version") or 0),
            },
            "scale": {
                "mm_per_pixel": floor.get("mm_per_pixel"),
                "verified": bool(floor.get("mm_per_pixel")) and int(floor.get("scale_version") or 0) > 0,
            },
            "building_envelope": {
                "points": room_polygon_builder.polygon_to_points(envelope)
                if not envelope.is_empty
                else []
            },
            "walls": wall_items,
            "inner_wall_faces": [item.get("footprint") or [] for item in wall_items],
            "door_closures": serialized.get("door_closures") or [],
            "openings": opening_items,
            "room_suggestions": suggestions,
            "rooms": rooms,
            "room_crop_evidence": room_crop_evidence,
            "vector_text": room_label_service.blocks(project_id, floor_id)[: self.max_text_blocks],
            "dimensions": dimension_items,
        }
        image_sha = self._file_hash(image_path)
        input_hash = hashlib.sha256(
            (json.dumps(context, sort_keys=True, separators=(",", ":"), default=str) + image_sha).encode("utf-8")
        ).hexdigest()
        return {
            "context": context,
            "image_path": image_path,
            "image_url": image_url,
            "room_crop_urls": room_crop_urls,
            "image_sha256": image_sha,
            "input_hash": input_hash,
            "versions": context["versions"],
        }

    @staticmethod
    def _dimension(item: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": item.get("id"),
            "label_text": item.get("label_text"),
            "value_mm": item.get("value_mm"),
            "orientation": item.get("orientation"),
            "point_a": item.get("point_a") or {},
            "point_b": item.get("point_b") or {},
            "confidence": item.get("confidence"),
        }

    @staticmethod
    def _image_size(path: Path) -> tuple[float, float]:
        with Image.open(path) as image:
            return float(image.width), float(image.height)

    @staticmethod
    def _file_hash(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as source:
            for chunk in iter(lambda: source.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    def _image_payload(self, path: Path) -> tuple[str, int, int]:
        with Image.open(path) as source:
            image = source.convert("RGB")
            if max(image.size) > self.max_image_dimension:
                image.thumbnail((self.max_image_dimension, self.max_image_dimension), Image.Resampling.LANCZOS)
            submitted_width, submitted_height = image.size
            buffer = io.BytesIO()
            image.save(buffer, format="JPEG", quality=88, optimize=True)
        encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
        return f"data:image/jpeg;base64,{encoded}", submitted_width, submitted_height

    def _room_crop_payloads(
        self,
        *,
        image_path: Path,
        rooms: list[dict[str, Any]],
        suggestions: list[dict[str, Any]],
        coordinate_width: float,
        coordinate_height: float,
    ) -> tuple[list[str], list[dict[str, str]]]:
        """Build a few contact sheets, keeping one floor-level model call."""
        maximum = int(getattr(settings, "room_llm_max_crops_per_floor", 20))
        if maximum <= 0:
            return [], []
        suggestion_by_room = {
            str(item.get("matched_room_id")): str(item.get("id"))
            for item in suggestions if item.get("matched_room_id")
        }
        targets = [
            room for room in rooms
            if not str(room.get("name") or "").strip()
            or re.fullmatch(r"\s*(?:room|space)(?:\s+\d+)*\s*", str(room.get("name") or ""), re.I)
        ][:maximum]
        if not targets:
            return [], []

        cells: list[tuple[Image.Image, str]] = []
        evidence: list[dict[str, str]] = []
        with Image.open(image_path) as source_image:
            source = source_image.convert("RGB")
            scale_x = source.width / max(coordinate_width, 1.0)
            scale_y = source.height / max(coordinate_height, 1.0)
            for room in targets:
                geometry = room.get("wall_corrected_polygon") or room.get("model_polygon") or {}
                points = geometry.get("points") or []
                if len(points) < 3:
                    continue
                xs = [float(point.get("x") or 0) * scale_x for point in points]
                ys = [float(point.get("y") or 0) * scale_y for point in points]
                span_x, span_y = max(xs) - min(xs), max(ys) - min(ys)
                pad_x, pad_y = max(18.0, span_x * 0.12), max(18.0, span_y * 0.12)
                box = (
                    max(0, int(min(xs) - pad_x)), max(0, int(min(ys) - pad_y)),
                    min(source.width, int(max(xs) + pad_x)), min(source.height, int(max(ys) + pad_y)),
                )
                if box[2] <= box[0] or box[3] <= box[1]:
                    continue
                room_id = str(room.get("id") or "")
                suggestion_id = suggestion_by_room.get(room_id, "")
                caption = f"ROOM {room_id} | SUGGESTION {suggestion_id or 'UNMATCHED'}"
                cells.append((source.crop(box), caption))
                evidence.append({"room_id": room_id, "room_suggestion_id": suggestion_id})

        urls: list[str] = []
        for start in range(0, len(cells), 8):
            page = cells[start : start + 8]
            sheet = Image.new("RGB", (1200, 1600), "white")
            draw = ImageDraw.Draw(sheet)
            for index, (crop, caption) in enumerate(page):
                column, row = index % 2, index // 2
                left, top = column * 600, row * 400
                draw.rectangle((left, top, left + 599, top + 399), outline="black", width=2)
                draw.text((left + 12, top + 10), caption, fill="black")
                crop.thumbnail((576, 350), Image.Resampling.LANCZOS)
                x = left + (600 - crop.width) // 2
                y = top + 42 + (350 - crop.height) // 2
                sheet.paste(crop, (x, y))
            buffer = io.BytesIO()
            sheet.save(buffer, format="JPEG", quality=90, optimize=True)
            encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
            urls.append(f"data:image/jpeg;base64,{encoded}")
        return urls, evidence

    def _data_url(self, path: Path) -> str:
        """Backward-compatible helper for callers that only need image bytes."""
        return self._image_payload(path)[0]


llm_room_context_service = LLMRoomContextService()

__all__ = ["LLMRoomContextService", "llm_room_context_service"]
