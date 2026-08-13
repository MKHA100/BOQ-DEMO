from __future__ import annotations


def test_semantic_label_overrides_inconsistent_llm_area_type():
    from app.floors.room_result_validator import room_result_validator

    context = {
        "floor_id": "f1",
        "building_envelope": {"points": [{"x": 0, "y": 0}, {"x": 50, "y": 0}, {"x": 50, "y": 50}, {"x": 0, "y": 50}]},
        "room_suggestions": [{"id": "s1", "polygon": {"points": [{"x": 5, "y": 5}, {"x": 40, "y": 5}, {"x": 40, "y": 40}, {"x": 5, "y": 40}]}}],
        "walls": [], "openings": [], "rooms": [], "dimensions": [],
    }
    response = {"floor_id": "f1", "warnings": [], "rooms": [{
        "room_suggestion_id": "s1", "room_name": "Bedroom", "room_type": "Bedroom",
        "semantic_type": "stair", "surrounding_wall_ids": [], "door_ids": [],
        "printed_width_mm": None, "printed_length_mm": None, "dimension_status": "unknown",
        "area_type": "circulation", "open_plan_group": None, "open_plan_with": [],
        "warnings": [], "confidence": 0.9,
    }]}
    room = room_result_validator.validate(response, context)["rooms"][0]
    assert room["area_type"] == "internal"
    assert room["semantic_type"] == "internal_room"


def test_room_names_are_case_insensitive_and_keep_combined_labels():
    from app.floors.room_semantics import room_semantics

    result = room_semantics.classify("dInInG / Pantry")

    assert result["name"] == "Dining Area / Pantry"
    assert result["labels"] == ["Dining Area", "Pantry"]
    assert result["open_plan"] is True


def test_room_names_fix_common_ocr_characters_and_filter_drawing_tags():
    from app.floors.room_semantics import room_semantics

    assert room_semantics.normalize("BATHR00M") == "Bathroom"
    assert room_semantics.extract_labels("FW2 FW2 + SL1 + LW + 14'-8\"") == []


def test_exception_room_aliases_are_normalized_and_grouped():
    from app.floors.room_semantics import room_semantics

    assert room_semantics.normalize("W.C.") == "Toilet"
    assert room_semantics.normalize("BATH") == "Bathroom"
    assert room_semantics.normalize("BAL.") == "Balcony"
    assert room_semantics.label_group("TOI") == "wet_area"
    assert room_semantics.label_group("VERANDAH") == "external_area"
    assert room_semantics.is_exception_recovery_label("BED RM") is True


def test_unknown_name_is_only_used_as_a_fallback():
    from app.floors.room_semantics import room_semantics

    assert room_semantics.normalize("Meditation Chamber") == "Meditation Chamber"


def test_drawing_tags_are_treated_as_replaceable_generated_names():
    from app.floors.service import floors_service

    assert floors_service._generic_room_name("FW2") is True
    assert floors_service._generic_room_name("LW + SL1") is True
    assert floors_service._generic_room_name("Meditation Chamber") is False


def test_known_room_name_beats_unknown_text_inside_room(monkeypatch):
    from app.floors.label_service import room_label_service

    monkeypatch.setattr(
        room_label_service,
        "_blocks",
        lambda *_: [
            {"text": "CUSTOM NOTE", "bbox": {"x0": 48, "y0": 48, "x1": 52, "y1": 52}},
            {"text": "bEd RoOm", "bbox": {"x0": 68, "y0": 48, "x1": 72, "y1": 52}},
        ],
    )
    rooms = [{
        "id": "r1",
        "geometry": {"points": [
            {"x": 0, "y": 0}, {"x": 100, "y": 0},
            {"x": 100, "y": 100}, {"x": 0, "y": 100},
        ]},
    }]

    result = room_label_service.suggestions("p1", "f1", rooms)["r1"]

    assert result["name"] == "Bedroom"
    assert result["label_candidates"] == ["Bedroom"]
