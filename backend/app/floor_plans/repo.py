from __future__ import annotations

from typing import Any
from uuid import uuid4

from app.database.session import get_connection, row_to_dict
from app.workflow.repo_base import dumps, loads, now_iso


class FloorPlansRepository:
    def ensure_ground_floor(self, project_id: str, created_by: str | None) -> dict:
        with get_connection() as connection:
            existing = connection.execute(
                "SELECT * FROM floors WHERE project_id = ? ORDER BY level_index LIMIT 1",
                (project_id,),
            ).fetchone()
            if existing:
                return dict(existing)
            now = now_iso()
            floor_id = str(uuid4())
            connection.execute(
                """
                INSERT INTO floors (
                  id, project_id, name, level_index, status, created_by,
                  uses_default_height, wall_height_mm, is_custom_name,
                  source_rotation, created_at, updated_at
                ) VALUES (?, ?, 'Ground Floor', 0, 'not_ready', ?, 1, NULL, 0, 0, ?, ?)
                """,
                (floor_id, project_id, created_by, now, now),
            )
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
            return dict(connection.execute("SELECT * FROM floors WHERE id = ?", (floor_id,)).fetchone())

    def get_project_settings(self, project_id: str) -> dict | None:
        with get_connection() as connection:
            row = connection.execute(
                "SELECT id, name, default_wall_height_mm, measurement_unit, updated_at FROM projects WHERE id = ?",
                (project_id,),
            ).fetchone()
        return row_to_dict(row)

    def update_project_settings(self, project_id: str, height_mm: float, unit: str) -> dict:
        now = now_iso()
        with get_connection() as connection:
            connection.execute(
                "UPDATE projects SET default_wall_height_mm = ?, measurement_unit = ?, updated_at = ? WHERE id = ?",
                (height_mm, unit, now, project_id),
            )
            row = connection.execute(
                "SELECT id, name, default_wall_height_mm, measurement_unit, updated_at FROM projects WHERE id = ?",
                (project_id,),
            ).fetchone()
        return dict(row)

    def next_floor_index(self, project_id: str) -> int:
        with get_connection() as connection:
            row = connection.execute(
                "SELECT COALESCE(MAX(level_index), -1) + 1 AS next_index FROM floors WHERE project_id = ?",
                (project_id,),
            ).fetchone()
        return int(row["next_index"] if row else 0)

    def create_floor(self, project_id: str, name: str, level_index: int, created_by: str | None) -> dict:
        now = now_iso()
        floor_id = str(uuid4())
        with get_connection() as connection:
            connection.execute(
                """
                INSERT INTO floors (
                  id, project_id, name, level_index, status, created_by,
                  uses_default_height, wall_height_mm, is_custom_name,
                  source_rotation, created_at, updated_at
                ) VALUES (?, ?, ?, ?, 'not_ready', ?, 1, NULL, 0, 0, ?, ?)
                """,
                (floor_id, project_id, name, level_index, created_by, now, now),
            )
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
            row = connection.execute("SELECT * FROM floors WHERE id = ?", (floor_id,)).fetchone()
        return dict(row)

    def get_floor(self, project_id: str, floor_id: str) -> dict | None:
        with get_connection() as connection:
            row = connection.execute(
                "SELECT * FROM floors WHERE id = ? AND project_id = ?",
                (floor_id, project_id),
            ).fetchone()
        return row_to_dict(row)

    def update_floor(self, project_id: str, floor_id: str, updates: dict[str, Any]) -> dict | None:
        if not updates:
            return self.get_floor(project_id, floor_id)
        clean = dict(updates)
        clean["updated_at"] = now_iso()
        set_clause = ", ".join(f"{key} = ?" for key in clean)
        with get_connection() as connection:
            connection.execute(
                f"UPDATE floors SET {set_clause} WHERE id = ? AND project_id = ?",
                (*clean.values(), floor_id, project_id),
            )
            row = connection.execute(
                "SELECT * FROM floors WHERE id = ? AND project_id = ?",
                (floor_id, project_id),
            ).fetchone()
        return row_to_dict(row)

    def delete_floor(self, project_id: str, floor_id: str) -> None:
        with get_connection() as connection:
            connection.execute("DELETE FROM floors WHERE id = ? AND project_id = ?", (floor_id, project_id))

    def floor_count(self, project_id: str) -> int:
        with get_connection() as connection:
            row = connection.execute("SELECT COUNT(*) AS total FROM floors WHERE project_id = ?", (project_id,)).fetchone()
        return int(row["total"] if row else 0)

    def list_floors_with_crops(self, project_id: str) -> list[dict]:
        with get_connection() as connection:
            rows = connection.execute(
                """
                SELECT f.*, fv.crop_version,
                       fc.id AS crop_id, fc.document_id AS crop_document_id,
                       fc.document_page_id AS crop_document_page_id,
                       fc.source_page_number AS crop_source_page_number,
                       fc.original_page_width, fc.original_page_height,
                       fc.rotation AS crop_rotation, fc.render_dpi,
                       fc.coordinates_json, fc.crop_asset_key, fc.preview_asset_key,
                       fc.status AS crop_status, fc.created_at AS crop_created_at,
                       fc.updated_at AS crop_updated_at
                FROM floors f
                LEFT JOIN floor_versions fv ON fv.floor_id = f.id
                LEFT JOIN floor_crops fc
                  ON fc.floor_id = f.id AND fc.project_id = f.project_id AND fc.is_current = 1
                WHERE f.project_id = ?
                ORDER BY f.level_index ASC
                """,
                (project_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def list_documents_with_pages(self, project_id: str) -> tuple[list[dict], list[dict]]:
        with get_connection() as connection:
            documents = connection.execute(
                """
                SELECT * FROM documents
                WHERE project_id = ? AND document_type IN ('source', 'floor_source')
                ORDER BY is_primary DESC, created_at DESC
                """,
                (project_id,),
            ).fetchall()
            pages = connection.execute(
                """
                SELECT * FROM document_pages
                WHERE project_id = ?
                ORDER BY document_id, page_number
                """,
                (project_id,),
            ).fetchall()
        return [dict(row) for row in documents], [dict(row) for row in pages]

    def get_document(self, project_id: str, document_id: str) -> dict | None:
        with get_connection() as connection:
            row = connection.execute(
                "SELECT * FROM documents WHERE project_id = ? AND id = ?",
                (project_id, document_id),
            ).fetchone()
        return row_to_dict(row)

    def get_document_page(self, project_id: str, document_id: str, page_id: str) -> dict | None:
        with get_connection() as connection:
            row = connection.execute(
                """
                SELECT * FROM document_pages
                WHERE project_id = ? AND document_id = ? AND id = ?
                """,
                (project_id, document_id, page_id),
            ).fetchone()
        return row_to_dict(row)

    def current_crop(self, project_id: str, floor_id: str) -> dict | None:
        with get_connection() as connection:
            row = connection.execute(
                """
                SELECT * FROM floor_crops
                WHERE project_id = ? AND floor_id = ? AND is_current = 1
                ORDER BY crop_version DESC LIMIT 1
                """,
                (project_id, floor_id),
            ).fetchone()
        return row_to_dict(row)

    def save_crop(
        self,
        *,
        project_id: str,
        floor_id: str,
        document_id: str,
        document_page_id: str,
        source_page_number: int,
        original_page_width: float,
        original_page_height: float,
        rotation: int,
        render_dpi: int,
        coordinates: dict,
        created_by: str | None,
        source_changed: bool,
    ) -> dict:
        from app.workflow.repo import workflow_repository

        now = now_iso()
        crop_id = str(uuid4())
        with get_connection() as connection:
            versions = workflow_repository.increment_floor_version(connection, project_id, floor_id, "crop_version")
            crop_version = int(versions["crop_version"])
            connection.execute(
                "UPDATE floor_crops SET is_current = 0, updated_at = ? WHERE project_id = ? AND floor_id = ? AND is_current = 1",
                (now, project_id, floor_id),
            )
            connection.execute(
                """
                INSERT INTO floor_crops (
                  id, project_id, floor_id, document_id, document_page_id,
                  coordinates_json, source_width, source_height, crop_asset_key,
                  crop_version, status, is_current, created_by, created_at, updated_at,
                  source_page_number, original_page_width, original_page_height,
                  rotation, render_dpi, preview_asset_key, coordinate_space, source_changed
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, NULL, ?, 'processing', 1, ?, ?, ?,
                          ?, ?, ?, ?, ?, NULL, 'original_source', ?)
                """,
                (
                    crop_id,
                    project_id,
                    floor_id,
                    document_id,
                    document_page_id,
                    dumps(coordinates),
                    original_page_width,
                    original_page_height,
                    crop_version,
                    created_by,
                    now,
                    now,
                    source_page_number,
                    original_page_width,
                    original_page_height,
                    rotation,
                    render_dpi,
                    int(source_changed),
                ),
            )
            connection.execute(
                """
                UPDATE floors
                SET source_document_id = ?, source_page_number = ?, source_rotation = ?,
                    status = 'processing', updated_at = ?
                WHERE id = ? AND project_id = ?
                """,
                (document_id, source_page_number, rotation, now, floor_id, project_id),
            )
            if source_changed:
                connection.execute(
                    "UPDATE calibrations SET status = 'needs_review', updated_at = ? WHERE project_id = ? AND floor_id = ? AND status = 'confirmed'",
                    (now, project_id, floor_id),
                )
            # A replacement crop creates a new source generation. Generated
            # records from earlier crops remain in the audit trail but disappear
            # from normal workflow queries. Manual and confirmed edits are kept
            # for geometric reconciliation with the new detections.
            connection.execute(
                """
                UPDATE elements
                SET measurement_status='not_ready',
                    generated_status=CASE WHEN COALESCE(is_manual,0)=1 THEN 'current' ELSE 'superseded' END,
                    excluded=CASE WHEN COALESCE(is_manual,0)=1 THEN excluded ELSE 1 END,
                    status=CASE WHEN COALESCE(is_manual,0)=1 OR user_confirmed=1 THEN status ELSE 'not_ready' END,
                    updated_at=?
                WHERE project_id=? AND floor_id=?
                """,
                (now, project_id, floor_id),
            )
            connection.execute(
                """UPDATE walls SET is_stale=1,status='not_ready',
                   generated_status=CASE WHEN user_confirmed=1 THEN 'current' ELSE 'superseded' END,updated_at=?
                   WHERE project_id=? AND floor_id=?""",
                (now, project_id, floor_id),
            )
            connection.execute(
                """UPDATE rooms SET is_stale=1,status='not_ready',
                   generated_status=CASE WHEN user_confirmed=1 THEN 'current' ELSE 'superseded' END,updated_at=?
                   WHERE project_id=? AND floor_id=?""",
                (now, project_id, floor_id),
            )
            connection.execute(
                "UPDATE boq_rows SET is_stale = 1, status = 'not_ready', updated_at = ? WHERE project_id = ? AND floor_id = ?",
                (now, project_id, floor_id),
            )
            row = connection.execute("SELECT * FROM floor_crops WHERE id = ?", (crop_id,)).fetchone()
        return dict(row)

    def mark_crop_preview_ready(self, crop_id: str, preview_asset_key: str) -> dict | None:
        now = now_iso()
        with get_connection() as connection:
            crop = connection.execute("SELECT * FROM floor_crops WHERE id = ?", (crop_id,)).fetchone()
            if not crop:
                return None
            connection.execute(
                "UPDATE floor_crops SET preview_asset_key=?, status='processing', updated_at=? WHERE id=?",
                (preview_asset_key, now, crop_id),
            )
            if bool(crop["is_current"]):
                # The user-facing drawing is ready even though the high-resolution
                # crop and analysis continue in the worker.
                connection.execute(
                    "UPDATE floors SET status='ready', updated_at=? WHERE id=?",
                    (now, crop["floor_id"]),
                )
            row = connection.execute("SELECT * FROM floor_crops WHERE id=?", (crop_id,)).fetchone()
        return row_to_dict(row)

    def mark_crop_failed(self, crop_id: str) -> None:
        now = now_iso()
        with get_connection() as connection:
            crop = connection.execute(
                "SELECT floor_id,is_current FROM floor_crops WHERE id=?", (crop_id,)
            ).fetchone()
            if not crop:
                return
            connection.execute(
                "UPDATE floor_crops SET status='failed',updated_at=? WHERE id=?", (now,crop_id)
            )
            if bool(crop["is_current"]):
                connection.execute(
                    "UPDATE floors SET status='failed',updated_at=? WHERE id=?",
                    (now,crop["floor_id"]),
                )

    def mark_crop_ready(self, crop_id: str, crop_key: str, preview_key: str) -> dict | None:
        now = now_iso()
        with get_connection() as connection:
            connection.execute(
                """
                UPDATE floor_crops
                SET crop_asset_key = ?, preview_asset_key = ?, status = 'ready', updated_at = ?
                WHERE id = ?
                """,
                (crop_key, preview_key, now, crop_id),
            )
            row = connection.execute("SELECT * FROM floor_crops WHERE id = ?", (crop_id,)).fetchone()
            if row and bool(row["is_current"]):
                connection.execute(
                    "UPDATE floors SET status = 'ready', updated_at = ? WHERE id = ?",
                    (now, row["floor_id"]),
                )
        return row_to_dict(row)

    def get_crop(self, project_id: str, crop_id: str) -> dict | None:
        with get_connection() as connection:
            row = connection.execute(
                "SELECT * FROM floor_crops WHERE project_id = ? AND id = ?",
                (project_id, crop_id),
            ).fetchone()
        return row_to_dict(row)

    def decode_crop(self, row: dict) -> dict:
        result = dict(row)
        result["coordinates"] = loads(result.pop("coordinates_json", "{}"))
        return result


floor_plans_repository = FloorPlansRepository()
