from __future__ import annotations


def _rectangle_walls(project_id, floor_id):
    from app.database.session import get_connection
    from app.workflow.repo import workflow_repository
    from app.walls.repo import walls_repository

    with get_connection() as connection:
        versions = workflow_repository.increment_floor_version(connection, project_id, floor_id, "wall_version")
        connection.execute("UPDATE floor_versions SET scale_version=1 WHERE floor_id=?", (floor_id,))
        connection.execute(
            "INSERT INTO calibrations (id,project_id,floor_id,point_a_json,point_b_json,pixel_distance,real_distance,unit,units_per_pixel,source_crop_version,scale_version,status,created_at,updated_at,real_distance_mm,mm_per_pixel,crop_version) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (f"cal-{floor_id}", project_id, floor_id, "{}", "{}", 100, 1000, "mm", 10, 1, 1, "calibrated", "x", "x", 1000, 10, 1),
        )
    for start, end in [
        ({"x": 0, "y": 0}, {"x": 100, "y": 0}),
        ({"x": 100, "y": 0}, {"x": 100, "y": 80}),
        ({"x": 100, "y": 80}, {"x": 0, "y": 80}),
        ({"x": 0, "y": 80}, {"x": 0, "y": 0}),
    ]:
        walls_repository.create_wall(
            project_id=project_id, floor_id=floor_id,
            centerline={"start": start, "end": end}, wall_type="W1",
            classification="external", thickness_mm=100, height_mm=3000,
            wall_version=versions["wall_version"], created_by=None, source_versions={},
        )


def test_user_confirmed_polygon_is_not_overwritten(foundation_db):
    from app.projects.project_service import project_service
    from app.workflow.service import workflow_service
    from app.floors.service import floors_service
    from app.floors.repo import floors_repository

    project = project_service.create_project("Protected room")
    floor = workflow_service.create_floor(project_id=project["id"], name=None, level_index=None, created_by=None)
    _rectangle_walls(project["id"], floor["id"])
    original = [{"x": 5, "y": 5}, {"x": 95, "y": 5}, {"x": 95, "y": 75}, {"x": 5, "y": 75}]
    room = floors_service.create(
        project["id"], floor["id"], {"points": original, "name": "Office", "floor_finish": "Tile"}, None
    )["record"]
    before = (floors_repository.get_room(project["id"], floor["id"], room["id"])["geometry"])["points"]

    floors_service.build_polygons(project["id"], floor["id"])
    after = floors_repository.get_room(project["id"], floor["id"], room["id"])
    assert after["geometry"]["points"] == before
    assert after["user_confirmed"] is True


def test_scale_dependency_recalculates_area_without_room_detection():
    from app.scale.service import SCALE_TASKS

    assert "rooms.calculate_areas" in SCALE_TASKS
    assert "vision.detect_rooms" not in SCALE_TASKS
    assert "rooms.build_polygons" not in SCALE_TASKS


def test_hybrid_floor_migration_repairs_partial_and_repeated_startup(foundation_db):
    from app.database.session import get_connection, init_db
    from app.floors.hybrid_schema import HYBRID_FLOOR_MIGRATION_VERSION

    with get_connection() as connection:
        connection.execute("DROP TABLE room_suggestions")
        connection.execute(
            "DELETE FROM schema_migrations WHERE version=?",
            (HYBRID_FLOOR_MIGRATION_VERSION,),
        )

    init_db()
    init_db()

    with get_connection() as connection:
        table = connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='room_suggestions'"
        ).fetchone()
        columns = {
            row["name"] for row in connection.execute("PRAGMA table_info(rooms)").fetchall()
        }
        version = connection.execute(
            "SELECT version FROM schema_migrations WHERE version=?",
            (HYBRID_FLOOR_MIGRATION_VERSION,),
        ).fetchone()
    assert table is not None
    assert {"detection_source", "model_verified", "excluded", "geometry_hash"}.issubset(columns)
    assert version is not None


def test_room_prepare_processor_enqueues_next_job(monkeypatch):
    from app.floors import jobs as floor_jobs

    monkeypatch.setattr(
        floor_jobs.floors_service,
        "prepare_lines",
        lambda project_id, floor_id: {
            "wall_lines": 4,
            "door_closures": 1,
            "prepared": {"large": "temporary"},
        },
    )
    calls = []

    def fake_enqueue(**kwargs):
        calls.append(kwargs)
        return ({"id": "job-build", "status": "pending"}, True)

    monkeypatch.setattr(floor_jobs.job_service, "enqueue", fake_enqueue)
    result = floor_jobs.prepare(
        {
            "project_id": "project-1",
            "floor_id": "floor-1",
            "payload_json": {},
            "input_versions_json": {"crop_version": 1, "wall_version": 2},
            "created_by": None,
        }
    )

    assert calls[0]["task_type"] == "rooms.build_polygons"
    assert result["next_job"]["id"] == "job-build"
    assert "prepared" not in result


def test_room_detection_continues_local_geometry_when_model_fails(monkeypatch):
    from app.floors import jobs as floor_jobs

    monkeypatch.setattr(
        floor_jobs.floors_service,
        "detect_room_suggestions",
        lambda project_id, floor_id: {"status": "failed", "suggestions": 0},
    )
    calls = []

    def fake_enqueue(**kwargs):
        calls.append(kwargs)
        return ({"id": "job-local", "status": "pending"}, True)

    monkeypatch.setattr(floor_jobs.job_service, "enqueue", fake_enqueue)
    result = floor_jobs.detect_rooms(
        {
            "project_id": "project-1",
            "floor_id": "floor-1",
            "payload_json": {},
            "input_versions_json": {"crop_version": 1},
            "created_by": None,
        }
    )

    assert calls[0]["task_type"] == "rooms.prepare_lines"
    assert result["next_job"]["id"] == "job-local"
    assert result["status"] == "failed"


def test_worker_startup_backfill_requeues_failed_room_analysis(monkeypatch):
    from app.floors.service import floors_service
    from app.floors.repo import floors_repository
    from app.jobs.job_service import job_service

    monkeypatch.setattr(
        floors_repository,
        "list_floors_needing_analysis",
        lambda: [
            {
                "project_id": "project-1",
                "floor_id": "floor-1",
                "crop_id": "crop-1",
                "crop_version": 1,
                "scale_version": 0,
                "element_version": 2,
                "wall_version": 3,
                "room_version": 0,
            }
        ],
    )
    monkeypatch.setattr(
        floors_service,
        "_enqueue_tasks",
        lambda *args, **kwargs: [
            {"id": "failed-job", "status": "failed", "created": False},
            {"id": "new-job", "status": "pending", "created": True},
        ],
    )
    monkeypatch.setattr(
        job_service,
        "requeue_job",
        lambda job_id: {"id": job_id, "status": "pending"},
    )

    result = floors_service.enqueue_missing_background_analyses()

    assert result["floors"] == 1
    assert result["scheduled"][0]["jobs"][0]["requeued"] is True
    assert result["scheduled"][0]["jobs"][0]["status"] == "pending"
