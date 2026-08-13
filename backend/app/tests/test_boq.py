from __future__ import annotations


def setup_boq_data():
    from app.projects.project_service import project_service
    from app.workflow.service import workflow_service
    from app.model_review.service import model_review_service
    from app.walls.repo import walls_repository
    from app.floors.repo import floors_repository
    from app.workflow.repo import workflow_repository
    from app.database.session import get_connection
    project=project_service.create_project("BOQ Test")
    floor=workflow_service.create_floor(project_id=project["id"],name=None,level_index=None,created_by=None)
    door=model_review_service.create(project_id=project["id"],floor_id=floor["id"],payload={"element_type":"door","geometry":{"x":0,"y":0,"width":2,"height":4,"rotation":0},"type_code":"D1"},created_by=None)["record"]
    model_review_service.update_property(project_id=project["id"],floor_id=floor["id"],element_id=door["id"],property_name="width_mm",value=900,unit="mm",confirm=True,created_by=None)
    model_review_service.update_property(project_id=project["id"],floor_id=floor["id"],element_id=door["id"],property_name="height_mm",value=2100,unit="mm",confirm=True,created_by=None)
    with get_connection() as connection:
        connection.execute("UPDATE elements SET status='confirmed',user_confirmed=1 WHERE id=?",(door["id"],))
        versions=workflow_repository.increment_floor_version(connection,project["id"],floor["id"],"wall_version")
    wall=walls_repository.create_wall(project_id=project["id"],floor_id=floor["id"],centerline={"start":{"x":0,"y":0},"end":{"x":100,"y":0}},wall_type="W1",classification="external",thickness_mm=200,height_mm=3000,wall_version=versions["wall_version"],created_by=None,source_versions={})
    with get_connection() as connection:
        connection.execute("UPDATE walls SET status='confirmed',user_confirmed=1,length_mm=10000,gross_area_m2=30,deduction_area_m2=1.89,net_area_m2=28.11 WHERE id=?",(wall["id"],))
        room_versions=workflow_repository.increment_floor_version(connection,project["id"],floor["id"],"room_version")
    room=floors_repository.create_room(project_id=project["id"],floor_id=floor["id"],points=[{"x":0,"y":0},{"x":100,"y":0},{"x":100,"y":80},{"x":0,"y":80}],generated=False,room_version=room_versions["room_version"],created_by=None,name="Office")
    with get_connection() as connection:
        connection.execute("UPDATE rooms SET status='confirmed',user_confirmed=1,area_m2=80,floor_type_code='F1',floor_finish='Tile' WHERE id=?",(room["id"],))
    return project,floor,door,wall,room


def test_boq_groups_confirmed_quantities(foundation_db):
    from app.boq.service import boq_service
    project,floor,door,wall,room=setup_boq_data()
    result=boq_service.refresh(project["id"])
    door_row=next(row for row in result["rows"] if row["entity_type"]=="door")
    wall_row=next(row for row in result["rows"] if row["entity_type"]=="wall_external")
    floor_row=next(row for row in result["rows"] if row["entity_type"]=="floor")
    assert door_row["quantity"] == 1
    assert isinstance(door_row["quantity"], (int,float))
    assert wall_row["quantity"] == 28.11
    assert floor_row["quantity"] == 80
    assert floor["id"] in door_row["floor_ids"]


def test_manual_row_and_protected_description_survive_refresh(foundation_db):
    from app.boq.service import boq_service
    project,*_=setup_boq_data(); first=boq_service.refresh(project["id"])
    generated=next(row for row in first["rows"] if row["entity_type"]=="door")
    boq_service.update_row(project["id"],generated["id"],{"description":"Protected door description"})
    manual=boq_service.add_manual(project["id"],{"description":"Site allowance","section":"Preliminaries","quantity":1,"unit":"item","floor_id":None},None)["row"]
    second=boq_service.refresh(project["id"])
    assert next(row for row in second["rows"] if row["id"]==generated["id"])["description"] == "Protected door description"
    assert next(row for row in second["rows"] if row["id"]==manual["id"])["manual"] is True


def test_boq_exports_are_cached_and_generated(foundation_db):
    from app.boq.service import boq_service
    from app.jobs.worker import process_one
    from app.boq.repo import boq_repository
    from app.storage.storage_service import storage_service
    project,*_=setup_boq_data(); boq_service.refresh(project["id"])
    request=boq_service.request_export(project["id"],{"format":"csv","floor_mode":"combined","floor_id":None},None)
    duplicate=boq_service.request_export(project["id"],{"format":"csv","floor_mode":"combined","floor_id":None},None)
    assert request["created"] is True and duplicate["created"] is False
    process_one("boq-test",["export.generate"])
    record=boq_repository.get_export(project["id"],request["export"]["id"])
    assert record["status"] == "ready"
    assert storage_service.file_exists(storage_service.key_to_path(record["object_key"]))


def test_boq_keeps_incomplete_elements_visible_for_review(foundation_db):
    from app.projects.project_service import project_service
    from app.workflow.service import workflow_service
    from app.model_review.service import model_review_service
    from app.boq.service import boq_service

    project = project_service.create_project("BOQ Review Visibility")
    floor = workflow_service.create_floor(project_id=project["id"], name=None, level_index=None, created_by=None)
    element = model_review_service.create(
        project_id=project["id"], floor_id=floor["id"],
        payload={"element_type": "door", "geometry": {"x": 0, "y": 0, "width": 2, "height": 4, "rotation": 0}},
        created_by=None,
    )["record"]
    result = boq_service.refresh(project["id"])
    row = next(item for item in result["rows"] if element["id"] in item["source_ids"])
    assert row["status"] == "needs_review"
    assert row["quantity"] == 1
    assert row["source_items"][0]["display_number"] == element["display_number"]
