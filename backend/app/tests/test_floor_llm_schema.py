from __future__ import annotations

import pytest
from pydantic import ValidationError


def _room():
    return {
        "room_suggestion_id": "suggestion-1",
        "room_name": "Master Bedroom",
        "room_type": "Bedroom",
        "semantic_type": "internal_room",
        "surrounding_wall_ids": ["wall-1"],
        "door_ids": ["door-1"],
        "printed_width_mm": 3600,
        "printed_length_mm": None,
        "dimension_status": "partial",
        "area_type": "internal",
        "open_plan_group": None,
        "open_plan_with": [],
        "warnings": [],
        "confidence": 0.91,
    }


def test_floor_schema_validates_structured_room_output():
    from app.floors.llm_room_schema import FloorRoomInterpretation, floor_room_response_schema

    result = FloorRoomInterpretation.model_validate(
        {"floor_id": "floor-1", "rooms": [_room()], "warnings": []}
    )
    assert result.rooms[0].dimension_status == "partial"
    schema = floor_room_response_schema()
    assert schema["additionalProperties"] is False
    assert schema["properties"]["rooms"]["items"]["additionalProperties"] is False
    assert "area_m2" not in schema["properties"]["rooms"]["items"]["properties"]


def test_floor_schema_rejects_unknown_fields_and_states():
    from app.floors.llm_room_schema import FloorRoomInterpretation

    room = {**_room(), "area_m2": 12, "dimension_status": "estimated"}
    with pytest.raises(ValidationError):
        FloorRoomInterpretation.model_validate(
            {"floor_id": "floor-1", "rooms": [room], "warnings": []}
        )
