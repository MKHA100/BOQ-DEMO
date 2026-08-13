def test_semantics_remove_dimension_and_section_noise():
    from app.floors.room_semantics import room_semantics
    assert room_semantics.normalize("SITTING AREA + 3600mm + A") == "Sitting Area"
    assert room_semantics.classify("DN")["include_in_boq"] is False
    assert room_semantics.classify("BALCONY")["space_kind"] == "external"
