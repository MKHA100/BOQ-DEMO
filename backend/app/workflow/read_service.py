from __future__ import annotations

from typing import Any

from app.core.errors import not_found
from app.database.session import get_connection, row_to_dict
from app.workflow.repo import loads


class WorkflowReadService:
    def list_document_pages(self, project_id: str, document_id: str) -> list[dict]:
        with get_connection() as connection:
            document = connection.execute(
                "SELECT id FROM documents WHERE id = ? AND project_id = ?",
                (document_id, project_id),
            ).fetchone()
            if not document:
                raise not_found("Document not found.")
            rows = connection.execute(
                "SELECT * FROM document_pages WHERE project_id = ? AND document_id = ? ORDER BY page_number",
                (project_id, document_id),
            ).fetchall()
        return [self._decode(row_to_dict(row) or {}) for row in rows]

    def list_extraction_records(
        self,
        project_id: str,
        *,
        document_id: str | None = None,
        extraction_type: str | None = None,
    ) -> list[dict]:
        from app.pdf_upload.repo import pdf_upload_repository

        if document_id:
            with get_connection() as connection:
                document = connection.execute(
                    "SELECT id FROM documents WHERE id = ? AND project_id = ?",
                    (document_id, project_id),
                ).fetchone()
                if not document:
                    raise not_found("Document not found.")
        return pdf_upload_repository.list_extraction_records(
            project_id,
            document_id=document_id,
            extraction_type=extraction_type,
        )

    def get_current_crop(self, project_id: str, floor_id: str) -> dict | None:
        with get_connection() as connection:
            self._require_floor(connection, project_id, floor_id)
            row = connection.execute(
                """
                SELECT * FROM floor_crops
                WHERE project_id = ? AND floor_id = ? AND is_current = 1
                ORDER BY crop_version DESC LIMIT 1
                """,
                (project_id, floor_id),
            ).fetchone()
        return self._decode(row_to_dict(row) or {}) if row else None

    def get_calibration(self, project_id: str, floor_id: str) -> dict | None:
        with get_connection() as connection:
            self._require_floor(connection, project_id, floor_id)
            row = connection.execute(
                """
                SELECT * FROM calibrations
                WHERE project_id = ? AND floor_id = ?
                ORDER BY scale_version DESC LIMIT 1
                """,
                (project_id, floor_id),
            ).fetchone()
        return self._decode(row_to_dict(row) or {}) if row else None

    def list_schedule_files(
        self,
        project_id: str,
        *,
        floor_id: str | None = None,
        schedule_type: str | None = None,
    ) -> list[dict]:
        where = ["project_id = ?"]
        params: list[Any] = [project_id]
        if floor_id:
            where.append("floor_id = ?")
            params.append(floor_id)
        if schedule_type:
            where.append("schedule_type = ?")
            params.append(schedule_type)
        with get_connection() as connection:
            if floor_id:
                self._require_floor(connection, project_id, floor_id)
            rows = connection.execute(
                f"SELECT * FROM schedule_files WHERE {' AND '.join(where)} ORDER BY created_at DESC",
                params,
            ).fetchall()
        return [self._decode(row_to_dict(row) or {}) for row in rows]

    def list_specification_files(self, project_id: str, *, floor_id: str | None = None) -> list[dict]:
        where = ["project_id = ?"]
        params: list[Any] = [project_id]
        if floor_id:
            where.append("floor_id = ?")
            params.append(floor_id)
        with get_connection() as connection:
            if floor_id:
                self._require_floor(connection, project_id, floor_id)
            rows = connection.execute(
                f"SELECT * FROM specification_files WHERE {' AND '.join(where)} ORDER BY created_at DESC",
                params,
            ).fetchall()
        return [self._decode(row_to_dict(row) or {}) for row in rows]

    def list_elements(
        self,
        project_id: str,
        floor_id: str,
        *,
        element_type: str | None,
        status: str | None,
        limit: int,
        offset: int,
    ) -> dict:
        self._validate_floor(project_id, floor_id)
        where = ["project_id = ?", "floor_id = ?"]
        params: list[Any] = [project_id, floor_id]
        if element_type:
            where.append("element_type = ?")
            params.append(element_type)
        if status:
            where.append("status = ?")
            params.append(status)
        return self._paged_entities(
            table="elements",
            where=where,
            params=params,
            order="updated_at DESC, id",
            limit=limit,
            offset=offset,
            include_properties=True,
        )

    def list_walls(self, project_id: str, floor_id: str, *, status: str | None, limit: int, offset: int) -> dict:
        return self._list_floor_table("walls", project_id, floor_id, status=status, limit=limit, offset=offset)

    def list_rooms(self, project_id: str, floor_id: str, *, status: str | None, limit: int, offset: int) -> dict:
        return self._list_floor_table("rooms", project_id, floor_id, status=status, limit=limit, offset=offset)

    def list_review_issues(
        self,
        project_id: str,
        *,
        floor_id: str | None,
        status: str | None,
        limit: int,
        offset: int,
    ) -> dict:
        where = ["project_id = ?"]
        params: list[Any] = [project_id]
        if floor_id:
            self._validate_floor(project_id, floor_id)
            where.append("floor_id = ?")
            params.append(floor_id)
        if status:
            where.append("status = ?")
            params.append(status)
        return self._paged_entities("review_issues", where, params, "updated_at DESC, id", limit, offset)

    def list_quantities(
        self,
        project_id: str,
        *,
        floor_id: str | None,
        entity_type: str | None,
        limit: int,
        offset: int,
    ) -> dict:
        where = ["project_id = ?"]
        params: list[Any] = [project_id]
        if floor_id:
            self._validate_floor(project_id, floor_id)
            where.append("floor_id = ?")
            params.append(floor_id)
        if entity_type:
            where.append("entity_type = ?")
            params.append(entity_type)
        return self._paged_entities("quantity_snapshots", where, params, "updated_at DESC, id", limit, offset)

    def get_boq_view(self, project_id: str, *, floor_id: str | None, limit: int, offset: int) -> dict:
        if floor_id:
            self._validate_floor(project_id, floor_id)
        with get_connection() as connection:
            boq_row = connection.execute(
                "SELECT * FROM boqs WHERE project_id = ? ORDER BY boq_version DESC LIMIT 1",
                (project_id,),
            ).fetchone()
        boq = self._decode(row_to_dict(boq_row) or {}) if boq_row else None
        if not boq:
            return {"boq": None, "items": [], "total": 0, "limit": limit, "offset": offset}
        where = ["project_id = ?", "boq_id = ?"]
        params: list[Any] = [project_id, boq["id"]]
        if floor_id:
            where.append("floor_id = ?")
            params.append(floor_id)
        rows = self._paged_entities("boq_rows", where, params, "section, item_code, id", limit, offset)
        return {"boq": boq, **rows}

    def _list_floor_table(
        self,
        table: str,
        project_id: str,
        floor_id: str,
        *,
        status: str | None,
        limit: int,
        offset: int,
    ) -> dict:
        self._validate_floor(project_id, floor_id)
        where = ["project_id = ?", "floor_id = ?"]
        params: list[Any] = [project_id, floor_id]
        if status:
            where.append("status = ?")
            params.append(status)
        return self._paged_entities(table, where, params, "updated_at DESC, id", limit, offset)

    def _paged_entities(
        self,
        table: str,
        where: list[str],
        params: list[Any],
        order: str,
        limit: int,
        offset: int,
        include_properties: bool = False,
    ) -> dict:
        with get_connection() as connection:
            clause = " AND ".join(where)
            total_row = connection.execute(
                f"SELECT COUNT(*) AS total FROM {table} WHERE {clause}",
                params,
            ).fetchone()
            rows = connection.execute(
                f"SELECT * FROM {table} WHERE {clause} ORDER BY {order} LIMIT ? OFFSET ?",
                [*params, limit, offset],
            ).fetchall()
            items = [self._decode(row_to_dict(row) or {}) for row in rows]
            if include_properties and items:
                ids = [item["id"] for item in items]
                placeholders = ",".join("?" for _ in ids)
                property_rows = connection.execute(
                    f"SELECT * FROM element_properties WHERE element_id IN ({placeholders}) ORDER BY property_name",
                    ids,
                ).fetchall()
                by_element: dict[str, list[dict]] = {element_id: [] for element_id in ids}
                for property_row in property_rows:
                    decoded = self._decode(row_to_dict(property_row) or {})
                    by_element.setdefault(decoded["element_id"], []).append(decoded)
                for item in items:
                    item["properties"] = by_element.get(item["id"], [])
        return {
            "items": items,
            "total": int(total_row["total"] if total_row else 0),
            "limit": limit,
            "offset": offset,
        }

    def _validate_floor(self, project_id: str, floor_id: str) -> None:
        with get_connection() as connection:
            self._require_floor(connection, project_id, floor_id)

    @staticmethod
    def _require_floor(connection: Any, project_id: str, floor_id: str) -> None:
        row = connection.execute(
            "SELECT id FROM floors WHERE project_id = ? AND id = ?",
            (project_id, floor_id),
        ).fetchone()
        if not row:
            raise not_found("Floor not found.")

    @staticmethod
    def _decode(record: dict) -> dict:
        decoded = dict(record)
        for key in list(decoded):
            if key.endswith("_json"):
                decoded[key[:-5]] = loads(decoded.pop(key))
        for key in ("is_confirmed", "user_confirmed", "excluded", "is_stale", "is_current", "is_primary", "vector_text_available"):
            if key in decoded:
                decoded[key] = bool(decoded[key])
        return decoded


workflow_read_service = WorkflowReadService()
