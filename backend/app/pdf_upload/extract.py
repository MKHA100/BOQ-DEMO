from __future__ import annotations

import hashlib
import re

import fitz
from collections.abc import Callable
from typing import Any

from app.pdf_upload.pdf import pdf_asset_service
from app.pdf_upload.repo import pdf_upload_repository
from app.pdf_upload.schemas import DoorExtraction, FloorExtraction, SourceLocation, WallExtraction, WindowExtraction
from app.storage.storage_service import storage_service

ProgressCallback = Callable[[int, str, dict | None], None]

DOOR_PAGE_TYPES = {"door_window_schedule", "door_schedule", "specification", "other"}
WINDOW_PAGE_TYPES = {"door_window_schedule", "window_schedule", "specification", "other"}
WALL_PAGE_TYPES = {"wall_schedule", "specification", "floor_plan", "other"}
FLOOR_PAGE_TYPES = {"floor_schedule", "floor_plan", "specification", "other"}

MATERIAL_TERMS = (
    "timber",
    "wood",
    "steel",
    "aluminium",
    "aluminum",
    "glass",
    "upvc",
    "pvc",
    "brick",
    "block",
    "concrete",
    "gypsum",
    "plasterboard",
    "masonry",
)
FINISH_TERMS = (
    "paint",
    "painted",
    "powder coated",
    "laminate",
    "veneer",
    "polished",
    "tile",
    "tiles",
    "carpet",
    "vinyl",
    "screed",
    "terrazzo",
)


class StructuredExtractionService:
    def extract(
        self,
        *,
        project_id: str,
        document_id: str,
        extraction_type: str,
        progress: ProgressCallback | None = None,
    ) -> dict:
        document = pdf_upload_repository.get_document(project_id, document_id)
        if not document:
            raise RuntimeError("Document not found.")
        pdf_asset_service.ensure_classifications(project_id=project_id, document_id=document_id)
        pages = pdf_upload_repository.list_pages(project_id, document_id)
        candidates = [page for page in pages if self._page_is_relevant(page, extraction_type)]
        if not candidates:
            candidates = pages

        records: dict[str, dict] = {}
        total = len(candidates)
        source_path = storage_service.ensure_local_file(storage_service.key_to_path(document["storage_key"]))
        source_pdf = fitz.open(source_path) if source_path.exists() and extraction_type in {"door", "window"} else None
        try:
            for index, page in enumerate(candidates, start=1):
                text_payload = pdf_asset_service.read_page_text(page)
                lines = self._page_lines(text_payload)
                parsed = self._parse_page(extraction_type, page, lines)
                if source_pdf is not None and page.get("classification") == "door_window_schedule":
                    parsed.extend(self._parse_door_window_details(source_pdf, page, extraction_type))
                for item in parsed:
                    records[item["entity_key"]] = item
                if progress:
                    progress(
                        max(1, min(int(round(index / max(total, 1) * 100)), 99)),
                        self._message(extraction_type),
                        {"page_number": page["page_number"], "record_count": len(records)},
                    )
        finally:
            if source_pdf is not None:
                source_pdf.close()

        count = pdf_upload_repository.replace_extraction_records(
            project_id=project_id,
            document_id=document_id,
            extraction_type=extraction_type,
            extraction_version=int(document.get("version") or 1),
            records=records.values(),
        )
        return {
            "document_id": document_id,
            "extraction_type": extraction_type,
            "record_count": count,
            "message": self._ready_message(extraction_type),
        }

    def _parse_door_window_details(self, pdf: fitz.Document, page_record: dict, extraction_type: str) -> list[dict]:
        page_number = int(page_record["page_number"])
        if page_number < 1 or page_number > pdf.page_count:
            return []
        page = pdf.load_page(page_number - 1)
        words = page.get_text("words", sort=True)
        code_words: list[tuple[float, float, tuple]] = []
        for word in words:
            code = re.sub(r"[^A-Za-z0-9]", "", str(word[4] or "")).upper()
            is_door = bool(re.fullmatch(r"D\d+[A-Z]*", code))
            is_window = bool(re.fullmatch(r"(?:W\d+[A-Z]*|FG\d*|F\d+[A-Z]*)", code))
            if not (is_door or is_window):
                continue
            code_words.append(((float(word[0]) + float(word[2])) / 2, (float(word[1]) + float(word[3])) / 2, word))
        if not code_words:
            return []

        rows: list[list[tuple[float, float, tuple]]] = []
        for candidate in sorted(code_words, key=lambda item: (item[1], item[0])):
            if not rows or abs(candidate[1] - sum(item[1] for item in rows[-1]) / len(rows[-1])) > 80:
                rows.append([candidate])
            else:
                rows[-1].append(candidate)

        results: list[dict] = []
        previous_row_y = 0.0
        for row in rows:
            row.sort(key=lambda item: item[0])
            row_y = sum(item[1] for item in row) / len(row)
            top = 0.0 if previous_row_y <= 0 else previous_row_y + 15.0
            bottom = max(top + 40.0, row_y - 5.0)
            for index, (center_x, _center_y, code_word) in enumerate(row):
                left = 0.0 if index == 0 else (row[index - 1][0] + center_x) / 2
                right = float(page.rect.width) if index == len(row) - 1 else (center_x + row[index + 1][0]) / 2
                cell = fitz.Rect(left, top, right, bottom)
                cell_words = [
                    word for word in words
                    if cell.contains(fitz.Point((float(word[0]) + float(word[2])) / 2, (float(word[1]) + float(word[3])) / 2))
                ]
                code = re.sub(r"[^A-Za-z0-9]", "", str(code_word[4] or "")).upper()
                is_door_code = bool(re.fullmatch(r"D\d+[A-Z]*", code))
                if (extraction_type == "door" and not is_door_code) or (extraction_type == "window" and is_door_code):
                    continue
                numbers = []
                for word in cell_words:
                    raw = str(word[4] or "").replace(",", "").strip()
                    if not re.fullmatch(r"\d+(?:\.\d+)?", raw):
                        continue
                    value = float(raw)
                    if 500 <= value <= 5000:
                        numbers.append({"value": value, "x": (float(word[0]) + float(word[2])) / 2, "y": (float(word[1]) + float(word[3])) / 2})
                if len(numbers) < 2:
                    continue
                width_item = min(numbers, key=lambda item: (item["y"], abs(item["x"] - center_x)))
                height_candidates = [item for item in numbers if item is not width_item]
                height_item = min(height_candidates, key=lambda item: item["x"])
                text = " ".join(str(word[4] or "") for word in cell_words)
                lower = text.lower()
                frame_material = next((value for term, value in (("aluminium", "Aluminium"), ("aluminum", "Aluminium"), ("timber", "Timber"), ("steel", "Steel"), ("upvc", "uPVC"), ("pvc", "PVC")) if term in lower), None)
                source = SourceLocation(
                    page_number=page_number,
                    text=text[:1000],
                    bbox=[float(cell.x0), float(cell.y0), float(cell.x1), float(cell.y1)],
                )
                if extraction_type == "door":
                    material = "Aluminium" if "aluminum" in lower or "aluminium" in lower else ("Timber" if "timber" in lower else None)
                    model = DoorExtraction(
                        type_code=code, width_mm=width_item["value"], height_mm=height_item["value"],
                        material=material, frame_material=frame_material, finish=None, fire_rating=None, quantity=None, source=source,
                    )
                else:
                    glass_type = "Glass Panel" if "glass" in lower else None
                    model = WindowExtraction(
                        type_code=code, width_mm=width_item["value"], height_mm=height_item["value"],
                        frame_material=frame_material, glass_type=glass_type, finish=None, quantity=None, source=source,
                    )
                record = self._record(extraction_type, page_record, model.model_dump(mode="json"), source, 0.94, code)
                record["extraction_method"] = "vector_detail_layout"
                record["review_state"] = "ready"
                results.append(record)
            previous_row_y = row_y
        return results

    def _parse_page(self, extraction_type: str, page: dict, lines: list[dict]) -> list[dict]:
        if extraction_type == "door":
            return self._parse_doors(page, lines)
        if extraction_type == "window":
            return self._parse_windows(page, lines)
        if extraction_type == "wall":
            return self._parse_walls(page, lines)
        if extraction_type == "floor":
            return self._parse_floors(page, lines)
        raise ValueError(f"Unsupported extraction type: {extraction_type}")

    def _parse_doors(self, page: dict, lines: list[dict]) -> list[dict]:
        results: list[dict] = []
        for line in lines:
            text = line["text"]
            code = _type_code(text, "D")
            dimensions = _dimensions(text)
            if not code and not (dimensions and "door" in text.lower()):
                continue
            source = self._source(page, line)
            model = DoorExtraction(
                type_code=code,
                width_mm=dimensions[0] if dimensions else None,
                height_mm=dimensions[1] if dimensions else None,
                material=_term(text, MATERIAL_TERMS),
                frame_material=_label_value(text, ("frame", "frame material")) or _frame_material(text),
                finish=_term(text, FINISH_TERMS),
                fire_rating=_fire_rating(text),
                quantity=_quantity(text),
                source=source,
            )
            confidence = _confidence(code=code, dimensions=dimensions, text=text, keywords=("door", "frame", "fire"))
            results.append(self._record("door", page, model.model_dump(mode="json"), source, confidence, code or text))
        return results

    def _parse_windows(self, page: dict, lines: list[dict]) -> list[dict]:
        results: list[dict] = []
        for line in lines:
            text = line["text"]
            code = _type_code(text, "W")
            dimensions = _dimensions(text)
            if not code and not (dimensions and "window" in text.lower()):
                continue
            source = self._source(page, line)
            model = WindowExtraction(
                type_code=code,
                width_mm=dimensions[0] if dimensions else None,
                height_mm=dimensions[1] if dimensions else None,
                frame_material=_label_value(text, ("frame", "frame material")) or _frame_material(text),
                glass_type=_glass_type(text),
                finish=_term(text, FINISH_TERMS),
                quantity=_quantity(text),
                source=source,
            )
            confidence = _confidence(code=code, dimensions=dimensions, text=text, keywords=("window", "glass", "glazing"))
            results.append(self._record("window", page, model.model_dump(mode="json"), source, confidence, code or text))
        return results

    def _parse_walls(self, page: dict, lines: list[dict]) -> list[dict]:
        results: list[dict] = []
        for line in lines:
            text = line["text"]
            lower = text.lower()
            code = _wall_code(text)
            thickness = _thickness(text)
            relevant = bool(code or thickness) and any(term in lower for term in ("wall", "brick", "block", "masonry", "partition", "cavity"))
            if not relevant:
                continue
            source = self._source(page, line)
            model = WallExtraction(
                wall_type=code,
                nominal_thickness_mm=thickness,
                material=_term(text, MATERIAL_TERMS),
                internal_external_hint=_wall_location(lower),
                cavity_information=text[:500] if "cavity" in lower else None,
                finish=_term(text, FINISH_TERMS),
                bond=_label_value(text, ("bond",)) or _bond(text),
                mortar=_label_value(text, ("mortar", "mortar mix")) or _mortar(text),
                source=source,
            )
            confidence = _confidence(code=code, dimensions=(thickness, None) if thickness else None, text=text, keywords=("wall", "masonry", "cavity"))
            results.append(self._record("wall", page, model.model_dump(mode="json"), source, confidence, code or text))
        return results

    def _parse_floors(self, page: dict, lines: list[dict]) -> list[dict]:
        results: list[dict] = []
        for line in lines:
            text = line["text"]
            lower = text.lower()
            code = _floor_code(text)
            has_finish = any(term in lower for term in FINISH_TERMS)
            relevant = bool(code or has_finish or re.search(r"\b(room|floor finish|finish schedule)\b", lower))
            if not relevant:
                continue
            room_label = _room_label(text)
            source = self._source(page, line)
            model = FloorExtraction(
                room_label=room_label,
                floor_type_code=code,
                floor_finish=_term(text, FINISH_TERMS),
                material_note=_term(text, MATERIAL_TERMS) or (text[:500] if "material" in lower else None),
                floor_schedule_reference=_schedule_reference(text),
                source=source,
            )
            confidence = _confidence(code=code, dimensions=None, text=text, keywords=("floor", "room", "finish"))
            results.append(self._record("floor", page, model.model_dump(mode="json"), source, confidence, code or room_label or text))
        return results

    @staticmethod
    def _record(
        extraction_type: str,
        page: dict,
        data: dict,
        source: SourceLocation,
        confidence: float,
        identity: str,
    ) -> dict:
        normalized_identity = re.sub(r"\s+", " ", identity.strip().lower())[:300]
        digest = hashlib.sha256(
            f"{extraction_type}|{page['id']}|{normalized_identity}".encode("utf-8")
        ).hexdigest()[:24]
        return {
            "document_page_id": page["id"],
            "entity_key": f"{extraction_type}:{page['page_number']}:{digest}",
            "data": data,
            "source_type": "main_pdf",
            "source_location": source.model_dump(mode="json"),
            "extraction_method": "vector_text_rules",
            "confidence": confidence,
            "quality_signal": _quality_signal(confidence),
            "review_state": "needs_review",
        }

    @staticmethod
    def _source(page: dict, line: dict) -> SourceLocation:
        return SourceLocation(
            page_number=int(page["page_number"]),
            line_number=int(line["line_number"]),
            text=str(line["text"])[:1000],
            bbox=line.get("bbox"),
        )

    @staticmethod
    def _page_lines(payload: dict) -> list[dict]:
        result: list[dict] = []
        line_number = 0
        blocks = payload.get("blocks") if isinstance(payload, dict) else None
        if isinstance(blocks, list):
            for block in blocks:
                if not isinstance(block, dict):
                    continue
                bbox = block.get("bbox")
                for value in str(block.get("text") or "").splitlines():
                    text = re.sub(r"\s+", " ", value).strip()
                    if not text:
                        continue
                    line_number += 1
                    result.append({"line_number": line_number, "text": text, "bbox": bbox})
        if result:
            return result
        for value in str(payload.get("text") or "").splitlines():
            text = re.sub(r"\s+", " ", value).strip()
            if text:
                line_number += 1
                result.append({"line_number": line_number, "text": text, "bbox": None})
        return result

    @staticmethod
    def _page_is_relevant(page: dict, extraction_type: str) -> bool:
        classification = page.get("classification") or "other"
        mapping = {
            "door": DOOR_PAGE_TYPES,
            "window": WINDOW_PAGE_TYPES,
            "wall": WALL_PAGE_TYPES,
            "floor": FLOOR_PAGE_TYPES,
        }
        return classification in mapping[extraction_type]

    @staticmethod
    def _message(extraction_type: str) -> str:
        return {
            "door": "Reading door information",
            "window": "Reading window information",
            "wall": "Reading wall information",
            "floor": "Reading floor information",
        }[extraction_type]

    @staticmethod
    def _ready_message(extraction_type: str) -> str:
        return {
            "door": "Door information ready",
            "window": "Window information ready",
            "wall": "Wall information ready",
            "floor": "Floor information ready",
        }[extraction_type]


def _type_code(text: str, prefix: str) -> str | None:
    patterns = (
        rf"\b{prefix}\s*[-:]?\s*(\d{{1,3}}[A-Z]?)\b",
        rf"\b{prefix}(\d{{1,3}}[A-Z]?)\b",
    )
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return f"{prefix}{match.group(1).upper()}"
    return None


def _wall_code(text: str) -> str | None:
    patterns = (
        r"\b(?:WALL\s*TYPE|WALL)\s*[-:]?\s*([A-Z]{0,3}\d{1,3}[A-Z]?)\b",
        r"\b((?:BW|CW|PW|IW|EW)\d{1,3}[A-Z]?)\b",
    )
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1).upper()
    return None


def _floor_code(text: str) -> str | None:
    match = re.search(r"\b(?:FLOOR\s*TYPE\s*)?(F\d{1,3}[A-Z]?)\b", text, re.IGNORECASE)
    return match.group(1).upper() if match else None


def _dimensions(text: str) -> tuple[float, float] | None:
    match = re.search(r"(?<!\d)(\d{2,4}(?:\.\d+)?)\s*(?:mm)?\s*[xX×]\s*(\d{2,4}(?:\.\d+)?)\s*(?:mm)?", text)
    if not match:
        return None
    width, height = float(match.group(1)), float(match.group(2))
    if width <= 0 or height <= 0:
        return None
    return width, height


def _thickness(text: str) -> float | None:
    patterns = (
        r"(?:thickness|thk|thick)\s*[:=-]?\s*(\d{2,4}(?:\.\d+)?)\s*mm",
        r"\b(\d{2,4}(?:\.\d+)?)\s*mm\s+(?:thick\s+)?(?:wall|brick|block|masonry|partition)",
        r"(?:wall|brick|block|masonry|partition)[^\d]{0,30}(\d{2,4}(?:\.\d+)?)\s*mm",
    )
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            value = float(match.group(1))
            if 25 <= value <= 2000:
                return value
    return None


def _quantity(text: str) -> int | None:
    match = re.search(r"\b(?:qty|quantity|count|no\.)\s*[:=-]?\s*(\d{1,5})\b", text, re.IGNORECASE)
    return int(match.group(1)) if match else None


def _term(text: str, terms: tuple[str, ...]) -> str | None:
    lower = text.lower()
    for term in terms:
        if term in lower:
            return term.title()
    return None


def _label_value(text: str, labels: tuple[str, ...]) -> str | None:
    for label in labels:
        match = re.search(rf"\b{re.escape(label)}\b\s*[:=-]\s*([^,;|]+)", text, re.IGNORECASE)
        if match:
            return match.group(1).strip()[:300]
    return None


def _frame_material(text: str) -> str | None:
    lower = text.lower()
    for material in ("timber", "steel", "aluminium", "aluminum", "upvc", "pvc"):
        if material in lower and "frame" in lower:
            return material.title()
    return None


def _glass_type(text: str) -> str | None:
    lower = text.lower()
    options = ("toughened glass", "laminated glass", "clear glass", "frosted glass", "double glazing", "single glazing")
    for option in options:
        if option in lower:
            return option.title()
    return _label_value(text, ("glass", "glazing"))


def _fire_rating(text: str) -> str | None:
    match = re.search(r"\b(?:fire\s*rating|frl)\s*[:=-]?\s*([A-Z0-9/\- ]{2,24})", text, re.IGNORECASE)
    return match.group(1).strip() if match else None


def _bond(text: str) -> str | None:
    match = re.search(r"\b(?:stretcher|english|flemish|stack)\s+bond\b", text, re.IGNORECASE)
    return match.group(0).title() if match else None


def _mortar(text: str) -> str | None:
    match = re.search(r"\b(?:mortar(?:\s+mix)?\s*[:=-]?\s*)?(\d\s*:\s*\d(?:\s*:\s*\d)?)\b", text, re.IGNORECASE)
    return match.group(1).replace(" ", "") if match else None


def _wall_location(lower: str) -> str:
    if "external" in lower or "exterior" in lower:
        return "external"
    if "internal" in lower or "interior" in lower:
        return "internal"
    return "unknown"


def _room_label(text: str) -> str | None:
    match = re.search(r"\b(?:room|space)\s*[:=-]\s*([^,;|]+)", text, re.IGNORECASE)
    if match:
        return match.group(1).strip()[:160]
    return None


def _schedule_reference(text: str) -> str | None:
    match = re.search(r"\b(?:refer|ref\.?|see)\s+(?:to\s+)?([^,;|]{3,100}(?:schedule|specification))", text, re.IGNORECASE)
    return match.group(1).strip() if match else None


def _confidence(*, code: str | None, dimensions: tuple[float | None, float | None] | None, text: str, keywords: tuple[str, ...]) -> float:
    value = 0.45
    if code:
        value += 0.18
    if dimensions and any(item is not None for item in dimensions):
        value += 0.17
    lower = text.lower()
    value += min(0.15, sum(0.05 for keyword in keywords if keyword in lower))
    return round(min(value, 0.95), 2)


def _quality_signal(confidence: float) -> str:
    if confidence >= 0.8:
        return "high"
    if confidence >= 0.6:
        return "medium"
    return "low"


structured_extraction_service = StructuredExtractionService()
