from __future__ import annotations


def _prediction(element_type, x, y, width, height, confidence):
    from app.model_review.prediction_processor import ProcessedPrediction

    return ProcessedPrediction(
        element_type=element_type,
        geometry={
            "x": float(x),
            "y": float(y),
            "width": float(width),
            "height": float(height),
            "rotation": 0.0,
        },
        confidence=confidence,
        status="confirmed",
        raw={"class": element_type, "recovery_source": "original_tile"},
    )


def test_opening_near_wall_is_accepted_and_isolated_weak_box_is_rejected():
    from app.model_review.opening_candidate_validator import (
        opening_candidate_validator,
    )

    near_wall = _prediction("door", 45, 42, 18, 20, 0.55)
    isolated = _prediction("door", 150, 140, 18, 20, 0.55)
    accepted = opening_candidate_validator.validate(
        [near_wall, isolated],
        seed_walls=[
            {
                "geometry": {
                    "x": 10,
                    "y": 30,
                    "width": 100,
                    "height": 10,
                }
            }
        ],
        crop_width=240,
        crop_height=200,
    )

    assert accepted == [near_wall]


def test_strong_independent_opening_is_retained_but_border_noise_is_rejected():
    from app.model_review.opening_candidate_validator import (
        opening_candidate_validator,
    )

    strong = _prediction("window", 100, 100, 24, 8, 0.80)
    border = _prediction("window", 0, 80, 24, 8, 0.70)
    accepted = opening_candidate_validator.validate(
        [strong, border],
        seed_walls=[],
        crop_width=240,
        crop_height=200,
    )

    assert accepted == [strong]
