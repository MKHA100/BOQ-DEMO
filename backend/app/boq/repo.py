from __future__ import annotations

from uuid import uuid4

from app.boq.template_repo import boq_template_repository
from app.database.session import get_connection, row_to_dict
from app.workflow.repo_base import dumps, loads, now_iso


class BoqRepository:
    def ensure_templates(self, project_id: str) -> list[dict]:
        return boq_template_repository.ensure_builtins(project_id)

    def ensure_template(self, project_id: str) -> dict:
        return boq_template_repository.selected(project_id)

    def select_template(self, project_id: str, template_id: str) -> dict:
        return boq_template_repository.select(project_id, template_id)

    def ensure_boq(self, project_id: str, template: dict, created_by: str | None = None, setup_version: int = 1) -> dict:
        now = now_iso()
        with get_connection() as connection:
            row = connection.execute(
                "SELECT * FROM boqs WHERE project_id=? ORDER BY created_at LIMIT 1", (project_id,)
            ).fetchone()
            if row and (row["template_id"] != template["id"] or int(row["setup_version"] or 1) != int(setup_version)):
                connection.execute(
                    "UPDATE boqs SET template_id=?,template_version=?,setup_version=?,is_stale=1,updated_at=? WHERE id=?",
                    (template["id"], int(template["version"]), int(setup_version), now, row["id"]),
                )
                row = connection.execute("SELECT * FROM boqs WHERE id=?", (row["id"],)).fetchone()
            if not row:
                boq_id = str(uuid4())
                connection.execute(
                    """
                    INSERT INTO boqs (
                      id,project_id,name,template_id,status,is_stale,boq_version,
                      source_versions_json,created_by,created_at,updated_at,template_version,
                      setup_version,report_json,currency,vat_percentage
                    ) VALUES (?,?,?,?,'not_ready',1,0,'{}',?,?,?, ?,?,'{}','Rs',0)
                    """,
                    (boq_id, project_id, "Bill of Quantities", template["id"], created_by, now, now, int(template["version"]), int(setup_version)),
                )
                row = connection.execute("SELECT * FROM boqs WHERE id=?", (boq_id,)).fetchone()
        return self._decode(row_to_dict(row) or {})

    def upsert_generated_row(
        self, *, boq: dict, group_key: str, floor_id: str | None, entity_type: str,
        section: str, item_code: str | None, description: str, quantity: float, unit: str,
        source_ids: list[str], floor_ids: list[str], source_versions: dict, source_hash: str,
        sort_order: int, status: str = "ready", bill_no: str | None = None,
        bill_name: str | None = None, subcategory_code: str | None = None,
        subcategory_name: str | None = None,
    ) -> dict:
        now = now_iso()
        with get_connection() as connection:
            existing = connection.execute(
                "SELECT * FROM boq_rows WHERE boq_id=? AND group_key=? AND manual=0",
                (boq["id"], group_key),
            ).fetchone()
            row_id = existing["id"] if existing else str(uuid4())
            protected_description = bool(existing and existing["protected_description"])
            protected_rate = bool(existing and existing["protected_rate"])
            resolved_description = existing["description"] if protected_description else description
            rate = existing["rate"] if existing and protected_rate else existing["rate"] if existing else None
            amount = round(float(quantity) * float(rate), 2) if rate not in (None, "") else None
            connection.execute(
                """
                INSERT INTO boq_rows (
                  id,project_id,floor_id,boq_id,entity_type,entity_id,section,item_code,
                  description,quantity,unit,rate,amount,status,is_stale,source_versions_json,
                  boq_version,created_at,updated_at,group_key,source_ids_json,floor_ids_json,
                  template_version,manual,protected_description,excluded,sort_order,
                  source_version_hash,bill_no,bill_name,subcategory_code,subcategory_name,
                  protected_rate
                ) VALUES (?,?,?,?,?,NULL,?,?,?,?,?,?,?,?,0,?,?,?,?,?,?,?,?,0,?,0,?,?,?,?,?,?,?)
                ON CONFLICT(boq_id,group_key) WHERE manual=0 DO UPDATE SET
                  floor_id=excluded.floor_id, entity_type=excluded.entity_type,
                  section=excluded.section, item_code=excluded.item_code,
                  description=CASE WHEN boq_rows.protected_description=1 THEN boq_rows.description ELSE excluded.description END,
                  quantity=excluded.quantity, unit=excluded.unit,
                  rate=CASE WHEN boq_rows.protected_rate=1 THEN boq_rows.rate ELSE excluded.rate END,
                  amount=CASE WHEN boq_rows.protected_rate=1 AND boq_rows.rate IS NOT NULL THEN ROUND(excluded.quantity*boq_rows.rate,2) ELSE excluded.amount END,
                  status=excluded.status, is_stale=0, source_versions_json=excluded.source_versions_json,
                  boq_version=excluded.boq_version, updated_at=excluded.updated_at,
                  source_ids_json=excluded.source_ids_json, floor_ids_json=excluded.floor_ids_json,
                  template_version=excluded.template_version, sort_order=excluded.sort_order,
                  source_version_hash=excluded.source_version_hash, bill_no=excluded.bill_no,
                  bill_name=excluded.bill_name, subcategory_code=excluded.subcategory_code,
                  subcategory_name=excluded.subcategory_name
                """,
                (
                    row_id, boq["project_id"], floor_id, boq["id"], entity_type, section,
                    item_code, resolved_description, quantity, unit, rate, amount, status,
                    dumps(source_versions), int(boq["boq_version"]), now, now, group_key,
                    dumps(source_ids), dumps(floor_ids), int(boq.get("template_version") or 1),
                    1 if protected_description else 0, sort_order, source_hash, bill_no,
                    bill_name, subcategory_code, subcategory_name, 1 if protected_rate else 0,
                ),
            )
            row = connection.execute(
                "SELECT * FROM boq_rows WHERE boq_id=? AND group_key=?", (boq["id"], group_key)
            ).fetchone()
        return self._decode(row_to_dict(row) or {})

    def delete_missing_generated(self, boq_id: str, group_keys: set[str]) -> None:
        with get_connection() as connection:
            rows = connection.execute(
                "SELECT id,group_key FROM boq_rows WHERE boq_id=? AND manual=0", (boq_id,)
            ).fetchall()
            for row in rows:
                if row["group_key"] not in group_keys:
                    connection.execute("DELETE FROM boq_rows WHERE id=?", (row["id"],))

    def rows(self, project_id: str, boq_id: str, floor_id: str | None = None) -> list[dict]:
        query = "SELECT * FROM boq_rows WHERE project_id=? AND boq_id=?"
        values: list[object] = [project_id, boq_id]
        if floor_id:
            query += " AND (floor_id=? OR floor_ids_json LIKE ?)"
            values.extend([floor_id, f'%"{floor_id}"%'])
        query += " ORDER BY excluded, sort_order, section, description"
        with get_connection() as connection:
            rows = connection.execute(query, values).fetchall()
        return [self._decode(row_to_dict(row) or {}) for row in rows]

    def update_boq(
        self, boq_id: str, *, version: int, source_versions: dict, status: str = "ready",
        setup_version: int | None = None, template_version: int | None = None,
        report: dict | None = None, report_hash: str | None = None,
        currency: str | None = None, vat_percentage: float | None = None,
    ) -> dict:
        assignments = ["boq_version=?", "source_versions_json=?", "status=?", "is_stale=0", "generated_at=?", "updated_at=?"]
        values: list[object] = [version, dumps(source_versions), status, now_iso(), now_iso()]
        optional = {
            "setup_version": setup_version, "template_version": template_version,
            "report_json": dumps(report) if report is not None else None,
            "report_hash": report_hash, "currency": currency, "vat_percentage": vat_percentage,
        }
        for column, value in optional.items():
            if value is not None:
                assignments.append(f"{column}=?"); values.append(value)
        values.append(boq_id)
        with get_connection() as connection:
            connection.execute(f"UPDATE boqs SET {','.join(assignments)} WHERE id=?", values)
            row = connection.execute("SELECT * FROM boqs WHERE id=?", (boq_id,)).fetchone()
        return self._decode(row_to_dict(row) or {})

    def add_manual(
        self, *, project_id: str, boq_id: str, floor_id: str | None, description: str,
        section: str | None, quantity: float, unit: str, version: int,
        rate: float | None = None, item_code: str | None = None,
    ) -> dict:
        row_id = str(uuid4()); now = now_iso()
        amount = round(float(quantity) * float(rate), 2) if rate is not None else None
        with get_connection() as connection:
            maximum = connection.execute(
                "SELECT COALESCE(MAX(sort_order),0) AS value FROM boq_rows WHERE boq_id=?", (boq_id,)
            ).fetchone()["value"]
            connection.execute(
                """
                INSERT INTO boq_rows (
                  id,project_id,floor_id,boq_id,entity_type,section,item_code,description,
                  quantity,unit,rate,amount,status,is_stale,source_versions_json,boq_version,
                  created_at,updated_at,manual,protected_description,protected_rate,sort_order,
                  bill_no,bill_name,subcategory_code,subcategory_name,source_ids_json,floor_ids_json
                ) VALUES (?,?,?,?,'manual',?,?,?,?,?,?,?,'ready',0,'{}',?,?,?,1,1,?,?,'09','Other items','9A',?,'[]',?)
                """,
                (
                    row_id, project_id, floor_id, boq_id, section or "Other items", item_code,
                    description, quantity, unit, rate, amount, version, now, now,
                    1 if rate is not None else 0, int(maximum or 0) + 10,
                    section or "Other items", dumps([floor_id] if floor_id else []),
                ),
            )
            row = connection.execute("SELECT * FROM boq_rows WHERE id=?", (row_id,)).fetchone()
        return self._decode(row_to_dict(row) or {})

    def update_row(self, project_id: str, row_id: str, updates: dict) -> dict:
        allowed = {
            "description", "section", "excluded", "sort_order", "rate", "quantity",
            "unit", "item_code", "status",
        }
        parts: list[str] = []; values: list[object] = []
        for key, value in updates.items():
            if key not in allowed: continue
            if key == "excluded": value = 1 if value else 0
            parts.append(f"{key}=?"); values.append(value)
            if key == "description": parts.append("protected_description=1")
            if key == "rate": parts.append("protected_rate=1")
        if not parts:
            return self.get_row(project_id, row_id) or {}
        parts.append("updated_at=?"); values.extend([now_iso(), project_id, row_id])
        with get_connection() as connection:
            connection.execute(f"UPDATE boq_rows SET {','.join(parts)} WHERE project_id=? AND id=?", values)
            connection.execute(
                "UPDATE boq_rows SET amount=CASE WHEN rate IS NULL THEN NULL ELSE ROUND(quantity*rate,2) END WHERE project_id=? AND id=?",
                (project_id, row_id),
            )
            connection.execute("UPDATE boqs SET is_stale=1,updated_at=? WHERE project_id=?", (now_iso(), project_id))
            row = connection.execute("SELECT * FROM boq_rows WHERE id=?", (row_id,)).fetchone()
        return self._decode(row_to_dict(row) or {})

    def get_row(self, project_id: str, row_id: str) -> dict | None:
        with get_connection() as connection:
            row = connection.execute("SELECT * FROM boq_rows WHERE project_id=? AND id=?", (project_id, row_id)).fetchone()
        return self._decode(row_to_dict(row) or {}) if row else None

    def apply_report_numbers(self, boq_id: str, report: dict) -> None:
        mapping: dict[str, str] = {}
        for bill in report.get("bills") or []:
            for section in bill.get("sections") or []:
                for item in section.get("items") or []:
                    if item.get("id") and item.get("item_number"):
                        mapping[str(item["id"])] = str(item["item_number"])
        if not mapping:
            return
        with get_connection() as connection:
            for row_id, item_number in mapping.items():
                connection.execute(
                    "UPDATE boq_rows SET boq_item_number=?,updated_at=? WHERE boq_id=? AND id=?",
                    (item_number, now_iso(), boq_id, row_id),
                )

    def sync_export_snapshot(self, export_id: str, boq: dict) -> dict:
        with get_connection() as connection:
            connection.execute(
                """
                UPDATE export_files
                SET boq_id=?,boq_version=?,template_version=?,setup_version=?,report_hash=?,updated_at=?
                WHERE id=?
                """,
                (boq["id"], int(boq.get("boq_version") or 0), int(boq.get("template_version") or 1),
                 int(boq.get("setup_version") or 1), boq.get("report_hash"), now_iso(), export_id),
            )
            row = connection.execute("SELECT * FROM export_files WHERE id=?", (export_id,)).fetchone()
        return self._decode(row_to_dict(row) or {})

    def create_or_get_export(
        self, *, project_id: str, boq: dict, format: str, floor_mode: str,
        floor_id: str | None, cache_key: str, created_by: str | None,
    ) -> tuple[dict, bool]:
        now = now_iso()
        with get_connection() as connection:
            row = connection.execute("SELECT * FROM export_files WHERE cache_key=?", (cache_key,)).fetchone()
            if row: return self._decode(row_to_dict(row) or {}), False
            export_id = str(uuid4())
            extension = "xlsx" if format == "xlsx" else format
            filename = f"boq-{int(boq['boq_version'])}-{floor_mode}.{extension}"
            connection.execute(
                """
                INSERT INTO export_files (
                  id,project_id,boq_id,format,floor_mode,floor_id,boq_version,
                  template_version,setup_version,report_hash,cache_key,filename,status,
                  created_by,created_at,updated_at
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?, 'processing',?,?,?)
                """,
                (
                    export_id, project_id, boq["id"], format, floor_mode, floor_id,
                    int(boq["boq_version"]), int(boq.get("template_version") or 1),
                    int(boq.get("setup_version") or 1), boq.get("report_hash"), cache_key,
                    filename, created_by, now, now,
                ),
            )
            row = connection.execute("SELECT * FROM export_files WHERE id=?", (export_id,)).fetchone()
        return self._decode(row_to_dict(row) or {}), True

    def finish_export(self, export_id: str, object_key: str | None, status: str, error: str | None = None) -> dict:
        with get_connection() as connection:
            connection.execute(
                "UPDATE export_files SET object_key=?,status=?,error_message=?,updated_at=? WHERE id=?",
                (object_key, status, error, now_iso(), export_id),
            )
            row = connection.execute("SELECT * FROM export_files WHERE id=?", (export_id,)).fetchone()
        return self._decode(row_to_dict(row) or {})

    def exports(self, project_id: str, boq_id: str) -> list[dict]:
        with get_connection() as connection:
            rows = connection.execute(
                "SELECT * FROM export_files WHERE project_id=? AND boq_id=? ORDER BY created_at DESC",
                (project_id, boq_id),
            ).fetchall()
        return [self._decode(row_to_dict(row) or {}) for row in rows]

    def get_export(self, project_id: str, export_id: str) -> dict | None:
        with get_connection() as connection:
            row = connection.execute(
                "SELECT * FROM export_files WHERE project_id=? AND id=?", (project_id, export_id)
            ).fetchone()
        return self._decode(row_to_dict(row) or {}) if row else None

    def get_boq(self, project_id: str, boq_id: str) -> dict | None:
        with get_connection() as connection:
            row = connection.execute("SELECT * FROM boqs WHERE project_id=? AND id=?", (project_id, boq_id)).fetchone()
        return self._decode(row_to_dict(row) or {}) if row else None

    @staticmethod
    def _decode(record: dict) -> dict:
        result = dict(record)
        for key in list(result):
            if key.endswith("_json"):
                result[key[:-5]] = loads(result.pop(key))
        for key in (
            "is_stale", "manual", "protected_description", "protected_rate", "excluded",
            "is_default", "is_builtin", "is_active",
        ):
            if key in result: result[key] = bool(result[key])
        return result


boq_repository = BoqRepository()
