from __future__ import annotations

from app.tests._unified_helpers import prediction_payload, project_with_crop, render_crop


def _detect(monkeypatch):
    from app.jobs.worker import process_one
    from app.model_review.provider import detection_provider
    monkeypatch.setattr(detection_provider, "detect", lambda *_args, **_kwargs: prediction_payload())
    assert process_one("crop-version-detect", ["vision.detect_floor_elements"]) is not None


def test_identical_crop_is_idempotent(foundation_db):
    from app.floor_plans.service import floor_plans_service
    project, floor, first = project_with_crop()
    crop = first["crop"]
    repeated = floor_plans_service.save_crop(
        project_id=project["id"], floor_id=floor["id"], created_by=None,
        payload={
            "document_id": crop["document_id"], "document_page_id": crop["document_page_id"],
            "source_page_number": crop["source_page_number"], "original_page_width": crop["original_page_width"],
            "original_page_height": crop["original_page_height"], "rotation": crop["rotation"], "render_dpi": crop["render_dpi"],
            "original_rect": crop["coordinates"]["original_rect"],
            "normalized_display_rect": crop["coordinates"]["normalized_display_rect"],
        },
    )
    assert repeated["unchanged"] is True
    assert repeated["crop"]["crop_version"] == 1
    assert repeated["jobs"] == []


def test_replacement_hides_old_generated_rows_and_preserves_manual(foundation_db, monkeypatch):
    from app.database.session import get_connection
    from app.floor_plans.service import floor_plans_service
    from app.model_review.service import model_review_service

    project, floor, first = project_with_crop()
    render_crop(); _detect(monkeypatch)
    manual = model_review_service.create(
        project_id=project["id"], floor_id=floor["id"], created_by=None,
        payload={"element_type": "door", "geometry": {"x": 5, "y": 5, "width": 8, "height": 12}, "type_code": "MANUAL"},
    )["record"]
    crop = first["crop"]
    replacement = floor_plans_service.save_crop(
        project_id=project["id"], floor_id=floor["id"], created_by=None,
        payload={
            "document_id": crop["document_id"], "document_page_id": crop["document_page_id"],
            "source_page_number": crop["source_page_number"], "original_page_width": crop["original_page_width"],
            "original_page_height": crop["original_page_height"], "rotation": crop["rotation"], "render_dpi": crop["render_dpi"],
            "original_rect": {"x": 70, "y": 80, "width": 470, "height": 640},
            "normalized_display_rect": {"x": .12, "y": .1, "width": .78, "height": .8},
        },
    )
    assert replacement["crop"]["crop_version"] == 2
    state = model_review_service.get_state(project, floor["id"])
    assert [item["id"] for item in state["elements"]] == [manual["id"]]
    with get_connection() as connection:
        superseded = connection.execute(
            "SELECT COUNT(*) total FROM elements WHERE project_id=? AND floor_id=? AND is_manual=0 AND generated_status='superseded'",
            (project["id"], floor["id"]),
        ).fetchone()["total"]
    assert superseded == 3
