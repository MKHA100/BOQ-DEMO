from __future__ import annotations

from uuid import uuid4


def _drain(*task_types: str) -> None:
    from app.jobs.worker import process_one

    while process_one("integration-test", task_types):
        pass


def _project_floor(name: str = "Integrated Project"):
    from app.database.session import get_connection
    from app.projects.project_service import project_service
    from app.workflow.service import workflow_service

    project = project_service.create_project(name)
    floor = workflow_service.create_floor(project_id=project["id"], name=None, level_index=None, created_by=None)
    with get_connection() as connection:
        connection.execute("UPDATE floors SET wall_height_mm = 3000 WHERE id = ?", (floor["id"],))
        connection.execute("UPDATE floor_versions SET scale_version = 1 WHERE floor_id = ?", (floor["id"],))
        connection.execute(
            """
            INSERT INTO calibrations (
              id, project_id, floor_id, point_a_json, point_b_json, pixel_distance,
              real_distance, unit, units_per_pixel, source_crop_version, scale_version,
              status, created_at, updated_at, real_distance_mm, mm_per_pixel, crop_version
            ) VALUES (?, ?, ?, '{}', '{}', 100, 10000, 'mm', 100, 1, 1,
                      'calibrated', 'x', 'x', 10000, 100, 1)
            """,
            (str(uuid4()), project["id"], floor["id"]),
        )
    return project, floor


def _clear_jobs() -> None:
    from app.database.session import get_connection

    with get_connection() as connection:
        connection.execute("DELETE FROM job_runs")


def test_door_dimension_change_updates_wall_review_and_boq(foundation_db):
    from app.boq.service import boq_service
    from app.database.session import get_connection
    from app.model_review.service import model_review_service
    from app.review.service import review_service
    from app.walls.repo import walls_repository
    from app.walls.service import walls_service
    from app.workflow.repo import workflow_repository

    project, floor = _project_floor("Door Dependency")
    with get_connection() as connection:
        versions = workflow_repository.increment_floor_version(connection, project["id"], floor["id"], "wall_version")
    wall = walls_repository.create_wall(
        project_id=project["id"], floor_id=floor["id"],
        centerline={"start": {"x": 0, "y": 0}, "end": {"x": 100, "y": 0}},
        wall_type="W1", classification="external", thickness_mm=200, height_mm=3000,
        wall_version=int(versions["wall_version"]), created_by=None, source_versions={},
    )
    door = model_review_service.create(
        project_id=project["id"], floor_id=floor["id"],
        payload={"element_type": "door", "geometry": {"x": 40, "y": 0, "width": 10, "height": 20, "rotation": 0}, "type_code": "D1"},
        created_by=None,
    )["record"]
    model_review_service.update_property(project_id=project["id"], floor_id=floor["id"], element_id=door["id"], property_name="width_mm", value=900, unit="mm", confirm=True, created_by=None)
    model_review_service.update_property(project_id=project["id"], floor_id=floor["id"], element_id=door["id"], property_name="height_mm", value=2100, unit="mm", confirm=True, created_by=None)
    walls_service.assign_opening(project["id"], floor["id"], wall["id"], door["id"], None)
    with get_connection() as connection:
        connection.execute("UPDATE elements SET status='confirmed', user_confirmed=1 WHERE id=?", (door["id"],))
        connection.execute("UPDATE walls SET status='confirmed', user_confirmed=1 WHERE id=?", (wall["id"],))
    walls_service.calculate(project["id"], floor["id"], [wall["id"]])
    review_service.refresh(project["id"])
    boq_service.refresh(project["id"])
    _clear_jobs()

    result = model_review_service.update_property(
        project_id=project["id"], floor_id=floor["id"], element_id=door["id"],
        property_name="width_mm", value=1000, unit="mm", confirm=True, created_by=None,
    )
    assert {job["task_type"] for job in result["jobs"]} == {"walls.recalculate_deduction", "review.refresh", "boq.refresh"}
    _drain("walls.recalculate_deduction")
    _drain("review.refresh")
    _drain("boq.refresh")

    changed_wall = walls_repository.get_wall(project["id"], floor["id"], wall["id"])
    assert changed_wall is not None
    assert changed_wall["deduction_area_m2"] == 2.1
    assert changed_wall["net_area_m2"] == 27.9
    review_item = next(item for item in review_service.state(project)["items"] if item["entity_id"] == door["id"])
    assert review_item["data"]["width_mm"] == 1000
    boq_state = boq_service.state(project)
    assert next(row for row in boq_state["rows"] if row["entity_type"] == "wall_external")["quantity"] == 27.9


def test_wall_geometry_change_recalculates_only_touching_rooms(foundation_db):
    from app.database.session import get_connection
    from app.floors.repo import floors_repository
    from app.walls.repo import walls_repository
    from app.walls.service import walls_service
    from app.workflow.repo import workflow_repository

    project, floor = _project_floor("Wall Room Dependency")
    with get_connection() as connection:
        versions = workflow_repository.increment_floor_version(connection, project["id"], floor["id"], "wall_version")
    wall = walls_repository.create_wall(
        project_id=project["id"], floor_id=floor["id"],
        centerline={"start": {"x": 0, "y": 0}, "end": {"x": 100, "y": 0}},
        wall_type="W1", classification="internal", thickness_mm=100, height_mm=3000,
        wall_version=int(versions["wall_version"]), created_by=None, source_versions={},
    )
    with get_connection() as connection:
        room_versions = workflow_repository.increment_floor_version(connection, project["id"], floor["id"], "room_version")
    touching = floors_repository.create_room(
        project_id=project["id"], floor_id=floor["id"],
        points=[{"x": 0, "y": 0}, {"x": 40, "y": 0}, {"x": 40, "y": 40}, {"x": 0, "y": 40}],
        generated=False, room_version=int(room_versions["room_version"]), created_by=None,
        wall_ids=[wall["id"]], name="Office",
    )
    untouched = floors_repository.create_room(
        project_id=project["id"], floor_id=floor["id"],
        points=[{"x": 50, "y": 50}, {"x": 80, "y": 50}, {"x": 80, "y": 80}, {"x": 50, "y": 80}],
        generated=False, room_version=int(room_versions["room_version"]), created_by=None,
        wall_ids=[], name="Store",
    )
    with get_connection() as connection:
        connection.execute("UPDATE rooms SET floor_finish='Tile', status='confirmed', user_confirmed=1 WHERE id IN (?,?)", (touching["id"], untouched["id"]))
    untouched_before = floors_repository.get_room(project["id"], floor["id"], untouched["id"])
    _clear_jobs()

    walls_service.update(
        project_id=project["id"], floor_id=floor["id"], wall_id=wall["id"],
        payload={"centerline": {"start": {"x": 0, "y": 0}, "end": {"x": 120, "y": 0}}, "classification": "external"},
        created_by=None,
    )
    _drain("rooms.rebuild_touching")
    current_touching = floors_repository.get_room(project["id"], floor["id"], touching["id"])
    current_untouched = floors_repository.get_room(project["id"], floor["id"], untouched["id"])
    assert current_touching is not None and current_touching["geometry_status"] == "needs_review"
    assert current_touching["status"] == "needs_review"
    assert current_untouched is not None and untouched_before is not None
    assert current_untouched["updated_at"] == untouched_before["updated_at"]
    assert current_untouched["room_version"] == untouched_before["room_version"]


def test_room_edit_updates_area_review_and_boq(foundation_db):
    from app.boq.service import boq_service
    from app.floors.service import floors_service
    from app.review.service import review_service

    project, floor = _project_floor("Room Dependency")
    room = floors_service.create(
        project["id"], floor["id"],
        {"points": [{"x": 0, "y": 0}, {"x": 20, "y": 0}, {"x": 20, "y": 20}, {"x": 0, "y": 20}], "name": "Office"},
        None,
    )["record"]
    floors_service.update(project["id"], floor["id"], room["id"], {"floor_type_code": "F1", "floor_finish": "Tile", "review_status": "confirmed"}, None)
    review_service.refresh(project["id"])
    boq_service.refresh(project["id"])
    _clear_jobs()

    floors_service.update(
        project["id"], floor["id"], room["id"],
        {"points": [{"x": 0, "y": 0}, {"x": 40, "y": 0}, {"x": 40, "y": 20}, {"x": 0, "y": 20}], "floor_finish": "Vinyl", "review_status": "confirmed"},
        None,
    )
    _drain("review.refresh")
    _drain("boq.refresh")
    saved = floors_service.get_state(project, floor["id"])["rooms"][0]
    assert saved["area_m2"] == 8.0
    review_item = next(item for item in review_service.state(project)["items"] if item["entity_id"] == room["id"])
    assert review_item["data"]["area_m2"] == 8.0
    floor_row = next(row for row in boq_service.state(project)["rows"] if row["entity_type"] == "floor")
    assert floor_row["quantity"] == 8.0
    assert "Vinyl" in floor_row["description"]


def test_scale_change_is_floor_scoped_and_preserves_detections(foundation_db):
    from app.database.session import get_connection
    from app.model_review.service import model_review_service
    from app.projects.project_service import project_service
    from app.scale.service import scale_service
    from app.workflow.repo_base import now_iso
    from app.workflow.service import workflow_service

    project = project_service.create_project("Scale Isolation")
    floors = [workflow_service.create_floor(project_id=project["id"], name=None, level_index=None, created_by=None) for _ in range(2)]
    now = now_iso()
    with get_connection() as connection:
        document_id = str(uuid4()); page_id = str(uuid4())
        connection.execute("INSERT INTO documents (id,project_id,document_type,file_name,mime_type,storage_key,size_bytes,status,version,created_at,updated_at) VALUES (?,?,?,?,?,?,0,'ready',1,?,?)", (document_id,project["id"],"source","plans.pdf","application/pdf","plans.pdf",now,now))
        connection.execute("INSERT INTO document_pages (id,project_id,document_id,page_number,width_points,height_points,status,version,created_at,updated_at) VALUES (?,?,?,?,600,400,'ready',1,?,?)", (page_id,project["id"],document_id,1,now,now))
        for floor in floors:
            connection.execute("UPDATE floor_versions SET crop_version=1 WHERE floor_id=?", (floor["id"],))
            connection.execute("INSERT INTO floor_crops (id,project_id,floor_id,document_id,document_page_id,coordinates_json,source_width,source_height,crop_version,status,is_current,created_at,updated_at,source_page_number,original_page_width,original_page_height,rotation,render_dpi) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (str(uuid4()),project["id"],floor["id"],document_id,page_id,"{}",600,400,1,"ready",1,now,now,1,600,400,0,144))
    detected = model_review_service.create(project_id=project["id"], floor_id=floors[1]["id"], payload={"element_type":"door","geometry":{"x":1,"y":1,"width":3,"height":4,"rotation":0},"type_code":"D1"}, created_by=None)["record"]
    _clear_jobs()

    result = scale_service.save(project_id=project["id"], floor_id=floors[0]["id"], payload={"point_a":{"x":0,"y":0},"point_b":{"x":100,"y":0},"real_distance":5,"unit":"m","crop_version":1}, confirmed_by=None)
    assert {job["floor_id"] for job in result["jobs"]} == {floors[0]["id"]}
    assert not any(job["task_type"].startswith("vision.") for job in result["jobs"])
    with get_connection() as connection:
        versions = {row["floor_id"]: row["scale_version"] for row in connection.execute("SELECT floor_id,scale_version FROM floor_versions WHERE project_id=?", (project["id"],)).fetchall()}
        preserved = connection.execute("SELECT id,type_code,geometry_json FROM elements WHERE id=?", (detected["id"],)).fetchone()
    assert versions[floors[0]["id"]] == 1
    assert versions[floors[1]["id"]] == 0
    assert preserved is not None and preserved["type_code"] == "D1"


def test_health_readiness_and_performance_headers(foundation_db):
    from fastapi.testclient import TestClient
    from app.main import app

    client = TestClient(app)
    response = client.get("/health/ready")
    assert response.status_code == 200
    assert response.json()["status"] == "ready"
    assert float(response.headers["X-Process-Time-Ms"]) >= 0
    assert int(response.headers["X-DB-Query-Count"]) >= 1
    assert "app;dur=" in response.headers["Server-Timing"]


def test_worker_skips_superseded_floor_job_and_recovers_expired_lease(foundation_db):
    import json
    from app.database.session import get_connection
    from app.jobs.job_repository import job_repository
    from app.jobs.job_service import job_service
    from app.jobs.worker import process_one
    from app.projects.project_service import project_service
    from app.workflow.service import workflow_service

    project = project_service.create_project("Worker Recovery")
    floor = workflow_service.create_floor(project_id=project["id"], name=None, level_index=None, created_by=None)
    job, created = job_service.enqueue(
        task_type="rooms.prepare_geometry",
        project_id=project["id"],
        floor_id=floor["id"],
        entity_id=floor["id"],
        payload={"floor_id": floor["id"]},
        input_versions={"scale_version": 1},
        created_by=None,
    )
    assert created is True
    with get_connection() as connection:
        connection.execute("UPDATE floor_versions SET scale_version=2 WHERE floor_id=?", (floor["id"],))
    completed = process_one("superseded-worker", ["rooms.prepare_geometry"])
    assert completed is not None
    assert json.loads(completed["result_json"])["superseded"] is True

    retry_job, _ = job_service.enqueue(
        task_type="review.refresh",
        project_id=project["id"],
        floor_id=floor["id"],
        entity_id="lease-test",
        payload={"floor_id": floor["id"]},
        input_versions={"review_version": 1},
        created_by=None,
    )
    claimed = job_repository.claim_next_job(worker_id="worker-a", task_types=["review.refresh"], lease_seconds=15)
    assert claimed is not None and claimed["id"] == retry_job["id"]
    with get_connection() as connection:
        connection.execute("UPDATE job_runs SET lease_expires_at='2000-01-01T00:00:00+00:00' WHERE id=?", (retry_job["id"],))
    assert job_repository.release_expired_leases() == 1
    recovered = job_repository.claim_next_job(worker_id="worker-b", task_types=["review.refresh"], lease_seconds=15)
    assert recovered is not None and recovered["id"] == retry_job["id"]
