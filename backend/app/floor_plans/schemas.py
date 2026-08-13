from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator


class ProjectFloorSettingsUpdate(BaseModel):
    default_wall_height_mm: float = Field(gt=0, le=30000)
    measurement_unit: Literal["mm", "cm", "m", "in", "ft"] = "mm"


class FloorUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    uses_default_height: bool | None = None
    wall_height_mm: float | None = Field(default=None, gt=0, le=30000)

    @model_validator(mode="after")
    def validate_height(self) -> "FloorUpdateRequest":
        if self.uses_default_height is False and self.wall_height_mm is None:
            raise ValueError("A floor wall height is required.")
        return self


class CropRect(BaseModel):
    x: float = Field(ge=0)
    y: float = Field(ge=0)
    width: float = Field(gt=0)
    height: float = Field(gt=0)


class NormalizedCropRect(BaseModel):
    x: float = Field(ge=0, le=1)
    y: float = Field(ge=0, le=1)
    width: float = Field(gt=0, le=1)
    height: float = Field(gt=0, le=1)

    @model_validator(mode="after")
    def inside_page(self) -> "NormalizedCropRect":
        if self.x + self.width > 1.000001 or self.y + self.height > 1.000001:
            raise ValueError("The crop must stay inside the source page.")
        return self


class FloorCropUpsertRequest(BaseModel):
    document_id: str
    document_page_id: str
    source_page_number: int = Field(ge=1)
    original_page_width: float = Field(gt=0)
    original_page_height: float = Field(gt=0)
    rotation: Literal[0, 90, 180, 270] = 0
    render_dpi: int = Field(default=144, ge=72, le=600)
    original_rect: CropRect
    normalized_display_rect: NormalizedCropRect

    @model_validator(mode="after")
    def rect_inside_source(self) -> "FloorCropUpsertRequest":
        rect = self.original_rect
        if rect.x + rect.width > self.original_page_width + 0.01:
            raise ValueError("The crop exceeds the source page width.")
        if rect.y + rect.height > self.original_page_height + 0.01:
            raise ValueError("The crop exceeds the source page height.")
        return self


class FloorPlanJob(BaseModel):
    id: str
    floor_id: str | None = None
    task_type: str
    status: str
    progress: int = 0


class FloorPlanPage(BaseModel):
    id: str
    document_id: str
    page_number: int
    page_label: str | None = None
    width: float | None = None
    height: float | None = None
    rotation: int = 0
    thumbnail_status: str = "not_ready"
    preview_status: str = "not_ready"
    thumbnail_url: str | None = None
    preview_url: str | None = None


class FloorPlanDocument(BaseModel):
    id: str
    project_id: str
    document_type: str
    file_name: str
    mime_type: str
    page_count: int | None = None
    status: str
    is_primary: bool = False
    pages: list[FloorPlanPage] = Field(default_factory=list)


class FloorCropRecord(BaseModel):
    id: str
    project_id: str
    floor_id: str
    document_id: str
    document_page_id: str
    source_page_number: int
    original_page_width: float
    original_page_height: float
    rotation: int
    render_dpi: int
    coordinates: dict[str, Any]
    crop_version: int
    status: str
    crop_asset_url: str | None = None
    preview_asset_url: str | None = None
    created_at: str
    updated_at: str


class FloorPlanFloor(BaseModel):
    id: str
    project_id: str
    name: str
    level_index: int
    status: str
    uses_default_height: bool
    wall_height_mm: float | None = None
    effective_wall_height_mm: float
    is_custom_name: bool
    source_document_id: str | None = None
    source_page_number: int | None = None
    source_rotation: int = 0
    crop_version: int = 0
    crop: FloorCropRecord | None = None
    last_error: str | None = None
    active_jobs: list[FloorPlanJob] = Field(default_factory=list)
    created_at: str
    updated_at: str


class FloorPlansState(BaseModel):
    project_id: str
    project_name: str
    default_wall_height_mm: float
    measurement_unit: str
    floors: list[FloorPlanFloor]
    documents: list[FloorPlanDocument]
    can_continue: bool
    updated_at: str


class FloorSourceUploadResult(BaseModel):
    document: FloorPlanDocument
    reused: bool = False
    duplicate: bool = False
    jobs: list[dict[str, Any]] = Field(default_factory=list)
