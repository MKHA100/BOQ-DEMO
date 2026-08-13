from __future__ import annotations

from app.tests._unified_helpers import prediction_payload, project_with_crop, render_crop


def _status(summary, key):
    return next(step["status"] for step in summary["steps"] if step["key"] == key)


def test_plans_and_model_status_use_only_their_own_durable_results(foundation_db, monkeypatch):
    from app.jobs.worker import process_one
    from app.model_review.provider import detection_provider
    from app.workflow.service import workflow_service
    project, floor, _ = project_with_crop()
    before=workflow_service.get_summary(project_id=project["id"],project=project)
    assert _status(before,"floor-plans") in {"ready","results_available"}
    monkeypatch.setattr(detection_provider,"detect",lambda *_args,**_kwargs:prediction_payload())
    render_crop(); process_one("status-detection",["vision.detect_floor_elements"])
    after=workflow_service.get_summary(project_id=project["id"],project=project)
    assert _status(after,"model-review") in {"needs_review","ready","results_available"}
    # Later room/BOQ work must not push Model back to Processing.
    assert _status(after,"model-review") != "processing"
