from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

WorkflowStatus = Literal["ready", "processing", "needs_review", "confirmed", "failed", "not_ready"]
ValueSource = Literal["user_confirmed", "schedule", "specification", "drawing_note", "model", "calculated", "default"]


class Point(BaseModel):
    x: float
    y: float


class FloorCreateRequest(BaseModel):
    name: str | None = Field(default=None, max_length=80)
    level_index: int | None = Field(default=None, ge=0)


class FloorResponse(BaseModel):
    id: str
    project_id: str
    name: str
    level_index: int
    status: WorkflowStatus
    created_at: str
    updated_at: str
    versions: dict[str, int] = Field(default_factory=dict)


class ElementCreateRequest(BaseModel):
    floor_id: str
    element_type: str = Field(min_length=1, max_length=40)
    type_code: str | None = Field(default=None, max_length=80)
    geometry: dict[str, Any] = Field(default_factory=dict)
    source: ValueSource = "model"
    confidence: float | None = Field(default=None, ge=0, le=1)
    status: WorkflowStatus = "needs_review"


class ElementPropertyUpdateRequest(BaseModel):
    value: Any
    unit: str | None = Field(default=None, max_length=20)
    source: ValueSource
    confirm: bool = False


class WallCreateRequest(BaseModel):
    floor_id: str
    geometry: dict[str, Any] = Field(default_factory=dict)
    wall_type: str | None = Field(default=None, max_length=80)
    classification: str | None = Field(default=None, max_length=40)
    thickness_mm: float | None = Field(default=None, gt=0)
    height_mm: float | None = Field(default=None, gt=0)
    gross_area_m2: float | None = Field(default=None, ge=0)
    status: WorkflowStatus = "needs_review"


class ElementRelationCreateRequest(BaseModel):
    floor_id: str
    source_element_id: str
    target_type: str = Field(min_length=1, max_length=40)
    target_id: str
    relation_type: str = Field(min_length=1, max_length=40)


class CalibrationUpsertRequest(BaseModel):
    point_a: Point
    point_b: Point
    real_distance: float = Field(gt=0)
    unit: Literal["mm", "cm", "m", "in", "ft"]
    source_crop_version: int = Field(ge=1)

    @model_validator(mode="after")
    def validate_distinct_points(self) -> "CalibrationUpsertRequest":
        if self.point_a.x == self.point_b.x and self.point_a.y == self.point_b.y:
            raise ValueError("Calibration points must be different.")
        return self


class RoomCreateRequest(BaseModel):
    floor_id: str
    name: str | None = Field(default=None, max_length=120)
    geometry: dict[str, Any] = Field(default_factory=dict)
    finish_code: str | None = Field(default=None, max_length=80)
    status: WorkflowStatus = "needs_review"


class RoomGeometryUpdateRequest(BaseModel):
    geometry: dict[str, Any]
    confirm: bool = False


class DocumentResponse(BaseModel):
    id: str
    project_id: str
    document_type: str
    file_name: str
    original_file_name: str | None = None
    mime_type: str
    storage_key: str
    content_hash: str | None = None
    size_bytes: int
    page_count: int | None = None
    status: WorkflowStatus
    validation_status: str = "ready"
    validation: dict[str, Any] = Field(default_factory=dict)
    manifest_status: str = "not_ready"
    ingestion_status: str = "not_ready"
    manifest_version: int = 0
    is_primary: bool = False
    version: int
    created_at: str
    updated_at: str


class DocumentUploadResult(BaseModel):
    document: DocumentResponse
    reused: bool = False
    duplicate: bool = False
    jobs: list[dict[str, Any]] = Field(default_factory=list)
    next_step: Literal["floor-plans"] = "floor-plans"


class FloorCropSaveRequest(BaseModel):
    floor_id: str
    document_id: str
    document_page_id: str
    coordinates: dict[str, Any]
    source_width: float | None = Field(default=None, gt=0)
    source_height: float | None = Field(default=None, gt=0)
    crop_asset_key: str | None = None


class ScheduleFileCreateRequest(BaseModel):
    document_id: str
    floor_id: str | None = None
    schedule_type: Literal["door", "window", "wall", "floor", "other"]
    source_crop: dict[str, Any] | None = None


class SpecificationFileCreateRequest(BaseModel):
    document_id: str
    floor_id: str | None = None
    specification_type: str = Field(default="general", min_length=1, max_length=80)
    source_crop: dict[str, Any] | None = None


class MutationResult(BaseModel):
    record: dict[str, Any]
    protected: bool = False
    changed: bool = True
    versions: dict[str, int] = Field(default_factory=dict)
    jobs: list[dict[str, Any]] = Field(default_factory=list)


class ProjectWorkflowSummary(BaseModel):
    project: dict[str, Any]
    project_versions: dict[str, int]
    floors: list[dict[str, Any]]
    counts: dict[str, int]
    steps: list[dict[str, Any]]
    active_jobs: list[dict[str, Any]]
    updated_at: str
