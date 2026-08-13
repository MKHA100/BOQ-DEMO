from __future__ import annotations

from uuid import uuid4
from app.database.session import get_connection, row_to_dict
from app.workflow.repo_base import dumps, loads, now_iso


class ReviewRepository:
    def upsert(self, *, project_id: str, floor_id: str, entity_type: str, entity_id: str, display_number: str | None, title: str, data: dict, status: str, critical: bool, source_version: int, review_version: int) -> dict:
        now = now_iso(); key = f"{entity_type}:{entity_id}"
        with get_connection() as connection:
            existing = connection.execute("SELECT id, created_at FROM review_items WHERE project_id=? AND entity_type=? AND entity_id=?", (project_id, entity_type, entity_id)).fetchone()
            item_id = existing["id"] if existing else str(uuid4()); created_at = existing["created_at"] if existing else now
            connection.execute(
                """
                INSERT INTO review_items (id,project_id,floor_id,entity_type,entity_id,display_number,title,data_json,status,critical,is_stale,source_version,review_version,created_at,updated_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,0,?,?,?,?)
                ON CONFLICT(project_id,entity_type,entity_id) DO UPDATE SET
                  floor_id=excluded.floor_id, display_number=excluded.display_number, title=excluded.title,
                  data_json=excluded.data_json, status=excluded.status, critical=excluded.critical,
                  is_stale=0, source_version=excluded.source_version, review_version=excluded.review_version,
                  updated_at=excluded.updated_at
                """,
                (item_id, project_id, floor_id, entity_type, entity_id, display_number, title, dumps(data), status, 1 if critical else 0, source_version, review_version, created_at, now),
            )
            row = connection.execute("SELECT * FROM review_items WHERE project_id=? AND entity_type=? AND entity_id=?", (project_id, entity_type, entity_id)).fetchone()
        return self._decode(row_to_dict(row) or {})

    def list(self, project_id: str, *, floor_id: str | None = None, category: str | None = None, needs_review: bool = False) -> list[dict]:
        clauses = ["project_id=?"]; values: list[object] = [project_id]
        if floor_id: clauses.append("floor_id=?"); values.append(floor_id)
        if category and category != "all": clauses.append("entity_type=?"); values.append(category)
        if needs_review: clauses.append("status='needs_review'")
        with get_connection() as connection:
            rows = connection.execute(f"SELECT * FROM review_items WHERE {' AND '.join(clauses)} ORDER BY floor_id, entity_type, display_number, title", values).fetchall()
        return [self._decode(row_to_dict(row) or {}) for row in rows]

    def get(self, project_id: str, item_id: str) -> dict | None:
        with get_connection() as connection:
            row = connection.execute("SELECT * FROM review_items WHERE project_id=? AND id=?", (project_id, item_id)).fetchone()
        return self._decode(row_to_dict(row) or {}) if row else None

    def delete_missing(self, project_id: str, valid_keys: set[tuple[str, str]]) -> None:
        with get_connection() as connection:
            rows = connection.execute("SELECT id,entity_type,entity_id FROM review_items WHERE project_id=?", (project_id,)).fetchall()
            for row in rows:
                if (row["entity_type"], row["entity_id"]) not in valid_keys:
                    connection.execute("DELETE FROM review_items WHERE id=?", (row["id"],))

    @staticmethod
    def _decode(record: dict) -> dict:
        result = dict(record)
        for key in list(result):
            if key.endswith("_json"): result[key[:-5]] = loads(result.pop(key))
        for key in ("critical", "is_stale"):
            if key in result: result[key] = bool(result[key])
        return result


review_repository = ReviewRepository()
