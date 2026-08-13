from __future__ import annotations

import re
from typing import Any

import fitz
from shapely.geometry import Point

from app.core.config import settings
from app.floors.polygon_builder import room_polygon_builder
from app.floors.repo import floors_repository
from app.floors.room_ocr_service import room_ocr_service
from app.floors.room_semantics import room_semantics
from app.floor_plans.repo import floor_plans_repository
from app.floor_plans.rendering import crop_clip, crop_source_path
from app.pdf_upload.repo import pdf_upload_repository
from app.storage.storage_service import storage_service


class RoomLabelService:
    """Assign semantic room labels from the saved vector text layer."""

    ignored = re.compile(
        r"^(?:D\s*\d+[A-Z]?|W\s*\d+[A-Z]?|F\s*\d+[A-Z]?|FG\s*\d*|GD\s*\d+|\d+(?:\.\d+)?(?:\s*(?:MM|CM|M))?|NORTH|SOUTH|EAST|WEST)$",
        re.IGNORECASE,
    )

    def suggestions(
        self, project_id: str, floor_id: str, rooms: list[dict[str, Any]]
    ) -> dict[str, dict[str, Any]]:
        blocks = self._blocks(project_id, floor_id)
        output = self._model_suggestions(project_id, floor_id)
        observations: list[tuple[str, Point]] = []
        prepared_blocks: list[tuple[Point, list[str], bool]] = []
        for block in blocks:
            text = self._clean(block.get("text"))
            if not text or self.ignored.match(text):
                continue
            bbox = block.get("bbox") or {}
            try:
                point = Point(
                    (float(bbox["x0"]) + float(bbox["x1"])) / 2,
                    (float(bbox["y0"]) + float(bbox["y1"])) / 2,
                )
            except (KeyError, TypeError, ValueError):
                continue
            known = room_semantics.match_known_labels(text)
            labels = known or room_semantics.extract_labels(text)
            if not labels:
                continue
            prepared_blocks.append((point, labels, bool(known)))
            for normalized in known:
                if normalized != "Area":
                    observations.append((normalized, point))
        for room in rooms:
            if str(room["id"]) in output:
                continue
            polygon = room_polygon_builder.points_to_polygon((room.get("geometry") or {}).get("points") or [])
            if polygon.is_empty:
                continue
            candidates: list[tuple[float, str, Point, bool]] = []
            expanded = polygon.buffer(max(1.0, polygon.length * 0.002))
            for point, labels, recognized in prepared_blocks:
                if expanded.contains(point):
                    for normalized in labels:
                        if normalized and normalized != "Area":
                            candidates.append((polygon.centroid.distance(point), normalized, point, recognized))
            if not candidates:
                continue
            # A dictionary-backed room name always beats arbitrary nearby text.
            # Keep an unknown OCR name only when no known room term was found.
            if any(item[3] for item in candidates):
                candidates = [item for item in candidates if item[3]]
            candidates.sort(key=lambda item: (item[0], len(item[1])))
            unique: list[str] = []
            for _, label, _, _ in candidates:
                if label not in unique:
                    unique.append(label)
            semantics = room_semantics.classify(unique)
            strongest_point = candidates[0][2] if candidates else polygon.representative_point()
            recognized = any(item[3] for item in candidates)
            confidence = (0.95 if polygon.contains(strongest_point) else 0.82) if recognized else 0.62
            output[str(room["id"])] = {
                "name": semantics["name"],
                "room_type": semantics["room_type"],
                "label_source": "drawing",
                "label_confidence": confidence,
                "label_candidates": semantics["labels"],
                "space_kind": semantics["space_kind"],
                "include_in_boq": semantics["include_in_boq"],
                "open_plan": semantics["open_plan"],
            }

        # PDF text engines occasionally merge labels from adjacent rooms into
        # one block whose center falls in the wall between them. Assign the
        # most specific nearby unused label to an otherwise unlabeled room.
        used = {
            label
            for item in output.values()
            for label in (item.get("label_candidates") or [])
        }
        used_points: set[tuple[float, float]] = set()
        for room in rooms:
            room_id = str(room["id"])
            if room_id in output:
                continue
            polygon = room_polygon_builder.points_to_polygon((room.get("geometry") or {}).get("points") or [])
            if polygon.is_empty:
                continue
            span = max(
                polygon.bounds[2] - polygon.bounds[0],
                polygon.bounds[3] - polygon.bounds[1],
                1.0,
            )
            nearby = [
                (polygon.distance(point), -len(label), label, point)
                for label, point in observations
                if label not in used
                and (round(point.x, 2), round(point.y, 2)) not in used_points
                and polygon.distance(point) <= max(24.0, span * 0.65)
            ]
            if not nearby:
                continue
            nearby.sort(key=lambda item: (item[0], item[1], item[2]))
            _, _, label, _ = nearby[0]
            semantics = room_semantics.classify(label)
            output[room_id] = {
                "name": semantics["name"],
                "room_type": semantics["room_type"],
                "label_source": "drawing_nearby",
                "label_confidence": 0.72,
                "label_candidates": semantics["labels"],
                "space_kind": semantics["space_kind"],
                "include_in_boq": semantics["include_in_boq"],
                "open_plan": semantics["open_plan"],
            }
            used.add(label)
            used_points.add((round(nearby[0][3].x, 2), round(nearby[0][3].y, 2)))

        # Rasterized/outlined labels are not present in the PDF text layer.
        # OCR only the still-unnamed room polygons in parallel; this is local
        # and remains available when the remote vision service is rate-limited.
        missing = [room for room in rooms if str(room["id"]) not in output]
        crop = floor_plans_repository.current_crop(project_id, floor_id)
        if missing and crop and crop.get("crop_asset_key"):
            decoded = floor_plans_repository.decode_crop(crop)
            rect = ((decoded.get("coordinates") or {}).get("original_rect") or {})
            rotation = int(crop.get("rotation") or 0) % 360
            width = float(rect.get("height") if rotation in {90, 270} else rect.get("width") or 0)
            height = float(rect.get("width") if rotation in {90, 270} else rect.get("height") or 0)
            image_path = storage_service.ensure_local_file(
                storage_service.key_to_path(str(crop["crop_asset_key"]))
            )
            output.update(room_ocr_service.suggestions(
                image_path=image_path,
                coordinate_width=width,
                coordinate_height=height,
                rooms=missing,
            ))

        # A stair is often split into flights and a landing by door-closure
        # lines. Name a small adjacent unlabeled cell as the landing instead
        # of leaving a generic Room number.
        circulation = [
            room
            for room in rooms
            if (output.get(str(room["id"])) or {}).get("space_kind") == "circulation"
        ]
        for room in rooms:
            room_id = str(room["id"])
            if room_id in output:
                continue
            polygon = room_polygon_builder.points_to_polygon((room.get("geometry") or {}).get("points") or [])
            if polygon.is_empty:
                continue
            span = max(polygon.bounds[2] - polygon.bounds[0], polygon.bounds[3] - polygon.bounds[1], 1.0)
            if not any(
                polygon.distance(
                    room_polygon_builder.points_to_polygon((item.get("geometry") or {}).get("points") or [])
                ) <= max(12.0, span * 0.22)
                for item in circulation
            ):
                continue
            semantics = room_semantics.classify("Stair Landing")
            output[room_id] = {
                "name": "Stair Landing",
                "room_type": "Stair Landing",
                "label_source": "drawing_inferred",
                "label_confidence": 0.68,
                "label_candidates": ["Stair Landing"],
                "space_kind": semantics["space_kind"],
                "include_in_boq": False,
                "open_plan": False,
            }
        return output

    @staticmethod
    def _model_suggestions(project_id: str, floor_id: str) -> dict[str, dict[str, Any]]:
        output: dict[str, dict[str, Any]] = {}
        for suggestion in floors_repository.list_suggestions(project_id, floor_id):
            room_id = str(suggestion.get("matched_room_id") or "")
            raw_class = str(suggestion.get("class_name") or "").replace("_", " ").strip()
            if not room_id or not raw_class or raw_class.casefold() in {
                "room", "rooms", "space", "floor", "floor area", "open plan",
            }:
                continue
            labels = room_semantics.match_known_labels(raw_class)
            if not labels:
                continue
            semantic = room_semantics.classify(labels)
            output[room_id] = {
                "name": semantic["name"],
                "room_type": semantic["room_type"],
                "label_source": "roboflow_class",
                "label_confidence": float(suggestion.get("confidence") or 0.8),
                "label_candidates": semantic["labels"],
                "space_kind": semantic["space_kind"],
                "include_in_boq": semantic["include_in_boq"],
                "open_plan": semantic["open_plan"],
            }
        return output

    def blocks(self, project_id: str, floor_id: str) -> list[dict[str, Any]]:
        """Return coordinate-aligned vector text for the selected floor only."""
        return self._blocks(project_id, floor_id)

    def evidence_blocks(self, project_id: str, floor_id: str) -> list[dict[str, Any]]:
        """Return positioned vector labels plus optional full-floor OCR labels."""
        vector = [
            {**block, "source": "drawing", "confidence": 0.95}
            for block in self._blocks(project_id, floor_id)
        ]
        if not settings.room_exception_full_floor_ocr_enabled:
            return vector
        crop = floor_plans_repository.current_crop(project_id, floor_id)
        if not crop or not crop.get("crop_asset_key"):
            return vector
        decoded = floor_plans_repository.decode_crop(crop)
        rect = ((decoded.get("coordinates") or {}).get("original_rect") or {})
        rotation = int(crop.get("rotation") or 0) % 360
        width = float(rect.get("height") if rotation in {90, 270} else rect.get("width") or 0)
        height = float(rect.get("width") if rotation in {90, 270} else rect.get("height") or 0)
        if width <= 0 or height <= 0:
            return vector
        image_path = storage_service.ensure_local_file(
            storage_service.key_to_path(str(crop["crop_asset_key"]))
        )
        ocr = room_ocr_service.blocks(
            image_path=image_path,
            coordinate_width=width,
            coordinate_height=height,
            maximum_dimension=settings.room_exception_ocr_max_dimension,
        )
        output = list(vector)
        known: list[tuple[str, Point]] = []
        for block in vector:
            labels = room_semantics.match_known_labels(block.get("text"))
            point = self._block_center(block)
            if point is not None:
                known.extend((label, point) for label in labels)
        for block in ocr:
            point = self._block_center(block)
            labels = room_semantics.match_known_labels(block.get("text"))
            if point is None or not labels:
                continue
            if any(
                label == existing and point.distance(existing_point) <= max(4.0, width * 0.004)
                for label in labels
                for existing, existing_point in known
            ):
                continue
            output.append(block)
            known.extend((label, point) for label in labels)
        return output

    @staticmethod
    def _block_center(block: dict[str, Any]) -> Point | None:
        bbox = block.get("bbox") or {}
        try:
            return Point(
                (float(bbox["x0"]) + float(bbox["x1"])) / 2,
                (float(bbox["y0"]) + float(bbox["y1"])) / 2,
            )
        except (KeyError, TypeError, ValueError):
            return None

    @staticmethod
    def _label_center(blocks: list[dict[str, Any]], label: str) -> tuple[float, float] | None:
        for block in blocks:
            if room_semantics.normalize(block.get("text")) != label:
                continue
            bbox = block.get("bbox") or {}
            try:
                return (
                    (float(bbox["x0"]) + float(bbox["x1"])) / 2,
                    (float(bbox["y0"]) + float(bbox["y1"])) / 2,
                )
            except (KeyError, TypeError, ValueError):
                return None
        return None

    def _blocks(self, project_id: str, floor_id: str) -> list[dict[str, Any]]:
        crop = floor_plans_repository.current_crop(project_id, floor_id)
        if not crop:
            return []
        decoded = floor_plans_repository.decode_crop(crop)
        rect = ((decoded.get("coordinates") or {}).get("original_rect") or {})
        crop_x = float(rect.get("x") or 0)
        crop_y = float(rect.get("y") or 0)
        crop_width = float(rect.get("width") or 0)
        crop_height = float(rect.get("height") or 0)
        if crop_width <= 0 or crop_height <= 0:
            return []
        rotation = int(crop.get("rotation") or 0) % 360
        display_width = crop_height if rotation in {90, 270} else crop_width
        display_height = crop_width if rotation in {90, 270} else crop_height

        records = [
            item
            for item in pdf_upload_repository.list_extraction_records(project_id)
            if item.get("extraction_type") == "floor_crop_note"
            and str((item.get("data") or {}).get("crop_id") or "")
        ]
        selected = [
            item
            for item in records
            if str((item.get("data") or {}).get("crop_id") or "") == str(crop.get("id") or "")
            and (
                f"floor:{floor_id}:" in str(item.get("entity_key") or "")
                or str((item.get("source_location") or {}).get("floor_id") or "") == floor_id
            )
        ]
        # Never borrow text from another floor. A missing crop-text extraction
        # is safer than assigning First Floor labels to Ground Floor rooms.
        if not selected:
            # Crop rendering, model detection and text extraction run in
            # parallel. Read the vector layer directly when the background
            # extraction has not finished yet, so rooms do not permanently
            # receive generated "Room N" labels because of that race.
            try:
                source_path = crop_source_path(project_id, crop)
                clip = crop_clip(crop)
                page_number = int(crop.get("source_page_number") or 1)
                direct_blocks: list[dict[str, Any]] = []
                with fitz.open(source_path) as source:
                    page = source.load_page(page_number - 1)
                    for block in page.get_text("blocks", clip=clip, sort=True):
                        if len(block) < 7 or int(block[6]) != 0:
                            continue
                        text = str(block[4] or "").strip()
                        if text:
                            direct_blocks.append({
                                "text": text,
                                "bbox": {
                                    "x0": float(block[0]), "y0": float(block[1]),
                                    "x1": float(block[2]), "y1": float(block[3]),
                                },
                            })
                selected = [{"data": {"blocks": direct_blocks}}] if direct_blocks else []
            except Exception:
                selected = []
        if not selected:
            return []

        blocks: list[dict[str, Any]] = []
        for item in selected:
            for block in (item.get("data") or {}).get("blocks") or []:
                bbox = block.get("bbox") or {}
                try:
                    x0, y0 = float(bbox["x0"]), float(bbox["y0"])
                    x1, y1 = float(bbox["x1"]), float(bbox["y1"])
                except (KeyError, TypeError, ValueError):
                    continue
                mapped = [
                    self._map(x0, y0, crop_x, crop_y, crop_width, crop_height, rotation),
                    self._map(x1, y1, crop_x, crop_y, crop_width, crop_height, rotation),
                ]
                blocks.append(
                    {
                        "text": block.get("text"),
                        "bbox": {
                            "x0": min(mapped[0][0], mapped[1][0]) * display_width,
                            "y0": min(mapped[0][1], mapped[1][1]) * display_height,
                            "x1": max(mapped[0][0], mapped[1][0]) * display_width,
                            "y1": max(mapped[0][1], mapped[1][1]) * display_height,
                        },
                    }
                )
        return blocks

    @staticmethod
    def _map(
        x: float,
        y: float,
        crop_x: float,
        crop_y: float,
        crop_width: float,
        crop_height: float,
        rotation: int,
    ) -> tuple[float, float]:
        u = min(1.0, max(0.0, (x - crop_x) / crop_width))
        v = min(1.0, max(0.0, (y - crop_y) / crop_height))
        if rotation == 90:
            return 1.0 - v, u
        if rotation == 180:
            return 1.0 - u, 1.0 - v
        if rotation == 270:
            return v, 1.0 - u
        return u, v

    @staticmethod
    def _clean(value: Any) -> str:
        return room_semantics.clean(value)


room_label_service = RoomLabelService()
