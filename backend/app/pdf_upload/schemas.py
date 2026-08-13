from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

ReviewState = Literal["ready", "needs_review", "confirmed", "failed"]
PageClassification = Literal[
    "cover",
    "floor_plan",
    "door_window_schedule",
    "door_schedule",
    "window_schedule",
    "wall_schedule",
    "floor_schedule",
    "specification",
    "elevation",
    "section",
    "detail",
    "other",
]


class SourceLocation(BaseModel):
    page_number: int = Field(ge=1)
    line_number: int | None = Field(default=None, ge=1)
    text: str | None = Field(default=None, max_length=1000)
    bbox: list[float] | None = None

    @field_validator("bbox")
    @classmethod
    def validate_bbox(cls, value: list[float] | None) -> list[float] | None:
        if value is not None and len(value) != 4:
            raise ValueError("bbox must contain four coordinates")
        return value


class DoorExtraction(BaseModel):
    type_code: str | None = Field(default=None, max_length=80)
    width_mm: float | None = Field(default=None, gt=0)
    height_mm: float | None = Field(default=None, gt=0)
    material: str | None = Field(default=None, max_length=300)
    frame_material: str | None = Field(default=None, max_length=300)
    finish: str | None = Field(default=None, max_length=300)
    fire_rating: str | None = Field(default=None, max_length=120)
    quantity: int | None = Field(default=None, ge=0)
    source: SourceLocation


class WindowExtraction(BaseModel):
    type_code: str | None = Field(default=None, max_length=80)
    width_mm: float | None = Field(default=None, gt=0)
    height_mm: float | None = Field(default=None, gt=0)
    frame_material: str | None = Field(default=None, max_length=300)
    glass_type: str | None = Field(default=None, max_length=300)
    finish: str | None = Field(default=None, max_length=300)
    quantity: int | None = Field(default=None, ge=0)
    source: SourceLocation


class WallExtraction(BaseModel):
    wall_type: str | None = Field(default=None, max_length=100)
    nominal_thickness_mm: float | None = Field(default=None, gt=0)
    material: str | None = Field(default=None, max_length=300)
    internal_external_hint: Literal["internal", "external", "unknown"] = "unknown"
    cavity_information: str | None = Field(default=None, max_length=500)
    finish: str | None = Field(default=None, max_length=300)
    bond: str | None = Field(default=None, max_length=200)
    mortar: str | None = Field(default=None, max_length=200)
    source: SourceLocation


class FloorExtraction(BaseModel):
    room_label: str | None = Field(default=None, max_length=160)
    floor_type_code: str | None = Field(default=None, max_length=80)
    floor_finish: str | None = Field(default=None, max_length=300)
    material_note: str | None = Field(default=None, max_length=500)
    floor_schedule_reference: str | None = Field(default=None, max_length=200)
    source: SourceLocation


class PageManifestItem(BaseModel):
    page_number: int = Field(ge=1)
    page_label: str | None = Field(default=None, max_length=120)
    width_points: float = Field(gt=0)
    height_points: float = Field(gt=0)
    rotation: int = 0
    media_box: dict[str, Any] = Field(default_factory=dict)


class ExtractionRecordPayload(BaseModel):
    extraction_type: Literal["door", "window", "wall", "floor"]
    entity_key: str = Field(min_length=1, max_length=240)
    data: dict[str, Any]
    source_location: SourceLocation
    confidence: float | None = Field(default=None, ge=0, le=1)
    quality_signal: str | None = Field(default=None, max_length=120)
    review_state: ReviewState = "needs_review"
