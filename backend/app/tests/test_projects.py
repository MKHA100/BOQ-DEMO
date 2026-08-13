from datetime import datetime, timezone

import pytest

from fastapi import HTTPException


def test_project_create_list_and_delete(foundation_db):
    from app.projects.project_service import project_service

    project = project_service.create_project("Harbour Office")
    assert project["name"] == "Harbour Office"
    assert project_service.get_project(project["id"])["status"] == "active"
    assert len(project_service.list_projects()) == 1
    project_service.delete_project(project["id"])
    assert project_service.list_projects() == []


def test_project_ownership_is_enforced(foundation_db):
    from app.database.session import get_connection
    from app.projects.project_service import project_service

    now = datetime.now(timezone.utc).isoformat()
    with get_connection() as connection:
        connection.execute(
            "INSERT INTO users (id,email,password_hash,role,status,created_at,updated_at) VALUES (?,?,?,?,?,?,?)",
            ("user-1", "one@example.com", "x", "member", "active", now, now),
        )
        connection.execute(
            "INSERT INTO users (id,email,password_hash,role,status,created_at,updated_at) VALUES (?,?,?,?,?,?,?)",
            ("user-2", "two@example.com", "x", "member", "active", now, now),
        )
    project = project_service.create_project("Private Project", user_id="user-1")

    with pytest.raises(HTTPException) as exc_info:
        project_service.get_project(project["id"], user_id="user-2")
    assert exc_info.value.status_code == 404
