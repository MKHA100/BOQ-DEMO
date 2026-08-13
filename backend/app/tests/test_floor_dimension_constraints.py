def test_dimension_constraint_corrects_near_rectangle():
    from app.floors.dimension_constraint_service import dimension_constraint_service
    points = [{"x": 0, "y": 0}, {"x": 98, "y": 0}, {"x": 98, "y": 50}, {"x": 0, "y": 50}]
    observations = [
        {"value_mm": 5000, "orientation": "horizontal"},
        {"value_mm": 2500, "orientation": "vertical"},
    ]
    result = dimension_constraint_service.apply(points, observations, 50)
    assert result["printed_length_mm"] == 5000
    assert len(result["points"]) == 4


def test_printed_dimensions_do_not_move_wall_face_geometry():
    from app.floors.service import floors_service

    points = [{"x": 0, "y": 0}, {"x": 98, "y": 0}, {"x": 98, "y": 50}, {"x": 0, "y": 50}]
    candidate = {"points": points, "boundary_source": "model_seed_wall_faces"}
    result = floors_service._correct_candidate_dimensions(
        candidate,
        [{"value_mm": 5000, "orientation": "horizontal", "confidence": 1}],
        50,
    )

    assert result["points"] == points


def test_vector_dimension_parser_supports_architectural_feet_and_inches():
    from app.floors.vector_geometry_service import vector_floor_geometry_service

    values = vector_floor_geometry_service._dimension_values("13'-6\"")
    assert len(values) == 1
    assert round(values[0][1], 1) == 4114.8

    values = vector_floor_geometry_service._dimension_values("21 FT 3 IN")
    assert len(values) == 1
    assert round(values[0][1], 1) == 6477.0

    assert vector_floor_geometry_service._dimension_values("FLOOR AREA: 628 SQ.FT") == []
    assert vector_floor_geometry_service._dimension_values("+13'-6\"") == []
    assert vector_floor_geometry_service._dimension_values("FFL +1200 MM") == []
