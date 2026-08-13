from __future__ import annotations

from typing import Any
from uuid import uuid4

from app.database.session import get_connection, row_to_dict
from app.workflow.constants import VERSION_LAYERS
from app.workflow.repo_base import dumps, loads, now_iso

class FileRepositoryMixin:
    def find_document_by_hash(self, connection: Any, project_id: str, content_hash: str) -> dict | None:
        return row_to_dict(
            connection.execute(
                "SELECT * FROM documents WHERE project_id = ? AND content_hash = ? ORDER BY created_at DESC LIMIT 1",
                (project_id, content_hash),
            ).fetchone()
        )

    def create_document(
        self,
        connection: Any,
        *,
        document_id: str,
        project_id: str,
        document_type: str,
        file_name: str,
        mime_type: str,
        storage_key: str,
        content_hash: str,
        size_bytes: int,
        version: int,
        created_by: str | None,
    ) -> dict:
        now = now_iso()
        connection.execute(
            """
            INSERT INTO documents (
              id, project_id, document_type, file_name, mime_type, storage_key,
              content_hash, size_bytes, page_count, status, version, created_by,
              created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, NULL, 'processing', ?, ?, ?, ?)
            """,
            (
                document_id,
                project_id,
                document_type,
                file_name,
                mime_type,
                storage_key,
                content_hash,
                size_bytes,
                version,
                created_by,
                now,
                now,
            ),
        )
        return row_to_dict(connection.execute("SELECT * FROM documents WHERE id = ?", (document_id,)).fetchone()) or {}

    def list_documents(self, project_id: str) -> list[dict]:
        with get_connection() as connection:
            rows = connection.execute(
                "SELECT * FROM documents WHERE project_id = ? ORDER BY created_at DESC",
                (project_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def get_document(self, connection: Any, project_id: str, document_id: str) -> dict | None:
        return row_to_dict(
            connection.execute(
                "SELECT * FROM documents WHERE id = ? AND project_id = ?",
                (document_id, project_id),
            ).fetchone()
        )

    def save_floor_crop(
        self,
        connection: Any,
        *,
        project_id: str,
        floor_id: str,
        document_id: str,
        document_page_id: str,
        coordinates: dict,
        source_width: float | None,
        source_height: float | None,
        crop_asset_key: str | None,
        crop_version: int,
        created_by: str | None,
    ) -> dict:
        now = now_iso()
        connection.execute(
            "UPDATE floor_crops SET is_current = 0, updated_at = ? WHERE project_id = ? AND floor_id = ? AND is_current = 1",
            (now, project_id, floor_id),
        )
        crop_id = str(uuid4())
        connection.execute(
            """
            INSERT INTO floor_crops (
              id, project_id, floor_id, document_id, document_page_id, coordinates_json,
              source_width, source_height, crop_asset_key, crop_version, status,
              is_current, created_by, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'confirmed', 1, ?, ?, ?)
            """,
            (
                crop_id,
                project_id,
                floor_id,
                document_id,
                document_page_id,
                dumps(coordinates),
                source_width,
                source_height,
                crop_asset_key,
                crop_version,
                created_by,
                now,
                now,
            ),
        )
        connection.execute(
            "UPDATE calibrations SET status = 'needs_review', updated_at = ? WHERE project_id = ? AND floor_id = ? AND status = 'confirmed'",
            (now, project_id, floor_id),
        )
        connection.execute(
            """
            UPDATE elements
            SET measurement_status = 'not_ready',
                status = CASE WHEN user_confirmed = 1 THEN status ELSE 'not_ready' END,
                updated_at = ?
            WHERE project_id = ? AND floor_id = ?
            """,
            (now, project_id, floor_id),
        )
        connection.execute(
            "UPDATE walls SET is_stale = 1, status = 'not_ready', updated_at = ? WHERE project_id = ? AND floor_id = ?",
            (now, project_id, floor_id),
        )
        connection.execute(
            "UPDATE rooms SET is_stale = 1, status = 'not_ready', updated_at = ? WHERE project_id = ? AND floor_id = ?",
            (now, project_id, floor_id),
        )
        connection.execute(
            "UPDATE boq_rows SET is_stale = 1, status = 'not_ready', updated_at = ? WHERE project_id = ? AND floor_id = ?",
            (now, project_id, floor_id),
        )
        connection.execute(
            "UPDATE boqs SET is_stale = 1, status = 'not_ready', updated_at = ? WHERE project_id = ?",
            (now, project_id),
        )
        return row_to_dict(connection.execute("SELECT * FROM floor_crops WHERE id = ?", (crop_id,)).fetchone()) or {}

    def create_schedule_file(
        self,
        connection: Any,
        *,
        project_id: str,
        floor_id: str | None,
        document_id: str,
        schedule_type: str,
        source_crop: dict | None,
        schedule_version: int,
        created_by: str | None,
    ) -> dict:
        now = now_iso()
        record_id = str(uuid4())
        connection.execute(
            """
            INSERT INTO schedule_files (
              id, project_id, floor_id, document_id, schedule_type, source_crop_json,
              extracted_data_json, status, schedule_version, created_by, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, '{}', 'processing', ?, ?, ?, ?)
            """,
            (
                record_id,
                project_id,
                floor_id,
                document_id,
                schedule_type,
                dumps(source_crop) if source_crop is not None else None,
                schedule_version,
                created_by,
                now,
                now,
            ),
        )
        return row_to_dict(connection.execute("SELECT * FROM schedule_files WHERE id = ?", (record_id,)).fetchone()) or {}

    def create_specification_file(
        self,
        connection: Any,
        *,
        project_id: str,
        floor_id: str | None,
        document_id: str,
        specification_type: str,
        source_crop: dict | None,
        specification_version: int,
        created_by: str | None,
    ) -> dict:
        now = now_iso()
        record_id = str(uuid4())
        connection.execute(
            """
            INSERT INTO specification_files (
              id, project_id, floor_id, document_id, specification_type, source_crop_json,
              extracted_data_json, status, specification_version, created_by, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, '{}', 'processing', ?, ?, ?, ?)
            """,
            (
                record_id,
                project_id,
                floor_id,
                document_id,
                specification_type,
                dumps(source_crop) if source_crop is not None else None,
                specification_version,
                created_by,
                now,
                now,
            ),
        )
        return row_to_dict(connection.execute("SELECT * FROM specification_files WHERE id = ?", (record_id,)).fetchone()) or {}
