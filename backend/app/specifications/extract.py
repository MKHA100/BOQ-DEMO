from __future__ import annotations

import base64
import re
from pathlib import Path
from typing import Any, Callable

import fitz

from app.core.config import settings
from app.pdf_upload.repo import pdf_upload_repository
from app.specifications.openai_provider import openai_schedule_extraction_provider
from app.specifications.schemas import ExtractionPayload
from app.storage.storage_service import storage_service

Progress = Callable[[int, str, dict | None], None]

MATERIALS = (
    "timber", "wood", "steel", "stainless steel", "aluminium", "aluminum", "upvc", "pvc",
    "glass", "brick", "block", "concrete", "gypsum", "plasterboard", "masonry", "ceramic",
    "porcelain", "vinyl", "carpet", "terrazzo", "stone",
)
FINISHES = (
    "painted", "paint", "powder coated", "laminate", "veneer", "polished", "tile", "tiles",
    "carpet", "vinyl", "screed", "terrazzo", "plaster", "render", "fair face",
)


class ScheduleExtractionService:
    def extract(self, source: dict, progress: Progress | None = None) -> tuple[list[dict], str]:
        pages = self._read_pages(source, progress)
        provider_rows = openai_schedule_extraction_provider.extract(source["category"], pages)
        if provider_rows is not None:
            rows = self._provider_records(source["category"], provider_rows)
            method = "openai_structured"
            if progress:
                progress(86, "Validating extracted details", {"items": len(rows)})
        else:
            rows = []
            total = max(len(pages), 1)
            for index, page in enumerate(pages, start=1):
                lines = [line.strip() for line in page["text"].splitlines() if line.strip()]
                rows.extend(self._parse(source["category"], page["page_number"], lines))
                if progress:
                    progress(min(86, 15 + int(index / total * 66)), "Reading supporting document", {"page": page["page_number"], "items": len(rows)})
            method = "structured_text"
        payload = ExtractionPayload(category=source["category"], rows=[item["data"] for item in rows])
        normalized: list[dict] = []
        for index, row in enumerate(payload.rows):
            raw = rows[index]
            clean = dict(row)
            clean.pop("confidence", None)
            normalized.append({**raw, "data": clean})
        return normalized, method

    def _provider_records(self, category: str, rows: list[dict[str, Any]]) -> list[dict]:
        records: list[dict] = []
        key_fields = {
            "door_schedule": ("type_code",),
            "window_schedule": ("type_code",),
            "wall_schedule": ("type_code", "material"),
            "floor_schedule": ("floor_type_code", "room_or_zone", "finish"),
            "specification": ("section",),
            "other": ("title",),
        }[category]
        for index, item in enumerate(rows):
            data = dict(item)
            confidence = float(data.pop("confidence", None) or 0.82)
            page = int(data.get("source_page") or 1)
            text = str(data.get("source_text") or "")
            key = next((str(data.get(name)) for name in key_fields if data.get(name)), f"{category}-{index + 1}")
            records.append(_record(key, data, page, text, confidence))
        return _dedupe(records)

    def render_preview(self, source: dict, destination: Path) -> Path | None:
        document = pdf_upload_repository.get_document(source["project_id"], source["document_id"])
        if not document:
            return None
        path = storage_service.ensure_local_file(storage_service.key_to_path(document["storage_key"]))
        destination.parent.mkdir(parents=True, exist_ok=True)
        try:
            with fitz.open(path) as doc:
                page_index = max(0, int(source.get("source_page_number") or 1) - 1)
                page = doc.load_page(min(page_index, doc.page_count - 1))
                clip = None
                crop = source.get("crop") or {}
                rect = crop.get("crop") if isinstance(crop, dict) else None
                if rect:
                    clip = fitz.Rect(float(rect["x"]), float(rect["y"]), float(rect["x"] + rect["width"]), float(rect["y"] + rect["height"]))
                matrix = fitz.Matrix(1.5, 1.5)
                pix = page.get_pixmap(matrix=matrix, clip=clip, alpha=False)
                pix.save(destination)
            storage_service.upload_file(destination)
            return destination
        except Exception:
            return None

    def _read_pages(self, source: dict, progress: Progress | None) -> list[dict]:
        document = pdf_upload_repository.get_document(source["project_id"], source["document_id"])
        if not document:
            raise RuntimeError("Supporting document is not available.")
        path = storage_service.ensure_local_file(storage_service.key_to_path(document["storage_key"]))
        if progress:
            progress(8, "Opening supporting document", None)
        with fitz.open(path) as doc:
            if doc.needs_pass:
                raise RuntimeError("Password-protected files are not supported.")
            if source["source_type"] == "crop":
                page_number = int(source.get("source_page_number") or 1)
                page = doc.load_page(page_number - 1)
                crop = source.get("crop") or {}
                rect_data = crop.get("crop") if isinstance(crop, dict) else None
                clip = None
                if rect_data:
                    clip = fitz.Rect(
                        float(rect_data["x"]),
                        float(rect_data["y"]),
                        float(rect_data["x"] + rect_data["width"]),
                        float(rect_data["y"] + rect_data["height"]),
                    )
                text = page.get_text("text", clip=clip) or ""
                return [self._page_payload(page, page_number, text, clip)]
            pages = []
            for index, page in enumerate(doc):
                text = page.get_text("text") or ""
                pages.append(self._page_payload(page, index + 1, text, None))
            return pages

    @staticmethod
    def _page_payload(page: fitz.Page, page_number: int, text: str, clip: fitz.Rect | None) -> dict[str, Any]:
        payload: dict[str, Any] = {"page_number": page_number, "text": text}
        if not openai_schedule_extraction_provider.is_configured() or len(text.strip()) >= 80:
            return payload
        try:
            pixmap = page.get_pixmap(matrix=fitz.Matrix(1.35, 1.35), clip=clip, alpha=False)
            encoded = base64.b64encode(pixmap.tobytes("png")).decode("ascii")
            payload["image_data_url"] = f"data:image/png;base64,{encoded}"
        except Exception:
            pass
        return payload

    def _parse(self, category: str, page_number: int, lines: list[str]) -> list[dict]:
        parser = {
            "door_schedule": self._doors,
            "window_schedule": self._windows,
            "wall_schedule": self._walls,
            "floor_schedule": self._floors,
            "specification": self._specifications,
            "other": self._other,
        }[category]
        return parser(page_number, lines)

    def _doors(self, page: int, lines: list[str]) -> list[dict]:
        rows = []
        for line in lines:
            code = _code(line, "D")
            dims = _dimensions(line)
            if not code and not ("door" in line.lower() and dims):
                continue
            data = {
                "type_code": code,
                "width_mm": dims[0] if dims else None,
                "height_mm": dims[1] if dims else None,
                "material": _term(line, MATERIALS),
                "frame_material": _label(line, ("frame material", "frame")) or _frame(line),
                "finish": _term(line, FINISHES),
                "fire_rating": _fire(line),
                "quantity": _quantity(line),
                "source_page": page,
                "source_text": line,
            }
            rows.append(_record(code or line, data, page, line, _confidence(code, dims, line, ("door", "frame", "fire"))))
        return _dedupe(rows)

    def _windows(self, page: int, lines: list[str]) -> list[dict]:
        rows = []
        for line in lines:
            code = _code(line, "W")
            dims = _dimensions(line)
            if not code and not ("window" in line.lower() and dims):
                continue
            data = {
                "type_code": code,
                "width_mm": dims[0] if dims else None,
                "height_mm": dims[1] if dims else None,
                "frame_material": _label(line, ("frame material", "frame")) or _frame(line),
                "glass_type": _glass(line),
                "finish": _term(line, FINISHES),
                "quantity": _quantity(line),
                "source_page": page,
                "source_text": line,
            }
            rows.append(_record(code or line, data, page, line, _confidence(code, dims, line, ("window", "glass", "glazing"))))
        return _dedupe(rows)

    def _walls(self, page: int, lines: list[str]) -> list[dict]:
        rows = []
        for line in lines:
            lower = line.lower()
            code = _wall_code(line)
            thickness = _thickness(line)
            if not code and not thickness and not any(word in lower for word in ("wall", "partition", "masonry", "blockwork", "brickwork")):
                continue
            data = {
                "type_code": code,
                "nominal_thickness_mm": thickness,
                "material": _term(line, MATERIALS),
                "use": "external" if "external" in lower else "internal" if "internal" in lower else "both" if "internal/external" in lower else "unknown",
                "cavity_information": line if "cavity" in lower else None,
                "finish": _term(line, FINISHES),
                "bond": _label(line, ("bond",)),
                "mortar": _mortar(line),
                "source_page": page,
                "source_text": line,
            }
            rows.append(_record(code or line, data, page, line, _confidence(code, (thickness, thickness) if thickness else None, line, ("wall", "brick", "block", "partition"))))
        return _dedupe(rows)

    def _floors(self, page: int, lines: list[str]) -> list[dict]:
        rows = []
        for line in lines:
            lower = line.lower()
            code = _floor_code(line)
            if not code and not any(word in lower for word in ("floor finish", "floor type", "skirting", "screed", "tile", "vinyl", "carpet")):
                continue
            data = {
                "floor_type_code": code,
                "finish": _term(line, FINISHES),
                "material": _term(line, MATERIALS),
                "room_or_zone": _label(line, ("room", "zone", "area")),
                "tile_size": _tile_size(line),
                "screed": line if "screed" in lower else None,
                "skirting": line if "skirting" in lower else None,
                "source_page": page,
                "source_text": line,
            }
            rows.append(_record(code or line, data, page, line, 0.72 if code else 0.58))
        return _dedupe(rows)

    def _specifications(self, page: int, lines: list[str]) -> list[dict]:
        rows = []
        for line in lines:
            lower = line.lower()
            matched = any(word in lower for word in ("brick", "block", "mortar", "wall finish", "floor finish", "glazing", "paint", "joinery", "door", "window"))
            if not matched:
                continue
            section = _section(line)
            data = {
                "section": section,
                "brick_block_type": line if any(word in lower for word in ("brick", "block")) else None,
                "mortar": line if "mortar" in lower else None,
                "wall_finishes": line if "wall" in lower and _term(line, FINISHES) else None,
                "floor_finishes": line if "floor" in lower and _term(line, FINISHES) else None,
                "door_window_materials": line if any(word in lower for word in ("door", "window", "frame")) else None,
                "glazing": line if any(word in lower for word in ("glass", "glazing")) else None,
                "paint_joinery": line if any(word in lower for word in ("paint", "joinery")) else None,
                "note": line,
                "source_page": page,
                "source_text": line,
            }
            rows.append(_record(f"{section}:{line}", data, page, line, 0.62))
        return _dedupe(rows)

    def _other(self, page: int, lines: list[str]) -> list[dict]:
        rows = []
        for line in lines[:200]:
            if len(line) < 4:
                continue
            data = {"title": line[:160], "note": line, "source_page": page, "source_text": line}
            rows.append(_record(line, data, page, line, 0.5))
        return _dedupe(rows)


def _record(key: str, data: dict, page: int, text: str, confidence: float) -> dict:
    clean_key = re.sub(r"\s+", " ", key.strip().upper())[:220]
    return {
        "entity_key": clean_key,
        "data": data,
        "source_location": {"page_number": page, "text": text[:1000]},
        "confidence": min(max(float(confidence), 0), 1),
    }


def _dedupe(rows: list[dict]) -> list[dict]:
    values: dict[str, dict] = {}
    for row in rows:
        values[row["entity_key"]] = row
    return list(values.values())


def _code(text: str, prefix: str) -> str | None:
    match = re.search(rf"\b{prefix}\s*[-:]?\s*(\d{{1,3}}[A-Z]?)\b", text, re.I)
    return f"{prefix}{match.group(1).upper()}" if match else None


def _wall_code(text: str) -> str | None:
    for pattern in (r"\b(?:WALL\s*TYPE|WALL)\s*[-:]?\s*([A-Z]{0,3}\d{1,3}[A-Z]?)\b", r"\b((?:BW|CW|PW|IW|EW)\d{1,3}[A-Z]?)\b"):
        match = re.search(pattern, text, re.I)
        if match:
            return match.group(1).upper()
    return None


def _floor_code(text: str) -> str | None:
    match = re.search(r"\b(?:FLOOR\s*TYPE\s*)?(F\d{1,3}[A-Z]?)\b", text, re.I)
    return match.group(1).upper() if match else None


def _dimensions(text: str) -> tuple[float, float] | None:
    match = re.search(r"(?<!\d)(\d{2,4}(?:\.\d+)?)\s*(?:mm)?\s*[xX×]\s*(\d{2,4}(?:\.\d+)?)\s*(?:mm)?", text)
    if not match:
        return None
    return float(match.group(1)), float(match.group(2))


def _thickness(text: str) -> float | None:
    for pattern in (r"(?:thickness|thk|thick)\s*[:=-]?\s*(\d{2,4}(?:\.\d+)?)\s*mm", r"\b(\d{2,4}(?:\.\d+)?)\s*mm\s+(?:thick\s+)?(?:wall|brick|block|masonry|partition)"):
        match = re.search(pattern, text, re.I)
        if match and 25 <= float(match.group(1)) <= 2000:
            return float(match.group(1))
    return None


def _quantity(text: str) -> int | None:
    match = re.search(r"\b(?:qty|quantity|count|no\.)\s*[:=-]?\s*(\d{1,5})\b", text, re.I)
    return int(match.group(1)) if match else None


def _term(text: str, terms: tuple[str, ...]) -> str | None:
    lower = text.lower()
    return next((term.title() for term in terms if term in lower), None)


def _label(text: str, labels: tuple[str, ...]) -> str | None:
    for label in labels:
        match = re.search(rf"\b{re.escape(label)}\s*[:=-]\s*([^,;|]+)", text, re.I)
        if match:
            return match.group(1).strip()[:300]
    return None


def _frame(text: str) -> str | None:
    lower = text.lower()
    for term in ("timber", "steel", "aluminium", "aluminum", "upvc", "pvc"):
        if term in lower and "frame" in lower:
            return term.title()
    return None


def _glass(text: str) -> str | None:
    match = re.search(r"\b((?:clear|tinted|laminated|toughened|tempered|frosted|double|single)[ -]?(?:glazed|glazing|glass))\b", text, re.I)
    return match.group(1).title() if match else ("Glass" if "glass" in text.lower() else None)


def _fire(text: str) -> str | None:
    match = re.search(r"\b(?:FR|FD|FIRE\s*RATED?)\s*[-:]?\s*(\d{2,3})\s*(?:MIN|MINS|MINUTES)?\b", text, re.I)
    return f"{match.group(1)} min" if match else None


def _mortar(text: str) -> str | None:
    match = re.search(r"\bmortar\b[^,;|]*", text, re.I)
    return match.group(0).strip()[:200] if match else None


def _tile_size(text: str) -> str | None:
    match = re.search(r"\b(\d{2,4}\s*[xX×]\s*\d{2,4}\s*(?:mm)?)\b", text)
    return match.group(1) if match else None


def _section(text: str) -> str:
    if ":" in text:
        value = text.split(":", 1)[0].strip()
        if 1 < len(value) <= 80:
            return value
    for name in ("Walls", "Floors", "Doors", "Windows", "Glazing", "Paint", "Joinery", "Masonry"):
        if name.lower() in text.lower():
            return name
    return "General"


def _confidence(code: str | None, dims: tuple[float, float] | None, text: str, keywords: tuple[str, ...]) -> float:
    score = 0.35 + (0.25 if code else 0) + (0.2 if dims else 0)
    score += min(sum(0.05 for word in keywords if word in text.lower()), 0.2)
    return min(score, 0.98)


schedule_extraction_service = ScheduleExtractionService()
