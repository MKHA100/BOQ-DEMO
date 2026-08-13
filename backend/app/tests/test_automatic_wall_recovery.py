from __future__ import annotations


def test_fast_detection_automatically_queues_wall_recovery(foundation_db, monkeypatch):
    from app.database.session import get_connection
    from app.jobs.worker import process_one
    from app.model_review.provider import detection_provider
    from app.tests._unified_helpers import prediction_payload, project_with_crop, render_crop

    project, floor, _ = project_with_crop()
    render_crop()
    monkeypatch.setattr(
        detection_provider, "detect",
        lambda image_path, *, analysis_mode="standard": prediction_payload(),
    )
    result = process_one("auto-wall-fast", ["vision.detect_floor_elements"])
    assert result is not None
    with get_connection() as connection:
        queued = connection.execute(
            """SELECT COUNT(*) total FROM job_runs
               WHERE project_id=? AND floor_id=? AND task_type='vision.recover_floor_walls'""",
            (project["id"], floor["id"]),
        ).fetchone()["total"]
    assert int(queued) == 1


def test_wall_recovery_adds_evidence_without_superseding_fast_results(
    foundation_db, monkeypatch
):
    from app.database.session import get_connection
    from app.jobs.worker import process_one
    from app.model_review.prediction_processor import ProcessedPrediction
    from app.model_review.provider import detection_provider
    from app.model_review.wall_recovery_service import wall_recovery_service
    from app.tests._unified_helpers import prediction_payload, project_with_crop, render_crop

    project, floor, _ = project_with_crop()
    render_crop()
    monkeypatch.setattr(
        detection_provider, "detect",
        lambda image_path, *, analysis_mode="standard": prediction_payload(),
    )
    assert process_one("auto-wall-standard", ["vision.detect_floor_elements"]) is not None
    recovered = ProcessedPrediction(
        element_type="wall",
        geometry={"x": 20.0, "y": 40.0, "width": 10.0, "height": 90.0, "rotation": 0.0},
        confidence=0.83,
        status="confirmed",
        raw={"class": "wall", "recovery_source": "original_tile"},
    )
    recovered_door = ProcessedPrediction(
        element_type="door",
        geometry={"x": 300.0, "y": 300.0, "width": 18.0, "height": 20.0, "rotation": 0.0},
        confidence=0.81,
        status="confirmed",
        raw={"class": "door", "recovery_source": "original_tile"},
    )
    monkeypatch.setattr(
        wall_recovery_service,
        "detect",
        lambda **kwargs: {
            "raw": {"predictions": [], "tile_count": 1},
            "groups": {"door": [recovered_door], "window": [], "wall": [recovered]},
            "door_count": 1,
            "window_count": 0,
            "wall_count": 1,
            "vector_wall_count": 0,
        },
    )
    result = process_one("auto-wall-recovery", ["vision.recover_floor_walls"])
    assert result is not None
    with get_connection() as connection:
        rows = connection.execute(
            """SELECT source,generated_status FROM elements
               WHERE project_id=? AND floor_id=? AND element_type='wall' AND excluded=0""",
            (project["id"], floor["id"]),
        ).fetchall()
    assert len(rows) == 2
    assert {row["generated_status"] for row in rows} == {"current"}
    assert "model_recovery" in {row["source"] for row in rows}


def test_existing_standard_floors_are_backfilled_automatically(
    foundation_db, monkeypatch
):
    from app.jobs.worker import process_one
    from app.model_review.provider import detection_provider
    from app.model_review.service import model_review_service
    from app.tests._unified_helpers import prediction_payload, project_with_crop, render_crop

    project_with_crop()
    render_crop()
    monkeypatch.setattr(
        detection_provider, "detect",
        lambda image_path, *, analysis_mode="standard": prediction_payload(),
    )
    assert process_one("wall-backfill-standard", ["vision.detect_floor_elements"]) is not None
    # The normal handoff already created the unique recovery job. The backfill
    # remains idempotent and does not create another one.
    result = model_review_service.enqueue_missing_wall_recoveries()
    assert result["floors"] == 0
