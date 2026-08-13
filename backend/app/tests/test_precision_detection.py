from __future__ import annotations


def test_compact_wall_symbol_is_not_saved_as_a_wall():
    from app.model_review.prediction_processor import process_predictions

    groups = process_predictions(
        {
            "predictions": [
                {
                    "class": "wall",
                    "confidence": 0.95,
                    "x": 100,
                    "y": 100,
                    "width": 30,
                    "height": 25,
                },
                {
                    "class": "wall",
                    "confidence": 0.95,
                    "x": 100,
                    "y": 150,
                    "width": 100,
                    "height": 10,
                },
            ]
        },
        image_width=200,
        image_height=200,
        crop_width=200,
        crop_height=200,
    )

    assert len(groups["wall"]) == 1
    assert groups["wall"][0].geometry["width"] == 100


def test_precision_provider_keeps_all_three_supported_classes(
    tmp_path, monkeypatch
):
    from app.core.config import settings
    from app.model_review.provider import detection_provider
    from app.model_review.wall_tile_service import WallRecoveryTile, wall_tile_service

    image_path = tmp_path / "plan.png"
    image_path.write_bytes(b"unused")
    tile = WallRecoveryTile(
        index=0,
        x=10,
        y=20,
        width=200,
        height=200,
        content=b"tile",
    )
    monkeypatch.setattr(wall_tile_service, "tiles", lambda *args, **kwargs: [tile])
    monkeypatch.setattr(
        detection_provider,
        "_request_content",
        lambda *args, **kwargs: {
            "predictions": [
                {"class": "wall", "confidence": 0.8, "x": 10, "y": 10, "width": 50, "height": 5},
                {"class": "door", "confidence": 0.8, "x": 30, "y": 30, "width": 15, "height": 20},
                {"class": "window", "confidence": 0.8, "x": 50, "y": 50, "width": 20, "height": 8},
                {"class": "chair", "confidence": 0.9, "x": 70, "y": 70, "width": 20, "height": 20},
            ]
        },
    )
    original_key = settings.roboflow_api_key
    object.__setattr__(settings, "roboflow_api_key", "test-key")
    try:
        result = detection_provider.detect_precision_recovery(image_path)
    finally:
        object.__setattr__(settings, "roboflow_api_key", original_key)

    assert {item["class"] for item in result["predictions"]} == {
        "wall",
        "door",
        "window",
    }
    assert all(item["x"] >= 20 and item["y"] >= 30 for item in result["predictions"])
