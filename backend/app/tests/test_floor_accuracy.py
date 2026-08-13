from __future__ import annotations


def test_room_semantics_special_areas():
    from app.floors.room_semantics import room_semantics
    assert room_semantics.classify("DN")["space_kind"] == "circulation"
    assert room_semantics.classify("DN")["include_in_boq"] is False
    assert room_semantics.classify("BALCONY")["space_kind"] == "external"
    assert room_semantics.classify("VOID")["include_in_boq"] is False
    assert room_semantics.normalize("MASTER BED ROOM") == "Master Bedroom"


def test_split_line_and_snap_geometry():
    from app.floors.line_builder import room_line_builder
    from app.floors.polygon_builder import room_polygon_builder
    prepared = room_line_builder.build(
        walls=[
            {"id": "a", "centerline": {"start": {"x": 0, "y": 0}, "end": {"x": 100, "y": 0}}, "thickness_mm": 10},
            {"id": "b", "centerline": {"start": {"x": 100, "y": 0}, "end": {"x": 100, "y": 80}}, "thickness_mm": 10},
        ], openings=[], mm_per_pixel=1,
    )
    points = [{"x": 5, "y": 5}, {"x": 95, "y": 5}, {"x": 95, "y": 75}, {"x": 5, "y": 75}]
    parts = room_polygon_builder.split_polygon_with_line(points, [{"x": 50, "y": -5}, {"x": 50, "y": 85}])
    assert len(parts) == 2
    snapped = room_polygon_builder.snap_polygon_to_walls(points, prepared, tolerance=10)
    assert len(snapped) >= 3


def test_accuracy_schema_is_idempotent(foundation_db):
    from app.database.migrations import run_migrations
    from app.database.session import get_connection
    with get_connection() as connection:
        run_migrations(connection)
        run_migrations(connection)
        room_columns = {row["name"] for row in connection.execute("PRAGMA table_info(rooms)").fetchall()}
        assert {"space_kind", "measurement_status", "is_finish_zone"}.issubset(room_columns)
        assert connection.execute("SELECT name FROM sqlite_master WHERE name='floor_dimension_observations'").fetchone()


def test_review_state_returns_saved_data_without_sync_refresh(foundation_db, monkeypatch):
    from app.projects.project_service import project_service
    from app.review.service import review_service
    project = project_service.create_project("Fast review")
    monkeypatch.setattr(review_service, "refresh", lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("sync refresh")))
    state = review_service.state(project)
    assert state["project_id"] == project["id"]
    assert "active_jobs" in state
