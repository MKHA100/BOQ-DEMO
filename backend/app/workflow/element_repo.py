from __future__ import annotations

from typing import Any
from uuid import uuid4

from app.database.session import get_connection, row_to_dict
from app.workflow.constants import VERSION_LAYERS
from app.workflow.repo_base import dumps, loads, now_iso

class ElementRepositoryMixin:
    def create_element(
        self,
        connection: Any,
        *,
        project_id: str,
        floor_id: str,
        element_type: str,
        type_code: str | None,
        geometry: dict,
        source: str,
        confidence: float | None,
        status: str,
        element_version: int,
        created_by: str | None,
        source_versions: dict,
    ) -> dict:
        now = now_iso()
        element_id = str(uuid4())
        connection.execute(
            """
            INSERT INTO elements (
              id, project_id, floor_id, element_type, type_code, geometry_json, source,
              confidence, status, excluded, user_confirmed, measurement_status,
              element_version, source_versions_json, created_by, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 0, 'not_ready', ?, ?, ?, ?, ?)
            """,
            (
                element_id,
                project_id,
                floor_id,
                element_type,
                type_code,
                dumps(geometry),
                source,
                confidence,
                status,
                element_version,
                dumps(source_versions),
                created_by,
                now,
                now,
            ),
        )
        return self.get_element(connection, project_id, element_id) or {}

    def get_element(self, connection: Any, project_id: str, element_id: str) -> dict | None:
        row = connection.execute(
            "SELECT * FROM elements WHERE id = ? AND project_id = ?",
            (element_id, project_id),
        ).fetchone()
        return row_to_dict(row)

    def get_element_property(self, connection: Any, element_id: str, property_name: str) -> dict | None:
        return row_to_dict(
            connection.execute(
                "SELECT * FROM element_properties WHERE element_id = ? AND property_name = ?",
                (element_id, property_name),
            ).fetchone()
        )

    def upsert_element_property(
        self,
        connection: Any,
        *,
        project_id: str,
        floor_id: str,
        element_id: str,
        property_name: str,
        value: Any,
        unit: str | None,
        source: str,
        source_priority: int,
        is_confirmed: bool,
        element_version: int,
        created_by: str | None,
    ) -> dict:
        now = now_iso()
        existing = self.get_element_property(connection, element_id, property_name)
        if existing:
            connection.execute(
                """
                UPDATE element_properties
                SET value_json = ?, unit = ?, source = ?, source_priority = ?, is_confirmed = ?,
                    suggestion_value_json = NULL, suggestion_source = NULL,
                    element_version = ?, created_by = COALESCE(?, created_by), updated_at = ?
                WHERE id = ?
                """,
                (
                    dumps(value),
                    unit,
                    source,
                    source_priority,
                    1 if is_confirmed else 0,
                    element_version,
                    created_by,
                    now,
                    existing["id"],
                ),
            )
        else:
            connection.execute(
                """
                INSERT INTO element_properties (
                  id, project_id, floor_id, element_id, property_name, value_json, unit, source,
                  source_priority, is_confirmed, suggestion_value_json, suggestion_source,
                  element_version, created_by, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, NULL, ?, ?, ?, ?)
                """,
                (
                    str(uuid4()),
                    project_id,
                    floor_id,
                    element_id,
                    property_name,
                    dumps(value),
                    unit,
                    source,
                    source_priority,
                    1 if is_confirmed else 0,
                    element_version,
                    created_by,
                    now,
                    now,
                ),
            )
        connection.execute(
            "UPDATE elements SET element_version = ?, updated_at = ? WHERE id = ?",
            (element_version, now, element_id),
        )
        return self.get_element_property(connection, element_id, property_name) or {}

    def save_property_suggestion(
        self,
        connection: Any,
        *,
        property_row: dict,
        value: Any,
        source: str,
    ) -> dict:
        now = now_iso()
        connection.execute(
            """
            UPDATE element_properties
            SET suggestion_value_json = ?, suggestion_source = ?, updated_at = ?
            WHERE id = ?
            """,
            (dumps(value), source, now, property_row["id"]),
        )
        return self.get_element_property(connection, property_row["element_id"], property_row["property_name"]) or {}

    def create_wall(
        self,
        connection: Any,
        *,
        project_id: str,
        floor_id: str,
        payload: dict,
        wall_version: int,
        created_by: str | None,
        source_versions: dict,
    ) -> dict:
        now = now_iso()
        wall_id = str(uuid4())
        connection.execute(
            """
            INSERT INTO walls (
              id, project_id, floor_id, geometry_json, wall_type, classification,
              thickness_mm, height_mm, gross_area_m2, deduction_area_m2, net_area_m2,
              status, is_stale, user_confirmed, wall_version, source_versions_json,
              created_by, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?, 0, 0, ?, ?, ?, ?, ?)
            """,
            (
                wall_id,
                project_id,
                floor_id,
                dumps(payload.get("geometry") or {}),
                payload.get("wall_type"),
                payload.get("classification"),
                payload.get("thickness_mm"),
                payload.get("height_mm"),
                payload.get("gross_area_m2"),
                payload.get("gross_area_m2"),
                payload.get("status") or "needs_review",
                wall_version,
                dumps(source_versions),
                created_by,
                now,
                now,
            ),
        )
        return row_to_dict(connection.execute("SELECT * FROM walls WHERE id = ?", (wall_id,)).fetchone()) or {}

    def create_relation(
        self,
        connection: Any,
        *,
        project_id: str,
        floor_id: str,
        source_element_id: str,
        target_type: str,
        target_id: str,
        relation_type: str,
        created_by: str | None,
    ) -> dict:
        now = now_iso()
        existing = connection.execute(
            """
            SELECT * FROM element_relations
            WHERE source_element_id = ? AND target_type = ? AND target_id = ? AND relation_type = ?
            """,
            (source_element_id, target_type, target_id, relation_type),
        ).fetchone()
        if existing:
            return dict(existing)
        relation_id = str(uuid4())
        connection.execute(
            """
            INSERT INTO element_relations (
              id, project_id, floor_id, source_element_id, target_type, target_id,
              relation_type, status, version, created_by, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, 'confirmed', 1, ?, ?, ?)
            """,
            (
                relation_id,
                project_id,
                floor_id,
                source_element_id,
                target_type,
                target_id,
                relation_type,
                created_by,
                now,
                now,
            ),
        )
        return dict(connection.execute("SELECT * FROM element_relations WHERE id = ?", (relation_id,)).fetchone())

    def related_wall_ids(self, connection: Any, project_id: str, floor_id: str, element_id: str) -> list[str]:
        rows = connection.execute(
            """
            SELECT target_id AS wall_id FROM element_relations
            WHERE project_id = ? AND floor_id = ? AND source_element_id = ?
              AND target_type = 'wall' AND relation_type IN ('opening', 'assigned_to')
              AND status = 'confirmed'
            UNION
            SELECT wall_id FROM wall_openings
            WHERE project_id = ? AND floor_id = ? AND element_id = ?
            """,
            (project_id, floor_id, element_id, project_id, floor_id, element_id),
        ).fetchall()
        return [str(row["wall_id"]) for row in rows]

    def mark_element_dependents_stale(
        self,
        connection: Any,
        *,
        project_id: str,
        floor_id: str,
        element_id: str,
        wall_ids: list[str],
    ) -> None:
        now = now_iso()
        if wall_ids:
            placeholders = ", ".join("?" for _ in wall_ids)
            connection.execute(
                f"UPDATE walls SET is_stale = 1, status = 'not_ready', updated_at = ? WHERE project_id = ? AND floor_id = ? AND id IN ({placeholders})",
                (now, project_id, floor_id, *wall_ids),
            )
        connection.execute(
            """
            UPDATE review_issues SET status = 'not_ready', updated_at = ?
            WHERE project_id = ? AND floor_id = ? AND entity_type = 'element' AND entity_id = ?
              AND status != 'confirmed'
            """,
            (now, project_id, floor_id, element_id),
        )
        entity_ids = [element_id, *wall_ids]
        placeholders = ", ".join("?" for _ in entity_ids)
        connection.execute(
            f"UPDATE boq_rows SET is_stale = 1, status = 'not_ready', updated_at = ? WHERE project_id = ? AND entity_id IN ({placeholders})",
            (now, project_id, *entity_ids),
        )
        connection.execute(
            "UPDATE boqs SET is_stale = 1, status = 'not_ready', updated_at = ? WHERE project_id = ?",
            (now, project_id),
        )
