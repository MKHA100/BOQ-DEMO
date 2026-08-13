from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from app.core.errors import bad_request, not_found
from app.database.session import get_connection
from app.projects.project_repository import ProjectRepository
from app.workflow.repo import workflow_repository


ALLOWED_PROJECT_STATUSES = {"active", "on_hold", "completed", "archived"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clean_optional(value: str | None) -> str | None:
    if value is None:
        return None
    clean = value.strip()
    return clean or None


class ProjectService:
    def __init__(self) -> None:
        self.repository = ProjectRepository()

    def create_project(self, payload: dict[str, Any] | str, user_id: str | None = None) -> dict:
        if isinstance(payload, str):
            payload = {"name": payload}
        name = str(payload.get("name") or "").strip()
        if not name:
            raise bad_request("Project name is required.")

        organization_id = self._primary_organization_id(user_id)
        now = _now()
        project = {
            "id": str(uuid4()),
            "user_id": user_id,
            "organization_id": organization_id,
            "name": name,
            "project_number": _clean_optional(payload.get("project_number")),
            "client_name": _clean_optional(payload.get("client_name")),
            "location": _clean_optional(payload.get("location")),
            "description": _clean_optional(payload.get("description")),
            "status": "active",
            "created_at": now,
            "updated_at": now,
        }
        self._ensure_project_limit(organization_id)
        self.repository.create(project)
        with get_connection() as connection:
            workflow_repository.ensure_project_versions(connection, project["id"])
            self._increment_project_usage(connection, organization_id, now)
            self._write_audit(connection, project, user_id, "project.created")
        return self.get_project(project["id"], user_id)

    def list_projects(self, user_id: str | None = None) -> list[dict]:
        projects, _ = self.repository.list(user_id, limit=100, offset=0)
        return projects

    def search_projects(
        self,
        user_id: str,
        *,
        search: str | None = None,
        status: str | None = None,
        limit: int = 24,
        offset: int = 0,
    ) -> tuple[list[dict], int]:
        if status and status not in ALLOWED_PROJECT_STATUSES:
            raise bad_request("Invalid project status.")
        return self.repository.list(
            user_id,
            search=search,
            status=status,
            limit=max(1, min(limit, 100)),
            offset=max(0, offset),
        )

    def recent_projects(self, user_id: str, limit: int = 5) -> list[dict]:
        return self.repository.recent(user_id, max(1, min(limit, 10)))

    def project_count(self, user_id: str) -> int:
        return self.repository.count(user_id)

    def get_project(self, project_id: str, user_id: str | None = None) -> dict:
        project = self.repository.get(project_id, user_id)
        if not project:
            raise not_found("Project not found.")
        return project

    def update_project(self, project_id: str, payload: dict[str, Any], user_id: str | None = None) -> dict:
        existing = self.get_project(project_id, user_id)
        updates: dict[str, Any] = {}
        for field in ("name", "project_number", "client_name", "location", "description"):
            if field not in payload:
                continue
            value = payload[field]
            if field == "name":
                value = str(value or "").strip()
                if not value:
                    raise bad_request("Project name is required.")
            else:
                value = _clean_optional(value)
            updates[field] = value
        if "status" in payload and payload["status"] is not None:
            status = str(payload["status"])
            if status not in ALLOWED_PROJECT_STATUSES:
                raise bad_request("Invalid project status.")
            updates["status"] = status
            updates["archived_at"] = _now() if status == "archived" else None
        updates["updated_at"] = _now()
        project = self.repository.update(project_id, user_id, updates)
        if not project:
            raise not_found("Project not found.")
        with get_connection() as connection:
            self._write_audit(connection, project, user_id, "project.updated", {"changes": list(updates)})
        return project

    def delete_project(self, project_id: str, user_id: str | None = None) -> None:
        project = self.get_project(project_id, user_id)
        self.repository.delete(project_id, user_id)
        with get_connection() as connection:
            self._write_audit(connection, project, user_id, "project.deleted")

    def _primary_organization_id(self, user_id: str | None) -> str | None:
        if not user_id:
            return None
        with get_connection() as connection:
            row = connection.execute(
                """
                SELECT organization_id
                FROM organization_memberships
                WHERE user_id = ? AND status = 'active'
                ORDER BY created_at ASC
                LIMIT 1
                """,
                (user_id,),
            ).fetchone()
        return row["organization_id"] if row else None

    def _ensure_project_limit(self, organization_id: str | None) -> None:
        if not organization_id:
            return
        with get_connection() as connection:
            org = connection.execute(
                "SELECT project_limit FROM organizations WHERE id = ?",
                (organization_id,),
            ).fetchone()
            count = connection.execute(
                "SELECT COUNT(*) AS count FROM projects WHERE organization_id = ? AND status != 'archived'",
                (organization_id,),
            ).fetchone()
        if org and int(org["project_limit"] or 0) > 0 and int(count["count"] or 0) >= int(org["project_limit"]):
            raise bad_request("The organization project limit has been reached.")

    @staticmethod
    def _increment_project_usage(connection: Any, organization_id: str | None, now: str) -> None:
        if not organization_id:
            return
        period_key = datetime.now(timezone.utc).strftime("%Y-%m")
        connection.execute(
            """
            INSERT INTO usage_counters
                (id, organization_id, period_key, projects_created, updated_at)
            VALUES (?, ?, ?, 1, ?)
            ON CONFLICT(organization_id, period_key) DO UPDATE SET
                projects_created = usage_counters.projects_created + 1,
                updated_at = excluded.updated_at
            """,
            (str(uuid4()), organization_id, period_key, now),
        )

    @staticmethod
    def _write_audit(
        connection: Any,
        project: dict,
        user_id: str | None,
        action: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        import json

        connection.execute(
            """
            INSERT INTO audit_logs
                (id, organization_id, user_id, action, entity_type, entity_id, metadata_json, created_at)
            VALUES (?, ?, ?, ?, 'project', ?, ?, ?)
            """,
            (
                str(uuid4()),
                project.get("organization_id"),
                user_id,
                action,
                project["id"],
                json.dumps(metadata or {"name": project.get("name")}),
                _now(),
            ),
        )


project_service = ProjectService()
