from __future__ import annotations

from typing import Any
from uuid import uuid4

from app.database.session import get_connection, row_to_dict
from app.workflow.constants import VERSION_LAYERS
from app.workflow.repo_base import dumps, loads, now_iso

class EventRepositoryMixin:
    def upsert_review_issue(
        self,
        connection: Any,
        *,
        project_id: str,
        floor_id: str | None,
        entity_type: str,
        entity_id: str | None,
        issue_type: str,
        title: str,
        detail: str | None,
        suggestion: dict | None,
        source: str | None,
        review_version: int,
    ) -> dict:
        now = now_iso()
        existing = connection.execute(
            """
            SELECT * FROM review_issues
            WHERE project_id = ? AND entity_type = ? AND entity_id = ? AND issue_type = ?
              AND status IN ('needs_review', 'not_ready')
            ORDER BY created_at DESC LIMIT 1
            """,
            (project_id, entity_type, entity_id, issue_type),
        ).fetchone()
        if existing:
            connection.execute(
                """
                UPDATE review_issues
                SET floor_id = ?, title = ?, detail = ?, suggestion_json = ?, source = ?,
                    status = 'needs_review', review_version = ?, updated_at = ?
                WHERE id = ?
                """,
                (floor_id, title, detail, dumps(suggestion) if suggestion is not None else None, source, review_version, now, existing["id"]),
            )
            issue_id = existing["id"]
        else:
            issue_id = str(uuid4())
            connection.execute(
                """
                INSERT INTO review_issues (
                  id, project_id, floor_id, entity_type, entity_id, issue_type, title,
                  detail, severity, status, suggestion_json, source, review_version,
                  created_at, updated_at, resolved_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'medium', 'needs_review', ?, ?, ?, ?, ?, NULL)
                """,
                (
                    issue_id,
                    project_id,
                    floor_id,
                    entity_type,
                    entity_id,
                    issue_type,
                    title,
                    detail,
                    dumps(suggestion) if suggestion is not None else None,
                    source,
                    review_version,
                    now,
                    now,
                ),
            )
        return row_to_dict(connection.execute("SELECT * FROM review_issues WHERE id = ?", (issue_id,)).fetchone()) or {}

    def create_outbox_event(
        self,
        connection: Any,
        *,
        project_id: str,
        floor_id: str | None,
        event_type: str,
        entity_type: str | None,
        entity_id: str | None,
        dedupe_key: str,
        payload: dict,
    ) -> dict:
        existing = connection.execute("SELECT * FROM outbox_events WHERE dedupe_key = ?", (dedupe_key,)).fetchone()
        if existing:
            return dict(existing)
        now = now_iso()
        event_id = str(uuid4())
        connection.execute(
            """
            INSERT INTO outbox_events (
              id, project_id, floor_id, event_type, entity_type, entity_id,
              dedupe_key, payload_json, status, attempts, available_at,
              locked_by, locked_at, published_at, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'pending', 0, ?, NULL, NULL, NULL, ?, ?)
            """,
            (
                event_id,
                project_id,
                floor_id,
                event_type,
                entity_type,
                entity_id,
                dedupe_key,
                dumps(payload),
                now,
                now,
                now,
            ),
        )
        return dict(connection.execute("SELECT * FROM outbox_events WHERE id = ?", (event_id,)).fetchone())

    def mark_outbox_published(self, event_id: str) -> None:
        now = now_iso()
        with get_connection() as connection:
            connection.execute(
                "UPDATE outbox_events SET status = 'published', published_at = ?, updated_at = ? WHERE id = ?",
                (now, now, event_id),
            )
