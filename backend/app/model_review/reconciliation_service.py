from __future__ import annotations

import math
from typing import Any


def _bounds(geometry: dict[str, Any]) -> tuple[float, float, float, float]:
    x = float(geometry.get("x") or 0.0)
    y = float(geometry.get("y") or 0.0)
    w = max(float(geometry.get("width") or 0.0), 0.0)
    h = max(float(geometry.get("height") or 0.0), 0.0)
    return x, y, x + w, y + h


def intersection_over_union(first: dict[str, Any], second: dict[str, Any]) -> float:
    ax1, ay1, ax2, ay2 = _bounds(first)
    bx1, by1, bx2, by2 = _bounds(second)
    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    intersection = max(0.0, ix2 - ix1) * max(0.0, iy2 - iy1)
    union = max(0.0, ax2 - ax1) * max(0.0, ay2 - ay1) + max(0.0, bx2 - bx1) * max(0.0, by2 - by1) - intersection
    return intersection / union if union > 0 else 0.0


def normalized_center_distance(first: dict[str, Any], second: dict[str, Any]) -> float:
    ax1, ay1, ax2, ay2 = _bounds(first)
    bx1, by1, bx2, by2 = _bounds(second)
    acx, acy = (ax1 + ax2) / 2.0, (ay1 + ay2) / 2.0
    bcx, bcy = (bx1 + bx2) / 2.0, (by1 + by2) / 2.0
    scale = max(math.hypot(ax2 - ax1, ay2 - ay1), math.hypot(bx2 - bx1, by2 - by1), 1.0)
    return math.hypot(acx - bcx, acy - bcy) / scale


def match_score(existing: dict[str, Any], candidate_geometry: dict[str, Any]) -> float:
    geometry = existing.get("geometry") or existing.get("geometry_json") or {}
    if not isinstance(geometry, dict):
        geometry = {}
    iou = intersection_over_union(geometry, candidate_geometry)
    distance = normalized_center_distance(geometry, candidate_geometry)
    return iou * 0.8 + max(0.0, 1.0 - distance) * 0.2


def choose_confirmed_match(
    candidates: list[dict[str, Any]],
    *,
    element_type: str,
    geometry: dict[str, Any],
    used_ids: set[str],
    minimum_score: float = 0.42,
) -> dict[str, Any] | None:
    best: dict[str, Any] | None = None
    best_score = minimum_score
    for candidate in candidates:
        if str(candidate.get("id")) in used_ids:
            continue
        if candidate.get("element_type") != element_type:
            continue
        if not candidate.get("user_confirmed"):
            continue
        score = match_score(candidate, geometry)
        if score > best_score:
            best = candidate
            best_score = score
    return best
