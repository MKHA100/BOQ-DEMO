from __future__ import annotations

from typing import Any, Iterable
from uuid import uuid4

from app.database.session import get_connection, row_to_dict
from app.workflow.repo_base import dumps, loads, now_iso


class PdfUploadRepository:
    def find_document_by_hash(self, connection: Any, project_id: str, content_hash: str) -> dict | None:
        row = connection.execute(
            """
            SELECT * FROM documents
            WHERE project_id = ? AND content_hash = ?
            ORDER BY created_at DESC LIMIT 1
            """,
            (project_id, content_hash),
        ).fetchone()
        return row_to_dict(row)

    def get_document(self, project_id: str, document_id: str) -> dict | None:
        with get_connection() as connection:
            row = connection.execute(
                "SELECT * FROM documents WHERE project_id = ? AND id = ?",
                (project_id, document_id),
            ).fetchone()
        return row_to_dict(row)

    def get_document_in_connection(self, connection: Any, project_id: str, document_id: str) -> dict | None:
        return row_to_dict(
            connection.execute(
                "SELECT * FROM documents WHERE project_id = ? AND id = ?",
                (project_id, document_id),
            ).fetchone()
        )

    def get_primary_document(self, project_id: str) -> dict | None:
        with get_connection() as connection:
            row = connection.execute(
                """
                SELECT * FROM documents
                WHERE project_id = ? AND document_type = 'source' AND is_primary = 1
                ORDER BY created_at DESC LIMIT 1
                """,
                (project_id,),
            ).fetchone()
        return row_to_dict(row)

    def list_documents(self, project_id: str) -> list[dict]:
        with get_connection() as connection:
            rows = connection.execute(
                """
                SELECT * FROM documents
                WHERE project_id = ?
                ORDER BY is_primary DESC, created_at DESC
                """,
                (project_id,),
            ).fetchall()
        return [row_to_dict(row) or {} for row in rows]

    def create_document(
        self,
        connection: Any,
        *,
        document_id: str,
        project_id: str,
        file_name: str,
        mime_type: str,
        storage_key: str,
        content_hash: str,
        size_bytes: int,
        page_count: int,
        version: int,
        validation: dict,
        created_by: str | None,
        document_type: str = "source",
        is_primary: bool = True,
    ) -> dict:
        now = now_iso()
        if is_primary:
            connection.execute(
                """
                UPDATE documents
                SET is_primary = 0, updated_at = ?
                WHERE project_id = ? AND document_type = 'source' AND is_primary = 1
                """,
                (now, project_id),
            )
        connection.execute(
            """
            INSERT INTO documents (
              id, project_id, document_type, file_name, original_file_name, mime_type,
              storage_key, content_hash, size_bytes, page_count, status, version,
              is_primary, validation_status, validation_json, manifest_status,
              ingestion_status, manifest_version, created_by, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'ready', ?, ?,
                      'ready', ?, 'not_ready', 'processing', 0, ?, ?, ?)
            """,
            (
                document_id,
                project_id,
                document_type,
                file_name,
                file_name,
                mime_type,
                storage_key,
                content_hash,
                size_bytes,
                page_count,
                version,
                int(is_primary),
                dumps(validation),
                created_by,
                now,
                now,
            ),
        )
        row = connection.execute("SELECT * FROM documents WHERE id = ?", (document_id,)).fetchone()
        return row_to_dict(row) or {}

    def make_primary(self, connection: Any, project_id: str, document_id: str) -> dict:
        now = now_iso()
        connection.execute(
            "UPDATE documents SET is_primary = 0, updated_at = ? WHERE project_id = ? AND is_primary = 1",
            (now, project_id),
        )
        connection.execute(
            "UPDATE documents SET is_primary = 1, updated_at = ? WHERE project_id = ? AND id = ?",
            (now, project_id, document_id),
        )
        return self.get_document_in_connection(connection, project_id, document_id) or {}

    def update_document(
        self,
        project_id: str,
        document_id: str,
        **updates: Any,
    ) -> dict | None:
        clean = {key: value for key, value in updates.items() if value is not None}
        if not clean:
            return self.get_document(project_id, document_id)
        clean["updated_at"] = now_iso()
        set_clause = ", ".join(f"{key} = ?" for key in clean)
        with get_connection() as connection:
            connection.execute(
                f"UPDATE documents SET {set_clause} WHERE project_id = ? AND id = ?",
                (*clean.values(), project_id, document_id),
            )
            row = connection.execute(
                "SELECT * FROM documents WHERE project_id = ? AND id = ?",
                (project_id, document_id),
            ).fetchone()
        return row_to_dict(row)

    def upsert_page_metadata(
        self,
        *,
        project_id: str,
        document_id: str,
        page_number: int,
        page_label: str | None,
        width_points: float,
        height_points: float,
        rotation: int,
        media_box: dict,
        version: int,
    ) -> dict:
        now = now_iso()
        page_id = str(uuid4())
        with get_connection() as connection:
            connection.execute(
                """
                INSERT INTO document_pages (
                  id, project_id, document_id, page_number, page_label, width_points,
                  height_points, rotation, media_box_json, status, metadata_status,
                  version, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'processing', 'ready', ?, ?, ?)
                ON CONFLICT(document_id, page_number) DO UPDATE SET
                  page_label = excluded.page_label,
                  width_points = excluded.width_points,
                  height_points = excluded.height_points,
                  rotation = excluded.rotation,
                  media_box_json = excluded.media_box_json,
                  metadata_status = 'ready',
                  error_message = NULL,
                  version = excluded.version,
                  updated_at = excluded.updated_at
                """,
                (
                    page_id,
                    project_id,
                    document_id,
                    page_number,
                    page_label,
                    width_points,
                    height_points,
                    rotation,
                    dumps(media_box),
                    version,
                    now,
                    now,
                ),
            )
            row = connection.execute(
                "SELECT * FROM document_pages WHERE document_id = ? AND page_number = ?",
                (document_id, page_number),
            ).fetchone()
        return row_to_dict(row) or {}

    def list_pages(self, project_id: str, document_id: str) -> list[dict]:
        with get_connection() as connection:
            rows = connection.execute(
                """
                SELECT * FROM document_pages
                WHERE project_id = ? AND document_id = ?
                ORDER BY page_number
                """,
                (project_id, document_id),
            ).fetchall()
        return [row_to_dict(row) or {} for row in rows]

    def get_manifest_snapshot(self, project_id: str, document_id: str) -> dict[str, int]:
        with get_connection() as connection:
            row = connection.execute(
                """
                SELECT
                  COUNT(*) AS page_rows,
                  SUM(CASE WHEN metadata_status = 'ready' THEN 1 ELSE 0 END) AS metadata_ready,
                  SUM(CASE WHEN thumbnail_status = 'ready' AND thumbnail_key IS NOT NULL THEN 1 ELSE 0 END) AS thumbnails_ready,
                  SUM(CASE WHEN preview_status = 'ready' AND preview_key IS NOT NULL THEN 1 ELSE 0 END) AS previews_ready,
                  SUM(CASE WHEN text_status = 'ready' AND text_layer_key IS NOT NULL THEN 1 ELSE 0 END) AS text_ready,
                  SUM(CASE WHEN classification_status = 'ready' THEN 1 ELSE 0 END) AS classifications_ready
                FROM document_pages
                WHERE project_id = ? AND document_id = ?
                """,
                (project_id, document_id),
            ).fetchone()
        return {
            "page_rows": int(row["page_rows"] or 0) if row else 0,
            "metadata_ready": int(row["metadata_ready"] or 0) if row else 0,
            "thumbnails_ready": int(row["thumbnails_ready"] or 0) if row else 0,
            "previews_ready": int(row["previews_ready"] or 0) if row else 0,
            "text_ready": int(row["text_ready"] or 0) if row else 0,
            "classifications_ready": int(row["classifications_ready"] or 0) if row else 0,
        }

    def get_page(self, project_id: str, document_id: str, page_number: int) -> dict | None:
        with get_connection() as connection:
            row = connection.execute(
                """
                SELECT * FROM document_pages
                WHERE project_id = ? AND document_id = ? AND page_number = ?
                """,
                (project_id, document_id, page_number),
            ).fetchone()
        return row_to_dict(row)

    def update_page_asset(
        self,
        *,
        page_id: str,
        key_column: str,
        storage_key: str,
        status_column: str,
        width_column: str | None = None,
        height_column: str | None = None,
        width: int | None = None,
        height: int | None = None,
    ) -> None:
        allowed_keys = {"thumbnail_key", "preview_key", "text_layer_key"}
        allowed_status = {"thumbnail_status", "preview_status", "text_status"}
        allowed_dimensions = {"thumbnail_width", "thumbnail_height", "preview_width", "preview_height"}
        if key_column not in allowed_keys or status_column not in allowed_status:
            raise ValueError("Unsupported page asset column")
        assignments = [f"{key_column} = ?", f"{status_column} = 'ready'", "error_message = NULL", "updated_at = ?"]
        params: list[Any] = [storage_key, now_iso()]
        if width_column and width_column in allowed_dimensions and width is not None:
            assignments.append(f"{width_column} = ?")
            params.append(int(width))
        if height_column and height_column in allowed_dimensions and height is not None:
            assignments.append(f"{height_column} = ?")
            params.append(int(height))
        params.append(page_id)
        with get_connection() as connection:
            connection.execute(
                f"UPDATE document_pages SET {', '.join(assignments)} WHERE id = ?",
                tuple(params),
            )
            self._refresh_page_status(connection, page_id)

    def update_page_text(
        self,
        *,
        page_id: str,
        storage_key: str,
        text_char_count: int,
        vector_text_available: bool,
    ) -> None:
        now = now_iso()
        with get_connection() as connection:
            connection.execute(
                """
                UPDATE document_pages
                SET text_layer_key = ?, text_status = 'ready', text_char_count = ?,
                    vector_text_available = ?, error_message = NULL, updated_at = ?
                WHERE id = ?
                """,
                (storage_key, int(text_char_count), int(vector_text_available), now, page_id),
            )
            self._refresh_page_status(connection, page_id)

    def update_page_classification(
        self,
        *,
        page_id: str,
        classification: str,
        confidence: float,
    ) -> None:
        now = now_iso()
        with get_connection() as connection:
            connection.execute(
                """
                UPDATE document_pages
                SET classification = ?, classification_confidence = ?,
                    classification_status = 'ready', error_message = NULL, updated_at = ?
                WHERE id = ?
                """,
                (classification, confidence, now, page_id),
            )
            self._refresh_page_status(connection, page_id)

    def mark_page_failed(self, page_id: str, status_column: str, message: str) -> None:
        allowed = {
            "metadata_status",
            "thumbnail_status",
            "preview_status",
            "text_status",
            "classification_status",
        }
        if status_column not in allowed:
            raise ValueError("Unsupported page status column")
        with get_connection() as connection:
            connection.execute(
                f"UPDATE document_pages SET {status_column} = 'failed', status = 'failed', error_message = ?, updated_at = ? WHERE id = ?",
                (message[:1000], now_iso(), page_id),
            )

    def replace_extraction_records(
        self,
        *,
        project_id: str,
        document_id: str,
        extraction_type: str,
        extraction_version: int,
        records: Iterable[dict],
        floor_id: str | None = None,
    ) -> int:
        now = now_iso()
        items = list(records)
        with get_connection() as connection:
            delete_sql = """DELETE FROM extraction_records
                WHERE project_id = ? AND document_id = ? AND extraction_type = ? AND extraction_version = ?"""
            delete_values: list[Any] = [project_id, document_id, extraction_type, extraction_version]
            if floor_id is not None:
                delete_sql += " AND floor_id = ?"
                delete_values.append(floor_id)
            connection.execute(delete_sql, tuple(delete_values))
            for record in items:
                connection.execute(
                    """
                    INSERT INTO extraction_records (
                      id, project_id, floor_id, document_id, document_page_id,
                      extraction_type, entity_key, data_json, source_type,
                      source_location_json, extraction_method, confidence,
                      quality_signal, review_state, extraction_version,
                      created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        record.get("id") or str(uuid4()),
                        project_id,
                        record.get("floor_id"),
                        document_id,
                        record["document_page_id"],
                        extraction_type,
                        record["entity_key"],
                        dumps(record["data"]),
                        record.get("source_type") or "main_pdf",
                        dumps(record.get("source_location") or {}),
                        record.get("extraction_method") or "vector_text_rules",
                        record.get("confidence"),
                        record.get("quality_signal"),
                        record.get("review_state") or "needs_review",
                        extraction_version,
                        now,
                        now,
                    ),
                )
        return len(items)

    def list_extraction_records(
        self,
        project_id: str,
        *,
        document_id: str | None = None,
        extraction_type: str | None = None,
    ) -> list[dict]:
        where = ["project_id = ?"]
        params: list[Any] = [project_id]
        if document_id:
            where.append("document_id = ?")
            params.append(document_id)
        if extraction_type:
            where.append("extraction_type = ?")
            params.append(extraction_type)
        with get_connection() as connection:
            rows = connection.execute(
                f"SELECT * FROM extraction_records WHERE {' AND '.join(where)} ORDER BY extraction_type, created_at, id",
                tuple(params),
            ).fetchall()
        return [self._decode(row_to_dict(row) or {}) for row in rows]

    def refresh_document_manifest_status(self, project_id: str, document_id: str) -> dict | None:
        with get_connection() as connection:
            total = connection.execute(
                "SELECT COUNT(*) AS total FROM document_pages WHERE project_id = ? AND document_id = ?",
                (project_id, document_id),
            ).fetchone()
            ready = connection.execute(
                """
                SELECT COUNT(*) AS total FROM document_pages
                WHERE project_id = ? AND document_id = ? AND metadata_status = 'ready'
                  AND thumbnail_status = 'ready' AND preview_status = 'ready'
                  AND text_status = 'ready' AND classification_status = 'ready'
                """,
                (project_id, document_id),
            ).fetchone()
            total_count = int(total["total"] if total else 0)
            ready_count = int(ready["total"] if ready else 0)
            status = "ready" if total_count > 0 and total_count == ready_count else "processing"
            connection.execute(
                """
                UPDATE documents
                SET manifest_status = ?, manifest_version = CASE WHEN ? = 'ready' THEN version ELSE manifest_version END,
                    updated_at = ?
                WHERE project_id = ? AND id = ?
                """,
                (status, status, now_iso(), project_id, document_id),
            )
            row = connection.execute(
                "SELECT * FROM documents WHERE project_id = ? AND id = ?",
                (project_id, document_id),
            ).fetchone()
        return row_to_dict(row)

    @staticmethod
    def _refresh_page_status(connection: Any, page_id: str) -> None:
        row = connection.execute(
            """
            SELECT metadata_status, thumbnail_status, preview_status, text_status, classification_status
            FROM document_pages WHERE id = ?
            """,
            (page_id,),
        ).fetchone()
        if not row:
            return
        statuses = [row[key] for key in ("metadata_status", "thumbnail_status", "preview_status", "text_status", "classification_status")]
        if "failed" in statuses:
            status = "failed"
        elif all(value == "ready" for value in statuses):
            status = "ready"
        else:
            status = "processing"
        connection.execute(
            "UPDATE document_pages SET status = ?, updated_at = ? WHERE id = ?",
            (status, now_iso(), page_id),
        )

    @staticmethod
    def _decode(record: dict) -> dict:
        decoded = dict(record)
        for key in list(decoded):
            if key.endswith("_json"):
                decoded[key[:-5]] = loads(decoded.pop(key))
        for key in ("is_primary", "vector_text_available"):
            if key in decoded:
                decoded[key] = bool(decoded[key])
        return decoded


pdf_upload_repository = PdfUploadRepository()
