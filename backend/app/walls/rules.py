from __future__ import annotations

from dataclasses import asdict, dataclass, replace
import math
from typing import Any

VOID_DEDUCTION_THRESHOLD_M2 = 0.50


@dataclass(frozen=True)
class WallTopologyRules:
    """Pixel-space tolerances for conservative wall network cleanup."""

    straighten_angle_degrees: float = 6.0
    parallel_angle_degrees: float = 4.0
    endpoint_snap_px: float = 7.0
    collinear_distance_px: float = 4.0
    merge_gap_px: float = 10.0
    intersection_extension_px: float = 9.0
    intersection_tolerance_px: float = 1.5
    duplicate_distance_px: float = 3.0
    duplicate_overlap_ratio: float = 0.88
    minimum_wall_length_px: float = 5.0
    opening_protection_padding_px: float = 3.0
    opening_attachment_px: float = 14.0
    drawing_margin_px: float = 8.0
    block_on_unconnected: bool = False

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def topology_rules(
    *,
    drawing_width: float | None = None,
    drawing_height: float | None = None,
    typical_thickness_px: float | None = None,
    overrides: WallTopologyRules | dict[str, Any] | None = None,
) -> WallTopologyRules:
    """Build bounded, drawing-relative rules instead of fixed magic pixels."""
    if isinstance(overrides, WallTopologyRules):
        return overrides

    width = max(float(drawing_width or 0), 0.0)
    height = max(float(drawing_height or 0), 0.0)
    diagonal = math.hypot(width, height)
    thickness = max(float(typical_thickness_px or 0), 0.0)
    reference = thickness if thickness > 0 else (diagonal * 0.006 if diagonal > 0 else 7.0)
    reference = max(2.0, min(14.0, reference))
    snap = max(3.0, min(14.0, reference * 0.8))
    rules = WallTopologyRules(
        endpoint_snap_px=snap,
        collinear_distance_px=max(2.0, min(8.0, reference * 0.5)),
        merge_gap_px=max(5.0, min(22.0, reference * 1.4)),
        intersection_extension_px=max(5.0, min(20.0, reference * 1.25)),
        intersection_tolerance_px=max(1.0, min(3.0, reference * 0.2)),
        duplicate_distance_px=max(1.5, min(6.0, reference * 0.4)),
        minimum_wall_length_px=max(3.0, min(12.0, reference * 0.65)),
        opening_protection_padding_px=max(2.0, min(7.0, reference * 0.4)),
        opening_attachment_px=max(8.0, min(30.0, reference * 2.0)),
        drawing_margin_px=max(4.0, min(20.0, reference)),
    )
    if not overrides:
        return rules
    allowed = {field for field in WallTopologyRules.__dataclass_fields__}
    normalized = {key: value for key, value in overrides.items() if key in allowed}
    return replace(rules, **normalized)


def gross_area(length_mm: float | None, height_mm: float | None) -> float | None:
    if not length_mm or not height_mm or length_mm <= 0 or height_mm <= 0:
        return None
    return round(length_mm / 1000 * height_mm / 1000, 4)


def opening_area(width_mm: float | None, height_mm: float | None) -> float | None:
    if not width_mm or not height_mm or width_mm <= 0 or height_mm <= 0:
        return None
    return round(width_mm / 1000 * height_mm / 1000, 4)


def deduction(area_m2: float | None) -> float:
    return round(area_m2 or 0, 4) if area_m2 is not None and area_m2 > VOID_DEDUCTION_THRESHOLD_M2 else 0.0
