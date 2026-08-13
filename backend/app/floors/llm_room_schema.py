from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


DimensionStatus = Literal["exact", "partial", "unknown"]
AreaType = Literal["internal", "external", "circulation", "void"]
SemanticType = Literal[
    "internal_room",
    "external_area",
    "open_plan",
    "circulation",
    "stair",
    "void",
    "shaft",
    "balcony",
    "verandah",
]


class RoomInterpretation(BaseModel):
    """Semantic evidence for one existing room suggestion.

    Deliberately absent: polygon coordinates, area and perimeter. Those remain
    deterministic outputs of the local wall/geometry pipeline.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    room_suggestion_id: str = Field(min_length=1, max_length=128)
    room_name: str = Field(default="", max_length=120)
    room_type: str = Field(default="", max_length=80)
    semantic_type: SemanticType = "internal_room"
    surrounding_wall_ids: list[str] = Field(default_factory=list, max_length=100)
    door_ids: list[str] = Field(default_factory=list, max_length=40)
    printed_width_mm: float | None = Field(default=None, gt=0, le=100_000)
    printed_length_mm: float | None = Field(default=None, gt=0, le=100_000)
    dimension_status: DimensionStatus = "unknown"
    area_type: AreaType = "internal"
    open_plan_group: str | None = Field(default=None, max_length=120)
    open_plan_with: list[str] = Field(default_factory=list, max_length=20)
    warnings: list[str] = Field(default_factory=list, max_length=20)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)

    @field_validator("surrounding_wall_ids", "door_ids", "open_plan_with", "warnings")
    @classmethod
    def unique_strings(cls, value: list[str]) -> list[str]:
        return list(dict.fromkeys(str(item).strip() for item in value if str(item).strip()))


class FloorRoomInterpretation(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    floor_id: str = Field(min_length=1, max_length=128)
    rooms: list[RoomInterpretation] = Field(default_factory=list, max_length=500)
    warnings: list[str] = Field(default_factory=list, max_length=40)

    @field_validator("warnings")
    @classmethod
    def unique_warnings(cls, value: list[str]) -> list[str]:
        return list(dict.fromkeys(str(item).strip() for item in value if str(item).strip()))


def floor_room_response_schema() -> dict[str, Any]:
    """Strict JSON schema accepted by the Responses API structured output."""
    string_array = {
        "type": "array",
        "items": {"type": "string"},
    }
    room = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "room_suggestion_id": {"type": "string"},
            "room_name": {"type": "string"},
            "room_type": {"type": "string"},
            "semantic_type": {
                "type": "string",
                "enum": [
                    "internal_room",
                    "external_area",
                    "open_plan",
                    "circulation",
                    "stair",
                    "void",
                    "shaft",
                    "balcony",
                    "verandah",
                ],
            },
            "surrounding_wall_ids": string_array,
            "door_ids": string_array,
            "printed_width_mm": {"type": ["number", "null"]},
            "printed_length_mm": {"type": ["number", "null"]},
            "dimension_status": {
                "type": "string",
                "enum": ["exact", "partial", "unknown"],
            },
            "area_type": {
                "type": "string",
                "enum": ["internal", "external", "circulation", "void"],
            },
            "open_plan_group": {"type": ["string", "null"]},
            "open_plan_with": string_array,
            "warnings": string_array,
            "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        },
        "required": [
            "room_suggestion_id",
            "room_name",
            "room_type",
            "semantic_type",
            "surrounding_wall_ids",
            "door_ids",
            "printed_width_mm",
            "printed_length_mm",
            "dimension_status",
            "area_type",
            "open_plan_group",
            "open_plan_with",
            "warnings",
            "confidence",
        ],
    }
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "floor_id": {"type": "string"},
            "rooms": {"type": "array", "items": room},
            "warnings": string_array,
        },
        "required": ["floor_id", "rooms", "warnings"],
    }


__all__ = [
    "AreaType",
    "DimensionStatus",
    "FloorRoomInterpretation",
    "RoomInterpretation",
    "SemanticType",
    "floor_room_response_schema",
]
