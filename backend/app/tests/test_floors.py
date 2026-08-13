from __future__ import annotations


def setup_rectangle():
    from app.projects.project_service import project_service
    from app.workflow.service import workflow_service
    from app.workflow.repo import workflow_repository
    from app.walls.repo import walls_repository
    from app.database.session import get_connection
    project = project_service.create_project("Room Test")
    floor = workflow_service.create_floor(project_id=project["id"], name=None, level_index=None, created_by=None)
    with get_connection() as connection:
        versions = workflow_repository.increment_floor_version(connection, project["id"], floor["id"], "wall_version")
        connection.execute("UPDATE floor_versions SET scale_version=1 WHERE floor_id=?", (floor["id"],))
        connection.execute("INSERT INTO calibrations (id,project_id,floor_id,point_a_json,point_b_json,pixel_distance,real_distance,unit,units_per_pixel,source_crop_version,scale_version,status,created_at,updated_at,real_distance_mm,mm_per_pixel,crop_version) VALUES ('room-cal',?,?, '{}','{}',100,1000,'mm',10,1,1,'calibrated','x','x',1000,10,1)", (project["id"], floor["id"]))
    lines = [
        ({"x":0,"y":0},{"x":100,"y":0}), ({"x":100,"y":0},{"x":100,"y":80}),
        ({"x":100,"y":80},{"x":0,"y":80}), ({"x":0,"y":80},{"x":0,"y":0}),
    ]
    for start,end in lines:
        walls_repository.create_wall(project_id=project["id"],floor_id=floor["id"],centerline={"start":start,"end":end},wall_type="W1",classification="external",thickness_mm=100,height_mm=3000,wall_version=versions["wall_version"],created_by=None,source_versions={})
    return project,floor


def test_automatic_polygonization_and_measurement(foundation_db):
    from app.floors.service import floors_service
    project,floor=setup_rectangle()
    result=floors_service.build_polygons(project["id"],floor["id"])
    assert result["created"] >= 1
    room=result["rooms"][0]
    # Quantity follows the inside wall faces: 90 px × 70 px at 10 mm/px.
    assert room["area_m2"] == 0.63
    assert room["perimeter_m"] == 3.2


def test_valid_system_room_does_not_require_review_only_for_missing_finish(foundation_db):
    from app.floors.repo import floors_repository
    from app.floors.service import floors_service

    project, floor = setup_rectangle()
    built = floors_service.build_polygons(project["id"], floor["id"])
    room = built["rooms"][0]
    floor_row = floors_repository.get_floor_row(project["id"], floor["id"])
    floors_repository.update_room(
        project["id"], floor["id"], room["id"],
        {"name": "Bedroom", "room_type": "Bedroom", "label_source": "vector"},
        int(floor_row["room_version"]), confirmed=False,
    )

    floors_service.calculate(project["id"], floor["id"], [room["id"]])
    checked = floors_repository.get_room(project["id"], floor["id"], room["id"])

    assert checked["floor_finish"] is None
    assert checked["measurement_status"] == "correct"
    assert checked["status"] == "confirmed"
    assert checked["user_confirmed"] is False


def test_manual_room_is_floor_scoped(foundation_db):
    from app.projects.project_service import project_service
    from app.workflow.service import workflow_service
    from app.floors.service import floors_service
    project=project_service.create_project("Room Floors")
    first=workflow_service.create_floor(project_id=project["id"],name=None,level_index=None,created_by=None)
    second=workflow_service.create_floor(project_id=project["id"],name=None,level_index=None,created_by=None)
    created=floors_service.create(project["id"],first["id"],{"points":[{"x":0,"y":0},{"x":20,"y":0},{"x":20,"y":20},{"x":0,"y":20}],"name":"Office"},None)["record"]
    assert created["floor_id"] == first["id"]
    assert floors_service.get_state(project,second["id"])["rooms"] == []


def test_room_edit_split_merge_and_restore(foundation_db):
    from app.floors.service import floors_service
    project,floor=setup_rectangle()
    room=floors_service.create(project["id"],floor["id"],{"points":[{"x":0,"y":0},{"x":40,"y":0},{"x":40,"y":40},{"x":0,"y":40}],"name":"Office"},None)["record"]
    updated=floors_service.update(project["id"],floor["id"],room["id"],{"floor_finish":"Tile","review_status":"confirmed"},None)["record"]
    assert updated["floor_finish"] == "Tile"
    split=floors_service.split(project["id"],floor["id"],room["id"],"vertical",0.5,None)
    assert len(split["rooms"]) == 2
    merged=floors_service.merge(project["id"],floor["id"],split["rooms"][0]["id"],split["rooms"][1]["id"],None)
    assert merged["room"]["id"] == room["id"]
