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

class FloorServiceMixin:
    def create_floor(
        self,
        *,
        project_id: str,
        name: str | None,
        level_index: int | None,
        created_by: str | None,
    ) -> dict:
        with get_connection() as connection:
            resolved_index = level_index if level_index is not None else workflow_repository.next_floor_index(connection, project_id)
            resolved_name = (name or self._floor_name(resolved_index)).strip()
            if not resolved_name:
                raise bad_request("Floor name is required.")
            floor = workflow_repository.create_floor(
                connection,
                project_id=project_id,
                name=resolved_name,
                level_index=resolved_index,
                created_by=created_by,
            )
            versions = workflow_repository.get_versions(connection, project_id, floor["id"])
            event = workflow_repository.create_outbox_event(
                connection,
                project_id=project_id,
                floor_id=floor["id"],
                event_type="floor.created",
                entity_type="floor",
                entity_id=floor["id"],
                dedupe_key=f"floor.created:{floor['id']}",
                payload={"level_index": resolved_index},
            )
        workflow_repository.mark_outbox_published(event["id"])
        return {**floor, "versions": versions}

    def list_floors(self, project_id: str) -> list[dict]:
        floors = workflow_repository.list_floors(project_id)
        version_names = {
            "crop_version",
            "schedule_version",
            "scale_version",
            "element_version",
            "wall_version",
            "room_version",
            "review_version",
            "boq_version",
        }
        return [
            {
                **{key: value for key, value in floor.items() if key not in version_names},
                "versions": {key: int(floor.get(key) or 0) for key in version_names},
            }
            for floor in floors
        ]
