from __future__ import annotations

from typing import Any
from uuid import uuid4

from app.database.session import get_connection, row_to_dict
from app.workflow.repo_base import dumps, loads, now_iso


class ScaleRepository:
    def list_floors(self, project_id: str) -> list[dict]:
        with get_connection() as connection:
            rows = connection.execute(
                """
                SELECT f.*, fv.crop_version, fv.scale_version,
                       fc.document_id AS current_source_document_id,
                       fc.source_page_number AS current_source_page_number,
                       fc.crop_asset_key, fc.preview_asset_key,
                       fc.original_page_width, fc.original_page_height, fc.coordinates_json,
                       fc.rotation, fc.status AS crop_status,
                       c.id AS calibration_id, c.point_a_json, c.point_b_json,
                       c.pixel_distance, c.real_distance_mm, c.mm_per_pixel,
                       c.verification_points_json, c.verification_expected_mm,
                       c.verification_measured_mm, c.verification_difference_percent,
                       c.input_unit, c.status AS calibration_status,
                       c.crop_version AS calibration_crop_version,
                       c.scale_version AS calibration_scale_version,
                       c.updated_at AS calibration_updated_at
                FROM floors f
                LEFT JOIN floor_versions fv ON fv.floor_id = f.id
                LEFT JOIN floor_crops fc ON fc.floor_id = f.id AND fc.project_id = f.project_id AND fc.is_current = 1
                LEFT JOIN calibrations c ON c.id = (
                  SELECT c2.id FROM calibrations c2
                  WHERE c2.project_id = f.project_id AND c2.floor_id = f.id
                  ORDER BY c2.scale_version DESC LIMIT 1
                )
                WHERE f.project_id = ?
                ORDER BY f.level_index ASC
                """,
                (project_id,),
            ).fetchall()
        return [self._decode(row_to_dict(row) or {}) for row in rows]

    def get_floor(self, project_id: str, floor_id: str) -> dict | None:
        return next((floor for floor in self.list_floors(project_id) if floor["id"] == floor_id), None)

    def save(
        self,
        *,
        project_id: str,
        floor_id: str,
        source_document_id: str,
        source_page_number: int,
        crop_version: int,
        point_a: dict,
        point_b: dict,
        pixel_distance: float,
        real_distance_mm: float,
        mm_per_pixel: float,
        input_unit: str,
        verification_points: dict | None,
        verification_expected_mm: float | None,
        verification_measured_mm: float | None,
        verification_difference_percent: float | None,
        scale_version: int,
        confirmed_by: str | None,
        status: str,
    ) -> dict:
        now = now_iso()
        calibration_id = str(uuid4())
        with get_connection() as connection:
            connection.execute(
                """
                INSERT INTO calibrations (
                  id, project_id, floor_id, point_a_json, point_b_json, pixel_distance,
                  real_distance, unit, units_per_pixel, source_crop_version, scale_version,
                  status, confirmed_by, created_at, updated_at,
                  source_document_id, source_page_number, crop_version, real_distance_mm,
                  mm_per_pixel, verification_points_json, verification_expected_mm,
                  verification_measured_mm, verification_difference_percent, input_unit
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 'mm', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    calibration_id,
                    project_id,
                    floor_id,
                    dumps(point_a),
                    dumps(point_b),
                    pixel_distance,
                    real_distance_mm,
                    mm_per_pixel,
                    crop_version,
                    scale_version,
                    status,
                    confirmed_by,
                    now,
                    now,
                    source_document_id,
                    source_page_number,
                    crop_version,
                    real_distance_mm,
                    mm_per_pixel,
                    dumps(verification_points) if verification_points else None,
                    verification_expected_mm,
                    verification_measured_mm,
                    verification_difference_percent,
                    input_unit,
                ),
            )
            row = connection.execute("SELECT * FROM calibrations WHERE id = ?", (calibration_id,)).fetchone()
        return self._decode(row_to_dict(row) or {})

    def mark_dependents_stale(self, project_id: str, floor_id: str) -> dict:
        now = now_iso()
        with get_connection() as connection:
            connection.execute(
                "UPDATE elements SET measurement_status='not_ready', updated_at=? WHERE project_id=? AND floor_id=? AND excluded=0",
                (now, project_id, floor_id),
            )
            connection.execute(
                "UPDATE walls SET is_stale=1, status='not_ready', updated_at=? WHERE project_id=? AND floor_id=?",
                (now, project_id, floor_id),
            )
            connection.execute(
                "UPDATE rooms SET is_stale=1, status='not_ready', updated_at=? WHERE project_id=? AND floor_id=?",
                (now, project_id, floor_id),
            )
            connection.execute(
                "UPDATE quantity_snapshots SET status='not_ready', updated_at=? WHERE project_id=? AND floor_id=?",
                (now, project_id, floor_id),
            )
            connection.execute(
                "UPDATE boq_rows SET is_stale=1, status='not_ready', updated_at=? WHERE project_id=? AND floor_id=?",
                (now, project_id, floor_id),
            )
            connection.execute(
                "UPDATE boqs SET is_stale=1, status='not_ready', updated_at=? WHERE project_id=?",
                (now, project_id),
            )
            counts = {
                "elements": connection.execute("SELECT COUNT(*) AS total FROM elements WHERE project_id=? AND floor_id=?", (project_id, floor_id)).fetchone()["total"],
                "walls": connection.execute("SELECT COUNT(*) AS total FROM walls WHERE project_id=? AND floor_id=?", (project_id, floor_id)).fetchone()["total"],
                "rooms": connection.execute("SELECT COUNT(*) AS total FROM rooms WHERE project_id=? AND floor_id=?", (project_id, floor_id)).fetchone()["total"],
            }
        return {key: int(value or 0) for key, value in counts.items()}

    @staticmethod
    def _decode(record: dict) -> dict:
        result = dict(record)
        for key in ("point_a_json", "point_b_json", "verification_points_json", "coordinates_json"):
            if key in result:
                result[key[:-5]] = loads(result.pop(key)) if result.get(key) else None
        return result


scale_repository = ScaleRepository()
