from __future__ import annotations

from typing import Any
from uuid import uuid4

from app.database.session import get_connection, row_to_dict
from app.workflow.constants import VERSION_LAYERS
from app.workflow.repo_base import dumps, loads, now_iso

class RoomRepositoryMixin:
    def save_calibration(
        self,
        connection: Any,
        *,
        project_id: str,
        floor_id: str,
        point_a: dict,
        point_b: dict,
        pixel_distance: float,
        real_distance: float,
        unit: str,
        units_per_pixel: float,
        source_crop_version: int,
        scale_version: int,
        confirmed_by: str | None,
    ) -> dict:
        now = now_iso()
        calibration_id = str(uuid4())
        connection.execute(
            """
            INSERT INTO calibrations (
              id, project_id, floor_id, point_a_json, point_b_json, pixel_distance,
              real_distance, unit, units_per_pixel, source_crop_version, scale_version,
              status, confirmed_by, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'confirmed', ?, ?, ?)
            """,
            (
                calibration_id,
                project_id,
                floor_id,
                dumps(point_a),
                dumps(point_b),
                pixel_distance,
                real_distance,
                unit,
                units_per_pixel,
                source_crop_version,
                scale_version,
                confirmed_by,
                now,
                now,
            ),
        )
        return row_to_dict(connection.execute("SELECT * FROM calibrations WHERE id = ?", (calibration_id,)).fetchone()) or {}

    def mark_scale_dependents_stale(self, connection: Any, *, project_id: str, floor_id: str) -> None:
        now = now_iso()
        connection.execute(
            "UPDATE elements SET measurement_status = 'not_ready', updated_at = ? WHERE project_id = ? AND floor_id = ? AND excluded = 0",
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
            "UPDATE review_issues SET status = 'not_ready', updated_at = ? WHERE project_id = ? AND floor_id = ? AND status != 'confirmed' AND source = 'calculated'",
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

    def create_room(
        self,
        connection: Any,
        *,
        project_id: str,
        floor_id: str,
        payload: dict,
        room_version: int,
        created_by: str | None,
        source_versions: dict,
    ) -> dict:
        now = now_iso()
        room_id = str(uuid4())
        connection.execute(
            """
            INSERT INTO rooms (
              id, project_id, floor_id, name, geometry_json, area_m2, perimeter_m,
              finish_code, status, is_stale, user_confirmed, room_version,
              source_versions_json, created_by, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, NULL, NULL, ?, ?, 1, 0, ?, ?, ?, ?, ?)
            """,
            (
                room_id,
                project_id,
                floor_id,
                payload.get("name"),
                dumps(payload.get("geometry") or {}),
                payload.get("finish_code"),
                payload.get("status") or "needs_review",
                room_version,
                dumps(source_versions),
                created_by,
                now,
                now,
            ),
        )
        return self.get_room(connection, project_id, room_id) or {}

    def get_room(self, connection: Any, project_id: str, room_id: str) -> dict | None:
        return row_to_dict(
            connection.execute(
                "SELECT * FROM rooms WHERE id = ? AND project_id = ?",
                (room_id, project_id),
            ).fetchone()
        )

    def update_room_geometry(
        self,
        connection: Any,
        *,
        room_id: str,
        geometry: dict,
        room_version: int,
        confirm: bool,
        source_versions: dict,
    ) -> dict:
        now = now_iso()
        connection.execute(
            """
            UPDATE rooms
            SET geometry_json = ?, area_m2 = NULL, perimeter_m = NULL, is_stale = 1,
                status = ?, user_confirmed = ?, room_version = ?, source_versions_json = ?, updated_at = ?
            WHERE id = ?
            """,
            (
                dumps(geometry),
                "confirmed" if confirm else "needs_review",
                1 if confirm else 0,
                room_version,
                dumps(source_versions),
                now,
                room_id,
            ),
        )
        return row_to_dict(connection.execute("SELECT * FROM rooms WHERE id = ?", (room_id,)).fetchone()) or {}

    def mark_room_dependents_stale(self, connection: Any, *, project_id: str, floor_id: str, room_id: str) -> None:
        now = now_iso()
        connection.execute(
            """
            UPDATE review_issues SET status = 'not_ready', updated_at = ?
            WHERE project_id = ? AND floor_id = ? AND entity_type = 'room' AND entity_id = ?
              AND status != 'confirmed'
            """,
            (now, project_id, floor_id, room_id),
        )
        connection.execute(
            """
            UPDATE boq_rows SET is_stale = 1, status = 'not_ready', updated_at = ?
            WHERE project_id = ? AND floor_id = ? AND entity_type = 'room' AND entity_id = ?
            """,
            (now, project_id, floor_id, room_id),
        )
        connection.execute(
            "UPDATE boqs SET is_stale = 1, status = 'not_ready', updated_at = ? WHERE project_id = ?",
            (now, project_id),
        )
