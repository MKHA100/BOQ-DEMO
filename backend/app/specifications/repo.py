from __future__ import annotations

import json
from typing import Any, Iterable
from uuid import uuid4

from app.database.session import get_connection, row_to_dict
from app.specifications.constants import CATEGORY_DEFINITIONS, CATEGORIES
from app.workflow.repo_base import now_iso


def _dumps(value: Any) -> str:
    return json.dumps(value if value is not None else {}, default=str, sort_keys=True, separators=(",", ":"))


def _loads(value: Any, default: Any = None) -> Any:
    if isinstance(value, (dict, list)):
        return value
    if not value:
        return {} if default is None else default
    try:
        return json.loads(value)
    except (TypeError, ValueError, json.JSONDecodeError):
        return {} if default is None else default


class SpecificationsRepository:
    def list_floors(self, project_id: str) -> list[dict]:
        with get_connection() as connection:
            rows = connection.execute(
                "SELECT id, name, level_index FROM floors WHERE project_id = ? ORDER BY level_index",
                (project_id,),
            ).fetchall()
        return [row_to_dict(row) or {} for row in rows]

    def list_documents_with_pages(self, project_id: str) -> list[dict]:
        with get_connection() as connection:
            documents = connection.execute(
                """
                SELECT * FROM documents
                WHERE project_id = ? AND document_type = 'source'
                ORDER BY is_primary DESC, created_at ASC
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
        page_map: dict[str, list[dict]] = {}
        for row in pages:
            page = row_to_dict(row) or {}
            page_map.setdefault(str(page.get("document_id")), []).append(page)
        result = []
        for row in documents:
            document = row_to_dict(row) or {}
            document["pages"] = page_map.get(str(document.get("id")), [])
            result.append(document)
        return result

    def list_sources(self, project_id: str) -> list[dict]:
        sources: list[dict] = []
        with get_connection() as connection:
            schedule_rows = connection.execute(
                "SELECT * FROM schedule_files WHERE project_id = ? AND is_active = 1 ORDER BY created_at",
                (project_id,),
            ).fetchall()
            specification_rows = connection.execute(
                "SELECT * FROM specification_files WHERE project_id = ? AND is_active = 1 ORDER BY created_at",
                (project_id,),
            ).fetchall()
            floor_rows = connection.execute(
                "SELECT source_id, floor_id FROM supporting_file_floors WHERE project_id = ? ORDER BY created_at",
                (project_id,),
            ).fetchall()
            entry_count_rows = connection.execute(
                """
                SELECT source_id, COUNT(*) AS entry_count
                FROM schedule_entries
                WHERE project_id = ?
                GROUP BY source_id
                """,
                (project_id,),
            ).fetchall()
            entry_rows = connection.execute(
                """
                SELECT * FROM schedule_entries
                WHERE project_id = ?
                ORDER BY created_at
                LIMIT 500
                """,
                (project_id,),
            ).fetchall()
        floor_map: dict[str, list[str]] = {}
        for row in floor_rows:
            floor_map.setdefault(str(row["source_id"]), []).append(str(row["floor_id"]))
        entry_count_map = {str(row["source_id"]): int(row["entry_count"] or 0) for row in entry_count_rows}
        entry_map: dict[str, list[dict]] = {}
        for row in entry_rows:
            entry = self._decode_entry(row_to_dict(row) or {})
            entry_map.setdefault(str(entry.get("source_id")), []).append(entry)
        for row in schedule_rows:
            source = self._decode_source(row_to_dict(row) or {}, "schedule")
            source["floor_ids"] = floor_map.get(source["id"], [])
            source["entry_count"] = entry_count_map.get(source["id"], 0)
            source["entries"] = entry_map.get(source["id"], [])
            sources.append(source)
        for row in specification_rows:
            source = self._decode_source(row_to_dict(row) or {}, "specification")
            source["floor_ids"] = floor_map.get(source["id"], [])
            source["entry_count"] = entry_count_map.get(source["id"], 0)
            source["entries"] = entry_map.get(source["id"], [])
            sources.append(source)
        return sorted(sources, key=lambda item: (CATEGORIES.index(item["category"]), item["created_at"]))

    def get_source(self, project_id: str, source_id: str) -> dict | None:
        with get_connection() as connection:
            schedule = connection.execute(
                "SELECT * FROM schedule_files WHERE project_id = ? AND id = ? AND is_active = 1",
                (project_id, source_id),
            ).fetchone()
            specification = None if schedule else connection.execute(
                "SELECT * FROM specification_files WHERE project_id = ? AND id = ? AND is_active = 1",
                (project_id, source_id),
            ).fetchone()
            floors = connection.execute(
                "SELECT floor_id FROM supporting_file_floors WHERE project_id = ? AND source_id = ? ORDER BY created_at",
                (project_id, source_id),
            ).fetchall()
            entries = connection.execute(
                "SELECT * FROM schedule_entries WHERE project_id = ? AND source_id = ? ORDER BY created_at",
                (project_id, source_id),
            ).fetchall()
        row = schedule or specification
        if not row:
            return None
        kind = "schedule" if schedule else "specification"
        source = self._decode_source(row_to_dict(row) or {}, kind)
        source["floor_ids"] = [str(item["floor_id"]) for item in floors]
        source["entries"] = [self._decode_entry(row_to_dict(item) or {}) for item in entries]
        source["entry_count"] = len(source["entries"])
        return source

    def create_source(
        self,
        connection: Any,
        *,
        project_id: str,
        category: str,
        document_id: str,
        source_type: str,
        file_name: str | None,
        mime_type: str | None,
        content_hash: str | None,
        size_bytes: int,
        asset_key: str | None,
        page_number: int | None,
        crop: dict | None,
        scope_mode: str,
        floor_ids: list[str],
        version: int,
        schema_version: int,
        created_by: str | None,
    ) -> dict:
        definition = CATEGORY_DEFINITIONS[category]
        kind = definition["kind"]
        table = "schedule_files" if kind == "schedule" else "specification_files"
        type_column = "schedule_type" if kind == "schedule" else "specification_type"
        source_id = str(uuid4())
        now = now_iso()
        connection.execute(
            f"""
            INSERT INTO {table} (
              id, project_id, floor_id, document_id, {type_column}, source_crop_json,
              extracted_data_json, status, {type_column.split('_')[0]}_version, created_by,
              created_at, updated_at, source_type, source_page_number, file_name,
              mime_type, content_hash, size_bytes, asset_key, preview_asset_key,
              scope_mode, extraction_schema_version, extraction_status, error_message, is_active
            ) VALUES (?, ?, NULL, ?, ?, ?, '{{}}', 'processing', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, ?, ?, 'processing', NULL, 1)
            """,
            (
                source_id,
                project_id,
                document_id,
                category if kind == "schedule" else category,
                _dumps(crop) if crop else None,
                version,
                created_by,
                now,
                now,
                source_type,
                page_number,
                file_name,
                mime_type,
                content_hash,
                int(size_bytes or 0),
                asset_key,
                scope_mode,
                schema_version,
            ),
        )
        self._replace_floor_scope(connection, project_id, source_id, kind, scope_mode, floor_ids)
        self.set_category_status(connection, project_id, category, "processing")
        row = connection.execute(f"SELECT * FROM {table} WHERE id = ?", (source_id,)).fetchone()
        source = self._decode_source(row_to_dict(row) or {}, kind)
        source["floor_ids"] = floor_ids if scope_mode == "selected" else []
        source["entry_count"] = 0
        source["entries"] = []
        return source

    def update_scope(self, connection: Any, source: dict, scope_mode: str, floor_ids: list[str]) -> None:
        table = "schedule_files" if source["source_kind"] == "schedule" else "specification_files"
        connection.execute(
            f"UPDATE {table} SET scope_mode = ?, updated_at = ? WHERE id = ? AND project_id = ?",
            (scope_mode, now_iso(), source["id"], source["project_id"]),
        )
        self._replace_floor_scope(connection, source["project_id"], source["id"], source["source_kind"], scope_mode, floor_ids)

    def mark_source_status(
        self,
        source: dict,
        *,
        status: str,
        extraction_status: str | None = None,
        error_message: str | None = None,
        extracted_data: dict | None = None,
        preview_asset_key: str | None = None,
    ) -> None:
        table = "schedule_files" if source["source_kind"] == "schedule" else "specification_files"
        assignments = ["status = ?", "extraction_status = ?", "error_message = ?", "updated_at = ?"]
        params: list[Any] = [status, extraction_status or status, error_message, now_iso()]
        if extracted_data is not None:
            assignments.append("extracted_data_json = ?")
            params.append(_dumps(extracted_data))
        if preview_asset_key is not None:
            assignments.append("preview_asset_key = ?")
            params.append(preview_asset_key)
        params.extend([source["project_id"], source["id"]])
        with get_connection() as connection:
            connection.execute(
                f"UPDATE {table} SET {', '.join(assignments)} WHERE project_id = ? AND id = ?",
                tuple(params),
            )
            self._refresh_category_state(connection, source["project_id"], source["category"])

    def deactivate_source(self, connection: Any, source: dict) -> None:
        table = "schedule_files" if source["source_kind"] == "schedule" else "specification_files"
        connection.execute(
            f"UPDATE {table} SET is_active = 0, updated_at = ? WHERE project_id = ? AND id = ?",
            (now_iso(), source["project_id"], source["id"]),
        )
        connection.execute("DELETE FROM supporting_file_floors WHERE source_id = ?", (source["id"],))
        connection.execute("DELETE FROM schedule_entries WHERE source_id = ?", (source["id"],))
        self._refresh_category_state(connection, source["project_id"], source["category"])

    def set_category_status(self, connection: Any, project_id: str, category: str, status: str) -> None:
        connection.execute(
            """
            INSERT INTO specification_category_states(project_id, category, status, updated_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(project_id, category) DO UPDATE SET
              status = excluded.status, updated_at = excluded.updated_at
            """,
            (project_id, category, status, now_iso()),
        )

    def category_states(self, project_id: str) -> dict[str, str]:
        with get_connection() as connection:
            rows = connection.execute(
                "SELECT category, status FROM specification_category_states WHERE project_id = ?",
                (project_id,),
            ).fetchall()
        return {str(row["category"]): str(row["status"]) for row in rows}

    def replace_entries(
        self,
        *,
        source: dict,
        rows: Iterable[dict],
        method: str,
        extraction_version: int,
    ) -> tuple[int, bool]:
        now = now_iso()
        conflict_found = False
        saved_count = 0
        with get_connection() as connection:
            connection.execute("DELETE FROM schedule_entries WHERE source_id = ?", (source["id"],))
            for item in rows:
                entity_key = str(item["entity_key"])
                data = item["data"]
                accepted = connection.execute(
                    """
                    SELECT * FROM schedule_entries
                    WHERE project_id = ? AND category = ? AND entity_key = ? AND is_accepted = 1
                    ORDER BY source_priority DESC, created_at ASC LIMIT 1
                    """,
                    (source["project_id"], source["category"], entity_key),
                ).fetchone()
                is_accepted = accepted is None
                review_state = "ready"
                if accepted:
                    accepted_data = _loads(accepted["data_json"])
                    if self._business_data(accepted_data) != self._business_data(data):
                        conflict_found = True
                        review_state = "needs_review"
                        self._create_conflict_issue(connection, source, entity_key, accepted_data, data)
                connection.execute(
                    """
                    INSERT INTO schedule_entries (
                      id, project_id, source_id, source_kind, category, entity_key,
                      data_json, source_location_json, extraction_method, confidence,
                      review_state, is_accepted, source_priority, extraction_version,
                      created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        str(uuid4()),
                        source["project_id"],
                        source["id"],
                        source["source_kind"],
                        source["category"],
                        entity_key,
                        _dumps(data),
                        _dumps(item.get("source_location") or {}),
                        method,
                        item.get("confidence"),
                        review_state,
                        int(is_accepted),
                        int(CATEGORY_DEFINITIONS[source["category"]]["priority"]),
                        extraction_version,
                        now,
                        now,
                    ),
                )
                saved_count += 1
            self._protect_confirmed_values(connection, source, list(rows))
        return saved_count, conflict_found

    def cache_get(self, content_hash: str | None, category: str, schema_version: int) -> list[dict] | None:
        if not content_hash:
            return None
        with get_connection() as connection:
            row = connection.execute(
                "SELECT result_json FROM schedule_extraction_cache WHERE content_hash = ? AND category = ? AND schema_version = ?",
                (content_hash, category, schema_version),
            ).fetchone()
        if not row:
            return None
        value = _loads(row["result_json"], [])
        return value if isinstance(value, list) else None

    def cache_put(self, content_hash: str | None, category: str, schema_version: int, rows: list[dict]) -> None:
        if not content_hash:
            return
        now = now_iso()
        with get_connection() as connection:
            connection.execute(
                """
                INSERT INTO schedule_extraction_cache(content_hash, category, schema_version, result_json, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(content_hash, category, schema_version) DO UPDATE SET
                  result_json = excluded.result_json, updated_at = excluded.updated_at
                """,
                (content_hash, category, schema_version, _dumps(rows), now, now),
            )

    def active_jobs_by_source(self, project_id: str) -> dict[str, dict]:
        with get_connection() as connection:
            rows = connection.execute(
                """
                SELECT * FROM job_runs
                WHERE project_id = ? AND status IN ('pending', 'running')
                ORDER BY created_at DESC
                """,
                (project_id,),
            ).fetchall()
        result: dict[str, dict] = {}
        for row in rows:
            item = row_to_dict(row) or {}
            key = str(item.get("job_key") or "")
            marker = ":entity:"
            if marker not in key:
                continue
            source_id = key.split(marker, 1)[1].split(":", 1)[0]
            result.setdefault(source_id, item)
        return result

    def active_job_for_source(self, project_id: str, source_id: str) -> dict | None:
        return self.active_jobs_by_source(project_id).get(source_id)

    def _replace_floor_scope(
        self,
        connection: Any,
        project_id: str,
        source_id: str,
        source_kind: str,
        scope_mode: str,
        floor_ids: list[str],
    ) -> None:
        connection.execute("DELETE FROM supporting_file_floors WHERE source_id = ?", (source_id,))
        if scope_mode != "selected":
            return
        now = now_iso()
        for floor_id in floor_ids:
            connection.execute(
                """
                INSERT INTO supporting_file_floors(source_id, source_kind, project_id, floor_id, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (source_id, source_kind, project_id, floor_id, now),
            )

    def _refresh_category_state(self, connection: Any, project_id: str, category: str) -> None:
        definition = CATEGORY_DEFINITIONS[category]
        table = "schedule_files" if definition["kind"] == "schedule" else "specification_files"
        type_column = "schedule_type" if definition["kind"] == "schedule" else "specification_type"
        rows = connection.execute(
            f"SELECT status, extraction_status FROM {table} WHERE project_id = ? AND {type_column} = ? AND is_active = 1",
            (project_id, category),
        ).fetchall()
        if not rows:
            current = connection.execute(
                "SELECT status FROM specification_category_states WHERE project_id = ? AND category = ?",
                (project_id, category),
            ).fetchone()
            status = "skipped" if current and current["status"] == "skipped" else "needs_review"
        elif any(str(row["extraction_status"]) == "failed" for row in rows):
            status = "failed"
        elif any(str(row["extraction_status"]) == "processing" for row in rows):
            status = "processing"
        elif any(str(row["status"]) == "needs_review" for row in rows):
            status = "needs_review"
        else:
            status = "ready"
        self.set_category_status(connection, project_id, category, status)

    def _create_conflict_issue(
        self,
        connection: Any,
        source: dict,
        entity_key: str,
        accepted_data: dict,
        suggestion_data: dict,
    ) -> None:
        existing = connection.execute(
            """
            SELECT id FROM review_issues
            WHERE project_id = ? AND entity_type = 'schedule_entry' AND entity_id = ?
              AND issue_type = 'source_conflict' AND status = 'needs_review'
            LIMIT 1
            """,
            (source["project_id"], entity_key),
        ).fetchone()
        if existing:
            return
        versions = connection.execute(
            "SELECT review_version FROM project_versions WHERE project_id = ?",
            (source["project_id"],),
        ).fetchone()
        review_version = int(versions["review_version"] or 0) + 1 if versions else 1
        connection.execute(
            "UPDATE project_versions SET review_version = ?, updated_at = ? WHERE project_id = ?",
            (review_version, now_iso(), source["project_id"]),
        )
        connection.execute(
            """
            INSERT INTO review_issues(
              id, project_id, floor_id, entity_type, entity_id, issue_type,
              title, detail, severity, status, suggestion_json, source,
              review_version, created_at, updated_at
            ) VALUES (?, ?, NULL, 'schedule_entry', ?, 'source_conflict', ?, ?, 'medium',
                      'needs_review', ?, 'schedule', ?, ?, ?)
            """,
            (
                str(uuid4()),
                source["project_id"],
                entity_key,
                "Conflicting schedule information",
                "Two supporting sources contain different values for the same item.",
                _dumps({"accepted": accepted_data, "suggested": suggestion_data, "source_id": source["id"]}),
                review_version,
                now_iso(),
                now_iso(),
            ),
        )

    def _protect_confirmed_values(self, connection: Any, source: dict, rows: list[dict]) -> None:
        for item in rows:
            data = item.get("data") or {}
            type_code = data.get("type_code") or data.get("floor_type_code")
            if not type_code:
                continue
            elements = connection.execute(
                "SELECT id FROM elements WHERE project_id = ? AND type_code = ? AND user_confirmed = 1",
                (source["project_id"], str(type_code)),
            ).fetchall()
            for element in elements:
                confirmed = connection.execute(
                    "SELECT property_name, value_json FROM element_properties WHERE element_id = ? AND is_confirmed = 1",
                    (element["id"],),
                ).fetchall()
                for prop in confirmed:
                    candidate = data.get(str(prop["property_name"]))
                    if candidate is None:
                        continue
                    if _loads(prop["value_json"]) != candidate:
                        self._create_conflict_issue(
                            connection,
                            source,
                            f"{element['id']}:{prop['property_name']}",
                            {"value": _loads(prop["value_json"]), "confirmed": True},
                            {"value": candidate, "source_id": source["id"]},
                        )


    @staticmethod
    def _business_data(value: dict) -> dict:
        return {key: item for key, item in value.items() if key not in {"source_page", "source_text"}}

    @staticmethod
    def _decode_source(row: dict, kind: str) -> dict:
        category = row.get("schedule_type") if kind == "schedule" else row.get("specification_type")
        return {
            **row,
            "source_kind": kind,
            "category": category,
            "crop": _loads(row.get("source_crop_json"), None) if row.get("source_crop_json") else None,
            "extracted_data": _loads(row.get("extracted_data_json")),
        }

    @staticmethod
    def _decode_entry(row: dict) -> dict:
        return {
            **row,
            "data": _loads(row.get("data_json")),
            "source_location": _loads(row.get("source_location_json")),
            "is_accepted": bool(row.get("is_accepted")),
        }


specifications_repository = SpecificationsRepository()
