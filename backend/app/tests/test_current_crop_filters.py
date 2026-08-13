from __future__ import annotations

from app.tests._unified_helpers import project_with_crop


def test_old_crop_elements_are_not_returned(foundation_db):
    from app.floor_plans.service import floor_plans_service
    from app.model_review.repo import model_review_repository
    project, floor, first = project_with_crop()
    crop=first["crop"]
    second=floor_plans_service.save_crop(project_id=project["id"],floor_id=floor["id"],created_by=None,payload={
        "document_id":crop["document_id"],"document_page_id":crop["document_page_id"],"source_page_number":1,
        "original_page_width":600,"original_page_height":800,"rotation":0,"render_dpi":144,
        "original_rect":{"x":70,"y":80,"width":470,"height":640},"normalized_display_rect":{"x":.12,"y":.1,"width":.78,"height":.8},
    })
    old=model_review_repository.create_element(project_id=project["id"],floor_id=floor["id"],element_type="door",geometry={"x":1,"y":1,"width":5,"height":5},type_code=None,source="model",confidence=.9,detection_version=1,is_manual=False,provider_name="test",created_by=None,crop_id=crop["id"],crop_version=1)
    current=model_review_repository.create_element(project_id=project["id"],floor_id=floor["id"],element_type="door",geometry={"x":10,"y":1,"width":5,"height":5},type_code=None,source="model",confidence=.9,detection_version=2,is_manual=False,provider_name="test",created_by=None,crop_id=second["crop"]["id"],crop_version=2)
    returned=model_review_repository.list_elements(project["id"],floor["id"])
    assert [item["id"] for item in returned] == [current["id"]]
    assert old["id"] not in {item["id"] for item in returned}
