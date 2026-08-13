from __future__ import annotations

from app.tests._unified_helpers import prediction_payload, project_with_crop, render_crop


def test_matching_confirmed_element_keeps_id_number_and_properties(foundation_db, monkeypatch):
    from app.floor_plans.service import floor_plans_service
    from app.jobs.worker import process_one
    from app.model_review.provider import detection_provider
    from app.model_review.service import model_review_service

    monkeypatch.setattr(detection_provider, "detect", lambda *_args, **_kwargs: prediction_payload())
    project, floor, first = project_with_crop(); render_crop()
    process_one("first-detect", ["vision.detect_floor_elements"])
    door = next(item for item in model_review_service.get_state(project, floor["id"])["elements"] if item["element_type"] == "door")
    model_review_service.update(project_id=project["id"], floor_id=floor["id"], element_id=door["id"], payload={"review_status":"confirmed","type_code":"D9"}, created_by=None)
    model_review_service.update_property(project_id=project["id"], floor_id=floor["id"], element_id=door["id"], property_name="width_mm", value=999, unit="mm", confirm=True, created_by=None)
    crop = first["crop"]
    floor_plans_service.save_crop(project_id=project["id"], floor_id=floor["id"], created_by=None, payload={
        "document_id":crop["document_id"],"document_page_id":crop["document_page_id"],"source_page_number":1,
        "original_page_width":600,"original_page_height":800,"rotation":0,"render_dpi":144,
        "original_rect":{"x":61,"y":80,"width":480,"height":640},"normalized_display_rect":{"x":.101,"y":.1,"width":.8,"height":.8},
    })
    render_crop(); process_one("second-detect", ["vision.detect_floor_elements"])
    current = next(item for item in model_review_service.get_state(project, floor["id"])["elements"] if item["element_type"] == "door")
    assert current["id"] == door["id"]
    assert current["item_number"] == door["item_number"]
    assert current["type_code"] == "D9"
    assert current["resolved_data"]["width_mm"] == 999
