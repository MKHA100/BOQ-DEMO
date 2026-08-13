from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import fitz

from app.core.config import settings
from app.floor_plans.repo import floor_plans_repository
from app.jobs.job_repository import job_repository
from app.jobs.job_service import job_service
from app.model_review.prediction_processor import process_predictions
from app.model_review.provider import detection_provider
from app.model_review.repo import model_review_repository
from app.model_review.wall_recovery_service import wall_recovery_service
from app.storage.storage_service import storage_service


class SupersededDetection(RuntimeError):
    pass


def _json_payload(job: dict) -> dict[str, Any]:
    raw = job.get("payload_json")
    if isinstance(raw, dict):
        return raw
    try:
        parsed = json.loads(raw or "{}")
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _input_versions(job: dict) -> dict[str, Any]:
    raw = job.get("input_versions_json")
    if isinstance(raw, dict):
        return raw
    try:
        parsed = json.loads(raw or "{}")
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


class UnifiedFloorDetectionService:
    def _active_crop(self, project_id: str, floor_id: str, expected_version: int) -> dict:
        crop = floor_plans_repository.current_crop(project_id, floor_id)
        if not crop or int(crop.get("crop_version") or 0) != int(expected_version):
            raise SupersededDetection("A newer floor crop is already active.")
        if not crop.get("crop_asset_key"):
            raise RuntimeError("The high-resolution floor crop is not ready.")
        return floor_plans_repository.decode_crop(crop)

    def run(self, job: dict) -> dict[str, Any]:
        project_id = str(job.get("project_id") or "")
        floor_id = str(job.get("floor_id") or "")
        payload = _json_payload(job)
        versions = _input_versions(job)
        expected_version = int(versions.get("crop_version") or payload.get("crop_version") or 0)
        analysis_mode = str(payload.get("analysis_mode") or "standard")
        if not project_id or not floor_id or expected_version <= 0:
            raise RuntimeError("Unified floor detection scope is incomplete.")

        crop = self._active_crop(project_id, floor_id, expected_version)
        crop_id = str(crop["id"])
        image_path = storage_service.ensure_local_file(storage_service.key_to_path(str(crop["crop_asset_key"])))
        image_hash = self._input_hash(image_path, expected_version, analysis_mode)
        cached = model_review_repository.get_detection_run(
            project_id=project_id,
            floor_id=floor_id,
            crop_version=expected_version,
            model_id=settings.roboflow_model_id,
            analysis_mode=analysis_mode,
        )
        if cached and cached.get("status") == "ready" and cached.get("input_hash") == image_hash:
            raw = cached.get("raw") or {}
            run_id = str(cached["id"])
        else:
            run = model_review_repository.begin_detection_run(
                project_id=project_id,
                floor_id=floor_id,
                crop_id=crop_id,
                crop_version=expected_version,
                provider_name=detection_provider.name,
                model_id=settings.roboflow_model_id,
                input_hash=image_hash,
                analysis_mode=analysis_mode,
            )
            run_id = str(run["id"])
            job_repository.update_progress(job["id"], progress=18, message="Detecting floor elements")
            try:
                raw = detection_provider.detect(image_path, analysis_mode=analysis_mode)
            except Exception as exc:
                model_review_repository.finish_detection_run_with_error(run_id, str(exc))
                raise

        # A network request may finish after a replacement crop was saved.
        try:
            crop = self._active_crop(project_id, floor_id, expected_version)
        except SupersededDetection:
            model_review_repository.finish_detection_run_with_error(run_id, "Superseded by a newer crop", status="superseded")
            raise
        rect = ((crop.get("coordinates") or {}).get("original_rect") or {})
        pixmap = fitz.Pixmap(str(image_path))
        try:
            groups = process_predictions(
                raw,
                image_width=int(pixmap.width),
                image_height=int(pixmap.height),
                crop_width=float(rect.get("width") or 1.0),
                crop_height=float(rect.get("height") or 1.0),
            )
        finally:
            pixmap = None
        job_repository.update_progress(job["id"], progress=70, message="Saving current crop results")
        counts = model_review_repository.reconcile_detection_results(
            project_id=project_id,
            floor_id=floor_id,
            crop_id=crop_id,
            crop_version=expected_version,
            run_id=run_id,
            model_id=settings.roboflow_model_id,
            input_hash=image_hash,
            analysis_mode=analysis_mode,
            provider_name=detection_provider.name,
            raw=raw,
            groups=groups,
            created_by=job.get("created_by"),
        )
        # Tag and wall work are independent of page navigation and use one shared run.
        followups: list[dict[str, Any]] = []
        for task_type in ("vision.read_tags", "walls.build_lines"):
            queued, created = job_service.enqueue(
                task_type=task_type,
                project_id=project_id,
                floor_id=floor_id,
                entity_id=floor_id,
                payload={"floor_id": floor_id, "crop_id": crop_id, "detection_run_id": run_id},
                input_versions={"crop_version": expected_version, "element_version": counts["element_version"]},
                created_by=job.get("created_by"),
            )
            followups.append({"id": queued.get("id"), "task_type": task_type, "created": created})
        if settings.wall_auto_recovery_enabled:
            queued, created = job_service.enqueue(
                task_type="vision.recover_floor_walls",
                project_id=project_id,
                floor_id=floor_id,
                entity_id=floor_id,
                payload={
                    "floor_id": floor_id, "crop_id": crop_id,
                    "crop_version": expected_version, "analysis_mode": "wall_recovery",
                },
                input_versions={
                    "crop_version": expected_version,
                    "element_version": counts["element_version"],
                    "model_id": settings.roboflow_model_id,
                    "analysis_mode": "wall_recovery",
                },
                created_by=job.get("created_by"),
            )
            followups.append({
                "id": queued.get("id"), "task_type": "vision.recover_floor_walls",
                "created": created,
            })
        return {
            "message": "Floor element results available",
            "crop_version": expected_version,
            "detection_run_id": run_id,
            "counts": {key: counts.get(key, 0) for key in ("door", "window", "wall")},
            "element_version": counts["element_version"],
            "followups": followups,
        }

    def run_wall_recovery(self, job: dict) -> dict[str, Any]:
        project_id = str(job.get("project_id") or "")
        floor_id = str(job.get("floor_id") or "")
        payload = _json_payload(job)
        versions = _input_versions(job)
        expected_version = int(versions.get("crop_version") or payload.get("crop_version") or 0)
        if not project_id or not floor_id or expected_version <= 0:
            raise RuntimeError("Wall recovery scope is incomplete.")
        crop = self._active_crop(project_id, floor_id, expected_version)
        crop_id = str(crop["id"])
        image_path = storage_service.ensure_local_file(
            storage_service.key_to_path(str(crop["crop_asset_key"]))
        )
        input_hash = self._recovery_input_hash(image_path, expected_version)
        cached = model_review_repository.get_detection_run(
            project_id=project_id, floor_id=floor_id, crop_version=expected_version,
            model_id=settings.roboflow_model_id, analysis_mode="wall_recovery",
        )
        if cached and cached.get("status") == "ready" and cached.get("input_hash") == input_hash:
            return {
                "message": "Automatic wall recovery already ready",
                "cached": True,
                "wall_count": int(cached.get("wall_count") or 0),
            }
        run = model_review_repository.begin_detection_run(
            project_id=project_id, floor_id=floor_id, crop_id=crop_id,
            crop_version=expected_version, provider_name="automatic_wall_recovery",
            model_id=settings.roboflow_model_id, input_hash=input_hash,
            analysis_mode="wall_recovery",
        )
        run_id = str(run["id"])
        rect = ((crop.get("coordinates") or {}).get("original_rect") or {})
        job_repository.update_progress(
            job["id"], progress=20, message="Checking wall details"
        )
        try:
            seed_walls = [
                item
                for item in model_review_repository.list_elements(project_id, floor_id)
                if item.get("element_type") == "wall"
                and not item.get("excluded")
                and (
                    item.get("source") not in {"model_recovery", "vector_recovery"}
                    or item.get("user_confirmed")
                    or item.get("is_manual")
                )
            ]
            recovered = wall_recovery_service.detect(
                project_id=project_id,
                floor_id=floor_id,
                image_path=image_path,
                crop_width=float(rect.get("width") or 1.0),
                crop_height=float(rect.get("height") or 1.0),
                seed_walls=seed_walls,
            )
            self._active_crop(project_id, floor_id, expected_version)
            job_repository.update_progress(
                job["id"], progress=72, message="Merging recovered walls"
            )
            counts = model_review_repository.reconcile_wall_recovery(
                project_id=project_id, floor_id=floor_id, crop_id=crop_id,
                crop_version=expected_version, run_id=run_id,
                model_id=settings.roboflow_model_id, input_hash=input_hash,
                provider_name="automatic_wall_recovery", raw=recovered["raw"],
                groups=recovered["groups"], created_by=job.get("created_by"),
            )
        except Exception as exc:
            model_review_repository.finish_detection_run_with_error(run_id, str(exc))
            raise
        followups: list[dict[str, Any]] = []
        for task_type in ("vision.read_tags", "walls.build_lines"):
            queued, created = job_service.enqueue(
                task_type=task_type,
                project_id=project_id,
                floor_id=floor_id,
                entity_id=floor_id,
                payload={
                    "floor_id": floor_id,
                    "crop_id": crop_id,
                    "detection_run_id": run_id,
                    "precision_recovery": True,
                },
                input_versions={
                    "crop_version": expected_version,
                    "element_version": counts["element_version"],
                },
                created_by=job.get("created_by"),
                job_key=(
                    f"{job.get('job_key') or job.get('id')}:{task_type}:precision"
                ),
            )
            followups.append(
                {"id": queued.get("id"), "task_type": task_type, "created": created}
            )
        return {
            "message": "Automatic element precision scan ready",
            "wall_count": counts["wall"],
            "door_count": counts["door"],
            "window_count": counts["window"],
            "added": counts["added"],
            "refreshed": counts["refreshed"],
            "protected": counts["protected"],
            "vector_wall_count": recovered.get("vector_wall_count", 0),
            "followups": followups,
        }

    @staticmethod
    def _input_hash(image_path: Path, crop_version: int, analysis_mode: str) -> str:
        digest = hashlib.sha256()
        digest.update(str(crop_version).encode("utf-8"))
        digest.update(settings.roboflow_model_id.encode("utf-8"))
        digest.update(analysis_mode.encode("utf-8"))
        with image_path.open("rb") as source:
            for chunk in iter(lambda: source.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    @staticmethod
    def _recovery_input_hash(image_path: Path, crop_version: int) -> str:
        mode = (
            f"wall_recovery:{settings.wall_recovery_tile_pixels}:"
            f"{settings.wall_recovery_tile_overlap}:{settings.wall_recovery_max_tiles}:"
            f"{settings.wall_recovery_min_confidence}:"
            f"{int(settings.wall_vector_recovery_enabled)}:"
            f"{settings.wall_recovery_min_length}:"
            f"{settings.wall_recovery_min_aspect_ratio}:"
            f"{settings.wall_recovery_min_thickness_ratio}:"
            f"{settings.wall_recovery_max_thickness_ratio}:"
            f"{settings.wall_recovery_max_gap}:"
            f"{settings.wall_recovery_repeated_line_limit}:original-colour-v2"
            f":doors={settings.door_recovery_min_confidence}"
            f":windows={settings.window_recovery_min_confidence}"
            f":opening-independent={settings.opening_recovery_independent_confidence}"
        )
        return UnifiedFloorDetectionService._input_hash(image_path, crop_version, mode)


unified_floor_detection_service = UnifiedFloorDetectionService()
