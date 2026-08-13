from __future__ import annotations


def setup_project():
    from app.projects.project_service import project_service
    from app.workflow.service import workflow_service
    from app.database.session import get_connection
    project=project_service.create_project("Wall Tower")
    floor=workflow_service.create_floor(project_id=project["id"],name=None,level_index=None,created_by=None)
    with get_connection() as connection:
        connection.execute("UPDATE floors SET wall_height_mm=3000 WHERE id=?",(floor["id"],))
        connection.execute("UPDATE floor_versions SET scale_version=1 WHERE floor_id=?",(floor["id"],))
    return project,floor


def test_wall_quantity_and_nrm2_opening_deduction(foundation_db):
    from app.walls.repo import walls_repository
    from app.walls.service import walls_service
    from app.model_review.service import model_review_service
    from app.workflow.repo import workflow_repository
    from app.database.session import get_connection
    project,floor=setup_project()
    with get_connection() as connection:versions=workflow_repository.increment_floor_version(connection,project["id"],floor["id"],"wall_version")
    wall=walls_repository.create_wall(project_id=project["id"],floor_id=floor["id"],centerline={"start":{"x":0,"y":0},"end":{"x":100,"y":0}},wall_type="W1",classification="internal",thickness_mm=100,height_mm=3000,wall_version=versions["wall_version"],created_by=None,source_versions={})
    door=model_review_service.create(project_id=project["id"],floor_id=floor["id"],payload={"element_type":"door","geometry":{"x":40,"y":0,"width":10,"height":20,"rotation":0}},created_by=None)["record"]
    model_review_service.update_property(project_id=project["id"],floor_id=floor["id"],element_id=door["id"],property_name="width_mm",value=900,unit="mm",confirm=True,created_by=None)
    model_review_service.update_property(project_id=project["id"],floor_id=floor["id"],element_id=door["id"],property_name="height_mm",value=2100,unit="mm",confirm=True,created_by=None)
    with get_connection() as connection:
        connection.execute("INSERT INTO calibrations (id,project_id,floor_id,point_a_json,point_b_json,pixel_distance,real_distance,unit,units_per_pixel,source_crop_version,scale_version,status,created_at,updated_at,real_distance_mm,mm_per_pixel,crop_version) VALUES ('c',?,?, '{}','{}',100,10000,'mm',100,1,1,'calibrated','x','x',10000,100,1)",(project["id"],floor["id"]))
    walls_service.assign_opening(project["id"],floor["id"],wall["id"],door["id"],None)
    calculated=walls_service.calculate(project["id"],floor["id"],[wall["id"]])["walls"][0]
    assert calculated["gross_area_m2"]==30
    assert calculated["deduction_area_m2"]==1.89
    assert calculated["net_area_m2"]==28.11


def test_opening_cannot_cross_floors(foundation_db):
    from app.projects.project_service import project_service
    from app.workflow.service import workflow_service
    from app.walls.service import walls_service
    from app.walls.repo import walls_repository
    from app.workflow.repo import workflow_repository
    from app.database.session import get_connection
    from app.model_review.service import model_review_service
    project=project_service.create_project("Isolation")
    floors=[workflow_service.create_floor(project_id=project["id"],name=None,level_index=None,created_by=None) for _ in range(2)]
    with get_connection() as connection:versions=workflow_repository.increment_floor_version(connection,project["id"],floors[0]["id"],"wall_version")
    wall=walls_repository.create_wall(project_id=project["id"],floor_id=floors[0]["id"],centerline={"start":{"x":0,"y":0},"end":{"x":10,"y":0}},wall_type="W1",classification="internal",thickness_mm=100,height_mm=3000,wall_version=versions["wall_version"],created_by=None,source_versions={})
    door=model_review_service.create(project_id=project["id"],floor_id=floors[1]["id"],payload={"element_type":"door","geometry":{"x":1,"y":1,"width":2,"height":3,"rotation":0}},created_by=None)["record"]
    import pytest
    with pytest.raises(Exception):walls_service.assign_opening(project["id"],floors[0]["id"],wall["id"],door["id"],None)
