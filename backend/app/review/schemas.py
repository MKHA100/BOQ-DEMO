from __future__ import annotations

from typing import Any, Literal
from pydantic import BaseModel, Field


class ReviewFieldUpdate(BaseModel):
    field: str = Field(min_length=1, max_length=80)
    value: Any


class ConfirmRequest(BaseModel):
    item_ids: list[str] = Field(default_factory=list, max_length=1000)
    scope: Literal["selected", "floor", "project"] = "selected"
    floor_id: str | None = None
