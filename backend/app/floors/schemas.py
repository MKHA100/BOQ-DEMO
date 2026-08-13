from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class Point(BaseModel):
    x: float
    y: float


class RoomCreateRequest(BaseModel):
    points: list[Point] = Field(min_length=3, max_length=1000)
    name: str | None = Field(default=None, max_length=160)
    room_type: str | None = Field(default=None, max_length=120)
    floor_type_code: str | None = Field(default=None, max_length=120)
    floor_finish: str | None = Field(default=None, max_length=200)
    space_kind: Literal["internal", "external", "circulation", "void"] | None = None
    include_in_boq: bool = True
    open_plan: bool = False


class RoomUpdateRequest(BaseModel):
    points: list[Point] | None = Field(default=None, min_length=3, max_length=1000)
    name: str | None = Field(default=None, max_length=160)
    room_type: str | None = Field(default=None, max_length=120)
    floor_type_code: str | None = Field(default=None, max_length=120)
    floor_finish: str | None = Field(default=None, max_length=200)
    review_status: Literal["ready", "needs_review", "confirmed"] | None = None
    manual_area_override_m2: float | None = Field(default=None, gt=0)
    space_kind: Literal["internal", "external", "circulation", "void"] | None = None
    include_in_boq: bool | None = None
    open_plan: bool | None = None


class RoomSplitRequest(BaseModel):
    axis: Literal["horizontal", "vertical"] = "vertical"
    ratio: float = Field(default=0.5, gt=0.1, lt=0.9)


class RoomSplitLineRequest(BaseModel):
    points: list[Point] = Field(min_length=2, max_length=100)


class FinishZoneCreateRequest(BaseModel):
    points: list[Point] = Field(min_length=3, max_length=1000)
    name: str | None = Field(default=None, max_length=160)
    floor_type_code: str | None = Field(default=None, max_length=120)
    floor_finish: str | None = Field(default=None, max_length=200)


class RoomMergeRequest(BaseModel):
    other_room_id: str


class RoomExcludeRequest(BaseModel):
    reason: str | None = Field(default=None, max_length=300)


class RoomSuggestionAcceptRequest(BaseModel):
    name: str | None = Field(default=None, max_length=160)
    room_type: str | None = Field(default=None, max_length=120)
    floor_type_code: str | None = Field(default=None, max_length=120)
    floor_finish: str | None = Field(default=None, max_length=200)


class RoomGeometryPatchRequest(BaseModel):
    action: Literal["replace", "add_point", "delete_point", "move_edge"] = "replace"
    points: list[Point] | None = Field(default=None, min_length=3, max_length=1000)
    point: Point | None = None
    point_index: int | None = Field(default=None, ge=0)
    edge_index: int | None = Field(default=None, ge=0)
    dx: float | None = None
    dy: float | None = None


class RoomCutoutCreateRequest(BaseModel):
    points: list[Point] = Field(min_length=3, max_length=1000)
    name: str | None = Field(default=None, max_length=120)


class RoomInterpretationStatusItem(BaseModel):
    room_id: str
    status: str
    warnings: list[str] = Field(default_factory=list)


class FloorInterpretationStatusResponse(BaseModel):
    project_id: str
    floor_id: str
    status: str
    run_id: str | None = None
    model: str | None = None
    prompt_version: str | None = None
    updated_at: str | None = None
    room_statuses: list[RoomInterpretationStatusItem] = Field(default_factory=list)
