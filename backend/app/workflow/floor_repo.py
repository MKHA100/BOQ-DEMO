from __future__ import annotations

from typing import Any
from uuid import uuid4

from app.database.session import get_connection, row_to_dict
from app.workflow.constants import VERSION_LAYERS
from app.workflow.repo_base import dumps, loads, now_iso

class FloorRepositoryMixin:
    def ensure_project_versions(self, connection: Any, project_id: str) -> dict:
        row = connection.execute("SELECT * FROM project_versions WHERE project_id = ?", (project_id,)).fetchone()
        if row:
            return dict(row)
        now = now_iso()
        connection.execute(
            """
            INSERT INTO project_versions (
              project_id, document_version, schedule_version, specification_version,
              review_version, boq_version, created_at, updated_at
            ) VALUES (?, 0, 0, 0, 0, 0, ?, ?)
            """,
            (project_id, now, now),
        )
        return dict(connection.execute("SELECT * FROM project_versions WHERE project_id = ?", (project_id,)).fetchone())

    def ensure_floor_versions(self, connection: Any, project_id: str, floor_id: str) -> dict:
        row = connection.execute(
            "SELECT * FROM floor_versions WHERE project_id = ? AND floor_id = ?",
            (project_id, floor_id),
        ).fetchone()
        if row:
            return dict(row)
        now = now_iso()
        connection.execute(
            """
            INSERT INTO floor_versions (
              floor_id, project_id, crop_version, schedule_version, scale_version,
              element_version, wall_version, room_version, review_version, boq_version,
              created_at, updated_at
            ) VALUES (?, ?, 0, 0, 0, 0, 0, 0, 0, 0, ?, ?)
            """,
            (floor_id, project_id, now, now),
        )
        return dict(
            connection.execute(
                "SELECT * FROM floor_versions WHERE project_id = ? AND floor_id = ?",
                (project_id, floor_id),
            ).fetchone()
        )

    def increment_floor_version(self, connection: Any, project_id: str, floor_id: str, layer: str) -> dict:
        if layer not in VERSION_LAYERS:
            raise ValueError(f"Unsupported version layer: {layer}")
        self.ensure_floor_versions(connection, project_id, floor_id)
        now = now_iso()
        connection.execute(
            f"UPDATE floor_versions SET {layer} = {layer} + 1, updated_at = ? WHERE project_id = ? AND floor_id = ?",
            (now, project_id, floor_id),
        )
        return dict(
            connection.execute(
                "SELECT * FROM floor_versions WHERE project_id = ? AND floor_id = ?",
                (project_id, floor_id),
            ).fetchone()
        )

    def increment_project_version(self, connection: Any, project_id: str, layer: str) -> dict:
        allowed = {"document_version", "schedule_version", "specification_version", "review_version", "boq_version"}
        if layer not in allowed:
            raise ValueError(f"Unsupported project version layer: {layer}")
        self.ensure_project_versions(connection, project_id)
        now = now_iso()
        connection.execute(
            f"UPDATE project_versions SET {layer} = {layer} + 1, updated_at = ? WHERE project_id = ?",
            (now, project_id),
        )
        return dict(connection.execute("SELECT * FROM project_versions WHERE project_id = ?", (project_id,)).fetchone())

    def create_floor(
        self,
        connection: Any,
        *,
        project_id: str,
        name: str,
        level_index: int,
        created_by: str | None,
    ) -> dict:
        now = now_iso()
        floor_id = str(uuid4())
        connection.execute(
            """
            INSERT INTO floors (id, project_id, name, level_index, status, created_by, created_at, updated_at)
            VALUES (?, ?, ?, ?, 'not_ready', ?, ?, ?)
            """,
            (floor_id, project_id, name, level_index, created_by, now, now),
        )
        self.ensure_floor_versions(connection, project_id, floor_id)
        return dict(connection.execute("SELECT * FROM floors WHERE id = ?", (floor_id,)).fetchone())

    def list_floors(self, project_id: str) -> list[dict]:
        with get_connection() as connection:
            rows = connection.execute(
                """
                SELECT f.*, fv.crop_version, fv.schedule_version, fv.scale_version,
                       fv.element_version, fv.wall_version, fv.room_version,
                       fv.review_version, fv.boq_version
                FROM floors f
                LEFT JOIN floor_versions fv ON fv.floor_id = f.id
                WHERE f.project_id = ?
                ORDER BY f.level_index ASC
                """,
                (project_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def get_floor(self, connection: Any, project_id: str, floor_id: str) -> dict | None:
        return row_to_dict(
            connection.execute(
                "SELECT * FROM floors WHERE id = ? AND project_id = ?",
                (floor_id, project_id),
            ).fetchone()
        )

    def next_floor_index(self, connection: Any, project_id: str) -> int:
        row = connection.execute(
            "SELECT COALESCE(MAX(level_index), -1) + 1 AS next_index FROM floors WHERE project_id = ?",
            (project_id,),
        ).fetchone()
        return int(row["next_index"] if row else 0)

    def get_versions(self, connection: Any, project_id: str, floor_id: str | None = None) -> dict:
        project_versions = self.ensure_project_versions(connection, project_id)
        if not floor_id:
            return {
                key: int(value or 0)
                for key, value in project_versions.items()
                if key.endswith("_version")
            }
        floor_versions = self.ensure_floor_versions(connection, project_id, floor_id)
        return {
            key: int(value or 0)
            for key, value in floor_versions.items()
            if key.endswith("_version")
        }
