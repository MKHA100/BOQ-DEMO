from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.core.config import settings


@dataclass(frozen=True)
class ProcessedPrediction:
    element_type: str
    geometry: dict[str, float]
    confidence: float
    status: str
    raw: dict[str, Any]


def normalize_class_name(value: Any) -> str:
    text = str(value or "").strip().lower().replace("_", " ").replace("-", " ")
    if "door" in text:
        return "door"
    if "window" in text or text in {"glazing", "opening window"}:
        return "window"
    if "wall" in text:
        return "wall"
    return text.replace(" ", "_")


def threshold_for(element_type: str) -> float:
    return {
        "door": settings.roboflow_door_confidence,
        "window": settings.roboflow_window_confidence,
        "wall": settings.roboflow_wall_confidence,
    }.get(element_type, 1.0)


def automatic_status(
    element_type: str,
    confidence: float,
    geometry: dict[str, float],
) -> str:
    """Return review only for genuinely uncertain model geometry.

    Missing schedule/type details are handled by enrichment and must not make
    a correctly classified door, window or wall require box-by-box approval.
    """
    accepted_confidence = {"door": 0.55, "window": 0.55, "wall": 0.52}.get(
        element_type, 1.0
    )
    if confidence < accepted_confidence:
        return "needs_review"
    if element_type == "wall":
        major = max(float(geometry.get("width") or 0), float(geometry.get("height") or 0))
        minor = min(float(geometry.get("width") or 0), float(geometry.get("height") or 0))
        if major < 8 or minor <= 0 or major / max(minor, 1e-6) < 1.8:
            return "needs_review"
    return "confirmed"


def process_predictions(
    raw: dict[str, Any],
    *,
    image_width: int,
    image_height: int,
    crop_width: float,
    crop_height: float,
    threshold_overrides: dict[str, float] | None = None,
) -> dict[str, list[ProcessedPrediction]]:
    """Split one multi-class model response into validated local element groups."""
    groups: dict[str, list[ProcessedPrediction]] = {"door": [], "window": [], "wall": []}
    predictions = raw.get("predictions") if isinstance(raw, dict) else []
    if not isinstance(predictions, list):
        return groups

    for prediction in predictions:
        if not isinstance(prediction, dict):
            continue
        element_type = normalize_class_name(prediction.get("class") or prediction.get("class_name"))
        if element_type not in groups:
            continue
        confidence = float(prediction.get("confidence") or 0.0)
        threshold = (threshold_overrides or {}).get(
            element_type, threshold_for(element_type)
        )
        if confidence < threshold:
            continue
        width = float(prediction.get("width") or 0.0) / max(image_width, 1) * crop_width
        height = float(prediction.get("height") or 0.0) / max(image_height, 1) * crop_height
        center_x = float(prediction.get("x") or 0.0) / max(image_width, 1) * crop_width
        center_y = float(prediction.get("y") or 0.0) / max(image_height, 1) * crop_height
        if width <= 0.5 or height <= 0.5:
            continue
        geometry = {
            "x": max(0.0, center_x - width / 2.0),
            "y": max(0.0, center_y - height / 2.0),
            "width": width,
            "height": height,
            "rotation": float(prediction.get("rotation") or 0.0),
        }
        if element_type == "wall":
            major = max(width, height)
            minor = min(width, height)
            # Compact boxes are commonly ducts, columns, furniture or symbols,
            # not linear wall segments.
            if major / max(minor, 1e-6) < 1.8:
                continue
        groups[element_type].append(
            ProcessedPrediction(
                element_type=element_type,
                geometry=geometry,
                confidence=confidence,
                status=automatic_status(element_type, confidence, geometry),
                raw=prediction,
            )
        )
    return groups
