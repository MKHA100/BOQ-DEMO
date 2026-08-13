from __future__ import annotations


def create_data():
    from app.projects.project_service import project_service
    from app.workflow.service import workflow_service
    from app.model_review.service import model_review_service
    project = project_service.create_project("Review Test")
    floor = workflow_service.create_floor(project_id=project["id"], name=None, level_index=None, created_by=None)
    door = model_review_service.create(project_id=project["id"], floor_id=floor["id"], payload={"element_type":"door","geometry":{"x":1,"y":1,"width":4,"height":8,"rotation":0}}, created_by=None)["record"]
    model_review_service.update_property(project_id=project["id"],floor_id=floor["id"],element_id=door["id"],property_name="width_mm",value=900,unit="mm",confirm=True,created_by=None)
    model_review_service.update_property(project_id=project["id"],floor_id=floor["id"],element_id=door["id"],property_name="height_mm",value=2100,unit="mm",confirm=True,created_by=None)
    return project,floor,door


def test_review_reads_canonical_multi_floor_data(foundation_db):
    from app.review.service import review_service
    project,floor,door=create_data()
    review_service.refresh(project["id"])
    result=review_service.state(project)
    item=next(item for item in result["items"] if item["entity_id"]==door["id"])
    assert item["data"]["width_mm"] == 900
    assert item["display_number"] == door["display_number"]
    assert item["data"]["item_number"] == door["item_number"]
    assert result["floors"][0]["id"] == floor["id"]


def test_review_field_edit_updates_canonical_value(foundation_db):
    from app.review.service import review_service
    from app.database.session import get_connection
    import json
    project,floor,door=create_data(); review_service.refresh(project["id"])
    item=next(item for item in review_service.state(project)["items"] if item["entity_id"]==door["id"])
    review_service.update_field(project["id"],item["id"],"width_mm",1000,None)
    with get_connection() as connection:
        row=connection.execute("SELECT value_json FROM element_properties WHERE element_id=? AND property_name='width_mm'",(door["id"],)).fetchone()
    assert json.loads(row["value_json"]) == 1000


def test_critical_items_cannot_be_bulk_confirmed(foundation_db):
    from app.projects.project_service import project_service
    from app.workflow.service import workflow_service
    from app.model_review.service import model_review_service
    from app.review.service import review_service
    project=project_service.create_project("Critical Review")
    floor=workflow_service.create_floor(project_id=project["id"],name=None,level_index=None,created_by=None)
    model_review_service.create(project_id=project["id"],floor_id=floor["id"],payload={"element_type":"window","geometry":{"x":0,"y":0,"width":2,"height":2,"rotation":0}},created_by=None)
    review_service.refresh(project["id"])
    result=review_service.confirm(project["id"],[],"project",None,None)
    assert result["confirmed"] == 0
    assert result["blocked"] == 1


def test_review_exposes_full_element_details(foundation_db):
    from app.model_review.service import model_review_service
    from app.review.service import review_service

    project, floor, door = create_data()
    model_review_service.update(
        project_id=project["id"], floor_id=floor["id"], element_id=door["id"],
        payload={"type_code": "D1"}, created_by=None,
    )
    model_review_service.update_property(
        project_id=project["id"], floor_id=floor["id"], element_id=door["id"],
        property_name="material", value="Timber", unit=None, confirm=True, created_by=None,
    )
    review_service.refresh(project["id"])
    item = next(row for row in review_service.state(project)["items"] if row["entity_id"] == door["id"])
    assert item["display_number"] == door["display_number"]
    assert item["data"]["type_code"] == "D1"
    assert item["data"]["material"] == "Timber"
    assert item["data"]["missing_fields"] == []
