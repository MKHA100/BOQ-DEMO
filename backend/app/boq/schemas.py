from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class BoqViewRequest(BaseModel):
    grouping_mode: Literal["item", "floor"] = "item"
    floor_id: str | None = None


class BoqRowUpdate(BaseModel):
    description: str | None = Field(default=None, max_length=2000)
    section: str | None = Field(default=None, max_length=160)
    item_code: str | None = Field(default=None, max_length=80)
    quantity: float | None = Field(default=None, ge=0)
    unit: str | None = Field(default=None, max_length=20)
    rate: float | None = Field(default=None, ge=0)
    status: Literal["ready", "needs_review"] | None = None
    excluded: bool | None = None
    sort_order: int | None = None


class ManualRowCreate(BaseModel):
    description: str = Field(min_length=1, max_length=2000)
    section: str | None = Field(default="Other items", max_length=160)
    item_code: str | None = Field(default=None, max_length=80)
    quantity: float = Field(gt=0)
    unit: str = Field(min_length=1, max_length=20)
    rate: float | None = Field(default=None, ge=0)
    floor_id: str | None = None


class ExportRequest(BaseModel):
    format: Literal["pdf", "xlsx", "csv"]
    floor_mode: Literal["combined", "floor_breakdown", "selected_floor"] = "combined"
    floor_id: str | None = None


class TemplateSelectRequest(BaseModel):
    template_id: str = Field(min_length=1)


class BoqDocumentSetupUpdate(BaseModel):
    project_name: str = Field(default="", max_length=200)
    client_name: str = Field(default="", max_length=200)
    consultant_name: str = Field(default="", max_length=200)
    location: str = Field(default="", max_length=240)
    boq_title: str = Field(default="Bill of Quantities", max_length=240)
    currency: str = Field(default="Rs", max_length=20)
    vat_percentage: float = Field(default=0, ge=0, le=100)
    include_rates: bool = False
    include_amounts: bool = False
    include_preliminaries: bool = True
    include_provisional_sums: bool = False
    include_signature_section: bool = True
    format_style: Literal["quantity_takeoff", "formal_tender", "lot_based", "standard_construction"] = "formal_tender"
    item_numbering_format: Literal["source_item_number", "section_sequence", "simple_sequence"] = "section_sequence"
    measurement_unit_style: Literal["metric", "imperial", "mixed"] = "metric"
    description_style: Literal["standard", "detailed", "short"] = "standard"
    section_order: list[str] = Field(default_factory=list)


class TemplatePackageCreate(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    description: str | None = Field(default=None, max_length=1000)
    category: str = Field(default="custom", max_length=60)


class TemplatePackageUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=160)
    description: str | None = Field(default=None, max_length=1000)
    category: str | None = Field(default=None, max_length=60)
    is_active: bool | None = None


class TemplateDuplicateRequest(BaseModel):
    name: str | None = Field(default=None, max_length=160)


class TemplateItemCreate(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    element_type: Literal["door", "window", "wall_external", "wall_internal", "floor", "manual"]
    section_code: str | None = Field(default=None, max_length=40)
    section_name: str = Field(min_length=1, max_length=160)
    unit: str = Field(min_length=1, max_length=20)
    description_template: str = Field(min_length=1, max_length=3000)
    keywords: list[str] = Field(default_factory=list)
    template_mode: Literal["standard", "conditional"] = "standard"
    conditional_rules: list[dict[str, Any]] | dict[str, Any] = Field(default_factory=list)
    formula: dict[str, Any] = Field(default_factory=dict)
    sort_order: int = 0
    is_active: bool = True


class TemplateItemUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=160)
    element_type: Literal["door", "window", "wall_external", "wall_internal", "floor", "manual"] | None = None
    section_code: str | None = Field(default=None, max_length=40)
    section_name: str | None = Field(default=None, min_length=1, max_length=160)
    unit: str | None = Field(default=None, min_length=1, max_length=20)
    description_template: str | None = Field(default=None, min_length=1, max_length=3000)
    keywords: list[str] | None = None
    template_mode: Literal["standard", "conditional"] | None = None
    conditional_rules: list[dict[str, Any]] | dict[str, Any] | None = None
    formula: dict[str, Any] | None = None
    sort_order: int | None = None
    is_active: bool | None = None


class TemplatePreviewRequest(BaseModel):
    values: dict[str, Any] = Field(default_factory=dict)
