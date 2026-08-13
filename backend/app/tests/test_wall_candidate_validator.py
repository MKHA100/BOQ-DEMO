from __future__ import annotations


def _prediction(x, y, width, height, confidence=0.8):
    from app.model_review.prediction_processor import ProcessedPrediction

    return ProcessedPrediction(
        element_type="wall",
        geometry={
            "x": float(x),
            "y": float(y),
            "width": float(width),
            "height": float(height),
            "rotation": 0.0,
        },
        confidence=confidence,
        status="confirmed",
        raw={"class": "wall", "recovery_source": "original_tile"},
    )


def _seed(x, y, width, height):
    return {
        "geometry": {
            "x": float(x),
            "y": float(y),
            "width": float(width),
            "height": float(height),
            "rotation": 0.0,
        }
    }


def test_accepts_wall_extension_but_rejects_isolated_line():
    from app.model_review.wall_candidate_validator import wall_candidate_validator

    extension = _prediction(112, 50, 45, 10)
    isolated = _prediction(130, 150, 45, 10)
    accepted = wall_candidate_validator.validate(
        [extension, isolated],
        seed_walls=[_seed(20, 50, 100, 10)],
        crop_width=300,
        crop_height=220,
    )

    assert accepted == [extension]


def test_rejects_stair_pattern_even_when_steps_touch_side_walls():
    from app.model_review.wall_candidate_validator import wall_candidate_validator

    steps = [
        _prediction(20, 22 + index * 12, 90, 5)
        for index in range(6)
    ]
    accepted = wall_candidate_validator.validate(
        steps,
        seed_walls=[
            _seed(10, 10, 10, 110),
            _seed(110, 10, 10, 110),
        ],
        crop_width=200,
        crop_height=160,
    )

    assert accepted == []


def test_rejects_page_border_and_wrong_wall_thickness():
    from app.model_review.wall_candidate_validator import wall_candidate_validator

    border = _prediction(0, 1, 180, 10)
    thin_dimension = _prediction(60, 50, 60, 1)
    accepted = wall_candidate_validator.validate(
        [border, thin_dimension],
        seed_walls=[_seed(20, 50, 100, 10)],
        crop_width=200,
        crop_height=160,
    )

    assert accepted == []


def test_recovery_requires_an_existing_wall_network():
    from app.model_review.wall_candidate_validator import wall_candidate_validator

    accepted = wall_candidate_validator.validate(
        [_prediction(20, 50, 100, 10)],
        seed_walls=[],
        crop_width=200,
        crop_height=160,
    )

    assert accepted == []
