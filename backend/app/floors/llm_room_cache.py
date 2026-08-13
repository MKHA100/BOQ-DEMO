from __future__ import annotations

from typing import Any
from uuid import uuid4

from app.database.session import get_connection, row_to_dict
from app.workflow.repo_base import dumps, loads, now_iso


class LLMRoomCache:
    """Short-transaction persistence for floor-level interpretation.

    No method performs network work. The interpreter claims a run, closes the
    transaction, calls the API, then opens a new transaction to complete it.
    """

    @staticmethod
    def _decode(row: Any) -> dict[str, Any] | None:
        record = row_to_dict(row)
        if not record:
            return None
        result = dict(record)
        for key in ("raw_response_json", "validated_response_json", "result_json"):
            if key in result:
                result[key[:-5]] = loads(result.pop(key))
        return result

    def get_exact(
        self,
        *,
        project_id: str,
        floor_id: str,
        crop_version: int,
        wall_version: int,
        scale_version: int,
        prompt_version: str,
        model: str,
    ) -> dict[str, Any] | None:
        with get_connection() as connection:
            row = connection.execute(
                """SELECT * FROM room_interpretation_runs
                   WHERE project_id=? AND floor_id=? AND crop_version=?
                     AND wall_version=? AND scale_version=? AND prompt_version=? AND model=?""",
                (
                    project_id,
                    floor_id,
                    crop_version,
                    wall_version,
                    scale_version,
                    prompt_version,
                    model,
                ),
            ).fetchone()
        return self._decode(row)

    def find_reusable(
        self,
        *,
        project_id: str,
        floor_id: str,
        crop_version: int,
        wall_version: int,
        prompt_version: str,
        model: str,
    ) -> dict[str, Any] | None:
        """Reuse semantic evidence across scale-only changes.

        Scale affects local measurement, not the visible crop or room meaning,
        so a new calibration must never trigger another model/LLM request.
        """
        with get_connection() as connection:
            row = connection.execute(
                """SELECT * FROM room_interpretation_runs
                   WHERE project_id=? AND floor_id=? AND crop_version=?
                     AND wall_version=? AND prompt_version=? AND model=? AND status='ready'
                   ORDER BY updated_at DESC LIMIT 1""",
                (project_id, floor_id, crop_version, wall_version, prompt_version, model),
            ).fetchone()
        return self._decode(row)

    def begin(
        self,
        *,
        project_id: str,
        floor_id: str,
        crop_version: int,
        wall_version: int,
        scale_version: int,
        prompt_version: str,
        model: str,
        input_hash: str,
    ) -> dict[str, Any]:
        now = now_iso()
        identity = (
            project_id,
            floor_id,
            crop_version,
            wall_version,
            scale_version,
            prompt_version,
            model,
        )
        with get_connection() as connection:
            existing = connection.execute(
                """SELECT * FROM room_interpretation_runs
                   WHERE project_id=? AND floor_id=? AND crop_version=?
                     AND wall_version=? AND scale_version=? AND prompt_version=? AND model=?""",
                identity,
            ).fetchone()
            if existing and str(existing["status"]) in {"ready", "processing"}:
                decoded = self._decode(existing) or {}
                decoded["claimed"] = False
                return decoded
            if existing:
                run_id = str(existing["id"])
                connection.execute(
                    """UPDATE room_interpretation_runs
                       SET status='processing',input_hash=?,raw_response_json='{}',
                           validated_response_json='{}',error_message=NULL,
                           attempt_count=attempt_count+1,updated_at=?,completed_at=NULL
                       WHERE id=?""",
                    (input_hash, now, run_id),
                )
            else:
                run_id = str(uuid4())
                connection.execute(
                    """INSERT INTO room_interpretation_runs(
                         id,project_id,floor_id,crop_version,wall_version,scale_version,
                         prompt_version,model,status,input_hash,attempt_count,created_at,updated_at
                       ) VALUES (?,?,?,?,?,?,?,?,'processing',?,1,?,?)""",
                    (run_id, *identity, input_hash, now, now),
                )
            row = connection.execute(
                "SELECT * FROM room_interpretation_runs WHERE id=?", (run_id,)
            ).fetchone()
        decoded = self._decode(row) or {}
        decoded["claimed"] = True
        return decoded

    def complete(
        self,
        run_id: str,
        *,
        raw_response: dict[str, Any],
        validated_response: dict[str, Any],
        results: list[dict[str, Any]],
    ) -> dict[str, Any]:
        now = now_iso()
        with get_connection() as connection:
            run = connection.execute(
                "SELECT * FROM room_interpretation_runs WHERE id=?", (run_id,)
            ).fetchone()
            if not run:
                raise RuntimeError("Room interpretation run no longer exists.")
            connection.execute(
                """UPDATE room_interpretation_runs
                   SET status='ready',raw_response_json=?,validated_response_json=?,
                       error_message=NULL,updated_at=?,completed_at=? WHERE id=?""",
                (dumps(raw_response), dumps(validated_response), now, now, run_id),
            )
            connection.execute(
                "DELETE FROM room_interpretation_results WHERE run_id=?", (run_id,)
            )
            for item in results:
                connection.execute(
                    """INSERT INTO room_interpretation_results(
                         id,run_id,project_id,floor_id,room_id,suggestion_id,status,
                         result_json,created_at,updated_at
                       ) VALUES (?,?,?,?,?,?,?, ?,?,?)""",
                    (
                        str(uuid4()),
                        run_id,
                        run["project_id"],
                        run["floor_id"],
                        item.get("room_id"),
                        item.get("room_suggestion_id") or item.get("suggestion_id"),
                        item.get("validation_status") or "validated",
                        dumps(item),
                        now,
                        now,
                    ),
                )
            saved = connection.execute(
                "SELECT * FROM room_interpretation_runs WHERE id=?", (run_id,)
            ).fetchone()
        return self._decode(saved) or {}

    def fail(self, run_id: str, message: str, raw_response: dict[str, Any] | None = None) -> None:
        with get_connection() as connection:
            connection.execute(
                """UPDATE room_interpretation_runs
                   SET status='failed',raw_response_json=?,error_message=?,updated_at=?,completed_at=?
                   WHERE id=?""",
                (dumps(raw_response or {}), str(message)[:2000], now_iso(), now_iso(), run_id),
            )

    def results(self, run_id: str) -> list[dict[str, Any]]:
        with get_connection() as connection:
            rows = connection.execute(
                "SELECT * FROM room_interpretation_results WHERE run_id=? ORDER BY created_at,id",
                (run_id,),
            ).fetchall()
        return [self._decode(row) or {} for row in rows]

    def status(self, project_id: str, floor_id: str) -> dict[str, Any]:
        with get_connection() as connection:
            row = connection.execute(
                """SELECT * FROM room_interpretation_runs
                   WHERE project_id=? AND floor_id=? ORDER BY updated_at DESC LIMIT 1""",
                (project_id, floor_id),
            ).fetchone()
        return self._decode(row) or {
            "project_id": project_id,
            "floor_id": floor_id,
            "status": "not_started",
        }


llm_room_cache = LLMRoomCache()

__all__ = ["LLMRoomCache", "llm_room_cache"]
