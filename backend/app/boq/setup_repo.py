from __future__ import annotations

from uuid import uuid4

from app.database.session import get_connection, row_to_dict
from app.workflow.repo_base import dumps, loads, now_iso

DEFAULT_SECTION_ORDER = ["1", "2", "3", "4", "5", "6", "7", "8", "9"]


class BoqSetupRepository:
    def ensure(self, project: dict) -> dict:
        now = now_iso()
        with get_connection() as connection:
            row = connection.execute(
                "SELECT * FROM boq_document_setups WHERE project_id=?",
                (project["id"],),
            ).fetchone()
            if not row:
                connection.execute(
                    """
                    INSERT INTO boq_document_setups (
                      id, project_id, project_name, client_name, consultant_name, location,
                      boq_title, currency, vat_percentage, include_rates, include_amounts,
                      include_preliminaries, include_provisional_sums, include_signature_section,
                      format_style, item_numbering_format, measurement_unit_style,
                      description_style, section_order_json, setup_version, created_at, updated_at
                    ) VALUES (?,?,?,?,?,?,'Bill of Quantities','Rs',0,0,0,1,0,1,
                              'formal_tender','section_sequence','metric','standard',?,1,?,?)
                    """,
                    (
                        str(uuid4()), project["id"], project.get("name") or "",
                        project.get("client_name") or "", "", project.get("location") or "",
                        dumps(DEFAULT_SECTION_ORDER), now, now,
                    ),
                )
                row = connection.execute(
                    "SELECT * FROM boq_document_setups WHERE project_id=?", (project["id"],)
                ).fetchone()
        return self._decode(row_to_dict(row) or {})

    def get(self, project_id: str) -> dict | None:
        with get_connection() as connection:
            row = connection.execute(
                "SELECT * FROM boq_document_setups WHERE project_id=?", (project_id,)
            ).fetchone()
        return self._decode(row_to_dict(row) or {}) if row else None

    def update(self, project_id: str, updates: dict) -> dict:
        allowed = {
            "project_name", "client_name", "consultant_name", "location", "boq_title",
            "currency", "vat_percentage", "include_rates", "include_amounts",
            "include_preliminaries", "include_provisional_sums", "include_signature_section",
            "format_style", "item_numbering_format", "measurement_unit_style",
            "description_style", "section_order",
        }
        parts: list[str] = []
        values: list[object] = []
        for key, value in updates.items():
            if key not in allowed:
                continue
            column = "section_order_json" if key == "section_order" else key
            if key == "section_order":
                value = dumps(value)
            elif key.startswith("include_"):
                value = 1 if value else 0
            parts.append(f"{column}=?")
            values.append(value)
        parts.extend(["setup_version=setup_version+1", "updated_at=?"])
        values.extend([now_iso(), project_id])
        with get_connection() as connection:
            connection.execute(
                f"UPDATE boq_document_setups SET {','.join(parts)} WHERE project_id=?",
                values,
            )
            connection.execute(
                "UPDATE boqs SET is_stale=1,updated_at=? WHERE project_id=?",
                (now_iso(), project_id),
            )
            row = connection.execute(
                "SELECT * FROM boq_document_setups WHERE project_id=?", (project_id,)
            ).fetchone()
        return self._decode(row_to_dict(row) or {})

    @staticmethod
    def _decode(record: dict) -> dict:
        result = dict(record)
        result["section_order"] = loads(result.pop("section_order_json", "[]"))
        for key in (
            "include_rates", "include_amounts", "include_preliminaries",
            "include_provisional_sums", "include_signature_section",
        ):
            result[key] = bool(result.get(key))
        return result


boq_setup_repository = BoqSetupRepository()
