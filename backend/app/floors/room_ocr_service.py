from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from io import BytesIO
from pathlib import Path
import csv
import io
import shutil
import subprocess
from typing import Any

import numpy as np
from PIL import Image, ImageEnhance, ImageFilter, ImageOps, ImageDraw

from app.floors.polygon_builder import room_polygon_builder
from app.floors.room_semantics import room_semantics


class RoomOcrService:
    """Read printed labels from detected room polygons without a network call."""

    workers = 4
    timeout_seconds = 10
    _rapid_engine: Any | None = None

    def blocks(
        self,
        *,
        image_path: Path,
        coordinate_width: float,
        coordinate_height: float,
        maximum_dimension: int = 3000,
    ) -> list[dict[str, Any]]:
        """Read positioned labels from a floor image for missed-room recovery."""
        executable = self._executable()
        rapid = self._rapid()
        if (not rapid and not executable) or not image_path.is_file():
            return []
        with Image.open(image_path) as opened:
            source = opened.convert("RGB")
        ratio = min(1.0, maximum_dimension / max(source.width, source.height, 1))
        image = source.resize(
            (max(1, round(source.width * ratio)), max(1, round(source.height * ratio))),
            Image.Resampling.LANCZOS,
        ) if ratio < 1.0 else source
        buffer = BytesIO()
        image.save(buffer, format="PNG", optimize=True)
        content = buffer.getvalue()
        raw: list[dict[str, Any]] = []
        if rapid:
            try:
                result, _ = rapid(np.asarray(image))
                for item in result or []:
                    if len(item) < 3:
                        continue
                    box, text, confidence = item[0], str(item[1]), float(item[2])
                    xs = [float(point[0]) for point in box]
                    ys = [float(point[1]) for point in box]
                    raw.append({
                        "text": text,
                        "confidence": confidence,
                        "bbox": {"x0": min(xs), "y0": min(ys), "x1": max(xs), "y1": max(ys)},
                    })
            except Exception:
                raw = []
        if not raw and executable:
            raw = self._tesseract_blocks(executable, content)

        scale_x = coordinate_width / max(image.width, 1)
        scale_y = coordinate_height / max(image.height, 1)
        return [
            {
                **item,
                "source": "drawing_ocr",
                "bbox": {
                    "x0": float(item["bbox"]["x0"]) * scale_x,
                    "y0": float(item["bbox"]["y0"]) * scale_y,
                    "x1": float(item["bbox"]["x1"]) * scale_x,
                    "y1": float(item["bbox"]["y1"]) * scale_y,
                },
            }
            for item in raw
            if room_semantics.match_known_labels(item.get("text"))
        ]

    def suggestions(
        self,
        *,
        image_path: Path,
        coordinate_width: float,
        coordinate_height: float,
        rooms: list[dict[str, Any]],
    ) -> dict[str, dict[str, Any]]:
        executable = self._executable()
        rapid = self._rapid()
        if (not rapid and not executable) or not image_path.is_file() or not rooms:
            return {}
        with Image.open(image_path) as opened:
            source = opened.convert("RGB")
        tasks: dict[str, bytes] = {}
        for room in rooms:
            prepared = self._crop(
                source,
                (room.get("geometry") or {}).get("points") or [],
                coordinate_width,
                coordinate_height,
            )
            if prepared:
                tasks[str(room["id"])] = prepared
        output: dict[str, dict[str, Any]] = {}
        with ThreadPoolExecutor(max_workers=min(self.workers, len(tasks) or 1)) as executor:
            pending = {
                executor.submit(self._read, executable, rapid, content): room_id
                for room_id, content in tasks.items()
            }
            for future in as_completed(pending):
                room_id = pending[future]
                try:
                    text = future.result()
                except Exception:
                    continue
                labels = room_semantics.match_known_labels(text)
                if not labels:
                    continue
                semantic = room_semantics.classify(labels)
                output[room_id] = {
                    "name": semantic["name"],
                    "room_type": semantic["room_type"],
                    "label_source": "local_ocr",
                    "label_confidence": 0.86,
                    "label_candidates": semantic["labels"],
                    "space_kind": semantic["space_kind"],
                    "include_in_boq": semantic["include_in_boq"],
                    "open_plan": semantic["open_plan"],
                }
        return output

    @staticmethod
    def _executable() -> str | None:
        discovered = shutil.which("tesseract")
        if discovered:
            return discovered
        windows = Path(r"C:\Program Files\Tesseract-OCR\tesseract.exe")
        return str(windows) if windows.is_file() else None

    @classmethod
    def _rapid(cls) -> Any | None:
        if cls._rapid_engine is not None:
            return cls._rapid_engine
        try:
            from rapidocr_onnxruntime import RapidOCR
            cls._rapid_engine = RapidOCR()
        except Exception:
            cls._rapid_engine = False
        return cls._rapid_engine or None

    @staticmethod
    def _crop(
        source: Image.Image,
        points: list[dict[str, Any]],
        coordinate_width: float,
        coordinate_height: float,
    ) -> bytes | None:
        polygon = room_polygon_builder.points_to_polygon(points)
        if polygon.is_empty or coordinate_width <= 0 or coordinate_height <= 0:
            return None
        scale_x = source.width / coordinate_width
        scale_y = source.height / coordinate_height
        mapped = [(float(x) * scale_x, float(y) * scale_y) for x, y in polygon.exterior.coords]
        xs, ys = [point[0] for point in mapped], [point[1] for point in mapped]
        pad = 8
        left, top = max(0, int(min(xs)) - pad), max(0, int(min(ys)) - pad)
        right, bottom = min(source.width, int(max(xs)) + pad), min(source.height, int(max(ys)) + pad)
        if right - left < 12 or bottom - top < 12:
            return None
        crop = source.crop((left, top, right, bottom))
        mask = Image.new("L", crop.size, 0)
        ImageDraw.Draw(mask).polygon(
            [(x - left, y - top) for x, y in mapped], fill=255
        )
        white = Image.new("RGB", crop.size, "white")
        crop = Image.composite(crop, white, mask)
        gray = ImageOps.grayscale(crop)
        gray = ImageOps.autocontrast(gray, cutoff=1)
        gray = ImageEnhance.Contrast(gray).enhance(1.8)
        gray = gray.resize((gray.width * 2, gray.height * 2), Image.Resampling.LANCZOS)
        gray = gray.filter(ImageFilter.SHARPEN)
        buffer = BytesIO()
        gray.save(buffer, format="PNG", optimize=True)
        return buffer.getvalue()

    def _read(self, executable: str | None, rapid: Any | None, content: bytes) -> str:
        if rapid:
            try:
                image = np.asarray(Image.open(BytesIO(content)).convert("RGB"))
                result, _ = rapid(image)
                text = " ".join(str(item[1]) for item in (result or []) if len(item) > 1)
                if text.strip():
                    return text
            except Exception:
                pass
        if not executable:
            return ""
        result = subprocess.run(
            [executable, "stdin", "stdout", "--psm", "11", "-l", "eng"],
            input=content,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            timeout=self.timeout_seconds,
            check=False,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        return result.stdout.decode("utf-8", errors="ignore") if result.returncode == 0 else ""

    def _tesseract_blocks(self, executable: str, content: bytes) -> list[dict[str, Any]]:
        try:
            result = subprocess.run(
                [executable, "stdin", "stdout", "--psm", "11", "-l", "eng", "tsv"],
                input=content,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                timeout=self.timeout_seconds * 2,
                check=False,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        except (OSError, subprocess.SubprocessError):
            return []
        if result.returncode != 0:
            return []
        rows = csv.DictReader(
            io.StringIO(result.stdout.decode("utf-8", errors="ignore")),
            delimiter="\t",
        )
        grouped: dict[tuple[str, str, str, str], list[dict[str, str]]] = {}
        for row in rows:
            text = str(row.get("text") or "").strip()
            if not text:
                continue
            key = tuple(str(row.get(name) or "") for name in (
                "page_num", "block_num", "par_num", "line_num"
            ))
            grouped.setdefault(key, []).append(row)
        output: list[dict[str, Any]] = []
        for words in grouped.values():
            try:
                left = min(int(item["left"]) for item in words)
                top = min(int(item["top"]) for item in words)
                right = max(int(item["left"]) + int(item["width"]) for item in words)
                bottom = max(int(item["top"]) + int(item["height"]) for item in words)
                confidences = [
                    max(0.0, float(item.get("conf") or 0) / 100.0) for item in words
                ]
            except (KeyError, TypeError, ValueError):
                continue
            output.append({
                "text": " ".join(str(item.get("text") or "").strip() for item in words),
                "confidence": sum(confidences) / max(len(confidences), 1),
                "bbox": {"x0": left, "y0": top, "x1": right, "y1": bottom},
            })
        return output


room_ocr_service = RoomOcrService()
