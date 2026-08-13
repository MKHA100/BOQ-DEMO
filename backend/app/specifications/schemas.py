from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Category = Literal[
    "door_schedule",
    "window_schedule",
    "wall_schedule",
    "floor_schedule",
    "specification",
    "other",
]
ScopeMode = Literal["all", "selected"]
SourceType = Literal["file", "crop"]
DisplayStatus = Literal["ready", "processing", "needs_review", "failed", "skipped"]


class StrictSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ScopeRequest(BaseModel):
    scope_mode: ScopeMode = "all"
    floor_ids: list[str] = Field(default_factory=list, max_length=100)

    @model_validator(mode="after")
    def validate_scope(self) -> "ScopeRequest":
        unique = list(dict.fromkeys(self.floor_ids))
        self.floor_ids = unique
        if self.scope_mode == "selected" and not unique:
            raise ValueError("Select at least one floor.")
        if self.scope_mode == "all":
            self.floor_ids = []
        return self


class CropRect(BaseModel):
    x: float = Field(ge=0)
    y: float = Field(ge=0)
    width: float = Field(gt=0)
    height: float = Field(gt=0)


class CropSourceRequest(ScopeRequest):
    category: Category
    document_id: str
    document_page_id: str
    page_number: int = Field(ge=1)
    original_page_width: float = Field(gt=0)
    original_page_height: float = Field(gt=0)
    crop: CropRect

    @model_validator(mode="after")
    def crop_inside_page(self) -> "CropSourceRequest":
        if self.crop.x + self.crop.width > self.original_page_width + 0.01:
            raise ValueError("The crop exceeds the source page width.")
        if self.crop.y + self.crop.height > self.original_page_height + 0.01:
            raise ValueError("The crop exceeds the source page height.")
        return self


class SourceScopeUpdate(ScopeRequest):
    pass


class CategorySkipRequest(BaseModel):
    skipped: bool = True


class SourceJob(BaseModel):
    id: str
    task_type: str
    status: str
    progress: int = 0


class FloorOption(BaseModel):
    id: str
    name: str
    level_index: int


class PageOption(BaseModel):
    id: str
    document_id: str
    page_number: int
    page_label: str | None = None
    width: float | None = None
    height: float | None = None
    thumbnail_url: str | None = None
    preview_url: str | None = None


class DocumentOption(BaseModel):
    id: str
    file_name: str
    page_count: int | None = None
    is_primary: bool = False
    pages: list[PageOption] = Field(default_factory=list)


class ExtractedEntry(BaseModel):
    id: str
    category: Category
    entity_key: str
    data: dict[str, Any]
    confidence: float | None = None
    review_state: str
    is_accepted: bool


class SupportingSource(BaseModel):
    id: str
    category: Category
    source_type: SourceType
    document_id: str
    file_name: str | None = None
    mime_type: str | None = None
    file_size: int = 0
    page_number: int | None = None
    crop: dict[str, Any] | None = None
    scope_mode: ScopeMode
    floor_ids: list[str] = Field(default_factory=list)
    status: DisplayStatus
    preview_url: str | None = None
    active_job: SourceJob | None = None
    entry_count: int = 0
    entries: list[ExtractedEntry] = Field(default_factory=list)
    created_at: str
    updated_at: str


class CategoryState(BaseModel):
    key: Category
    label: str
    description: str
    status: DisplayStatus
    sources: list[SupportingSource] = Field(default_factory=list)
    entry_count: int = 0


class SpecificationsState(BaseModel):
    project_id: str
    project_name: str
    categories: list[CategoryState]
    floors: list[FloorOption]
    documents: list[DocumentOption]
    can_continue: bool = True
    updated_at: str


class SourceMutationResult(BaseModel):
    source: SupportingSource
    state: SpecificationsState | None = None


class DoorScheduleRow(StrictSchema):
    confidence: float | None = Field(default=None, ge=0, le=1)
    type_code: str | None = Field(default=None, max_length=80)
    width_mm: float | None = Field(default=None, gt=0)
    height_mm: float | None = Field(default=None, gt=0)
    material: str | None = Field(default=None, max_length=300)
    frame_material: str | None = Field(default=None, max_length=300)
    finish: str | None = Field(default=None, max_length=300)
    fire_rating: str | None = Field(default=None, max_length=120)
    quantity: int | None = Field(default=None, ge=0)
    source_page: int | None = Field(default=None, ge=1)
    source_text: str | None = Field(default=None, max_length=1200)


class WindowScheduleRow(StrictSchema):
    confidence: float | None = Field(default=None, ge=0, le=1)
    type_code: str | None = Field(default=None, max_length=80)
    width_mm: float | None = Field(default=None, gt=0)
    height_mm: float | None = Field(default=None, gt=0)
    frame_material: str | None = Field(default=None, max_length=300)
    glass_type: str | None = Field(default=None, max_length=300)
    finish: str | None = Field(default=None, max_length=300)
    quantity: int | None = Field(default=None, ge=0)
    source_page: int | None = Field(default=None, ge=1)
    source_text: str | None = Field(default=None, max_length=1200)


class WallScheduleRow(StrictSchema):
    confidence: float | None = Field(default=None, ge=0, le=1)
    type_code: str | None = Field(default=None, max_length=100)
    nominal_thickness_mm: float | None = Field(default=None, gt=0)
    material: str | None = Field(default=None, max_length=300)
    use: Literal["internal", "external", "both", "unknown"] = "unknown"
    cavity_information: str | None = Field(default=None, max_length=500)
    finish: str | None = Field(default=None, max_length=300)
    bond: str | None = Field(default=None, max_length=200)
    mortar: str | None = Field(default=None, max_length=200)
    source_page: int | None = Field(default=None, ge=1)
    source_text: str | None = Field(default=None, max_length=1200)


class FloorScheduleRow(StrictSchema):
    confidence: float | None = Field(default=None, ge=0, le=1)
    floor_type_code: str | None = Field(default=None, max_length=80)
    finish: str | None = Field(default=None, max_length=300)
    material: str | None = Field(default=None, max_length=300)
    room_or_zone: str | None = Field(default=None, max_length=200)
    tile_size: str | None = Field(default=None, max_length=120)
    screed: str | None = Field(default=None, max_length=200)
    skirting: str | None = Field(default=None, max_length=200)
    source_page: int | None = Field(default=None, ge=1)
    source_text: str | None = Field(default=None, max_length=1200)


class SpecificationRow(StrictSchema):
    confidence: float | None = Field(default=None, ge=0, le=1)
    section: str = Field(min_length=1, max_length=120)
    brick_block_type: str | None = Field(default=None, max_length=300)
    mortar: str | None = Field(default=None, max_length=300)
    wall_finishes: str | None = Field(default=None, max_length=500)
    floor_finishes: str | None = Field(default=None, max_length=500)
    door_window_materials: str | None = Field(default=None, max_length=500)
    glazing: str | None = Field(default=None, max_length=500)
    paint_joinery: str | None = Field(default=None, max_length=500)
    note: str | None = Field(default=None, max_length=1200)
    source_page: int | None = Field(default=None, ge=1)
    source_text: str | None = Field(default=None, max_length=1200)


class OtherSupportingRow(StrictSchema):
    confidence: float | None = Field(default=None, ge=0, le=1)
    title: str = Field(min_length=1, max_length=200)
    note: str | None = Field(default=None, max_length=1200)
    source_page: int | None = Field(default=None, ge=1)
    source_text: str | None = Field(default=None, max_length=1200)


class DoorScheduleExtraction(StrictSchema):
    rows: list[DoorScheduleRow] = Field(default_factory=list, max_length=5000)


class WindowScheduleExtraction(StrictSchema):
    rows: list[WindowScheduleRow] = Field(default_factory=list, max_length=5000)


class WallScheduleExtraction(StrictSchema):
    rows: list[WallScheduleRow] = Field(default_factory=list, max_length=5000)


class FloorScheduleExtraction(StrictSchema):
    rows: list[FloorScheduleRow] = Field(default_factory=list, max_length=5000)


class SpecificationExtraction(StrictSchema):
    rows: list[SpecificationRow] = Field(default_factory=list, max_length=5000)


class OtherSupportingExtraction(StrictSchema):
    rows: list[OtherSupportingRow] = Field(default_factory=list, max_length=5000)


def extraction_model(category: str) -> type[StrictSchema]:
    models: dict[str, type[StrictSchema]] = {
        "door_schedule": DoorScheduleExtraction,
        "window_schedule": WindowScheduleExtraction,
        "wall_schedule": WallScheduleExtraction,
        "floor_schedule": FloorScheduleExtraction,
        "specification": SpecificationExtraction,
        "other": OtherSupportingExtraction,
    }
    return models[category]


class ExtractionPayload(BaseModel):
    category: Category
    rows: list[dict[str, Any]] = Field(default_factory=list, max_length=5000)

    @field_validator("rows")
    @classmethod
    def validate_rows(cls, rows: list[dict[str, Any]], info):
        category = info.data.get("category")
        model = {
            "door_schedule": DoorScheduleRow,
            "window_schedule": WindowScheduleRow,
            "wall_schedule": WallScheduleRow,
            "floor_schedule": FloorScheduleRow,
            "specification": SpecificationRow,
            "other": OtherSupportingRow,
        }.get(category)
        if not model:
            return rows
        return [model.model_validate(row).model_dump(mode="json") for row in rows]
