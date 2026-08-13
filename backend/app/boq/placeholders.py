from __future__ import annotations

PLACEHOLDERS: tuple[dict[str, str], ...] = (
    {"key": "TYPE_CODE", "label": "Type code", "example": "D2"},
    {"key": "MATERIAL", "label": "Material", "example": "Timber"},
    {"key": "FRAME_MATERIAL", "label": "Frame material", "example": "Hardwood"},
    {"key": "FINISH", "label": "Finish", "example": "Stain and polyurethane varnish"},
    {"key": "WIDTH", "label": "Width (mm)", "example": "990"},
    {"key": "HEIGHT", "label": "Height (mm)", "example": "2130"},
    {"key": "THICKNESS", "label": "Thickness (mm)", "example": "215"},
    {"key": "CLASSIFICATION", "label": "Wall classification", "example": "External"},
    {"key": "FLOOR_FINISH", "label": "Floor finish", "example": "Porcelain tile"},
    {"key": "ROOM_NAME", "label": "Room name", "example": "Office"},
    {"key": "FIRE_RATING", "label": "Fire rating", "example": "FD30"},
    {"key": "GLASS_TYPE", "label": "Glass type", "example": "4 mm clear float glass"},
    {"key": "QUANTITY", "label": "Quantity", "example": "5"},
    {"key": "UNIT", "label": "Unit", "example": "nr"},
    {"key": "FLOOR_NAMES", "label": "Floors", "example": "Ground Floor"},
    {"key": "SIDE_1_FINISH", "label": "Wall side 1 finish", "example": "Plaster and paint"},
    {"key": "SIDE_2_FINISH", "label": "Wall side 2 finish", "example": "Plaster and paint"},
)

PLACEHOLDER_KEYS = {item["key"] for item in PLACEHOLDERS}
