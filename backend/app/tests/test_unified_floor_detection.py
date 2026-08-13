from __future__ import annotations

from app.tests._unified_helpers import prediction_payload, project_with_crop, render_crop


def test_one_floor_crop_uses_one_shared_model_call(foundation_db, monkeypatch):
    from app.database.session import get_connection
    from app.jobs.worker import process_one
    from app.model_review.provider import detection_provider

    project, floor, _ = project_with_crop()
    render_crop()
    calls: list[str] = []

    def fake_detect(image_path, *, analysis_mode="standard"):
        calls.append(str(image_path))
        return prediction_payload()

    monkeypatch.setattr(detection_provider, "detect", fake_detect)
    result = process_one("unified-detection", ["vision.detect_floor_elements"])
    assert result is not None
    assert calls and len(calls) == 1
    with get_connection() as connection:
        run = connection.execute(
            "SELECT * FROM floor_element_detection_runs WHERE project_id=? AND floor_id=?",
            (project["id"], floor["id"]),
        ).fetchone()
        rows = connection.execute(
            "SELECT element_type,status,COUNT(*) total FROM elements WHERE project_id=? AND floor_id=? AND generated_status='current' GROUP BY element_type,status",
            (project["id"], floor["id"]),
        ).fetchall()
        legacy = connection.execute(
            "SELECT COUNT(*) total FROM job_runs WHERE project_id=? AND task_type IN ('vision.detect_doors','vision.detect_windows','vision.detect_walls')",
            (project["id"],),
        ).fetchone()["total"]
        recovery = connection.execute(
            """SELECT COUNT(*) total FROM job_runs
               WHERE project_id=? AND floor_id=? AND task_type='vision.recover_floor_walls'""",
            (project["id"], floor["id"]),
        ).fetchone()["total"]
    assert run["status"] == "ready"
    assert {row["element_type"]: int(row["total"]) for row in rows} == {"door": 1, "window": 1, "wall": 1}
    assert {row["status"] for row in rows} == {"confirmed"}
    assert legacy == 0
    assert int(recovery) == 1


def test_deep_provider_merges_tiled_results_without_duplicates(tmp_path, monkeypatch):
    from PIL import Image
    from app.model_review.provider import DetectionProvider
    from app.core.config import settings

    original_key = settings.roboflow_api_key
    object.__setattr__(settings, "roboflow_api_key", "test-key")
    image_path = tmp_path / "large-floor.png"
    Image.new("RGB", (1600, 1200), "white").save(image_path)
    provider = DetectionProvider()
    calls = []

    def fake_request(path):
        calls.append(path.name)
        # Every pass returns the same local box. Tile offsets will transform the
        # tiled responses; exact full/tile duplicates are removed by NMS.
        return {
            "predictions": [
                {"class": "door", "confidence": .9, "x": 100, "y": 100, "width": 40, "height": 60}
            ]
        }

    monkeypatch.setattr(provider, "_request", fake_request)
    try:
        result = provider.detect(image_path, analysis_mode="deep")
    finally:
        object.__setattr__(settings, "roboflow_api_key", original_key)
    assert result["analysis_mode"] == "deep"
    assert result["request_count"] == len(calls)
    assert result["tile_count"] >= 1
    assert result["predictions"]


def test_manual_deep_analysis_queues_separate_mode(foundation_db):
    from app.model_review.service import model_review_service
    from app.tests._unified_helpers import project_with_crop, render_crop

    project, floor, _ = project_with_crop()
    render_crop()
    result = model_review_service.analyze_floor(
        project_id=project["id"], floor_id=floor["id"], analysis_mode="deep", created_by=None
    )
    assert result["analysis_mode"] == "deep"
    assert result["job"]["task_type"] == "vision.detect_floor_elements"
    assert result["job"]["input_versions"]["analysis_mode"] == "deep"
