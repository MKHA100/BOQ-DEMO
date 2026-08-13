from __future__ import annotations

from typing import Any

from app.database.session import get_connection, row_to_dict


PROJECT_SELECT = """
SELECT
    projects.id,
    projects.user_id,
    projects.organization_id,
    projects.name,
    projects.project_number,
    projects.client_name,
    projects.location,
    projects.description,
    projects.status,
    projects.archived_at,
    projects.created_at,
    projects.updated_at,
    organizations.name AS organization_name
FROM projects
LEFT JOIN organizations ON organizations.id = projects.organization_id
"""


class ProjectRepository:
    def create(self, project: dict[str, Any]) -> dict[str, Any]:
        with get_connection() as connection:
            connection.execute(
                """
                INSERT INTO projects (
                    id, user_id, organization_id, name, project_number,
                    client_name, location, description, status, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    project["id"],
                    project.get("user_id"),
                    project.get("organization_id"),
                    project["name"],
                    project.get("project_number"),
                    project.get("client_name"),
                    project.get("location"),
                    project.get("description"),
                    project["status"],
                    project["created_at"],
                    project["updated_at"],
                ),
            )
        return project

    def list(
        self,
        user_id: str | None,
        *,
        search: str | None = None,
        status: str | None = None,
        limit: int = 24,
        offset: int = 0,
    ) -> tuple[list[dict], int]:
        where, params = self._ownership_filter(user_id)
        clauses = [where]
        if search:
            query = f"%{search.strip().lower()}%"
            clauses.append(
                """
                (
                    LOWER(projects.name) LIKE ? OR
                    LOWER(COALESCE(projects.project_number, '')) LIKE ? OR
                    LOWER(COALESCE(projects.client_name, '')) LIKE ? OR
                    LOWER(COALESCE(projects.location, '')) LIKE ?
                )
                """
            )
            params.extend([query, query, query, query])
        if status:
            clauses.append("projects.status = ?")
            params.append(status)
        else:
            clauses.append("projects.status != 'archived'")

        where_sql = " WHERE " + " AND ".join(f"({clause})" for clause in clauses)
        with get_connection() as connection:
            count_row = connection.execute(
                f"SELECT COUNT(*) AS count FROM projects{where_sql}",
                tuple(params),
            ).fetchone()
            rows = connection.execute(
                f"{PROJECT_SELECT}{where_sql} ORDER BY projects.updated_at DESC LIMIT ? OFFSET ?",
                (*params, limit, offset),
            ).fetchall()
        return [dict(row) for row in rows], int(count_row["count"] if count_row else 0)

    def recent(self, user_id: str | None, limit: int = 5) -> list[dict]:
        where, params = self._ownership_filter(user_id)
        with get_connection() as connection:
            rows = connection.execute(
                f"{PROJECT_SELECT} WHERE ({where}) AND projects.status != 'archived' ORDER BY projects.updated_at DESC LIMIT ?",
                (*params, limit),
            ).fetchall()
        return [dict(row) for row in rows]

    def count(self, user_id: str | None) -> int:
        where, params = self._ownership_filter(user_id)
        with get_connection() as connection:
            row = connection.execute(
                f"SELECT COUNT(*) AS count FROM projects WHERE ({where}) AND status != 'archived'",
                tuple(params),
            ).fetchone()
        return int(row["count"] if row else 0)

    def get(self, project_id: str, user_id: str | None) -> dict | None:
        where, params = self._ownership_filter(user_id)
        with get_connection() as connection:
            row = connection.execute(
                f"{PROJECT_SELECT} WHERE projects.id = ? AND ({where})",
                (project_id, *params),
            ).fetchone()
        return row_to_dict(row)

    def update(self, project_id: str, user_id: str | None, updates: dict[str, Any]) -> dict | None:
        if not updates:
            return self.get(project_id, user_id)
        where, ownership_params = self._ownership_filter(user_id)
        set_clause = ", ".join(f"{column} = ?" for column in updates)
        with get_connection() as connection:
            connection.execute(
                f"UPDATE projects SET {set_clause} WHERE id = ? AND ({where})",
                (*updates.values(), project_id, *ownership_params),
            )
        return self.get(project_id, user_id)

    def delete(self, project_id: str, user_id: str | None) -> None:
        where, params = self._ownership_filter(user_id)
        with get_connection() as connection:
            connection.execute(
                f"DELETE FROM projects WHERE id = ? AND ({where})",
                (project_id, *params),
            )

    @staticmethod
    def _ownership_filter(user_id: str | None) -> tuple[str, list[str]]:
        if not user_id:
            return "1 = 1", []
        return (
            """
            (
                projects.user_id = ? OR
                projects.organization_id IN (
                    SELECT organization_id
                    FROM organization_memberships
                    WHERE user_id = ? AND status = 'active'
                )
            )
            """,
            [user_id, user_id],
        )
