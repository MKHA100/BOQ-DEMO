from __future__ import annotations

from typing import Final

STATUS_READY: Final = "ready"
STATUS_PROCESSING: Final = "processing"
STATUS_NEEDS_REVIEW: Final = "needs_review"
STATUS_CONFIRMED: Final = "confirmed"
STATUS_FAILED: Final = "failed"
STATUS_NOT_READY: Final = "not_ready"

WORKFLOW_STATUSES: Final[set[str]] = {
    STATUS_READY,
    STATUS_PROCESSING,
    STATUS_NEEDS_REVIEW,
    STATUS_CONFIRMED,
    STATUS_FAILED,
    STATUS_NOT_READY,
}

SOURCE_USER_CONFIRMED: Final = "user_confirmed"
SOURCE_SCHEDULE: Final = "schedule"
SOURCE_SPECIFICATION: Final = "specification"
SOURCE_DRAWING_NOTE: Final = "drawing_note"
SOURCE_MODEL: Final = "model"
SOURCE_CALCULATED: Final = "calculated"
SOURCE_DEFAULT: Final = "default"

VALUE_SOURCE_PRIORITY: Final[dict[str, int]] = {
    SOURCE_DEFAULT: 100,
    SOURCE_MODEL: 200,
    SOURCE_CALCULATED: 200,
    SOURCE_DRAWING_NOTE: 300,
    SOURCE_SPECIFICATION: 400,
    SOURCE_SCHEDULE: 500,
    SOURCE_USER_CONFIRMED: 600,
}

VERSION_LAYERS: Final[tuple[str, ...]] = (
    "crop_version",
    "schedule_version",
    "scale_version",
    "element_version",
    "wall_version",
    "room_version",
    "review_version",
    "boq_version",
)

ELEMENT_TYPES: Final[set[str]] = {"door", "window", "wall_marker", "room_label", "other"}
