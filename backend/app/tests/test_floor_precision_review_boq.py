def test_precision_migration_adds_history_and_cutouts(foundation_db):
    from app.database.session import get_connection
    with get_connection() as connection:
        columns = {row["name"] for row in connection.execute("PRAGMA table_info(rooms)").fetchall()}
        assert {"shape_type", "regularized_geometry_json", "user_edited"}.issubset(columns)
        assert connection.execute("SELECT name FROM sqlite_master WHERE name='room_geometry_revisions'").fetchone()
        assert connection.execute("SELECT name FROM sqlite_master WHERE name='room_cutouts'").fetchone()
