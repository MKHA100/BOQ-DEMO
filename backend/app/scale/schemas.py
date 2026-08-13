from __future__ import annotations

from typing import Literal
from pydantic import BaseModel, Field, model_validator


ScaleUnit = Literal["mm", "cm", "m", "ft_in"]


def _validate_distance(
    unit: ScaleUnit,
    metric_value: float | None,
    feet: int | None,
    inches: float | None,
) -> None:
    if unit == "ft_in":
        if float(feet or 0) * 12 + float(inches or 0) <= 0:
            raise ValueError("Enter a feet and inches distance greater than zero.")
    elif metric_value is None or metric_value <= 0:
        raise ValueError("Enter a distance greater than zero.")


class Point(BaseModel):
    x: float = Field(ge=0)
    y: float = Field(ge=0)


class VerificationInput(BaseModel):
    point_a: Point
    point_b: Point
    expected_distance: float | None = Field(default=None, gt=0)
    unit: ScaleUnit
    feet: int | None = Field(default=None, ge=0)
    inches: float | None = Field(default=None, ge=0, lt=12)

    @model_validator(mode="after")
    def validate_distance(self):
        _validate_distance(self.unit, self.expected_distance, self.feet, self.inches)
        return self


class CalibrationSaveRequest(BaseModel):
    point_a: Point
    point_b: Point
    real_distance: float | None = Field(default=None, gt=0)
    unit: ScaleUnit
    feet: int | None = Field(default=None, ge=0)
    inches: float | None = Field(default=None, ge=0, lt=12)
    crop_version: int = Field(ge=1)
    verification: VerificationInput | None = None

    @model_validator(mode="after")
    def validate_points(self):
        _validate_distance(self.unit, self.real_distance, self.feet, self.inches)
        distance = ((self.point_b.x - self.point_a.x) ** 2 + (self.point_b.y - self.point_a.y) ** 2) ** 0.5
        if distance < 5:
            raise ValueError("Select two points further apart.")
        if self.verification:
            verification_distance = (
                (self.verification.point_b.x - self.verification.point_a.x) ** 2
                + (self.verification.point_b.y - self.verification.point_a.y) ** 2
            ) ** 0.5
            if verification_distance < 5:
                raise ValueError("Verification points are too close together.")
        return self


class CopyCalibrationRequest(BaseModel):
    source_floor_id: str
    confirm: bool = False
