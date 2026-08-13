from __future__ import annotations

from typing import Literal
from pydantic import BaseModel, Field, model_validator


class Point(BaseModel):
    x: float
    y: float


class Centerline(BaseModel):
    start: Point
    end: Point

    @model_validator(mode="after")
    def non_zero(self):
        if ((self.end.x-self.start.x)**2+(self.end.y-self.start.y)**2)**0.5 < 2:
            raise ValueError("Wall centerline is too short.")
        return self


class WallUpdateRequest(BaseModel):
    centerline: Centerline | None = None
    classification: Literal["internal","external"] | None = None
    wall_type: str | None = Field(default=None,max_length=120)
    thickness_mm: float | None = Field(default=None,gt=0)
    height_override_mm: float | None = Field(default=None,gt=0)
    use_floor_height: bool | None = None
    side_1_finish: str | None = Field(default=None,max_length=160)
    side_2_finish: str | None = Field(default=None,max_length=160)
    review_status: Literal["ready","needs_review","confirmed"] | None = None


class WallCreateRequest(BaseModel):
    centerline: Centerline
    classification: Literal["internal", "external"] = "internal"
    wall_type: str | None = Field(default=None, max_length=120)
    thickness_mm: float | None = Field(default=None, gt=0)
    height_mm: float | None = Field(default=None, gt=0)


class OpeningAssignRequest(BaseModel):
    element_id: str


class WallSplitRequest(BaseModel):
    point: Point | None = None
    ratio: float = Field(default=0.5,gt=0.05,lt=0.95)


class WallMergeRequest(BaseModel):
    other_wall_id: str
