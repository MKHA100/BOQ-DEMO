from __future__ import annotations


def test_dimension_matching_uses_printed_evidence_and_scale():
    from app.floors.dimension_constraint_service import dimension_constraint_service

    points = [{"x": 0, "y": 0}, {"x": 100, "y": 0}, {"x": 100, "y": 80}, {"x": 0, "y": 80}]
    observations = [
        {"value_mm": 800, "orientation": "vertical", "point_a": {"x": 5, "y": 0}, "point_b": {"x": 5, "y": 80}, "confidence": 0.9},
        {"value_mm": 1000, "orientation": "horizontal", "point_a": {"x": 0, "y": 5}, "point_b": {"x": 100, "y": 5}, "confidence": 0.9},
    ]
    result = dimension_constraint_service.match(
        points,
        observations,
        10,
        preferred_width_mm=800,
        preferred_length_mm=1000,
        preferred_source="llm_verified",
    )
    assert result["printed_width_mm"] == 800
    assert result["printed_length_mm"] == 1000
    assert result["dimension_status"] == "exact"
    assert result["dimension_source"] == "llm_verified"
    assert result["difference_percent"] == 0


def test_unobserved_llm_dimension_is_not_used():
    from app.floors.dimension_constraint_service import dimension_constraint_service

    points = [{"x": 0, "y": 0}, {"x": 100, "y": 0}, {"x": 100, "y": 80}, {"x": 0, "y": 80}]
    result = dimension_constraint_service.match(
        points,
        [{"value_mm": 1000, "orientation": "horizontal"}],
        10,
        preferred_width_mm=7777,
        preferred_source="llm_verified",
    )
    assert result["printed_width_mm"] is None
    assert result["dimension_status"] == "partial"


def test_printed_dimensions_are_retained_before_scale_is_verified():
    from app.floors.dimension_constraint_service import dimension_constraint_service

    points = [{"x": 0, "y": 0}, {"x": 100, "y": 0}, {"x": 100, "y": 80}, {"x": 0, "y": 80}]
    observations = [
        {"value_mm": 800, "orientation": "vertical", "confidence": 0.9},
        {"value_mm": 1000, "orientation": "horizontal", "confidence": 0.9},
    ]
    result = dimension_constraint_service.match(
        points,
        observations,
        0,
        preferred_width_mm=800,
        preferred_length_mm=1000,
        preferred_source="llm_verified",
    )
    assert result["points"] == points
    assert result["printed_width_mm"] == 800
    assert result["printed_length_mm"] == 1000
    assert result["dimension_status"] == "exact"
    assert result["dimension_source"] == "llm_verified"
    assert result["difference_percent"] is None
