from __future__ import annotations

import math
from typing import Any

from app.core.errors import bad_request, not_found
from app.database.session import get_connection
from app.jobs.job_service import job_service
from app.floors.repo import floors_repository
from app.scale.repo import scale_repository
from app.workflow.repo import workflow_repository

SCALE_TASKS = (
    "measure.elements",
    "walls.build_centerlines",
    "walls.prepare_quantities",
    # Scale changes preserve room polygons. Only measurements are refreshed;
    # Roboflow and polygon generation are intentionally not rerun.
    "rooms.calculate_areas",
)


def to_mm(value: float, unit: str) -> float:
    factor = {"mm": 1.0, "cm": 10.0, "m": 1000.0}.get(unit)
    if factor is None:
        raise bad_request("Select a valid unit.")
    return value * factor


def payload_distance_mm(payload: dict[str, Any], value_key: str) -> float:
    if payload.get("unit") == "ft_in":
        feet = float(payload.get("feet") or 0)
        inches = float(payload.get("inches") or 0)
        if feet < 0 or inches < 0 or inches >= 12:
            raise bad_request("Enter valid feet and inches. Inches must be less than 12.")
        return feet * 304.8 + inches * 25.4
    value = payload.get(value_key)
    if value is None:
        raise bad_request("Enter a valid distance.")
    return to_mm(float(value), str(payload.get("unit") or ""))


class ScaleService:
    def get_state(self, project: dict) -> dict:
        floors = [self._serialize_floor(project["id"], floor) for floor in scale_repository.list_floors(project["id"])]
        return {
            "project_id": project["id"],
            "project_name": project["name"],
            "floors": floors,
            "can_continue": bool(floors) and all(floor["status"] in {"calibrated", "needs_review"} for floor in floors),
        }

    def save(self, *, project_id: str, floor_id: str, payload: dict[str, Any], confirmed_by: str | None) -> dict:
        floor = scale_repository.get_floor(project_id, floor_id)
        if not floor:
            raise not_found("Floor not found.")
        if not floor.get("current_source_document_id") or not floor.get("current_source_page_number") or not floor.get("crop_version"):
            raise bad_request("Save the floor crop before calibration.")
        if int(payload["crop_version"]) != int(floor["crop_version"]):
            raise bad_request("The floor crop changed. Reload the drawing and calibrate again.")

        point_a = payload["point_a"]
        point_b = payload["point_b"]
        pixel_distance = math.dist((point_a["x"], point_a["y"]), (point_b["x"], point_b["y"]))
        if pixel_distance < 5:
            raise bad_request("Select two points further apart.")
        real_distance_mm = payload_distance_mm(payload, "real_distance")
        if real_distance_mm <= 0:
            raise bad_request("Enter a valid distance.")
        mm_per_pixel = real_distance_mm / pixel_distance

        verification_points = None
        expected_mm = measured_mm = difference = None
        status = "calibrated"
        verification = payload.get("verification")
        if verification:
            verification_points = {
                "point_a": verification["point_a"],
                "point_b": verification["point_b"],
            }
            verification_pixels = math.dist(
                (verification["point_a"]["x"], verification["point_a"]["y"]),
                (verification["point_b"]["x"], verification["point_b"]["y"]),
            )
            expected_mm = payload_distance_mm(verification, "expected_distance")
            measured_mm = verification_pixels * mm_per_pixel
            difference = abs(measured_mm - expected_mm) / expected_mm * 100 if expected_mm else None
            if difference is not None and difference > 2.0:
                status = "needs_review"

        with get_connection() as connection:
            versions = workflow_repository.increment_floor_version(connection, project_id, floor_id, "scale_version")
            workflow_repository.create_outbox_event(
                connection,
                project_id=project_id,
                floor_id=floor_id,
                event_type="scale.changed",
                entity_type="calibration",
                entity_id=floor_id,
                dedupe_key=f"scale.changed:{floor_id}:{versions['scale_version']}",
                payload={"scale_version": versions["scale_version"], "crop_version": floor["crop_version"]},
            )
        record = scale_repository.save(
            project_id=project_id,
            floor_id=floor_id,
            source_document_id=floor["current_source_document_id"],
            source_page_number=int(floor["current_source_page_number"]),
            crop_version=int(floor["crop_version"]),
            point_a=point_a,
            point_b=point_b,
            pixel_distance=pixel_distance,
            real_distance_mm=real_distance_mm,
            mm_per_pixel=mm_per_pixel,
            input_unit=payload["unit"],
            verification_points=verification_points,
            verification_expected_mm=expected_mm,
            verification_measured_mm=measured_mm,
            verification_difference_percent=difference,
            scale_version=int(versions["scale_version"]),
            confirmed_by=confirmed_by,
            status=status,
        )
        scale_repository.mark_dependents_stale(project_id, floor_id)
        input_versions = {
            "crop_version": int(floor["crop_version"]),
            "scale_version": int(versions["scale_version"]),
        }
        jobs = []
        for task_type in SCALE_TASKS:
            job, created = job_service.enqueue(
                task_type=task_type,
                project_id=project_id,
                floor_id=floor_id,
                payload={"floor_id": floor_id, "calibration_id": record["id"]},
                input_versions=input_versions,
                entity_id=floor_id,
                created_by=confirmed_by,
            )
            jobs.append({**job, "created": created})
        return {"calibration": self._serialize_calibration(record), "jobs": jobs, "versions": input_versions}

    def copy(self, *, project_id: str, floor_id: str, source_floor_id: str, confirm: bool, confirmed_by: str | None) -> dict:
        if not confirm:
            raise bad_request("Confirm before copying a calibration.")
        source = scale_repository.get_floor(project_id, source_floor_id)
        target = scale_repository.get_floor(project_id, floor_id)
        if not source or not target:
            raise not_found("Floor not found.")
        calibration = source.get("calibration")
        if not calibration:
            raise bad_request("The source floor is not calibrated.")
        return self.save(
            project_id=project_id,
            floor_id=floor_id,
            payload={
                "point_a": calibration["point_a"],
                "point_b": calibration["point_b"],
                "real_distance": calibration["real_distance_mm"],
                "unit": "mm",
                "crop_version": target["crop_version"],
            },
            confirmed_by=confirmed_by,
        )

    def _serialize_floor(self, project_id: str, row: dict) -> dict:
        calibration = None
        if row.get("calibration_id"):
            calibration = {
                "id": row["calibration_id"],
                "point_a": row.get("point_a"),
                "point_b": row.get("point_b"),
                "pixel_distance": row.get("pixel_distance"),
                "real_distance_mm": row.get("real_distance_mm"),
                "mm_per_pixel": row.get("mm_per_pixel"),
                "verification_points": row.get("verification_points"),
                "verification_expected_mm": row.get("verification_expected_mm"),
                "verification_measured_mm": row.get("verification_measured_mm"),
                "verification_difference_percent": row.get("verification_difference_percent"),
                "input_unit": row.get("input_unit") or "mm",
                "crop_version": row.get("calibration_crop_version"),
                "scale_version": row.get("calibration_scale_version"),
                "status": row.get("calibration_status"),
                "updated_at": row.get("calibration_updated_at"),
            }
        status = "not_calibrated"
        if not row.get("current_source_document_id"):
            status = "not_calibrated"
        elif calibration and int(calibration.get("crop_version") or 0) != int(row.get("crop_version") or 0):
            status = "needs_review"
        elif calibration:
            status = calibration.get("status") or "calibrated"
        crop_rect = ((row.get("coordinates") or {}).get("original_rect") or {})
        dimensions = floors_repository.list_dimension_observations(
            project_id, row["id"], int(row.get("crop_version") or 0)
        )
        suggestions = [
            {
                "id": item["id"], "label_text": item.get("label_text"),
                "value_mm": item.get("value_mm"), "point_a": item.get("point_a"),
                "point_b": item.get("point_b"), "confidence": item.get("confidence"),
                "suggested_mm_per_pixel": item.get("suggested_mm_per_pixel"),
            }
            for item in dimensions[:5]
        ]
        return {
            "id": row["id"],
            "project_id": project_id,
            "name": row["name"],
            "level_index": int(row["level_index"]),
            "crop_version": int(row.get("crop_version") or 0),
            "scale_version": int(row.get("scale_version") or 0),
            "source_document_id": row.get("current_source_document_id"),
            "source_page_number": row.get("current_source_page_number"),
            "original_page_width": crop_rect.get("width") or row.get("original_page_width"),
            "original_page_height": crop_rect.get("height") or row.get("original_page_height"),
            "rotation": int(row.get("rotation") or 0),
            "drawing_url": (
                f"/api/v1/projects/{project_id}/floor-plans/floors/{row['id']}/crop-asset"
                if row.get("crop_asset_key") or row.get("preview_asset_key")
                else None
            ),
            "status": status,
            "calibration": calibration,
            "dimension_suggestions": suggestions,
        }

    @staticmethod
    def _serialize_calibration(record: dict) -> dict:
        return {
            "id": record["id"],
            "point_a": record.get("point_a"),
            "point_b": record.get("point_b"),
            "pixel_distance": record.get("pixel_distance"),
            "real_distance_mm": record.get("real_distance_mm"),
            "mm_per_pixel": record.get("mm_per_pixel"),
            "verification_points": record.get("verification_points"),
            "verification_expected_mm": record.get("verification_expected_mm"),
            "verification_measured_mm": record.get("verification_measured_mm"),
            "verification_difference_percent": record.get("verification_difference_percent"),
            "input_unit": record.get("input_unit") or "mm",
            "crop_version": record.get("crop_version"),
            "scale_version": record.get("scale_version"),
            "status": record.get("status"),
        }


scale_service = ScaleService()
