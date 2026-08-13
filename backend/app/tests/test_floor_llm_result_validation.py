from __future__ import annotations


def _room(suggestion_id: str, **updates):
    value = {
        "room_suggestion_id": suggestion_id,
        "room_name": "Bedroom",
        "room_type": "Bedroom",
        "semantic_type": "internal_room",
        "surrounding_wall_ids": ["wall-1", "invented-wall"],
        "door_ids": ["door-1", "invented-door"],
        "printed_width_mm": 3600,
        "printed_length_mm": 9999,
        "dimension_status": "exact",
        "area_type": "internal",
        "open_plan_group": None,
        "open_plan_with": [],
        "warnings": [],
        "confidence": 0.9,
    }
    value.update(updates)
    return value


def test_validator_removes_invented_measurements_and_references():
    from app.floors.room_result_validator import room_result_validator

    context = {
        "floor_id": "floor-1",
        "building_envelope": {"points": [{"x": 0, "y": 0}, {"x": 100, "y": 0}, {"x": 100, "y": 100}, {"x": 0, "y": 100}]},
        "room_suggestions": [
            {"id": "s1", "polygon": {"points": [{"x": 5, "y": 5}, {"x": 45, "y": 5}, {"x": 45, "y": 45}, {"x": 5, "y": 45}]}},
            {"id": "s2", "polygon": {"points": [{"x": 55, "y": 55}, {"x": 85, "y": 55}, {"x": 85, "y": 85}, {"x": 55, "y": 85}]}},
        ],
        "walls": [{"id": "wall-1"}],
        "openings": [{"id": "door-1", "type": "door"}],
        "rooms": [],
        "dimensions": [
            {"value_mm": 3600, "point_a": {"x": 10, "y": 10}, "point_b": {"x": 40, "y": 10}}
        ],
    }
    result = room_result_validator.validate(
        {"floor_id": "floor-1", "rooms": [_room("s1")], "warnings": []}, context
    )
    room = result["rooms"][0]
    assert room["surrounding_wall_ids"] == ["wall-1"]
    assert room["door_ids"] == ["door-1"]
    assert room["printed_width_mm"] == 3600
    assert room["printed_length_mm"] is None
    assert room["dimension_status"] == "partial"


def test_validator_rejects_large_background_and_duplicate_ids():
    from app.floors.room_result_validator import room_result_validator

    context = {
        "floor_id": "floor-1",
        "building_envelope": {"points": [{"x": 0, "y": 0}, {"x": 100, "y": 0}, {"x": 100, "y": 100}, {"x": 0, "y": 100}]},
        "room_suggestions": [
            {"id": "background", "polygon": {"points": [{"x": 1, "y": 1}, {"x": 99, "y": 1}, {"x": 99, "y": 99}, {"x": 1, "y": 99}]}},
            {"id": "small", "polygon": {"points": [{"x": 5, "y": 5}, {"x": 25, "y": 5}, {"x": 25, "y": 25}, {"x": 5, "y": 25}]}},
        ],
        "walls": [], "openings": [], "rooms": [], "dimensions": [],
    }
    result = room_result_validator.validate(
        {"floor_id": "floor-1", "rooms": [_room("background", surrounding_wall_ids=[], door_ids=[], printed_width_mm=None, printed_length_mm=None), _room("small", surrounding_wall_ids=[], door_ids=[], printed_width_mm=None, printed_length_mm=None), _room("small", surrounding_wall_ids=[], door_ids=[], printed_width_mm=None, printed_length_mm=None)], "warnings": []},
        context,
    )
    assert [item["room_suggestion_id"] for item in result["rooms"]] == ["small"]
    assert len(result["rejected"]) == 2


def test_validator_removes_drawing_tags_from_room_names():
    from app.floors.room_result_validator import room_result_validator

    context = {
        "floor_id": "floor-1",
        "building_envelope": {"points": [{"x": 0, "y": 0}, {"x": 100, "y": 0}, {"x": 100, "y": 100}, {"x": 0, "y": 100}]},
        "room_suggestions": [{"id": "s1", "polygon": {"points": [{"x": 5, "y": 5}, {"x": 45, "y": 5}, {"x": 45, "y": 45}, {"x": 5, "y": 45}]}}],
        "walls": [], "openings": [], "rooms": [], "dimensions": [],
    }
    result = room_result_validator.validate(
        {"floor_id": "floor-1", "rooms": [_room(
            "s1", room_name="FW2 FW2 + SL1 + LW", room_type="FW2",
            surrounding_wall_ids=[], door_ids=[], printed_width_mm=None, printed_length_mm=None,
        )], "warnings": []},
        context,
    )

    assert result["rooms"][0]["room_name"] == ""
    assert result["rooms"][0]["room_type"] == ""
