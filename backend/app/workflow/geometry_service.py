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

class GeometryServiceMixin:
    def save_calibration(
        self,
        *,
        project_id: str,
        floor_id: str,
        point_a: dict,
        point_b: dict,
        real_distance: float,
        unit: str,
        source_crop_version: int,
        confirmed_by: str | None,
    ) -> dict:
        pixel_distance = math.dist((point_a["x"], point_a["y"]), (point_b["x"], point_b["y"]))
        if pixel_distance <= 0:
            raise bad_request("Calibration points must be different.")
        planned_jobs = dependency_planner.for_scale_change(floor_id=floor_id)
        with get_connection() as connection:
            self._require_floor(connection, project_id, floor_id)
            versions = workflow_repository.increment_floor_version(connection, project_id, floor_id, "scale_version")
            calibration = workflow_repository.save_calibration(
                connection,
                project_id=project_id,
                floor_id=floor_id,
                point_a=point_a,
                point_b=point_b,
                pixel_distance=pixel_distance,
                real_distance=real_distance,
                unit=unit,
                units_per_pixel=real_distance / pixel_distance,
                source_crop_version=source_crop_version,
                scale_version=versions["scale_version"],
                confirmed_by=confirmed_by,
            )
            workflow_repository.mark_scale_dependents_stale(connection, project_id=project_id, floor_id=floor_id)
            event = workflow_repository.create_outbox_event(
                connection,
                project_id=project_id,
                floor_id=floor_id,
                event_type="calibration.changed",
                entity_type="calibration",
                entity_id=calibration["id"],
                dedupe_key=f"calibration.changed:{floor_id}:{versions['scale_version']}",
                payload={"versions": self._version_values(versions)},
            )
            version_values = self._version_values(versions)
        jobs = self._enqueue_jobs(project_id=project_id, created_by=confirmed_by, input_versions=version_values, jobs=planned_jobs)
        workflow_repository.mark_outbox_published(event["id"])
        return {"record": self._decode_record(calibration), "protected": False, "changed": True, "versions": version_values, "jobs": jobs}

    def create_room(self, *, project_id: str, payload: dict, created_by: str | None) -> dict:
        floor_id = payload["floor_id"]
        with get_connection() as connection:
            self._require_floor(connection, project_id, floor_id)
            versions = workflow_repository.increment_floor_version(connection, project_id, floor_id, "room_version")
            room = workflow_repository.create_room(
                connection,
                project_id=project_id,
                floor_id=floor_id,
                payload=payload,
                room_version=versions["room_version"],
                created_by=created_by,
                source_versions=workflow_repository.get_versions(connection, project_id, floor_id),
            )
            event = workflow_repository.create_outbox_event(
                connection,
                project_id=project_id,
                floor_id=floor_id,
                event_type="room.created",
                entity_type="room",
                entity_id=room["id"],
                dedupe_key=f"room.created:{room['id']}:{versions['room_version']}",
                payload={"versions": self._version_values(versions)},
            )
        workflow_repository.mark_outbox_published(event["id"])
        return {"record": self._decode_record(room), "protected": False, "changed": True, "versions": self._version_values(versions), "jobs": []}

    def update_room_geometry(
        self,
        *,
        project_id: str,
        room_id: str,
        geometry: dict,
        confirm: bool,
        created_by: str | None,
    ) -> dict:
        with get_connection() as connection:
            room = workflow_repository.get_room(connection, project_id, room_id)
            if not room:
                raise not_found("Room not found.")
            floor_id = room["floor_id"]
            if loads(room.get("geometry_json")) == geometry and bool(room.get("user_confirmed")) == confirm:
                versions = workflow_repository.get_versions(connection, project_id, floor_id)
                return {"record": self._decode_record(room), "protected": False, "changed": False, "versions": versions, "jobs": []}
            versions = workflow_repository.increment_floor_version(connection, project_id, floor_id, "room_version")
            updated = workflow_repository.update_room_geometry(
                connection,
                room_id=room_id,
                geometry=geometry,
                room_version=versions["room_version"],
                confirm=confirm,
                source_versions=workflow_repository.get_versions(connection, project_id, floor_id),
            )
            workflow_repository.mark_room_dependents_stale(
                connection,
                project_id=project_id,
                floor_id=floor_id,
                room_id=room_id,
            )
            planned_jobs = dependency_planner.for_room_geometry(floor_id=floor_id, room_id=room_id)
            event = workflow_repository.create_outbox_event(
                connection,
                project_id=project_id,
                floor_id=floor_id,
                event_type="room.geometry.changed",
                entity_type="room",
                entity_id=room_id,
                dedupe_key=f"room.geometry.changed:{room_id}:{versions['room_version']}",
                payload={"versions": self._version_values(versions)},
            )
            version_values = self._version_values(versions)
        jobs = self._enqueue_jobs(project_id=project_id, created_by=created_by, input_versions=version_values, jobs=planned_jobs)
        workflow_repository.mark_outbox_published(event["id"])
        return {"record": self._decode_record(updated), "protected": False, "changed": True, "versions": version_values, "jobs": jobs}
