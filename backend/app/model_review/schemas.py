from __future__ import annotations

from typing import Any, Literal
from pydantic import BaseModel, Field, model_validator


class ElementGeometry(BaseModel):
    x: float = Field(ge=0)
    y: float = Field(ge=0)
    width: float = Field(gt=0)
    height: float = Field(gt=0)
    rotation: float = 0


class ElementCreateRequest(BaseModel):
    element_type: Literal["door", "window", "wall"]
    geometry: ElementGeometry
    type_code: str | None = Field(default=None, max_length=80)


class ElementUpdateRequest(BaseModel):
    geometry: ElementGeometry | None = None
    type_code: str | None = Field(default=None, max_length=80)
    review_status: Literal["ready", "needs_review", "confirmed"] | None = None
    excluded: bool | None = None
    tag_text: str | None = Field(default=None, max_length=120)


class PropertyUpdateRequest(BaseModel):
    value: Any
    unit: str | None = Field(default=None, max_length=20)
    confirm: bool = True


class ScheduleAssignRequest(BaseModel):
    schedule_entry_id: str


class BulkConfirmRequest(BaseModel):
    element_ids: list[str] = Field(min_length=1, max_length=500)

    @model_validator(mode="after")
    def unique_ids(self):
        self.element_ids = list(dict.fromkeys(self.element_ids))
        return self


class DetectionAnalysisRequest(BaseModel):
    analysis_mode: Literal["standard", "deep"] = "standard"
