from __future__ import annotations

import re
from difflib import SequenceMatcher
from functools import lru_cache
from typing import Iterable


class RoomSemantics:
    """Fast, deterministic cleanup and matching for printed room labels."""

    _spaces = re.compile(r"\s+")
    _number = re.compile(r"^\d+(?:\.\d+)?(?:\s*(?:MM|CM|M|M2|M²))?$", re.IGNORECASE)
    _metric_dimension = re.compile(
        r"(?:\+\s*)?\b\d{3,5}(?:[.,]\d+)?\s*(?:MM|CM|M)?\b|\b\d+(?:[.,]\d+)?\s*(?:MM|CM|M2|M²)\b",
        re.IGNORECASE,
    )
    _imperial_dimension = re.compile(
        r"\b\d+(?:\s+\d+/\d+)?\s*['’](?:\s*[-–Xx]\s*\d+(?:\s+\d+/\d+)?\s*[\"”]?)?|\b\d+\s*[-–]\s*\d+(?:\s+\d+/\d+)?\s*[\"”]",
        re.IGNORECASE,
    )
    _unit_or_type = re.compile(
        r"\b(?:UNIT|TYPE)\s*[-:#]?\s*(?:NO\.?\s*)?[A-Z0-9][A-Z0-9/(),.-]*",
        re.IGNORECASE,
    )
    _floor_note = re.compile(
        r"\b(?:GROUND|FIRST|SECOND|THIRD|FOURTH|FIFTH|TYPICAL)\s+FLOOR\b",
        re.IGNORECASE,
    )
    _annotation_token = re.compile(
        r"(?<![A-Z0-9])(?:D|DR|W|FW|LW|SW|F|FG|GD|G|S|SL|SD|FD|V)\s*-?\s*\d+[A-Z]?(?![A-Z0-9])"
        r"|(?<![A-Z0-9])(?:FW|LW|SL|FG|FR|BUR|W/M|WM)(?![A-Z0-9])",
        re.IGNORECASE,
    )
    _tag = re.compile(
        r"^(?:(?:D|DR|W|FW|LW|SW|F|FG|GD|G|S|SL|SD|FD|V)\s*-?\s*\d+[A-Z]?|FW|LW|SL|FG|FR|BUR|W/M|WM)$",
        re.IGNORECASE,
    )
    _section = re.compile(r"^(?:SECTION\s*)?[A-Z](?:\s*[-–]\s*[A-Z])?$", re.IGNORECASE)

    # Keys are aliases commonly printed on architectural floor plans. Values
    # are the stable names shown by the application. Matching is case-insensitive.
    NORMALIZATION = {
        "PRIMARY BEDROOM": "Master Bedroom",
        "MASTER BED ROOM": "Master Bedroom",
        "MASTER BEDROOM": "Master Bedroom",
        "MASTER BED": "Master Bedroom",
        "M BED ROOM": "Master Bedroom",
        "M BEDROOM": "Master Bedroom",
        "GUEST BED ROOM": "Guest Bedroom",
        "GUEST BEDROOM": "Guest Bedroom",
        "CHILDREN BEDROOM": "Children's Bedroom",
        "CHILD BEDROOM": "Children's Bedroom",
        "KIDS BEDROOM": "Children's Bedroom",
        "BED ROOM": "Bedroom",
        "BEDROOM": "Bedroom",
        "BEDRM": "Bedroom",
        "BDRM": "Bedroom",
        "BED RM": "Bedroom",
        "TOILET AND BATH ROOM": "Bathroom",
        "TOILET & BATH ROOM": "Bathroom",
        "TOILET AND BATH": "Bathroom",
        "BATH ROOM": "Bathroom",
        "BATHROOM": "Bathroom",
        "BATH": "Bathroom",
        "WASH ROOM": "Bathroom",
        "WASHROOM": "Bathroom",
        "ENSUITE BATHROOM": "Ensuite Bathroom",
        "EN SUITE BATHROOM": "Ensuite Bathroom",
        "ENSUITE": "Ensuite Bathroom",
        "POWDER ROOM": "Toilet",
        "LAVATORY": "Toilet",
        "TOILET": "Toilet",
        "TOIL": "Toilet",
        "TOI": "Toilet",
        "TOL": "Toilet",
        "T0I": "Toilet",
        "T0L": "Toilet",
        "W C": "Toilet",
        "WC": "Toilet",
        "W/C": "Toilet",
        "DINING ROOM": "Dining Area",
        "DINING AREA": "Dining Area",
        "DINING": "Dining Area",
        "DIN": "Dining Area",
        "FAMILY ROOM": "Living Room",
        "LIVING ROOM": "Living Room",
        "LIVING AREA": "Living Area",
        "LIVING": "Living Room",
        "LOUNGE": "Living Room",
        "SITTING ROOM": "Sitting Area",
        "SITTING AREA": "Sitting Area",
        "SITTING": "Sitting Area",
        "KITCHENETTE": "Kitchenette",
        "KITCHEN": "Kitchen",
        "KITCH": "Kitchen",
        "KIT": "Kitchen",
        "BUTLERS PANTRY": "Pantry",
        "BUTLER PANTRY": "Pantry",
        "PANTRY": "Pantry",
        "BALCONY": "Balcony",
        "BALC": "Balcony",
        "BAL": "Balcony",
        "VERANDAH": "Verandah",
        "VERANDA": "Verandah",
        "TERRACE": "Terrace",
        "PATIO": "Patio",
        "PORCH": "Porch",
        "DECK": "Deck",
        "UTILITY ROOM": "Utility",
        "UTILITY": "Utility",
        "UTIL": "Utility",
        "LAUNDRY ROOM": "Laundry",
        "LAUNDRY": "Laundry",
        "WASH AREA": "Wash Area",
        "SERVICE YARD": "Service Yard",
        "STORE ROOM": "Store",
        "STOREROOM": "Store",
        "STORAGE ROOM": "Store",
        "STORAGE": "Store",
        "STORE": "Store",
        "BOX ROOM": "Store",
        "WALK IN CLOSET": "Walk-in Closet",
        "WALK IN WARDROBE": "Walk-in Closet",
        "DRESSING ROOM": "Dressing Room",
        "DRESSING": "Dressing Room",
        "WARDROBE": "Wardrobe",
        "CLOSET": "Closet",
        "ENTRANCE LOBBY": "Lobby",
        "ENTRANCE HALL": "Lobby",
        "LIFT LOBBY": "Lift Lobby",
        "ELEVATOR LOBBY": "Lift Lobby",
        "LOBBY": "Lobby",
        "FOYER": "Foyer",
        "CORRIDOR": "Corridor",
        "HALLWAY": "Corridor",
        "PASSAGE": "Passage",
        "OFFICE ROOM": "Office",
        "HOME OFFICE": "Office",
        "OFFICE": "Office",
        "STUDY ROOM": "Study",
        "STUDY": "Study",
        "WORK ROOM": "Work Room",
        "PRAYER ROOM": "Prayer Room",
        "POOJA ROOM": "Prayer Room",
        "PUJA ROOM": "Prayer Room",
        "MAIDS ROOM": "Maid's Room",
        "MAID ROOM": "Maid's Room",
        "SERVANT ROOM": "Maid's Room",
        "NURSERY": "Nursery",
        "PLAY ROOM": "Playroom",
        "PLAYROOM": "Playroom",
        "GYMNASIUM": "Gym",
        "GYM": "Gym",
        "GARBAGE A C": "Garbage Room",
        "GARBAGE ROOM": "Garbage Room",
        "GARBAGE": "Garbage Room",
        "REFUSE ROOM": "Garbage Room",
        "GARAGE": "Garage",
        "CAR PORT": "Carport",
        "CARPORT": "Carport",
        "PARKING": "Parking",
        "DRIVE WAY": "Driveway",
        "DRIVEWAY": "Driveway",
        "RECEPTION": "Reception",
        "MEETING ROOM": "Meeting Room",
        "CONFERENCE ROOM": "Conference Room",
        "CLASS ROOM": "Classroom",
        "CLASSROOM": "Classroom",
        "JANITOR ROOM": "Janitor Room",
        "JANITOR": "Janitor Room",
        "ELECTRICAL ROOM": "Electrical Room",
        "MECHANICAL ROOM": "Mechanical Room",
        "PLANT ROOM": "Plant Room",
        "LIFT MACHINE ROOM": "Lift Machine Room",
        "MACHINE ROOM": "Machine Room",
        "WATER TANK": "Water Tank",
        "PANEL ROOM": "Panel Room",
        "CONDOMINIUM MANAGEMENT ROOM": "Management Room",
        "MANAGEMENT ROOM": "Management Room",
        "SERVER ROOM": "Server Room",
        "STAIR LANDING": "Stair Landing",
        "STAIRCASE": "Stair",
        "STAIRS": "Stair",
        "STAIR": "Stair",
        "LANDING": "Stair Landing",
        "DN": "Stair",
        "UP": "Stair",
        "LIFT": "Lift",
        "ELEVATOR": "Lift",
        "FIRE DUCT": "Shaft",
        "ELEC DUCT": "Shaft",
        "ELECTRICAL DUCT": "Shaft",
        "DUCT": "Shaft",
        "LIFT SHAFT": "Shaft",
        "ELEVATOR SHAFT": "Shaft",
        "SHAFT": "Shaft",
        "VOID": "Void",
        "FLOWER TROUGH": "Landscaping",
        "LANDSCAPING": "Landscaping",
        "PLANTER": "Landscaping",
        "R C C SLAB BELOW": "Below Reference",
        "RCC SLAB BELOW": "Below Reference",
        "TERRACE BELOW": "Below Reference",
        "R C C SLAB": "Roof Slab",
        "RCC SLAB": "Roof Slab",
        "OPEN PLAN": "Open Plan",
    }

    _sorted_aliases = tuple(sorted(NORMALIZATION, key=lambda item: (-len(item), item)))
    # Only these clear architectural labels may recover a model-missed room
    # from an existing wall cell. Generic or inferred names still label rooms,
    # but are not strong enough to create geometry.
    EXCEPTION_RECOVERY_LABELS = frozenset({
        "Master Bedroom", "Guest Bedroom", "Children's Bedroom", "Bedroom",
        "Bathroom", "Ensuite Bathroom", "Toilet",
        "Dining Area", "Living Room", "Living Area", "Sitting Area",
        "Kitchen", "Kitchenette", "Pantry",
        "Balcony", "Verandah", "Terrace", "Patio", "Porch", "Deck",
        "Utility", "Laundry", "Store", "Walk-in Closet", "Dressing Room",
    })
    WET_AREA_LABELS = frozenset({"Bathroom", "Ensuite Bathroom", "Toilet"})
    EXTERNAL_AREA_LABELS = frozenset({
        "Balcony", "Verandah", "Terrace", "Patio", "Porch", "Deck",
    })

    def clean(self, value: object) -> str:
        text = str(value or "").replace("\r", "\n")
        text = self._imperial_dimension.sub(" ", text)
        text = self._metric_dimension.sub(" ", text)
        text = self._unit_or_type.sub(" ", text)
        text = self._floor_note.sub(" ", text)
        text = self._annotation_token.sub(" ", text)
        text = re.sub(r"\b(?:NORTH|SOUTH|EAST|WEST)\b", " ", text, flags=re.IGNORECASE)
        # Remove isolated apartment/grid markers, while retaining meaningful
        # two-letter room aliases such as WC, UP and DN.
        text = re.sub(r"(?:^|[\s+])\b[A-Z]\b(?=$|[\s+])", " ", text, flags=re.IGNORECASE)
        text = re.sub(r"\+\s*\+", " ", text)
        text = re.sub(r"[|,:;()\[\]{}]+", " ", text)
        text = re.sub(r"[./\\]+", " ", text)
        text = self._spaces.sub(" ", text.replace("\n", " ")).strip(" -_:+/")
        if len(text) < 2 or len(text) > 80:
            return ""
        if self._number.match(text) or self._tag.match(text) or self._section.match(text):
            return ""
        if not re.search(r"[A-Za-z]{2,}", text) and not re.fullmatch(
            r"W\s+C", text, flags=re.IGNORECASE
        ):
            return ""
        return text

    @staticmethod
    def _ocr_key(value: str) -> str:
        tokens: list[str] = []
        for token in re.findall(r"[A-Z0-9]+", value.upper()):
            if re.search(r"[A-Z]", token):
                token = token.replace("0", "O").replace("1", "I").replace("5", "S")
            tokens.append(token)
        return " ".join(tokens)

    @staticmethod
    def _contains_phrase(text: str, phrase: str) -> bool:
        return f" {phrase} " in f" {text} "

    def match_known_labels(self, value: object) -> list[str]:
        """Return dictionary-backed names, ignoring case and mild OCR errors."""
        return list(self._match_known_text(str(value or "")))

    @lru_cache(maxsize=4096)
    def _match_known_text(self, value: str) -> tuple[str, ...]:
        cleaned = self.clean(value)
        if not cleaned:
            return ()
        key = self._ocr_key(cleaned)
        matches: list[str] = []
        matched_aliases: list[str] = []
        for alias in self._sorted_aliases:
            alias_key = self._ocr_key(alias)
            if not self._contains_phrase(key, alias_key):
                continue
            # Avoid returning Bedroom as well as Master Bedroom, for example.
            if any(self._contains_phrase(chosen, alias_key) for chosen in matched_aliases):
                continue
            matched_aliases.append(alias_key)
            normalized = self.NORMALIZATION[alias]
            if normalized not in matches:
                matches.append(normalized)
        if matches:
            return tuple(matches)

        # Cheap fuzzy fallback for a single OCR-damaged label. Exact/phrase
        # matching above handles the normal path and combined room labels.
        words = key.split()
        best: tuple[float, str] | None = None
        for alias in self._sorted_aliases:
            alias_key = self._ocr_key(alias)
            compact_alias = alias_key.replace(" ", "")
            if len(compact_alias) < 5:
                continue
            word_count = len(alias_key.split())
            for size in {max(1, word_count - 1), word_count, word_count + 1}:
                for start in range(0, len(words) - size + 1):
                    candidate = "".join(words[start : start + size])
                    score = SequenceMatcher(None, candidate, compact_alias).ratio()
                    if score >= 0.84 and (best is None or score > best[0]):
                        best = (score, self.NORMALIZATION[alias])
        return (best[1],) if best else ()

    def extract_labels(self, value: object) -> list[str]:
        known = self.match_known_labels(value)
        if known:
            return known
        cleaned = self.clean(value)
        if not cleaned:
            return []
        fallback = " ".join(part.capitalize() for part in cleaned.upper().split())
        return [fallback] if fallback else []

    def normalize(self, value: object) -> str:
        known = self.match_known_labels(value)
        if known:
            return " / ".join(known)
        extracted = self.extract_labels(value)
        return extracted[0] if extracted else ""

    def is_exception_recovery_label(self, value: object) -> bool:
        return any(
            label in self.EXCEPTION_RECOVERY_LABELS
            for label in self.match_known_labels(value)
        )

    def label_group(self, value: object) -> str:
        labels = set(self.match_known_labels(value))
        if labels & self.WET_AREA_LABELS:
            return "wet_area"
        if labels & self.EXTERNAL_AREA_LABELS:
            return "external_area"
        return "internal_room"

    def classify(self, labels: Iterable[str] | str) -> dict[str, object]:
        normalized: list[str] = []
        values = [labels] if isinstance(labels, str) else labels
        for item in values:
            extracted = self.extract_labels(item)
            for value in extracted:
                if value and value not in normalized:
                    normalized.append(value)
        upper = " | ".join(normalized).upper()
        if any(token in upper for token in ("BELOW REFERENCE", "LANDSCAPING")):
            kind = "excluded"
            include = False
            semantic_type = "landscaping" if "LANDSCAPING" in upper else "reference_only"
        elif any(token in upper for token in ("VOID", "SHAFT")):
            kind = "void"
            include = False
            semantic_type = "shaft" if "SHAFT" in upper else "void"
        elif "LIFT" in upper and "LOBBY" not in upper and "MACHINE ROOM" not in upper:
            kind = "void"
            include = False
            semantic_type = "lift"
        elif any(token in upper for token in ("STAIR", "DN", "UP", "LANDING")):
            kind = "circulation"
            include = False
            semantic_type = "stair"
        elif "WATER TANK" in upper:
            kind = "service"
            include = False
            semantic_type = "equipment"
        elif any(token in upper for token in ("LIFT MACHINE ROOM", "MACHINE ROOM", "PANEL ROOM", "PLANT ROOM")):
            kind = "service"
            include = True
            semantic_type = "service_room"
        elif any(token in upper for token in ("PARKING", "DRIVEWAY", "ROOF SLAB")):
            kind = "external"
            include = True
            semantic_type = "parking" if "PARKING" in upper else "driveway" if "DRIVEWAY" in upper else "roof_slab"
        elif any(token in upper for token in ("BALCONY", "VERANDAH", "TERRACE", "PORCH", "PATIO", "DECK")):
            kind = "external"
            include = True
            semantic_type = "verandah" if "VERANDA" in upper else "balcony" if "BALCONY" in upper else "external_area"
        else:
            kind = "internal"
            include = True
            semantic_type = "internal_room"
        room_labels = [item for item in normalized if item not in {"Stair", "Stair Landing"}]
        open_plan = len(room_labels) > 1 and kind == "internal"
        if open_plan:
            name = " / ".join(room_labels[:3])
            room_type = "Open Plan"
            semantic_type = "open_plan"
        else:
            name = normalized[0] if normalized else ""
            room_type = normalized[0] if normalized else ""
        return {
            "labels": normalized,
            "name": name,
            "room_type": room_type,
            "space_kind": kind,
            "include_in_boq": include,
            "open_plan": open_plan,
            "semantic_type": semantic_type,
        }


room_semantics = RoomSemantics()
