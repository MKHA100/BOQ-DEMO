from __future__ import annotations

CATEGORY_DEFINITIONS = {
    "door_schedule": {
        "label": "Door Schedule",
        "description": "Door types, sizes, materials, finishes and quantities.",
        "kind": "schedule",
        "priority": 500,
    },
    "window_schedule": {
        "label": "Window Schedule",
        "description": "Window types, sizes, frames, glazing and quantities.",
        "kind": "schedule",
        "priority": 500,
    },
    "wall_schedule": {
        "label": "Wall Schedule",
        "description": "Wall types, thicknesses, materials, finishes and construction notes.",
        "kind": "schedule",
        "priority": 500,
    },
    "floor_schedule": {
        "label": "Floor Schedule",
        "description": "Floor types, finishes, room or zone use, screed and skirting.",
        "kind": "schedule",
        "priority": 500,
    },
    "specification": {
        "label": "Specification",
        "description": "General material, finish, glazing, paint and joinery requirements.",
        "kind": "specification",
        "priority": 400,
    },
    "other": {
        "label": "Other Supporting Files",
        "description": "Additional notes or documents that support later review.",
        "kind": "specification",
        "priority": 300,
    },
}

CATEGORIES = tuple(CATEGORY_DEFINITIONS)
EXTRACTION_SCHEMA_VERSION = 1
STATUS_VALUES = {"ready", "processing", "needs_review", "failed", "skipped"}
