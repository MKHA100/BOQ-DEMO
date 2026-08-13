def test_foundation_schema_contains_canonical_domain(foundation_db):
    from app.database.session import get_connection

    expected = {
        "projects",
        "documents",
        "document_pages",
        "floors",
        "floor_crops",
        "schedule_files",
        "specification_files",
        "calibrations",
        "elements",
        "element_properties",
        "element_relations",
        "walls",
        "rooms",
        "review_issues",
        "quantity_snapshots",
        "boqs",
        "boq_rows",
        "job_runs",
        "outbox_events",
        "project_versions",
        "floor_versions",
    }
    with get_connection() as connection:
        rows = connection.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    names = {row["name"] for row in rows}
    assert expected.issubset(names)
