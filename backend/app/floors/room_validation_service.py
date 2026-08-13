from __future__ import annotations

from typing import Any

from app.core.config import settings


class RoomValidationService:
    def validate(
        self,
        *,
        scale_verified: bool,
        valid_geometry: bool,
        label: str | None,
        difference_percent: float | None,
        boundary_source: str,
        space_kind: str,
        model_verified: bool,
        shape_type: str | None = None,
        point_count: int | None = None,
        wall_aligned: bool | None = None,
    ) -> dict[str, Any]:
        issues: list[str] = []
        blocking: list[str] = []
        if not scale_verified:
            return {"status": "missing_scale", "issues": ["Verify the drawing scale."]}
        if not valid_geometry:
            return {"status": "invalid", "issues": ["Repair the room boundary."]}
        if not label:
            blocking.append("Room name is missing.")
        if difference_percent is not None and difference_percent > settings.room_dimension_warning_percent:
            issues.append("Drawing dimensions do not match the polygon.")
        if boundary_source in {"model_only", "roboflow", "unknown"}:
            blocking.append("Detected by the room model; boundary correction is still required.")
        if wall_aligned is False:
            blocking.append("Boundary is not aligned to the detected inner wall faces.")
        normalized_shape = str(shape_type or "").lower()
        count = int(point_count or 0)
        if normalized_shape in {"rectangle", "trapezium"} and count > 6:
            issues.append("A simple room has too many boundary points.")
        elif normalized_shape == "irregular" and count > 12:
            issues.append("Boundary contains unnecessary short or collinear edges.")
        if space_kind in {"circulation", "void"}:
            issues.append("This is not a normal floor-finish room.")
        if not model_verified and boundary_source not in {
            "user", "wall_cell", "wall_only", "wall_geometry", "model_seed_wall_region",
            "model_seed_wall_faces", "wall_corrected", "label_seed_wall_cell",
        }:
            blocking.append("Only one detection source found this room.")
        issues.extend(blocking)
        # Printed dimensions and polygon complexity are review warnings. They
        # must not invalidate scale-based area from a valid wall boundary,
        # because OCR can associate a nearby dimension with the wrong room.
        return {"status": "check" if blocking else "correct", "issues": issues}


room_validation_service = RoomValidationService()
