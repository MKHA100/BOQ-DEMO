from __future__ import annotations

import math
import re
from typing import Any

from app.core.errors import bad_request, not_found
from app.database.session import get_connection
from app.jobs.job_service import job_service
from app.workflow.constants import SOURCE_USER_CONFIRMED, VALUE_SOURCE_PRIORITY
from app.workflow.dependencies import DependencyJob, dependency_planner
from app.workflow.repo import dumps, loads, now_iso, workflow_repository

PROPERTY_NAME_PATTERN = re.compile(r"^[a-z][a-z0-9_]{0,79}$")

class ServiceBaseMixin:
    def _enqueue_jobs(
        self,
        *,
        project_id: str,
        created_by: str | None,
        input_versions: dict,
        jobs: list[DependencyJob],
    ) -> list[dict]:
        enqueued: list[dict] = []
        for request in jobs:
            job, created = job_service.enqueue(
                task_type=request.task_type,
                project_id=project_id,
                floor_id=request.floor_id,
                payload=request.payload,
                input_versions=input_versions,
                entity_id=request.entity_id,
                created_by=created_by,
            )
            enqueued.append({**job, "created": created})
        return enqueued

    @staticmethod
    def _require_floor(connection: Any, project_id: str, floor_id: str) -> dict:
        floor = workflow_repository.get_floor(connection, project_id, floor_id)
        if not floor:
            raise not_found("Floor not found.")
        return floor

    @staticmethod
    def _floor_name(level_index: int) -> str:
        if level_index == 0:
            return "Ground Floor"
        ordinal = {1: "First", 2: "Second", 3: "Third", 4: "Fourth", 5: "Fifth"}.get(level_index)
        return f"{ordinal} Floor" if ordinal else f"Floor {level_index}"

    @staticmethod
    def _version_values(record: dict) -> dict[str, int]:
        return {key: int(value or 0) for key, value in record.items() if key.endswith("_version")}

    @staticmethod
    def _same_property(existing: dict, value: Any, unit: str | None, source: str, confirmed: bool) -> bool:
        effective_source = SOURCE_USER_CONFIRMED if confirmed else source
        return (
            loads(existing.get("value_json")) == value
            and existing.get("unit") == unit
            and existing.get("source") == effective_source
            and bool(existing.get("is_confirmed")) == confirmed
        )

    @staticmethod
    def _decode_record(record: dict) -> dict:
        decoded = dict(record)
        for key in list(decoded):
            if key.endswith("_json"):
                decoded[key[:-5]] = loads(decoded.pop(key))
        for key in ("is_confirmed", "user_confirmed", "excluded", "is_stale", "is_current"):
            if key in decoded:
                decoded[key] = bool(decoded[key])
        return decoded

    @staticmethod
    def _count(connection: Any, table: str, project_id: str, extra: str | None = None) -> int:
        where = "project_id = ?" + (f" AND {extra}" if extra else "")
        row = connection.execute(f"SELECT COUNT(*) AS total FROM {table} WHERE {where}", (project_id,)).fetchone()
        return int(row["total"] or 0)

    @staticmethod
    def _count_floor(connection: Any, table: str, project_id: str, floor_id: str, extra: str | None = None) -> int:
        where = "project_id = ? AND floor_id = ?" + (f" AND {extra}" if extra else "")
        row = connection.execute(f"SELECT COUNT(*) AS total FROM {table} WHERE {where}", (project_id, floor_id)).fetchone()
        return int(row["total"] or 0)
