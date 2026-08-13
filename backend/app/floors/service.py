from __future__ import annotations

import hashlib
import re
import statistics
from typing import Any

from app.core.config import settings
from app.core.errors import bad_request, not_found
from app.database.session import get_connection
from app.floors.geometry import polygon_area, polygon_perimeter, self_intersects
from app.floors.hybrid_matcher import hybrid_room_matcher
from app.floors.label_service import room_label_service
from app.floors.line_builder import room_line_builder
from app.floors.llm_room_interpreter import llm_room_interpreter
from app.floors.llm_room_cache import llm_room_cache
from app.floors.polygon_builder import room_polygon_builder
from app.floors.polygon_regularizer import polygon_regularizer
from app.floors.precision_pipeline import precision_room_pipeline
from app.floors.room_edit_service import room_edit_service
from app.floors.room_seed_service import room_seed_service
from app.floors.building_envelope_service import building_envelope_service
from app.floors.edit_history_service import edit_history_service
from app.floors.finish_zone_service import finish_zone_service
from app.floors.repo import floors_repository
from app.floors.room_segmentation_provider import RoomSegmentationError, room_segmentation_provider
from app.floors.room_semantics import room_semantics
from app.floors.room_validation_service import room_validation_service
from app.floors.room_area_resolver import room_area_resolver
from app.floors.room_candidate_filter import room_candidate_filter
from app.floors.room_exception_service import room_exception_service
from app.floors.room_overlap_service import room_overlap_service
from app.floors.room_reconciliation_service import room_reconciliation_service
from app.floors.wall_cell_service import wall_cell_service
from app.floors.dimension_constraint_service import dimension_constraint_service
from app.floors.vector_geometry_service import vector_floor_geometry_service
from app.jobs.job_service import job_service
from app.storage.storage_service import storage_service
from app.walls.repo import walls_repository
from app.workflow.repo import workflow_repository


class FloorsService:
    # Start only the independent first jobs. Every processor schedules the
    # next durable step after it succeeds, so multiple workers cannot run
    # Review or BOQ before room quantities are ready.
    ANALYSIS_TASKS = (
        "vision.detect_rooms",
        "rooms.prepare_lines",
    )
    ANALYSIS_JOB_TYPES = {
        "vision.detect_rooms",
        "rooms.publish_model_results",
        "rooms.prepare_lines",
        "rooms.build_polygons",
        "rooms.reconcile",
        "rooms.identify_labels",
        "rooms.assign_finishes",
        "rooms.calculate_areas",
        "rooms.precision_refine",
        "rooms.interpret_floor",
        "rooms.interpret_ambiguous",
    }
    RECALCULATE_TASKS = (
        "rooms.prepare_lines",
    )


    def get_state(self, project: dict, floor_id: str | None = None) -> dict:
        active = job_service.list_project_jobs(project_id=project["id"], active_only=True, limit=200)
        floors: list[dict] = []
        for row in floors_repository.floor_rows(project["id"]):
            rect = ((row.get("coordinates") or {}).get("original_rect") or {})
            rooms = floors_repository.list_rooms(project["id"], row["id"])
            visible = [room for room in rooms if not room.get("excluded")]
            physical = [room for room in visible if not room.get("is_finish_zone")]
            zones = [room for room in visible if room.get("is_finish_zone")]
            floor_jobs = [
                job for job in active
                if job.get("floor_id") == row["id"]
                and job.get("task_type") in self.ANALYSIS_JOB_TYPES
            ]
            observations = floors_repository.list_dimension_observations(
                project["id"], row["id"], int(row.get("crop_version") or 0)
            )
            interpretation = llm_room_cache.status(project["id"], row["id"])
            interpreting = any(
                job.get("task_type") in {"rooms.interpret_floor", "rooms.interpret_ambiguous"}
                for job in floor_jobs
            )
            correcting = any(
                job.get("task_type")
                in {
                    "rooms.prepare_lines",
                    "rooms.build_polygons",
                    "rooms.reconcile",
                    "rooms.precision_refine",
                    "rooms.calculate_areas",
                }
                for job in floor_jobs
            )
            floors.append({
                "id": row["id"], "name": row["name"], "level_index": int(row["level_index"]),
                "crop_version": int(row.get("crop_version") or 0),
                "scale_version": int(row.get("scale_version") or 0),
                "element_version": int(row.get("element_version") or 0),
                "wall_version": int(row.get("wall_version") or 0),
                "room_version": int(row.get("room_version") or 0),
                "mm_per_pixel": row.get("mm_per_pixel"),
                "scale_verified": bool(row.get("mm_per_pixel")) and int(row.get("scale_version") or 0) > 0,
                "room_count": len(physical), "finish_zone_count": len(zones),
                "needs_review_count": sum(room.get("measurement_status") != "correct" or room.get("status") == "needs_review" for room in visible),
                "confirmed_count": sum(room.get("status") == "confirmed" for room in visible),
                "area_total_m2": round(sum(float(room.get("area_m2") or 0) for room in visible if room.get("include_in_boq")), 4),
                "dimension_suggestions": observations[:5],
                "drawing_url": (
                    f"/api/v1/projects/{project['id']}/floor-plans/floors/{row['id']}/crop-asset"
                    if row.get("crop_asset_key") or row.get("preview_asset_key") else None
                ),
                "drawing_width": float(rect.get("width") or 1),
                "drawing_height": float(rect.get("height") or 1),
                "active_jobs": floor_jobs,
                "interpretation_status": interpretation.get("status") or "not_started",
                "analysis_status": (
                    "interpreting" if interpreting and physical
                    else "correcting" if correcting and physical
                    else "detected" if floor_jobs and physical
                    else "processing" if floor_jobs
                    else "ready" if physical
                    else "not_ready"
                ),
            })
        selected = floor_id or (floors[0]["id"] if floors else None)
        rooms = floors_repository.list_rooms(project["id"], selected) if selected else []
        if selected:
            selected_jobs = [job for job in active if job.get("floor_id") == selected and job.get("task_type") in self.ANALYSIS_JOB_TYPES]
            interpreting = any(
                job.get("task_type") in {"rooms.interpret_floor", "rooms.interpret_ambiguous"}
                for job in selected_jobs
            )
            correcting = any(
                job.get("task_type")
                in {"rooms.prepare_lines", "rooms.build_polygons", "rooms.reconcile", "rooms.precision_refine", "rooms.calculate_areas"}
                for job in selected_jobs
            )
            for room in rooms:
                if interpreting and not room.get("user_confirmed"):
                    room["processing_stage"] = "interpreting"
                elif room.get("processing_stage") == "detected" and correcting:
                    room["processing_stage"] = "correcting"
        suggestions = floors_repository.list_suggestions(project["id"], selected) if selected else []
        return {
            "project_id": project["id"], "floors": floors, "selected_floor_id": selected,
            "rooms": rooms,
            "suggestions": [item for item in suggestions if item.get("status") in {"new", "matched"}],
        }

    # ---- Analysis orchestration ------------------------------------------

    def analyze(self, project_id: str, floor_id: str, created_by: str | None) -> dict:
        floor = floors_repository.get_floor_row(project_id, floor_id)
        if not floor or not floor.get("crop_id") or not floor.get("crop_asset_key"):
            raise bad_request("Save the floor crop before analyzing rooms.")
        with get_connection() as connection:
            versions = workflow_repository.increment_floor_version(connection, project_id, floor_id, "room_version")
        jobs = self._enqueue_tasks(
            project_id,
            floor_id,
            self.ANALYSIS_TASKS,
            versions,
            created_by,
            payload={"floor_id": floor_id, "analysis": "hybrid"},
        )
        return {"status": "processing", "jobs": jobs, "versions": self._versions(versions)}

    def recalculate(self, project_id: str, floor_id: str, created_by: str | None) -> dict:
        floor = floors_repository.get_floor_row(project_id, floor_id)
        if not floor or not floor.get("crop_id"):
            raise bad_request("Save the floor crop before recalculating rooms.")
        with get_connection() as connection:
            versions = workflow_repository.increment_floor_version(connection, project_id, floor_id, "room_version")
        jobs = self._enqueue_tasks(
            project_id,
            floor_id,
            self.RECALCULATE_TASKS,
            versions,
            created_by,
            payload={"floor_id": floor_id, "analysis": "geometry_only"},
        )
        return {"status": "processing", "jobs": jobs, "versions": self._versions(versions)}

    def request_interpretation(
        self, project_id: str, floor_id: str, created_by: str | None
    ) -> dict:
        floor = floors_repository.get_floor_row(project_id, floor_id)
        if not floor or not floor.get("crop_asset_key"):
            raise bad_request("Save the floor crop before interpreting rooms.")
        with get_connection() as connection:
            versions = workflow_repository.get_versions(connection, project_id, floor_id)
        jobs = self._enqueue_tasks(
            project_id,
            floor_id,
            ("rooms.interpret_floor",),
            versions,
            created_by,
            payload={"floor_id": floor_id, "analysis": "interpretation"},
        )
        return {"status": "processing", "jobs": jobs, "versions": self._versions(versions)}

    def request_precision(
        self, project_id: str, floor_id: str, created_by: str | None
    ) -> dict:
        floor = floors_repository.get_floor_row(project_id, floor_id)
        if not floor or not floor.get("crop_asset_key"):
            raise bad_request("Save the floor crop before refining rooms.")
        with get_connection() as connection:
            versions = workflow_repository.get_versions(connection, project_id, floor_id)
        jobs = self._enqueue_tasks(
            project_id,
            floor_id,
            ("rooms.precision_refine",),
            versions,
            created_by,
            payload={"floor_id": floor_id, "analysis": "precision", "interpretation_complete": True},
        )
        return {"status": "processing", "jobs": jobs, "versions": self._versions(versions)}

    def enqueue_missing_background_analyses(self) -> dict:
        """Queue room analysis for existing ready floor crops that have no rooms.

        This runs once when the worker starts. It is intentionally conservative:
        floors that already contain canonical rooms are left untouched, while a
        previously failed current-version job is requeued instead of duplicated.
        """
        scheduled: list[dict] = []
        for floor in floors_repository.list_floors_needing_analysis():
            project_id = str(floor["project_id"])
            floor_id = str(floor["floor_id"])
            versions = self._versions(floor)
            jobs = self._enqueue_tasks(
                project_id,
                floor_id,
                self.ANALYSIS_TASKS,
                versions,
                None,
                payload={
                    "floor_id": floor_id,
                    "crop_id": floor.get("crop_id"),
                    "analysis": "background",
                },
            )
            repaired: list[dict] = []
            for item in jobs:
                if not item.get("created") and item.get("status") == "failed" and item.get("id"):
                    requeued = job_service.requeue_job(str(item["id"]))
                    if requeued:
                        repaired.append({**requeued, "created": False, "requeued": True})
                        continue
                repaired.append(item)
            scheduled.append(
                {
                    "project_id": project_id,
                    "floor_id": floor_id,
                    "jobs": repaired,
                }
            )
        return {"floors": len(scheduled), "scheduled": scheduled}

    def detect_room_suggestions(self, project_id: str, floor_id: str) -> dict:
        floor = floors_repository.get_floor_row(project_id, floor_id)
        if not floor or not floor.get("crop_id") or not floor.get("crop_asset_key"):
            return {"status": "not_ready", "suggestions": 0}
        crop_version = int(floor.get("crop_version") or 0)
        cached = floors_repository.get_segmentation_run(
            project_id, floor_id, crop_version, settings.roboflow_floor_model_id
        )
        if cached and cached.get("status") == "ready":
            published = self.publish_model_results(project_id, floor_id)
            return {
                "status": "cached",
                "run_id": cached["id"],
                "suggestions": int(cached.get("prediction_count") or 0),
                "published": published.get("published", 0),
                "room_ids": published.get("room_ids", []),
            }

        run = floors_repository.begin_segmentation_run(
            project_id=project_id,
            floor_id=floor_id,
            crop_id=str(floor["crop_id"]),
            crop_version=crop_version,
            model_id=settings.roboflow_floor_model_id,
        )
        image_path = storage_service.ensure_local_file(
            storage_service.key_to_path(str(floor["crop_asset_key"]))
        )
        try:
            result = room_segmentation_provider.detect(image_path, crop_version=crop_version)
            if result.get("status") not in {"ready"}:
                # Do not cache a missing key or disabled model as a successful
                # run. The same crop can be analyzed later after configuration
                # changes without forcing a new crop version.
                floors_repository.fail_segmentation_run(
                    run["id"], str(result.get("status") or "not_ready")
                )
                return {"status": result.get("status"), "run_id": run["id"], "suggestions": 0}
            saved = floors_repository.complete_segmentation_run(
                run["id"],
                raw_response=result.get("raw") or {},
                predictions=result.get("predictions") or [],
                image_width=float(result.get("image_width") or 0),
                image_height=float(result.get("image_height") or 0),
                crop_width=self._crop_size(floor)[0],
                crop_height=self._crop_size(floor)[1],
            )
            published = self.publish_model_results(project_id, floor_id)
            return {
                "status": "ready",
                "run_id": saved["id"],
                "suggestions": int(saved.get("prediction_count") or 0),
                "published": published.get("published", 0),
                "room_ids": published.get("room_ids", []),
            }
        except RoomSegmentationError as exc:
            floors_repository.fail_segmentation_run(run["id"], str(exc))
            # Geometry jobs must continue even if the optional model is unavailable.
            return {"status": "failed", "run_id": run["id"], "suggestions": 0, "warning": str(exc)}

    def publish_model_results(self, project_id: str, floor_id: str) -> dict:
        """Publish current Roboflow rooms before wall correction completes.

        This is intentionally idempotent.  Current-crop model polygons become
        visible provisional canonical rooms. Confirmed user geometry is never
        overwritten; it only receives updated model evidence.
        """
        if not settings.room_fast_pass_enabled or not settings.room_results_publish_early:
            return {
                "status": "disabled",
                "published": 0,
                "room_ids": [],
            }
        floor = floors_repository.get_floor_row(project_id, floor_id)
        if not floor:
            raise not_found("Floor not found.")
        suggestions = [
            item for item in floors_repository.list_suggestions(project_id, floor_id)
            if item.get("status") not in {"rejected", "superseded"}
        ]
        if not suggestions:
            return {"status": "not_ready", "published": 0, "room_ids": []}

        rooms = [
            item for item in floors_repository.list_rooms(project_id, floor_id)
            if not item.get("excluded") and not item.get("is_finish_zone")
        ]
        # Publishing is intentionally independent from wall/vector preparation.
        # The hosted model result must become visible immediately; the lower-priority
        # precision pipeline corrects it against walls afterwards.
        typical = 0.0
        proposals: list[tuple[dict, dict, dict | None, float]] = []
        used_rooms: set[str] = set()

        for suggestion in suggestions:
            provisional = room_seed_service.provisional(suggestion, wall_thickness_px=typical)
            if not provisional:
                continue
            model_polygon = room_polygon_builder.points_to_polygon(provisional["model_points"])
            best_room: dict | None = None
            best_score = -1.0
            matched_id = str(suggestion.get("matched_room_id") or "")
            for room in rooms:
                if room["id"] in used_rooms:
                    continue
                current = room_polygon_builder.points_to_polygon((room.get("geometry") or {}).get("points") or [])
                if current.is_empty:
                    continue
                iou = room_polygon_builder.iou(model_polygon, current)
                contains = current.buffer(2).contains(model_polygon.representative_point())
                reverse = model_polygon.buffer(2).contains(current.representative_point())
                score = iou + (0.32 if contains else 0.0) + (0.18 if reverse else 0.0)
                if matched_id and room["id"] == matched_id:
                    score += 1.0
                if score > best_score:
                    best_room, best_score = room, score
            if best_score < 0.18:
                best_room = None
            if best_room:
                used_rooms.add(str(best_room["id"]))
            proposals.append((suggestion, provisional, best_room, best_score))

        if not proposals:
            return {"status": "not_ready", "published": 0, "room_ids": []}

        # Never publish a raw outer/background mask as a canonical room.  This
        # lightweight pass runs even before the wall correction job finishes.
        crop_width, crop_height = self._crop_size(floor)
        early_candidates = [
            {
                **provisional,
                "seed_suggestion_id": str(suggestion.get("id") or ""),
                "boundary_source": "model_only",
                "wall_ids": [],
                "area_px": float(
                    room_polygon_builder.points_to_polygon(provisional.get("points") or []).area
                ),
            }
            for suggestion, provisional, _, _ in proposals
        ]
        filtered = room_candidate_filter.filter(
            early_candidates,
            envelope=None,
            mm_per_pixel=float(floor.get("mm_per_pixel") or 0) or None,
            rejected_rooms=floors_repository.list_room_records(
                project_id, floor_id, generated_status="rejected"
            ),
        )
        accepted_by_suggestion = {
            str(item.get("seed_suggestion_id") or ""): item
            for item in filtered["accepted"]
        }
        proposals = [
            (suggestion, {**provisional, **accepted_by_suggestion[str(suggestion.get("id") or "")]}, room, score)
            for suggestion, provisional, room, score in proposals
            if str(suggestion.get("id") or "") in accepted_by_suggestion
        ]
        if not proposals:
            return {"status": "filtered", "published": 0, "room_ids": []}

        changes_required = False
        for _, provisional, room, _ in proposals:
            if room is None:
                changes_required = True
                break
            raw_hash = room_polygon_builder.geometry_hash(
                room_polygon_builder.points_to_polygon((room.get("raw_geometry") or {}).get("points") or [])
            )
            if raw_hash != room_polygon_builder.geometry_hash(
                room_polygon_builder.points_to_polygon(provisional["model_points"])
            ):
                changes_required = True
                break
            if not room.get("user_confirmed") and str(room.get("boundary_source") or "") not in {
                "model_only", "model_seed_wall_region", "model_seed_wall_faces", "wall_corrected"
            }:
                changes_required = True
                break
        if not changes_required:
            return {"status": "ready", "published": 0, "room_ids": [str(room["id"]) for _, _, room, _ in proposals if room]}

        with get_connection() as connection:
            versions = workflow_repository.increment_floor_version(connection, project_id, floor_id, "room_version")
        room_version = int(versions.get("room_version") or 0)
        published_ids: list[str] = []
        for suggestion, provisional, room, score in proposals:
            model_geometry = {"points": provisional["model_points"]}
            display_geometry = {"points": provisional["points"]}
            if room and room.get("user_confirmed"):
                floors_repository.update_room(
                    project_id, floor_id, str(room["id"]),
                    {
                        "generated_geometry": model_geometry,
                        "raw_geometry": model_geometry,
                        "confidence": provisional["confidence"],
                        "comparison_status": "model_available",
                    },
                    room_version, confirmed=True,
                )
                room_id = str(room["id"])
            elif room:
                room_id = str(room["id"])
                floors_repository.update_room(
                    project_id, floor_id, room_id,
                    {
                        "points": provisional["points"],
                        "generated_geometry": model_geometry,
                        "raw_geometry": model_geometry,
                        "wall_corrected_geometry": {},
                        "regularized_geometry": display_geometry,
                        "confirmed_geometry": {},
                        "shape_type": provisional["shape_type"],
                        "boundary_source": "model_only",
                        "precision_status": "detected",
                        "detection_source": "roboflow",
                        "confidence": provisional["confidence"],
                        "model_verified": False,
                        "comparison_status": "model_provisional",
                        "geometry_hash": provisional["geometry_hash"],
                        "geometry_status": "needs_review",
                        "measurement_status": "check",
                        "status": "needs_review",
                        "is_stale": True,
                        "user_edited": False,
                    },
                    room_version, confirmed=False,
                )
            else:
                created = floors_repository.create_room(
                    project_id=project_id, floor_id=floor_id, points=provisional["points"],
                    generated=True, room_version=room_version, created_by=None,
                    detection_source="roboflow", confidence=provisional["confidence"],
                    model_verified=False, comparison_status="model_provisional",
                    geometry_hash=provisional["geometry_hash"], geometry_status="needs_review",
                    suggestion_geometry=model_geometry, space_kind="internal", include_in_boq=True,
                )
                room_id = str(created["id"])
                floors_repository.update_room(
                    project_id, floor_id, room_id,
                    {
                        "raw_geometry": model_geometry,
                        "wall_corrected_geometry": {},
                        "regularized_geometry": display_geometry,
                        "confirmed_geometry": {},
                        "shape_type": provisional["shape_type"],
                        "boundary_source": "model_only",
                        "precision_status": "detected",
                        "measurement_status": "check",
                    },
                    room_version, confirmed=False,
                )
            floors_repository.update_suggestion(
                project_id, floor_id, str(suggestion["id"]), status="matched",
                matched_room_id=room_id, comparison_score=max(0.0, float(score)),
            )
            published_ids.append(room_id)

        # Provisional areas can be shown immediately when scale is available.
        if published_ids and float(floor.get("mm_per_pixel") or 0) > 0:
            self.calculate(project_id, floor_id, published_ids)
        return {"status": "ready", "published": len(published_ids), "room_ids": published_ids}

    def prepare_lines(self, project_id: str, floor_id: str) -> dict:
        floor = floors_repository.get_floor_row(project_id, floor_id)
        if not floor:
            raise not_found("Floor not found.")
        prepared, evidence = self._prepared_geometry(project_id, floor_id, floor)
        serialized = room_line_builder.serialize(prepared)
        return {
            "wall_lines": len(serialized["wall_segments"]),
            "vector_walls": int(serialized.get("vector_wall_count") or 0),
            "door_closures": len(serialized["door_closures"]),
            "dimension_suggestions": len(evidence.get("dimensions") or []),
            "prepared": serialized,
        }

    def build_polygons(
        self,
        project_id: str,
        floor_id: str,
        created_by: str | None = None,
        *,
        target_room_ids: list[str] | None = None,
    ) -> dict:
        floor = floors_repository.get_floor_row(project_id, floor_id)
        if not floor:
            raise not_found("Floor not found.")
        prepared, evidence = self._prepared_geometry(project_id, floor_id, floor)
        crop_width, crop_height = self._crop_size(floor)
        wall_cells = wall_cell_service.build(
            prepared,
            crop_width=crop_width,
            crop_height=crop_height,
            mm_per_pixel=float(floor.get("mm_per_pixel") or 0) or None,
        )
        # Labels describe a space; they are not physical boundaries.  Keep an
        # open-plan wall cell intact and combine its semantic names later.
        # Artificial Voronoi/label partitions produced plausible-looking but
        # incorrect areas where no wall exists on the drawing.
        # Fast pass: remove raster/model noise immediately so the first visible
        # result is already usable. The lower-priority precision job performs
        # envelope, dimension and semantic validation later.
        regularized_candidates: list[dict] = []
        for candidate in wall_cells:
            regularized = polygon_regularizer.regularize(candidate.get("points") or [])
            points = regularized.get("points") or candidate.get("points") or []
            polygon = room_polygon_builder.points_to_polygon(points)
            if polygon.is_empty:
                continue
            regularized_candidates.append({
                **candidate,
                "points": points,
                "raw_points": candidate.get("points") or [],
                "shape_type": regularized.get("shape_type") or "polygon",
                "area_px": float(polygon.area),
                "perimeter_px": float(polygon.length),
                "geometry_hash": room_polygon_builder.geometry_hash(polygon),
                "boundary_source": candidate.get("boundary_source") or "wall_cell",
                "model_points": [],
            })
        # Model instances are the discovery authority. Wall cells remain as a
        # fallback for spaces missed by the model and are de-duplicated below.
        candidates: list[dict] = []

        # Use the room model as a seed, then take the exact boundary from the
        # wall-bounded free-space region. This replaces noisy raw contours
        # without making the model the final measurement authority.
        suggestions = floors_repository.list_suggestions(project_id, floor_id)
        crop_rect = ((floor.get("coordinates") or {}).get("original_rect") or {})
        envelope = building_envelope_service.build(
            prepared,
            float(crop_rect.get("width") or crop_width or 1),
            float(crop_rect.get("height") or crop_height or 1),
        )
        for seeded in room_seed_service.candidates(
            suggestions=suggestions, prepared=prepared, envelope=envelope
        ):
            regularized = polygon_regularizer.regularize(
                seeded.get("points") or [],
                wall_thickness_px=float(prepared.get("typical_thickness_px") or 0),
            )
            points = regularized.get("points") or seeded.get("points") or []
            polygon = room_polygon_builder.points_to_polygon(points)
            if polygon.is_empty:
                continue
            boundary_source = str(seeded.get("boundary_source") or "model_only")
            wall_grounded = boundary_source in {
                "model_seed_wall_region",
                "model_seed_wall_faces",
            }
            candidate = {
                "points": points,
                "raw_points": seeded.get("points") or [],
                "shape_type": regularized.get("shape_type") or "polygon",
                "area_px": float(polygon.area),
                "perimeter_px": float(polygon.length),
                "width_px": room_polygon_builder.oriented_dimensions(polygon)[0],
                "length_px": room_polygon_builder.oriented_dimensions(polygon)[1],
                "geometry_hash": room_polygon_builder.geometry_hash(polygon),
                "touches_crop_edge": False,
                "geometry_status": "ready" if wall_grounded else "needs_review",
                "wall_ids": [],
                "opening_ids": [],
                "seed_suggestion_id": seeded.get("suggestion_id"),
                "seed_score": seeded.get("seed_score"),
                "boundary_source": boundary_source,
                "model_points": seeded.get("model_points") or [],
                "confidence": seeded.get("confidence"),
                "wall_alignment": seeded.get("wall_alignment"),
            }
            candidate = wall_cell_service.attach_relations(candidate, wall_cells)
            duplicate_index = next(
                (
                    index
                    for index, item in enumerate(candidates)
                    if room_polygon_builder.iou(
                        polygon,
                        room_polygon_builder.points_to_polygon(item.get("points") or []),
                    )
                    >= 0.82
                ),
                None,
            )
            if duplicate_index is None:
                candidates.append(candidate)
            elif float(candidate.get("confidence") or 0) > float(
                candidates[duplicate_index].get("confidence") or 0
            ):
                candidates[duplicate_index] = candidate

        # Keep wall-only rooms as a recovery path for model misses. The
        # candidate filter removes enclosing masks and gives model instances
        # priority when both sources describe the same space.
        candidates.extend(regularized_candidates)
        exception_result = {
            "candidates": candidates,
            "recovered": 0,
            "labelled": 0,
            "ambiguous": 0,
        }
        if settings.room_exception_correction_enabled:
            exception_result = room_exception_service.recover(
                candidates=candidates,
                wall_cells=wall_cells,
                text_blocks=room_label_service.evidence_blocks(project_id, floor_id),
                minimum_label_confidence=settings.room_exception_min_label_confidence,
            )
            candidates = exception_result["candidates"]

        mm_per_pixel = float(floor.get("mm_per_pixel") or 0)
        if mm_per_pixel > 0 and evidence.get("dimensions"):
            candidates = [
                self._correct_candidate_dimensions(candidate, evidence.get("dimensions") or [], mm_per_pixel)
                for candidate in candidates
            ]
        filtered_candidates = room_candidate_filter.filter(
            candidates,
            envelope=envelope,
            mm_per_pixel=mm_per_pixel or None,
            rejected_rooms=floors_repository.list_room_records(
                project_id, floor_id, generated_status="rejected"
            ),
        )
        candidates = filtered_candidates["accepted"]
        with get_connection() as connection:
            versions = workflow_repository.increment_floor_version(connection, project_id, floor_id, "room_version")
        room_version = int(versions["room_version"])
        existing = floors_repository.list_rooms(project_id, floor_id)
        target_set = set(target_room_ids or [])
        if target_set:
            target_rooms = [item for item in existing if item["id"] in target_set]
            unrelated = [item for item in existing if item["id"] not in target_set]
        else:
            target_rooms = existing
            unrelated = []

        matched_existing: set[str] = set()
        used_candidates: set[int] = set()
        changed: list[str] = []
        created: list[str] = []

        reconciliation = room_reconciliation_service.match(target_rooms, candidates)

        # Match each existing room against the closest regenerated candidate.
        for room_index, room in enumerate(target_rooms):
            old_polygon = room_polygon_builder.points_to_polygon(
                (room.get("geometry") or {}).get("points") or []
            )
            is_manual_room = str(room.get("detection_source") or "") == "user"
            if (
                room.get("user_confirmed")
                and not is_manual_room
                and self._contains_multiple_candidates(old_polygon, candidates)
            ):
                floors_repository.supersede_generated_room(project_id, floor_id, room["id"])
                changed.append(room["id"])
                continue
            matched = reconciliation["matches"].get(room_index)
            best_index, best_score = matched if matched is not None else (None, 0.0)
            if best_index is None or best_score < 0.15:
                if self._has_current_model_support(room, suggestions):
                    # A wall/envelope refinement failure must not erase a room
                    # still supplied by the current segmentation model.
                    floors_repository.update_room(
                        project_id,
                        floor_id,
                        room["id"],
                        {
                            "comparison_status": "model_provisional",
                            "boundary_source": "model_only",
                            "precision_status": "detected",
                            "geometry_status": "needs_review",
                            "status": "needs_review",
                        },
                        room_version,
                        confirmed=bool(room.get("user_confirmed")),
                    )
                    matched_existing.add(room["id"])
                    changed.append(room["id"])
                    continue
                if (not room.get("user_confirmed") or not is_manual_room) and not room.get("excluded"):
                    floors_repository.delete_room(project_id, floor_id, room["id"])
                    changed.append(room["id"])
                elif room.get("user_confirmed"):
                    floors_repository.update_room(
                        project_id,
                        floor_id,
                        room["id"],
                        {"comparison_status": "regeneration_missing", "status": "needs_review"},
                        room_version,
                        confirmed=True,
                    )
                continue

            candidate = candidates[best_index]
            used_candidates.add(best_index)
            matched_existing.add(room["id"])
            if room.get("excluded"):
                continue
            if room.get("user_confirmed") and is_manual_room:
                patch: dict[str, Any] = {
                    "generated_geometry": {"points": candidate["points"]},
                    "geometry_hash": room.get("geometry_hash"),
                }
                if best_score < 0.75:
                    patch.update({"comparison_status": "regenerated_differs", "status": "needs_review"})
                floors_repository.update_room(
                    project_id,
                    floor_id,
                    room["id"],
                    patch,
                    room_version,
                    confirmed=True,
                    wall_ids=candidate["wall_ids"],
                    opening_ids=candidate["opening_ids"],
                )
            else:
                automated_patch: dict[str, Any] = {
                    "points": candidate["points"],
                    "generated_geometry": {"points": candidate.get("model_points") or candidate["points"]},
                    "raw_geometry": {"points": candidate.get("model_points") or candidate.get("raw_points") or candidate["points"]},
                    "wall_corrected_geometry": {"points": candidate["points"]},
                    "regularized_geometry": {"points": candidate["points"]},
                    "geometry_hash": candidate["geometry_hash"],
                    "geometry_status": candidate["geometry_status"],
                    "detection_source": "hybrid" if candidate.get("model_points") else "wall_geometry",
                    "boundary_source": candidate.get("boundary_source") or "wall_only",
                    "precision_status": "correcting" if candidate.get("model_points") else "needs_review",
                    "shape_type": candidate.get("shape_type") or "irregular",
                    "comparison_status": "wall_corrected" if candidate.get("model_points") else "not_compared",
                    "confidence": candidate.get("confidence") or room.get("confidence"),
                    "model_verified": False,
                    "is_stale": True,
                    "status": "needs_review",
                    "user_edited": False,
                    "confirmed_geometry": {},
                }
                if candidate.get("label_hint") and room.get("label_source") != "user":
                    automated_patch.update({
                        "name": candidate.get("label_hint"),
                        "room_type": candidate.get("room_type_hint") or candidate.get("label_hint"),
                        "label_source": candidate.get("label_source_hint") or "drawing",
                        "label_confidence": candidate.get("label_confidence_hint"),
                        "label_candidates": candidate.get("label_candidates") or [],
                        "space_kind": candidate.get("space_kind") or "internal",
                        "include_in_boq": candidate.get("include_in_boq", True),
                        "open_plan": candidate.get("open_plan", False),
                    })
                floors_repository.update_room(
                    project_id,
                    floor_id,
                    room["id"],
                    automated_patch,
                    room_version,
                    confirmed=False,
                    wall_ids=candidate["wall_ids"],
                    opening_ids=candidate["opening_ids"],
                )
            changed.append(room["id"])

        # Do not recreate a candidate that matches an excluded room or an
        # unrelated room protected by a targeted rebuild.
        suppress_rooms = [item for item in existing if item.get("excluded")] + unrelated
        for index, candidate in enumerate(candidates):
            if index in used_candidates:
                continue
            candidate_polygon = room_polygon_builder.points_to_polygon(candidate["points"])
            if any(
                room_polygon_builder.iou(
                    candidate_polygon,
                    room_polygon_builder.points_to_polygon((room.get("geometry") or {}).get("points") or []),
                )
                >= 0.60
                for room in suppress_rooms
            ):
                continue
            room = floors_repository.create_room(
                project_id=project_id,
                floor_id=floor_id,
                points=candidate["points"],
                generated=True,
                room_version=room_version,
                created_by=created_by,
                wall_ids=candidate["wall_ids"],
                opening_ids=candidate["opening_ids"],
                detection_source="hybrid" if candidate.get("model_points") else "wall_geometry",
                confidence=candidate.get("confidence") or (0.75 if not candidate.get("touches_crop_edge") else 0.5),
                comparison_status="wall_corrected" if candidate.get("model_points") else "not_compared",
                geometry_hash=candidate["geometry_hash"],
                geometry_status=candidate["geometry_status"],
                space_kind=str(candidate.get("space_kind") or "internal"),
                include_in_boq=bool(candidate.get("include_in_boq", True)),
                name=candidate.get("label_hint"),
                room_type=candidate.get("room_type_hint") or candidate.get("label_hint"),
                open_plan=bool(candidate.get("open_plan")),
                label_candidates=candidate.get("label_candidates") or [],
            )
            floors_repository.update_room(
                project_id, floor_id, str(room["id"]),
                {
                    "raw_geometry": {"points": candidate.get("model_points") or candidate.get("raw_points") or candidate["points"]},
                    "wall_corrected_geometry": {"points": candidate["points"]},
                    "regularized_geometry": {"points": candidate["points"]},
                    "confirmed_geometry": {},
                    "shape_type": candidate.get("shape_type") or "irregular",
                    "boundary_source": candidate.get("boundary_source") or "wall_only",
                    "precision_status": "correcting" if candidate.get("model_points") else "needs_review",
                    "label_source": candidate.get("label_source_hint") or "drawing",
                    "label_confidence": candidate.get("label_confidence_hint"),
                },
                room_version, confirmed=False,
            )
            created.append(room["id"])

        affected_ids = created + changed
        if affected_ids and float(floor.get("mm_per_pixel") or 0) > 0:
            self.calculate(project_id, floor_id, affected_ids)
        return {
            "created": len(created),
            "updated": len(changed),
            "candidate_count": len(candidates),
            "exception_recovered": int(exception_result.get("recovered") or 0),
            "exception_labelled": int(exception_result.get("labelled") or 0),
            "exception_ambiguous": int(exception_result.get("ambiguous") or 0),
            "room_ids": affected_ids,
            "rooms": floors_repository.list_rooms(project_id, floor_id),
        }

    @staticmethod
    def _has_current_model_support(room: dict[str, Any], suggestions: list[dict[str, Any]]) -> bool:
        room_id = str(room.get("id") or "")
        model_polygon = room_polygon_builder.points_to_polygon(
            (room.get("raw_geometry") or room.get("generated_geometry") or room.get("geometry") or {}).get("points") or []
        )
        if model_polygon.is_empty:
            return False
        for suggestion in suggestions:
            if suggestion.get("status") in {"rejected", "superseded"}:
                continue
            if room_id and str(suggestion.get("matched_room_id") or "") == room_id:
                return True
            suggestion_polygon = room_polygon_builder.points_to_polygon(
                (suggestion.get("polygon") or {}).get("points") or suggestion.get("points") or []
            )
            if not suggestion_polygon.is_empty and room_polygon_builder.iou(
                model_polygon, suggestion_polygon
            ) >= 0.35:
                return True
        return False

    def reconcile(
        self, project_id: str, floor_id: str, room_ids: list[str] | None = None
    ) -> dict:
        rooms = [room for room in floors_repository.list_rooms(project_id, floor_id) if not room.get("excluded")]
        if room_ids:
            target_ids = set(room_ids)
            rooms = [room for room in rooms if room["id"] in target_ids]
        suggestions = floors_repository.list_suggestions(project_id, floor_id)
        if room_ids:
            target_ids = set(room_ids)
            suggestions = [
                item for item in suggestions
                if item.get("status") == "new" or item.get("matched_room_id") in target_ids
            ]
        else:
            floors_repository.clear_suggestion_matches(project_id, floor_id)
        wall_candidates = [
            {
                "points": (room.get("geometry") or {}).get("points") or [],
                "geometry_hash": room.get("geometry_hash"),
                "touches_crop_edge": room.get("geometry_status") == "needs_review",
                "room_id": room["id"],
            }
            for room in rooms
        ]
        reconciled = hybrid_room_matcher.reconcile(wall_candidates, suggestions)
        with get_connection() as connection:
            versions = workflow_repository.increment_floor_version(connection, project_id, floor_id, "room_version")
        room_version = int(versions["room_version"])
        by_id = {room["id"]: room for room in rooms}
        updated = 0
        for result in reconciled["canonical"]:
            room_id = str(result.get("room_id") or "")
            room = by_id.get(room_id)
            if not room:
                continue
            status = room.get("status")
            if result.get("geometry_status") == "needs_review" and status != "confirmed":
                status = "needs_review"
            floors_repository.update_room(
                project_id,
                floor_id,
                room_id,
                {
                    "detection_source": result.get("detection_source"),
                    "model_verified": bool(result.get("model_verified")),
                    "comparison_status": result.get("comparison_status"),
                    "confidence": result.get("confidence"),
                    "geometry_status": result.get("geometry_status") or room.get("geometry_status"),
                    "boundary_source": result.get("boundary_source") or room.get("boundary_source"),
                    "precision_status": "corrected" if result.get("boundary_source") in {
                        "model_seed_wall_region", "model_seed_wall_faces"
                    } else room.get("precision_status"),
                    "status": status,
                },
                room_version,
                confirmed=bool(room.get("user_confirmed")),
            )
            if result.get("suggestion_id"):
                floors_repository.update_suggestion(
                    project_id,
                    floor_id,
                    str(result["suggestion_id"]),
                    status="matched",
                    matched_room_id=room_id,
                    comparison_score=float(result.get("comparison_score") or 0),
                )
            updated += 1
        return {
            "updated": updated,
            "matched": len(reconciled["matches"]),
            "unmatched_suggestions": len(reconciled["unmatched_suggestions"]),
        }

    def suggest_labels(self, project_id: str, floor_id: str) -> dict:
        rooms = floors_repository.list_rooms(project_id, floor_id, include_excluded=False)
        label_suggestions = room_label_service.suggestions(project_id, floor_id, rooms)
        with get_connection() as connection:
            versions = workflow_repository.get_versions(connection, project_id, floor_id)
        updated = 0
        physical_index = max(
            (
                int(match.group(1))
                for room in rooms
                if (match := re.fullmatch(r"\s*(?:room|space)\s+(\d+)\s*", str(room.get("name") or ""), re.I))
            ),
            default=0,
        )
        used_names: set[str] = {
            str(room.get("name") or "").strip().casefold()
            for room in rooms
            if room.get("label_source") == "user"
            and room.get("name")
            and not self._generic_room_name(room.get("name"))
        }
        for room in rooms:
            patch: dict[str, Any] = {}
            suggestion = label_suggestions.get(room["id"])
            current_name = str(room.get("name") or "").strip()
            invalid_automatic_name = bool(
                current_name
                and room.get("label_source") != "user"
                and not room_semantics.clean(current_name)
            )
            if suggestion and (
                not room.get("name")
                or room.get("label_source") != "user"
                or self._generic_room_name(room.get("name"))
                or invalid_automatic_name
            ):
                patch.update(suggestion)
            elif not room.get("name") or invalid_automatic_name:
                physical_index += 1
                patch.update({
                    "name": f"Room {physical_index}", "room_type": "Room",
                    "label_source": "generated", "label_confidence": 0.25,
                    "space_kind": "internal", "include_in_boq": True,
                    "label_candidates": [],
                })
            elif room.get("label_source") != "user":
                patch["name"] = room.get("name")
            if patch:
                semantics = room_semantics.classify(str(patch.get("name") or room.get("name") or ""))
                patch.setdefault("space_kind", semantics["space_kind"])
                patch.setdefault("include_in_boq", semantics["include_in_boq"])
                patch.setdefault("open_plan", semantics["open_plan"])
                proposed = str(patch.get("name") or room.get("name") or "Room").strip() or "Room"
                base = proposed
                suffix = 2
                # Repeated semantic room types are valid (for example several
                # BEDROOMS). Friendly room numbers already identify instances.
                if not room_semantics.match_known_labels(proposed):
                    while proposed.casefold() in used_names:
                        proposed = f"{base} {suffix}"
                        suffix += 1
                patch["name"] = proposed
                used_names.add(proposed.casefold())
                floors_repository.update_room(
                    project_id, floor_id, room["id"], patch,
                    int(versions.get("room_version") or 0),
                    confirmed=bool(room.get("user_confirmed")),
                )
                updated += 1
        return {"updated": updated}

    @staticmethod
    def _generic_room_name(value: Any) -> bool:
        text = str(value or "").strip()
        return bool(
            re.fullmatch(r"\s*(?:room|space)(?:\s+\d+)*\s*", text, re.IGNORECASE)
            or (text and not room_semantics.clean(text))
        )

    def assign_finishes(self, project_id: str, floor_id: str) -> dict:
        with get_connection() as connection:
            entries = connection.execute(
                "SELECT * FROM schedule_entries WHERE project_id=? AND category='floor' ORDER BY is_accepted DESC,source_priority DESC,created_at",
                (project_id,),
            ).fetchall()
            versions = workflow_repository.get_versions(connection, project_id, floor_id)
        import json

        parsed = []
        for row in entries:
            try:
                parsed.append(json.loads(row["data_json"] or "{}"))
            except Exception:
                continue
        rooms = floors_repository.list_rooms(project_id, floor_id, include_excluded=False)
        updated = 0
        for room in rooms:
            if room.get("floor_finish"):
                continue
            matched = self._match_finish(room, parsed)
            if not matched:
                continue
            floors_repository.update_room(
                project_id,
                floor_id,
                room["id"],
                {
                    "floor_finish": matched,
                    "finish_source": "schedule",
                },
                int(versions.get("room_version") or 0),
                confirmed=bool(room.get("user_confirmed")),
            )
            updated += 1
        return {"updated": updated}

    def calculate(self, project_id: str, floor_id: str, room_ids: list[str] | None = None) -> dict:
        floor = floors_repository.get_floor_row(project_id, floor_id)
        if not floor:
            raise not_found("Floor not found.")
        mm_per_pixel = float(floor.get("mm_per_pixel") or 0)
        scale_verified = bool(mm_per_pixel and int(floor.get("scale_version") or 0) > 0)
        observations = floors_repository.list_dimension_observations(
            project_id, floor_id, int(floor.get("crop_version") or 0)
        )
        rooms = floors_repository.list_rooms(project_id, floor_id)
        if room_ids:
            rooms = [room for room in rooms if room["id"] in room_ids]
        with get_connection() as connection:
            versions = workflow_repository.increment_floor_version(connection, project_id, floor_id, "room_version")
        updated = []
        for room in rooms:
            quantity = room_area_resolver.resolve(room, mm_per_pixel if scale_verified else None)
            quantity_geometry = quantity.get("geometry") or {}
            points = quantity_geometry.get("points") or []
            invalid = len(points) < 3 or self_intersects(points)
            polygon = room_polygon_builder.points_to_polygon(points)
            if polygon.is_empty:
                invalid = True
            width_px, length_px = room_polygon_builder.oriented_dimensions(polygon)
            dimension = dimension_constraint_service.match(
                points,
                observations,
                mm_per_pixel if scale_verified else 0,
                preferred_width_mm=room.get("printed_width_mm"),
                preferred_length_mm=room.get("printed_length_mm"),
                preferred_source=room.get("dimension_source"),
            )
            printed_width = dimension.get("printed_width_mm")
            printed_length = dimension.get("printed_length_mm")
            difference = dimension.get("difference_percent")
            geometry_state = "invalid" if invalid else str(room.get("geometry_status") or "ready")
            semantic = room_semantics.classify(str(room.get("name") or room.get("room_type") or ""))
            validation = room_validation_service.validate(
                scale_verified=scale_verified,
                valid_geometry=not invalid and geometry_state != "invalid",
                label=room.get("name"),
                difference_percent=difference,
                boundary_source=str(room.get("boundary_source") or room.get("detection_source") or "unknown"),
                space_kind=str(room.get("space_kind") or semantic.get("space_kind") or "internal"),
                model_verified=bool(room.get("model_verified")),
                shape_type=str(room.get("shape_type") or "irregular"),
                point_count=len(points),
                wall_aligned=str(room.get("boundary_source") or "") in {"user", "wall_cell", "label_seed_wall_cell", "model_seed_wall_region", "model_seed_wall_faces", "wall_geometry", "wall_corrected"},
            )
            measurement_status = str(validation.get("status") or "check")
            space_kind = str(room.get("space_kind") or semantic["space_kind"])
            include_in_boq = bool(room.get("include_in_boq")) if room.get("label_source") == "user" else bool(semantic["include_in_boq"])
            # Floor detection review is about geometry, scale and labels.
            # A missing finish belongs to Specifications/BOQ setup and must not
            # force every correctly detected room into manual floor review.
            status = "confirmed" if measurement_status == "correct" else "needs_review"
            updated.append(floors_repository.update_room(
                project_id, floor_id, room["id"], {
                    "area_m2": None if invalid else quantity.get("area_m2"),
                    "perimeter_m": None if invalid else quantity.get("perimeter_m"),
                    "measured_width_m": None if invalid else quantity.get("measured_width_m"),
                    "measured_length_m": None if invalid else quantity.get("measured_length_m"),
                    "printed_width_mm": printed_width,
                    "printed_length_mm": printed_length,
                    "dimension_difference_percent": round(difference, 3) if difference is not None else None,
                    "dimension_status": dimension.get("dimension_status") or "unknown",
                    "dimension_source": dimension.get("dimension_source") or "unknown",
                    "measurement_status": measurement_status,
                    "geometry_status": geometry_state,
                    "validation_details": {
                        **(room.get("validation_details") or {}),
                        **validation,
                        "point_count": len(points),
                        "quantity_geometry_source": quantity.get("source"),
                    },
                    "space_kind": space_kind,
                    "include_in_boq": include_in_boq,
                    "status": status,
                    "is_stale": False,
                }, int(versions["room_version"]), confirmed=bool(room.get("user_confirmed")),
            ))
        return {"updated": len(updated), "rooms": updated, "scale_verified": scale_verified}

    def precision_refine(
        self, project_id: str, floor_id: str, *, calculate_areas: bool = True
    ) -> dict:
        if not settings.room_precision_pass_enabled:
            return {"status": "disabled", "updated": 0}
        floor = floors_repository.get_floor_row(project_id, floor_id)
        if not floor:
            raise not_found("Floor not found.")
        rooms = [item for item in floors_repository.list_rooms(project_id, floor_id) if not item.get("excluded")]
        prepared, evidence = self._prepared_geometry(project_id, floor_id, floor)
        versions = self._versions(floor)
        run = floors_repository.begin_precision_run(project_id, floor_id, versions)
        try:
            patches = precision_room_pipeline.refine(
                project_id=project_id,
                floor_id=floor_id,
                floor=floor,
                rooms=rooms,
                prepared=prepared,
                evidence=evidence,
                suggestions=floors_repository.list_suggestions(project_id, floor_id),
            )
            with get_connection() as connection:
                current = workflow_repository.increment_floor_version(connection, project_id, floor_id, "room_version")
            room_version = int(current.get("room_version") or 0)
            changed = 0
            for room in rooms:
                patch = patches.get(str(room["id"]))
                if not patch:
                    continue
                patch["precision_updated_at"] = __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat()
                patch["geometry_version"] = int(room.get("geometry_version") or 0) + (1 if patch.get("points") else 0)
                floors_repository.update_room(
                    project_id,
                    floor_id,
                    str(room["id"]),
                    patch,
                    room_version,
                    confirmed=bool(room.get("user_confirmed")),
                )
                changed += 1
            suppressed = self._suppress_generated_overlaps(project_id, floor_id)
            if calculate_areas:
                self.calculate(project_id, floor_id)
            floors_repository.complete_precision_run(str(run["id"]), len(rooms), changed)
            return {
                "status": "ready",
                "rooms": len(rooms),
                "updated": changed,
                "duplicates_suppressed": suppressed,
            }
        except Exception as exc:
            floors_repository.complete_precision_run(str(run["id"]), len(rooms), 0, str(exc))
            raise

    def interpret_floor(self, project_id: str, floor_id: str) -> dict:
        """Interpret one floor without delaying or modifying quantity geometry."""
        floor = floors_repository.get_floor_row(project_id, floor_id)
        if not floor:
            raise not_found("Floor not found.")
        rooms = [
            room
            for room in floors_repository.list_rooms(project_id, floor_id, include_excluded=False)
            if not room.get("is_finish_zone")
        ]
        with get_connection() as connection:
            versions = (
                workflow_repository.increment_floor_version(
                    connection, project_id, floor_id, "room_version"
                )
                if rooms
                else workflow_repository.get_versions(connection, project_id, floor_id)
            )
        room_version = int(versions.get("room_version") or 0)
        for room in rooms:
            if not room.get("user_confirmed"):
                floors_repository.update_room(
                    project_id,
                    floor_id,
                    str(room["id"]),
                    {"interpretation_status": "processing", "interpretation_warnings": []},
                    room_version,
                    confirmed=False,
                )

        result = llm_room_interpreter.interpret_floor(project_id, floor_id)
        if rooms:
            # Interpretation status, labels and dimension evidence are room
            # state too. Publish a second version so quiet cache/version checks
            # observe the completed result rather than remaining on processing.
            with get_connection() as connection:
                versions = workflow_repository.increment_floor_version(
                    connection, project_id, floor_id, "room_version"
                )
            room_version = int(versions.get("room_version") or 0)
        status = str(result.get("status") or "failed")
        if status in {"disabled", "not_configured", "not_needed", "processing"}:
            final_status = "skipped" if status != "processing" else "processing"
            for room in rooms:
                if not room.get("user_confirmed"):
                    floors_repository.update_room(
                        project_id,
                        floor_id,
                        str(room["id"]),
                        {"interpretation_status": final_status},
                        room_version,
                        confirmed=False,
                    )
            return {**result, "updated": 0}

        if status == "failed":
            warning = str(result.get("warning") or "Room interpretation was unavailable.")
            for room in rooms:
                if not room.get("user_confirmed"):
                    floors_repository.update_room(
                        project_id,
                        floor_id,
                        str(room["id"]),
                        {
                            "interpretation_status": "failed",
                            "interpretation_warnings": [warning],
                        },
                        room_version,
                        confirmed=False,
                    )
            return {**result, "updated": 0}

        by_id = {str(room["id"]): room for room in rooms}
        updated = 0
        interpreted_ids: set[str] = set()
        threshold = float(getattr(settings, "room_llm_confidence_threshold", 0.65))
        for interpreted in result.get("rooms") or []:
            room_id = str(interpreted.get("room_id") or "")
            room = by_id.get(room_id)
            if not room:
                continue
            interpreted_ids.add(room_id)
            confidence = float(interpreted.get("confidence") or 0)
            warnings = list(interpreted.get("warnings") or [])
            patch: dict[str, Any] = {
                "interpretation_run_id": result.get("run_id"),
                "interpretation_status": "ready" if confidence >= threshold else "needs_review",
                "interpretation_warnings": warnings,
            }
            label_is_protected = room.get("label_source") == "user" or (
                room.get("label_source") == "drawing" and float(room.get("label_confidence") or 0) >= 0.85
            )
            if not label_is_protected:
                interpreted_name = str(interpreted.get("room_name") or "")
                interpreted_type = str(interpreted.get("room_type") or "")
                known_labels = room_semantics.match_known_labels(
                    f"{interpreted_name} {interpreted_type}"
                )
                if known_labels:
                    normalized = room_semantics.classify(known_labels)
                    patch.update(
                        {
                            "name": normalized.get("name") or room.get("name"),
                            "room_type": normalized.get("room_type") or room.get("room_type"),
                            "label_source": "llm",
                            "label_confidence": confidence,
                        }
                    )
                else:
                    fallback = room_semantics.clean(interpreted_name) or room_semantics.clean(
                        interpreted_type
                    )
                    if fallback:
                        cleaned = room_semantics.normalize(fallback)
                        patch.update(
                            {
                                "name": cleaned,
                                "room_type": cleaned,
                                "label_source": "llm",
                                "label_confidence": confidence,
                            }
                        )
            area_type = interpreted.get("area_type")
            if room.get("label_source") != "user" and area_type in {
                "internal",
                "external",
                "circulation",
                "void",
            }:
                patch["space_kind"] = area_type
                patch["include_in_boq"] = area_type not in {"circulation", "void"}
            patch["open_plan"] = interpreted.get("semantic_type") == "open_plan" or bool(
                interpreted.get("open_plan_group")
            )
            printed_width = interpreted.get("printed_width_mm")
            printed_length = interpreted.get("printed_length_mm")
            patch.update(
                {
                    "printed_width_mm": printed_width,
                    "printed_length_mm": printed_length,
                    "dimension_status": interpreted.get("dimension_status") or "unknown",
                    "dimension_source": (
                        "llm_verified"
                        if printed_width is not None or printed_length is not None
                        else "unknown"
                    ),
                }
            )
            floors_repository.update_room(
                project_id,
                floor_id,
                room_id,
                patch,
                room_version,
                confirmed=bool(room.get("user_confirmed")),
            )
            updated += 1

        for room in rooms:
            if room["id"] not in interpreted_ids and not room.get("user_confirmed"):
                floors_repository.update_room(
                    project_id,
                    floor_id,
                    str(room["id"]),
                    {
                        "interpretation_run_id": result.get("run_id"),
                        "interpretation_status": "needs_review",
                        "interpretation_warnings": ["No validated interpretation matched this room."],
                    },
                    room_version,
                    confirmed=False,
                )
        return {**result, "updated": updated}

    def interpret_ambiguous(self, project_id: str, floor_id: str) -> dict:
        """Compatibility alias for queued jobs created by older versions."""
        return self.interpret_floor(project_id, floor_id)

    def interpretation_status(self, project_id: str, floor_id: str) -> dict:
        if not floors_repository.get_floor_row(project_id, floor_id):
            raise not_found("Floor not found.")
        run = llm_room_cache.status(project_id, floor_id)
        rooms = floors_repository.list_rooms(project_id, floor_id, include_excluded=False)
        return {
            "project_id": project_id,
            "floor_id": floor_id,
            "status": run.get("status") or "not_started",
            "run_id": run.get("id"),
            "model": run.get("model"),
            "prompt_version": run.get("prompt_version"),
            "updated_at": run.get("updated_at"),
            "room_statuses": [
                {
                    "room_id": room["id"],
                    "status": room.get("interpretation_status") or "not_started",
                    "warnings": room.get("interpretation_warnings") or [],
                }
                for room in rooms
                if not room.get("is_finish_zone")
            ],
        }

    def auto_fix_preview(self, project_id: str, floor_id: str, room_id: str) -> dict:
        room = floors_repository.get_room(project_id, floor_id, room_id)
        floor = floors_repository.get_floor_row(project_id, floor_id)
        if not room or not floor:
            raise not_found("Room not found.")
        original_points = (room.get("geometry") or {}).get("points") or []
        original_polygon = room_polygon_builder.points_to_polygon(original_points)
        if original_polygon.is_empty:
            raise bad_request("The current room polygon is invalid.")

        prepared, _ = self._prepared_geometry(project_id, floor_id, floor)
        crop_rect = ((floor.get("coordinates") or {}).get("original_rect") or {})
        crop_width, crop_height = self._crop_size(floor)
        envelope = building_envelope_service.build(
            prepared,
            float(crop_rect.get("width") or crop_width or 1),
            float(crop_rect.get("height") or crop_height or 1),
        )
        seeded = room_seed_service.refine(
            room_id=room_id,
            room_points=original_points,
            suggestions=floors_repository.list_suggestions(project_id, floor_id),
            prepared=prepared,
            envelope=envelope,
        )
        candidate_points = seeded.points if seeded is not None else original_points
        candidate_points = room_polygon_builder.snap_polygon_to_walls(
            candidate_points, prepared, tolerance=max(4.0, float(prepared.get("typical_thickness_px") or 8) * 1.8)
        )
        result = polygon_regularizer.regularize(
            candidate_points,
            wall_thickness_px=float(prepared.get("typical_thickness_px") or 0),
        )
        proposed_points = result.get("points") or original_points
        proposed_polygon = room_polygon_builder.points_to_polygon(proposed_points)
        if proposed_polygon.is_empty:
            proposed_points = original_points
            proposed_polygon = original_polygon

        area_change = (proposed_polygon.area - original_polygon.area) / max(original_polygon.area, 1e-9) * 100.0
        changed = room_polygon_builder.geometry_hash(original_polygon) != room_polygon_builder.geometry_hash(proposed_polygon)
        warnings: list[str] = []
        if seeded is None:
            warnings.append("No strong room-model seed matched this room; wall snapping and polygon cleanup were used.")
        if abs(area_change) > 10:
            warnings.append("The proposed area differs by more than 10%. Review the preview before applying it.")
        return {
            "room_id": room_id,
            "original": {"points": original_points},
            "proposed": {"points": proposed_points},
            "changed": changed,
            "shape_type": result.get("shape_type"),
            "original_vertex_count": len(original_points),
            "proposed_vertex_count": len(proposed_points),
            "area_change_percent": round(area_change, 3),
            "source": seeded.source if seeded is not None else "wall_snap_regularizer",
            "seed_score": seeded.score if seeded is not None else None,
            "model_overlap": seeded.model_overlap if seeded is not None else None,
            "warnings": warnings,
        }

    def reset_to_model(self, project_id: str, floor_id: str, room_id: str, created_by: str | None) -> dict:
        room = floors_repository.get_room(project_id, floor_id, room_id)
        if not room:
            raise not_found("Room not found.")
        points = (room.get("model_polygon") or room.get("raw_geometry") or room.get("generated_geometry") or {}).get("points") or []
        self._validate(points)
        edit_history_service.record(project_id, floor_id, room, "reset_to_model", created_by)
        regularized = polygon_regularizer.regularize(points)
        display_points = regularized.get("points") or points
        polygon = room_polygon_builder.points_to_polygon(display_points)
        with get_connection() as connection:
            versions = workflow_repository.increment_floor_version(connection, project_id, floor_id, "room_version")
        record = floors_repository.update_room(
            project_id, floor_id, room_id,
            {
                "points": display_points,
                "regularized_geometry": {"points": display_points},
                "confirmed_geometry": {},
                "geometry_hash": room_polygon_builder.geometry_hash(polygon),
                "shape_type": regularized.get("shape_type") or "irregular",
                "detection_source": "roboflow",
                "boundary_source": "model_only",
                "comparison_status": "model_provisional",
                "precision_status": "detected",
                "geometry_status": "needs_review",
                "measurement_status": "check",
                "status": "needs_review",
                "model_verified": False,
                "user_edited": False,
                "geometry_version": int(room.get("geometry_version") or 0) + 1,
            },
            int(versions["room_version"]), confirmed=False,
        )
        self.calculate(project_id, floor_id, [room_id])
        return {"record": floors_repository.get_room(project_id, floor_id, room_id), "jobs": []}

    def reset_to_corrected(self, project_id: str, floor_id: str, room_id: str, created_by: str | None) -> dict:
        room = floors_repository.get_room(project_id, floor_id, room_id)
        if not room:
            raise not_found("Room not found.")
        points = (
            (room.get("wall_corrected_geometry") or {}).get("points")
            or (room.get("regularized_geometry") or {}).get("points")
            or []
        )
        seeded = None
        if not points or str(room.get("boundary_source") or "") == "model_only":
            floor = floors_repository.get_floor_row(project_id, floor_id)
            if not floor:
                raise not_found("Floor not found.")
            prepared, _ = self._prepared_geometry(project_id, floor_id, floor)
            crop_rect = ((floor.get("coordinates") or {}).get("original_rect") or {})
            crop_width, crop_height = self._crop_size(floor)
            envelope = building_envelope_service.build(prepared, float(crop_rect.get("width") or crop_width or 1), float(crop_rect.get("height") or crop_height or 1))
            seeded = room_seed_service.refine(
                room_id=room_id, room_points=(room.get("geometry") or {}).get("points") or [],
                suggestions=floors_repository.list_suggestions(project_id, floor_id), prepared=prepared, envelope=envelope,
            )
            if seeded is None or seeded.source == "model_only":
                raise bad_request("A wall-corrected boundary is not available yet.")
            points = polygon_regularizer.regularize(
                seeded.points, wall_thickness_px=float(prepared.get("typical_thickness_px") or 0)
            ).get("points") or seeded.points
        edit_history_service.record(project_id, floor_id, room, "reset_to_corrected", created_by)
        polygon = room_polygon_builder.points_to_polygon(points)
        with get_connection() as connection:
            versions = workflow_repository.increment_floor_version(connection, project_id, floor_id, "room_version")
        floors_repository.update_room(
            project_id, floor_id, room_id,
            {
                "points": points,
                "wall_corrected_geometry": {"points": points},
                "regularized_geometry": {"points": points},
                "confirmed_geometry": {},
                "geometry_hash": room_polygon_builder.geometry_hash(polygon),
                "detection_source": "hybrid",
                "boundary_source": seeded.source if seeded else (
                    room.get("boundary_source")
                    if room.get("boundary_source") in {"model_seed_wall_region", "model_seed_wall_faces"}
                    else "model_seed_wall_region"
                ),
                "comparison_status": "wall_corrected", "precision_status": "corrected",
                "geometry_status": "needs_review", "status": "needs_review", "user_edited": False,
                "geometry_version": int(room.get("geometry_version") or 0) + 1,
            },
            int(versions["room_version"]), confirmed=False,
        )
        self.calculate(project_id, floor_id, [room_id])
        return {"record": floors_repository.get_room(project_id, floor_id, room_id), "jobs": []}

    def auto_fix(self, project_id: str, floor_id: str, room_id: str, created_by: str | None) -> dict:
        room = floors_repository.get_room(project_id, floor_id, room_id)
        if not room:
            raise not_found("Room not found.")
        preview = self.auto_fix_preview(project_id, floor_id, room_id)
        return self._save_editor_geometry(
            project_id, floor_id, room, (preview.get("proposed") or {}).get("points") or [],
            "auto_fix", created_by, {
                "shape_type": preview.get("shape_type"),
                "auto_fix_source": preview.get("source"),
                "auto_fix_area_change_percent": preview.get("area_change_percent"),
            }
        )

    def simplify_room(self, project_id: str, floor_id: str, room_id: str, created_by: str | None) -> dict:
        room = floors_repository.get_room(project_id, floor_id, room_id)
        if not room:
            raise not_found("Room not found.")
        points = room_edit_service.simplify((room.get("geometry") or {}).get("points") or [])
        return self._save_editor_geometry(project_id, floor_id, room, points, "simplify", created_by)

    def make_rectangle(self, project_id: str, floor_id: str, room_id: str, created_by: str | None) -> dict:
        room = floors_repository.get_room(project_id, floor_id, room_id)
        if not room:
            raise not_found("Room not found.")
        points = room_edit_service.make_rectangle((room.get("geometry") or {}).get("points") or [])
        return self._save_editor_geometry(project_id, floor_id, room, points, "make_rectangle", created_by, {"shape_type": "rectangle"})

    def straighten_room(self, project_id: str, floor_id: str, room_id: str, created_by: str | None) -> dict:
        room = floors_repository.get_room(project_id, floor_id, room_id)
        if not room:
            raise not_found("Room not found.")
        points = room_edit_service.straighten((room.get("geometry") or {}).get("points") or [])
        return self._save_editor_geometry(project_id, floor_id, room, points, "straighten", created_by)

    def patch_geometry(self, project_id: str, floor_id: str, room_id: str, payload: dict, created_by: str | None) -> dict:
        room = floors_repository.get_room(project_id, floor_id, room_id)
        if not room:
            raise not_found("Room not found.")
        points = (room.get("geometry") or {}).get("points") or []
        action = str(payload.get("action") or "replace")
        if action == "replace":
            next_points = payload.get("points") or points
        elif action == "add_point":
            next_points = room_edit_service.add_point(points, int(payload.get("edge_index") or 0), payload.get("point") or {})
        elif action == "delete_point":
            next_points = room_edit_service.delete_point(points, int(payload.get("point_index") or 0))
        elif action == "move_edge":
            next_points = room_edit_service.move_edge(points, int(payload.get("edge_index") or 0), float(payload.get("dx") or 0), float(payload.get("dy") or 0))
        else:
            raise bad_request("Unsupported geometry edit action.")
        return self._save_editor_geometry(project_id, floor_id, room, next_points, action, created_by)

    def create_cutout(self, project_id: str, floor_id: str, room_id: str, payload: dict, created_by: str | None) -> dict:
        room = floors_repository.get_room(project_id, floor_id, room_id)
        if not room:
            raise not_found("Room not found.")
        points = payload.get("points") or []
        self._validate(points)
        room_polygon = room_polygon_builder.points_to_polygon((room.get("geometry") or {}).get("points") or [])
        cutout_polygon = room_polygon_builder.points_to_polygon(points)
        clipped = cutout_polygon.intersection(room_polygon)
        if clipped.is_empty or clipped.area < 1:
            raise bad_request("Draw the cutout inside the room.")
        if hasattr(clipped, "geoms"):
            parts = [item for item in clipped.geoms if hasattr(item, "exterior")]
            clipped = max(parts, key=lambda item: item.area) if parts else clipped
        floor = floors_repository.get_floor_row(project_id, floor_id) or {}
        mm_per_pixel = float(floor.get("mm_per_pixel") or 0)
        area_m2 = clipped.area * mm_per_pixel * mm_per_pixel / 1_000_000 if mm_per_pixel > 0 else None
        edit_history_service.record(project_id, floor_id, room, "add_cutout", created_by)
        cutout = floors_repository.create_cutout(
            project_id=project_id,
            floor_id=floor_id,
            room_id=room_id,
            points=room_polygon_builder.polygon_to_points(clipped),
            name=payload.get("name"),
            area_m2=area_m2,
            created_by=created_by,
        )
        self.calculate(project_id, floor_id, [room_id])
        return {"record": floors_repository.get_room(project_id, floor_id, room_id), "cutout": cutout}

    def delete_cutout(self, project_id: str, floor_id: str, room_id: str, cutout_id: str, created_by: str | None) -> dict:
        room = floors_repository.get_room(project_id, floor_id, room_id)
        if not room:
            raise not_found("Room not found.")
        edit_history_service.record(project_id, floor_id, room, "delete_cutout", created_by, {"cutout_id": cutout_id})
        if not floors_repository.delete_cutout(project_id, floor_id, room_id, cutout_id):
            raise not_found("Cutout not found.")
        self.calculate(project_id, floor_id, [room_id])
        return {"deleted": True, "record": floors_repository.get_room(project_id, floor_id, room_id)}

    def revisions(self, project_id: str, floor_id: str, room_id: str) -> dict:
        if not floors_repository.get_room(project_id, floor_id, room_id):
            raise not_found("Room not found.")
        return {"items": floors_repository.list_geometry_revisions(project_id, floor_id, room_id)}

    def restore_revision(self, project_id: str, floor_id: str, room_id: str, revision_id: str, created_by: str | None) -> dict:
        room = floors_repository.get_room(project_id, floor_id, room_id)
        revision = floors_repository.get_geometry_revision(project_id, floor_id, room_id, revision_id)
        if not room or not revision:
            raise not_found("Geometry revision not found.")
        points = (revision.get("geometry") or {}).get("points") or []
        return self._save_editor_geometry(project_id, floor_id, room, points, "restore_revision", created_by, {"revision_id": revision_id})

    def _save_editor_geometry(
        self,
        project_id: str,
        floor_id: str,
        room: dict,
        points: list[dict],
        action: str,
        created_by: str | None,
        extra: dict | None = None,
    ) -> dict:
        self._validate(points)
        self._assert_no_overlap(
            project_id,
            floor_id,
            points,
            ignore_room_id=str(room["id"]),
            allow_finish_zone=bool(room.get("is_finish_zone")),
        )
        edit_history_service.record(project_id, floor_id, room, action, created_by)
        polygon = room_polygon_builder.points_to_polygon(points)
        normalized = room_polygon_builder.polygon_to_points(polygon)
        recognition = polygon_regularizer.regularize(normalized)
        with get_connection() as connection:
            versions = workflow_repository.increment_floor_version(connection, project_id, floor_id, "room_version")
        patch = {
            "points": normalized,
            "regularized_geometry": {"points": recognition.get("points") or normalized},
            "confirmed_geometry": {"points": normalized},
            "geometry_hash": room_polygon_builder.geometry_hash(polygon),
            "geometry_status": "ready",
            "detection_source": "user",
            "boundary_source": "user",
            "comparison_status": "user_edited",
            "precision_status": "needs_review",
            "user_edited": True,
            "geometry_version": int(room.get("geometry_version") or 0) + 1,
            "shape_type": (extra or {}).get("shape_type") or recognition.get("shape_type") or "polygon",
            "precision_updated_at": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
        }
        floors_repository.update_room(project_id, floor_id, str(room["id"]), patch, int(versions["room_version"]), confirmed=True)
        self.calculate(project_id, floor_id, [str(room["id"])])
        return {
            "record": floors_repository.get_room(project_id, floor_id, str(room["id"])),
            "jobs": self._downstream(project_id, floor_id, versions, created_by),
        }

    # ---- User actions -----------------------------------------------------

    def create(self, project_id: str, floor_id: str, payload: dict, created_by: str | None) -> dict:
        points = payload["points"]
        self._validate(points)
        self._assert_no_overlap(
            project_id,
            floor_id,
            points,
            allow_finish_zone=bool(payload.get("is_finish_zone")),
        )
        polygon = room_polygon_builder.points_to_polygon(points)
        with get_connection() as connection:
            versions = workflow_repository.increment_floor_version(connection, project_id, floor_id, "room_version")
        room = floors_repository.create_room(
            project_id=project_id,
            floor_id=floor_id,
            points=room_polygon_builder.polygon_to_points(polygon),
            generated=False,
            room_version=int(versions["room_version"]),
            created_by=created_by,
            name=payload.get("name"),
            room_type=payload.get("room_type"),
            floor_type_code=payload.get("floor_type_code"),
            floor_finish=payload.get("floor_finish"),
            detection_source="user",
            confidence=1.0,
            comparison_status="user_defined",
            geometry_hash=room_polygon_builder.geometry_hash(polygon),
            geometry_status="ready",
            space_kind=payload.get("space_kind") or "internal",
            include_in_boq=bool(payload.get("include_in_boq", True)),
            parent_room_id=payload.get("parent_room_id"),
            is_finish_zone=bool(payload.get("is_finish_zone", False)),
            open_plan=bool(payload.get("open_plan", False)),
        )
        self.calculate(project_id, floor_id, [room["id"]])
        return {
            "record": floors_repository.get_room(project_id, floor_id, room["id"]),
            "jobs": self._downstream(project_id, floor_id, versions, created_by),
        }

    def update(
        self,
        project_id: str,
        floor_id: str,
        room_id: str,
        payload: dict,
        created_by: str | None,
        *,
        overlap_ignore_room_ids: set[str] | None = None,
    ) -> dict:
        room = floors_repository.get_room(project_id, floor_id, room_id)
        if not room:
            raise not_found("Room not found.")
        if payload.get("points") is not None:
            self._validate(payload["points"])
            self._assert_no_overlap(
                project_id,
                floor_id,
                payload["points"],
                ignore_room_id=room_id,
                ignore_room_ids=overlap_ignore_room_ids,
                allow_finish_zone=bool(room.get("is_finish_zone")),
            )
            edit_history_service.record(project_id, floor_id, room, "geometry_update", created_by)
        updates = {
            key: value
            for key, value in payload.items()
            if key
            in {
                "points",
                "name",
                "room_type",
                "floor_type_code",
                "floor_finish",
                "manual_area_override_m2",
                "space_kind",
                "include_in_boq",
                "open_plan",
            }
        }
        if payload.get("review_status") is not None:
            updates["status"] = payload["review_status"]
        if payload.get("points") is not None:
            polygon = room_polygon_builder.points_to_polygon(payload["points"])
            updates.update(
                {
                    "points": room_polygon_builder.polygon_to_points(polygon),
                    "is_stale": True,
                    "geometry_status": "ready",
                    "detection_source": "user",
                    "confidence": 1.0,
                    "model_verified": False,
                    "comparison_status": "user_edited",
                    "geometry_hash": room_polygon_builder.geometry_hash(polygon),
                    "raw_geometry": room.get("raw_geometry") or room.get("generated_geometry") or room.get("geometry") or {},
                    "regularized_geometry": {"points": room_polygon_builder.polygon_to_points(polygon)},
                    "confirmed_geometry": {"points": room_polygon_builder.polygon_to_points(polygon)},
                    "shape_type": polygon_regularizer.regularize(payload["points"]).get("shape_type") or "polygon",
                    "boundary_source": "user",
                    "precision_status": "needs_review",
                    "user_edited": True,
                    "geometry_version": int(room.get("geometry_version") or 0) + 1,
                    "precision_updated_at": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
                }
            )
        if "name" in payload:
            semantics = room_semantics.classify(str(payload.get("name") or ""))
            updates.update({
                "label_source": "user",
                "label_confidence": 1.0,
                "space_kind": semantics["space_kind"],
                "include_in_boq": semantics["include_in_boq"],
                "open_plan": semantics["open_plan"],
            })
            if not payload.get("room_type") and semantics.get("room_type"):
                updates["room_type"] = semantics["room_type"]
        if "floor_finish" in payload:
            updates["finish_source"] = "user"
        with get_connection() as connection:
            versions = workflow_repository.increment_floor_version(connection, project_id, floor_id, "room_version")
        floors_repository.update_room(
            project_id, floor_id, room_id, updates, int(versions["room_version"]), confirmed=True
        )
        self.calculate(project_id, floor_id, [room_id])
        return {
            "record": floors_repository.get_room(project_id, floor_id, room_id),
            "jobs": self._downstream(project_id, floor_id, versions, created_by),
        }

    def delete(self, project_id: str, floor_id: str, room_id: str, created_by: str | None) -> dict:
        room = floors_repository.get_room(project_id, floor_id, room_id)
        if not room:
            raise not_found("Room not found.")
        floors_repository.reject_room(project_id, floor_id, room_id)
        with get_connection() as connection:
            versions = workflow_repository.increment_floor_version(connection, project_id, floor_id, "room_version")
        return {
            "deleted": True,
            "suppressed": True,
            "room_id": room_id,
            "jobs": self._downstream(project_id, floor_id, versions, created_by),
        }

    def confirm(self, project_id: str, floor_id: str, room_id: str, created_by: str | None) -> dict:
        room = floors_repository.get_room(project_id, floor_id, room_id)
        if not room:
            raise not_found("Room not found.")
        if room.get("measurement_status") == "missing_scale":
            raise bad_request("Verify the drawing scale before confirming this floor area.")
        if room.get("measurement_status") != "correct":
            raise bad_request("Correct the highlighted boundary or dimensions before confirmation.")
        if room.get("include_in_boq") and not room.get("floor_finish"):
            raise bad_request("Select a floor finish before confirmation.")
        self._assert_no_overlap(
            project_id,
            floor_id,
            (room.get("geometry") or {}).get("points") or [],
            ignore_room_id=room_id,
            allow_finish_zone=bool(room.get("is_finish_zone")),
        )
        with get_connection() as connection:
            versions = workflow_repository.increment_floor_version(connection, project_id, floor_id, "room_version")
        confirmed_geometry, _ = room_area_resolver.geometry(room)
        record = floors_repository.update_room(
            project_id, floor_id, room_id,
            {
                "status": "confirmed",
                "geometry_status": "confirmed",
                "confirmed_geometry": confirmed_geometry,
                "interpretation_status": (
                    "confirmed"
                    if room.get("interpretation_status") in {"processing", "needs_review"}
                    else room.get("interpretation_status")
                ),
                "excluded": False,
                "exclusion_reason": None,
            },
            int(versions["room_version"]), confirmed=True,
        )
        return {"record": record, "jobs": self._downstream(project_id, floor_id, versions, created_by)}

    def confirm_all(self, project_id: str, floor_id: str, created_by: str | None) -> dict:
        rooms = floors_repository.list_rooms(project_id, floor_id, include_excluded=False)
        confirmable: list[dict] = []
        for room in rooms:
            if (
                room.get("measurement_status") != "correct"
                or (room.get("include_in_boq") and not room.get("floor_finish"))
                or room.get("geometry_status") == "invalid"
            ):
                continue
            if room.get("is_finish_zone") or not room_overlap_service.conflicts(room, confirmable):
                confirmable.append(room)
        with get_connection() as connection:
            versions = workflow_repository.increment_floor_version(connection, project_id, floor_id, "room_version")
        floors_repository.confirm_rooms(project_id, floor_id, [room["id"] for room in confirmable], room_version=int(versions["room_version"]))
        return {"confirmed": len(confirmable), "blocked": len(rooms) - len(confirmable), "jobs": self._downstream(project_id, floor_id, versions, created_by)}

    def exclude(
        self, project_id: str, floor_id: str, room_id: str, reason: str | None, created_by: str | None
    ) -> dict:
        room = floors_repository.get_room(project_id, floor_id, room_id)
        if not room:
            raise not_found("Room not found.")
        with get_connection() as connection:
            versions = workflow_repository.increment_floor_version(connection, project_id, floor_id, "room_version")
        record = floors_repository.update_room(
            project_id,
            floor_id,
            room_id,
            {"excluded": True, "exclusion_reason": reason or "Excluded by user", "status": "confirmed"},
            int(versions["room_version"]),
            confirmed=True,
        )
        return {"record": record, "jobs": self._downstream(project_id, floor_id, versions, created_by)}

    def restore(self, project_id: str, floor_id: str, room_id: str, created_by: str | None) -> dict:
        with get_connection() as connection:
            versions = workflow_repository.increment_floor_version(connection, project_id, floor_id, "room_version")
        room = floors_repository.restore(project_id, floor_id, room_id, int(versions["room_version"]))
        self.calculate(project_id, floor_id, [room_id])
        return {"record": room, "jobs": self._downstream(project_id, floor_id, versions, created_by)}

    def accept_suggestion(
        self, project_id: str, floor_id: str, suggestion_id: str, payload: dict, created_by: str | None
    ) -> dict:
        suggestion = floors_repository.get_suggestion(project_id, floor_id, suggestion_id)
        if not suggestion:
            raise not_found("Room suggestion not found.")
        if suggestion.get("status") == "rejected":
            raise bad_request("This suggestion was rejected.")
        points = (suggestion.get("polygon") or {}).get("points") or []
        self._validate(points)
        polygon = room_polygon_builder.points_to_polygon(points)
        with get_connection() as connection:
            versions = workflow_repository.increment_floor_version(connection, project_id, floor_id, "room_version")
        room = floors_repository.create_room(
            project_id=project_id,
            floor_id=floor_id,
            points=room_polygon_builder.polygon_to_points(polygon),
            generated=True,
            room_version=int(versions["room_version"]),
            created_by=created_by,
            name=payload.get("name"),
            room_type=payload.get("room_type"),
            floor_type_code=payload.get("floor_type_code"),
            floor_finish=payload.get("floor_finish"),
            detection_source="roboflow",
            confidence=suggestion.get("confidence"),
            model_verified=False,
            comparison_status="model_only_accepted",
            geometry_hash=room_polygon_builder.geometry_hash(polygon),
            geometry_status="needs_review",
        )
        floors_repository.update_room(
            project_id, floor_id, str(room["id"]),
            {
                "raw_geometry": {"points": room_polygon_builder.polygon_to_points(polygon)},
                "regularized_geometry": {"points": polygon_regularizer.regularize(room_polygon_builder.polygon_to_points(polygon)).get("points") or room_polygon_builder.polygon_to_points(polygon)},
                "confirmed_geometry": {},
                "boundary_source": "model_only",
                "precision_status": "detected",
                "measurement_status": "check",
                "user_edited": False,
            },
            int(versions["room_version"]), confirmed=False,
        )
        floors_repository.update_suggestion(
            project_id,
            floor_id,
            suggestion_id,
            status="accepted",
            matched_room_id=room["id"],
            comparison_score=1.0,
        )
        self.calculate(project_id, floor_id, [room["id"]])
        return {
            "record": floors_repository.get_room(project_id, floor_id, room["id"]),
            "jobs": self._downstream(project_id, floor_id, versions, created_by),
        }

    def correct_suggestion_with_walls(
        self, project_id: str, floor_id: str, suggestion_id: str, created_by: str | None
    ) -> dict:
        suggestion = floors_repository.get_suggestion(project_id, floor_id, suggestion_id)
        if not suggestion or suggestion.get("status") in {"rejected", "superseded"}:
            raise not_found("Room suggestion not found.")
        room_id = str(suggestion.get("matched_room_id") or "")
        room = floors_repository.get_room(project_id, floor_id, room_id) if room_id else None
        if room is None:
            accepted = self.accept_suggestion(project_id, floor_id, suggestion_id, {}, created_by)
            room = accepted.get("record") or {}
            room_id = str(room.get("id") or "")
        if not room_id:
            raise bad_request("The detected room could not be created.")
        try:
            return self.reset_to_corrected(project_id, floor_id, room_id, created_by)
        except Exception:
            # Keep the provisional model room visible while wall topology is incomplete.
            return {
                "record": floors_repository.get_room(project_id, floor_id, room_id),
                "jobs": self.recalculate(project_id, floor_id, created_by).get("jobs", []),
                "status": "correcting",
            }

    def reject_suggestion(self, project_id: str, floor_id: str, suggestion_id: str) -> dict:
        if not floors_repository.get_suggestion(project_id, floor_id, suggestion_id):
            raise not_found("Room suggestion not found.")
        record = floors_repository.update_suggestion(
            project_id, floor_id, suggestion_id, status="rejected"
        )
        return {"record": record}

    def split(
        self, project_id: str, floor_id: str, room_id: str, axis: str, ratio: float, created_by: str | None
    ) -> dict:
        room = floors_repository.get_room(project_id, floor_id, room_id)
        if not room:
            raise not_found("Room not found.")
        parts = room_polygon_builder.split_polygon(
            (room.get("geometry") or {}).get("points") or [], axis=axis, ratio=ratio
        )
        if len(parts) != 2:
            raise bad_request("The selected room cannot be split at that position.")
        self.update(project_id, floor_id, room_id, {"points": parts[0]}, created_by)
        created = self.create(
            project_id,
            floor_id,
            {
                "points": parts[1],
                "name": None,
                "room_type": room.get("room_type"),
                "floor_type_code": room.get("floor_type_code"),
                "floor_finish": room.get("floor_finish"),
            },
            created_by,
        )
        return {"rooms": [floors_repository.get_room(project_id, floor_id, room_id), created["record"]]}

    def split_with_line(self, project_id: str, floor_id: str, room_id: str, points: list[dict], created_by: str | None) -> dict:
        room = floors_repository.get_room(project_id, floor_id, room_id)
        if not room:
            raise not_found("Room not found.")
        parts = room_polygon_builder.split_polygon_with_line((room.get("geometry") or {}).get("points") or [], points)
        if len(parts) != 2:
            raise bad_request("Draw a line that crosses the selected room from one side to the other.")
        self.update(project_id, floor_id, room_id, {"points": parts[0]}, created_by)
        created = self.create(project_id, floor_id, {
            "points": parts[1], "name": None, "room_type": room.get("room_type"),
            "floor_type_code": room.get("floor_type_code"), "floor_finish": room.get("floor_finish"),
            "space_kind": room.get("space_kind") or "internal", "include_in_boq": room.get("include_in_boq", True),
        }, created_by)
        return {"rooms": [floors_repository.get_room(project_id, floor_id, room_id), created["record"]]}

    def snap_to_walls(self, project_id: str, floor_id: str, room_id: str, created_by: str | None) -> dict:
        room = floors_repository.get_room(project_id, floor_id, room_id)
        floor = floors_repository.get_floor_row(project_id, floor_id)
        if not room or not floor:
            raise not_found("Room not found.")
        prepared, _ = self._prepared_geometry(project_id, floor_id, floor)
        points = room_polygon_builder.snap_polygon_to_walls((room.get("geometry") or {}).get("points") or [], prepared)
        return self.update(project_id, floor_id, room_id, {"points": points}, created_by)

    def create_finish_zone(self, project_id: str, floor_id: str, room_id: str, payload: dict, created_by: str | None) -> dict:
        parent = floors_repository.get_room(project_id, floor_id, room_id)
        if not parent:
            raise not_found("Room not found.")
        zone_points = finish_zone_service.validate(
            (parent.get("geometry") or {}).get("points") or [],
            payload.get("points") or [],
        )
        return self.create(project_id, floor_id, {
            "points": zone_points,
            "name": payload.get("name") or "Finish zone", "room_type": "Finish zone",
            "floor_type_code": payload.get("floor_type_code"), "floor_finish": payload.get("floor_finish"),
            "space_kind": parent.get("space_kind") or "internal", "include_in_boq": True,
            "parent_room_id": room_id, "is_finish_zone": True, "open_plan": True,
        }, created_by)

    def update_finish_zone(
        self, project_id: str, floor_id: str, room_id: str, zone_id: str, payload: dict, created_by: str | None
    ) -> dict:
        zone = floors_repository.get_room(project_id, floor_id, zone_id)
        if not zone or not zone.get("is_finish_zone") or zone.get("parent_room_id") != room_id:
            raise not_found("Finish zone not found.")
        if payload.get("points") is not None:
            parent = floors_repository.get_room(project_id, floor_id, room_id)
            if not parent:
                raise not_found("Parent room not found.")
            payload = dict(payload)
            payload["points"] = finish_zone_service.validate(
                (parent.get("geometry") or {}).get("points") or [], payload["points"]
            )
        return self.update(project_id, floor_id, zone_id, payload, created_by)

    def delete_finish_zone(
        self, project_id: str, floor_id: str, room_id: str, zone_id: str, created_by: str | None
    ) -> dict:
        zone = floors_repository.get_room(project_id, floor_id, zone_id)
        if not zone or not zone.get("is_finish_zone") or zone.get("parent_room_id") != room_id:
            raise not_found("Finish zone not found.")
        return self.delete(project_id, floor_id, zone_id, created_by)

    def merge(
        self, project_id: str, floor_id: str, room_id: str, other_room_id: str, created_by: str | None
    ) -> dict:
        first = floors_repository.get_room(project_id, floor_id, room_id)
        second = floors_repository.get_room(project_id, floor_id, other_room_id)
        if not first or not second:
            raise not_found("Room not found.")
        merged = room_polygon_builder.merge_polygons(
            (first.get("geometry") or {}).get("points") or [],
            (second.get("geometry") or {}).get("points") or [],
        )
        if not merged:
            raise bad_request("Only touching rooms can be merged.")
        self.update(
            project_id,
            floor_id,
            room_id,
            {"points": merged},
            created_by,
            overlap_ignore_room_ids={other_room_id},
        )
        floors_repository.delete_room(project_id, floor_id, other_room_id)
        return {"room": floors_repository.get_room(project_id, floor_id, room_id)}

    def recalculate_touching(
        self, project_id: str, floor_id: str, wall_id: str | None = None, element_id: str | None = None
    ) -> dict:
        room_ids: set[str] = set()
        if wall_id:
            room_ids.update(floors_repository.room_ids_for_wall(project_id, floor_id, wall_id))
        if element_id:
            room_ids.update(floors_repository.room_ids_for_opening(project_id, floor_id, element_id))
        if not room_ids:
            return {"updated": 0, "room_ids": []}
        result = self.build_polygons(
            project_id,
            floor_id,
            target_room_ids=sorted(room_ids),
        )
        self.reconcile(project_id, floor_id, sorted(room_ids))
        self.calculate(project_id, floor_id, sorted(room_ids))
        # Any confirmed room that depends on changed wall geometry must be
        # reviewed again, even when its regenerated polygon still has a high
        # overlap score with the previous shape.
        with get_connection() as connection:
            versions = workflow_repository.increment_floor_version(
                connection, project_id, floor_id, "room_version"
            )
        for room_id in sorted(room_ids):
            room = floors_repository.get_room(project_id, floor_id, room_id)
            if room and room.get("user_confirmed"):
                floors_repository.update_room(
                    project_id,
                    floor_id,
                    room_id,
                    {
                        "status": "needs_review",
                        "geometry_status": "needs_review",
                        "comparison_status": "wall_geometry_changed",
                    },
                    int(versions["room_version"]),
                    confirmed=True,
                )
        return {"updated": len(room_ids), "room_ids": sorted(room_ids), "result": result}

    # ---- helpers ----------------------------------------------------------

    @staticmethod
    def _validate(points: list[dict]) -> None:
        if len(points) < 3 or polygon_area(points) <= 4:
            raise bad_request("Draw a larger closed room.")
        if self_intersects(points):
            raise bad_request("The room boundary crosses itself.")
        polygon = room_polygon_builder.points_to_polygon(points)
        if polygon.is_empty or polygon.area <= 4:
            raise bad_request("Draw a valid closed room.")

    @staticmethod
    def _crop_size(floor: dict) -> tuple[float, float]:
        rect = ((floor.get("coordinates") or {}).get("original_rect") or {})
        return float(rect.get("width") or 0), float(rect.get("height") or 0)

    @staticmethod
    def _best_candidate(old_polygon: Any, candidates: list[dict], used: set[int]) -> tuple[int | None, float]:
        best_index: int | None = None
        best_score = 0.0
        for index, candidate in enumerate(candidates):
            if index in used:
                continue
            score = room_polygon_builder.iou(
                old_polygon, room_polygon_builder.points_to_polygon(candidate.get("points") or [])
            )
            if score > best_score:
                best_index, best_score = index, score
        return best_index, best_score

    @staticmethod
    def _contains_multiple_candidates(old_polygon: Any, candidates: list[dict]) -> bool:
        if old_polygon is None or old_polygon.is_empty:
            return False
        contained = 0
        for candidate in candidates:
            polygon = room_polygon_builder.points_to_polygon(candidate.get("points") or [])
            if polygon.is_empty or polygon.area >= old_polygon.area * 0.70:
                continue
            coverage = old_polygon.intersection(polygon).area / max(polygon.area, 1e-9)
            if coverage >= 0.72:
                contained += 1
        return contained >= 2

    def _assert_no_overlap(
        self,
        project_id: str,
        floor_id: str,
        points: list[dict],
        *,
        ignore_room_id: str | None = None,
        ignore_room_ids: set[str] | None = None,
        allow_finish_zone: bool = False,
    ) -> None:
        if allow_finish_zone:
            return
        conflicts = room_overlap_service.conflicts(
            {"points": points},
            floors_repository.list_rooms(project_id, floor_id, include_excluded=False),
            ignore_room_id=ignore_room_id,
            ignore_room_ids=ignore_room_ids,
        )
        if conflicts:
            names = ", ".join(str(item["name"]) for item in conflicts[:3])
            raise bad_request(f"Room overlaps {names}. Edit or delete the existing room first.")

    def _suppress_generated_overlaps(self, project_id: str, floor_id: str) -> int:
        """Keep one canonical room for every physical area after refinement.

        User-confirmed or edited geometry always wins. Among generated rooms,
        wall-grounded and validated geometry wins over raw model geometry.
        """
        rooms = [
            room
            for room in floors_repository.list_rooms(project_id, floor_id, include_excluded=False)
            if not room.get("is_finish_zone")
        ]

        def priority(room: dict) -> tuple[int, int, int, float]:
            protected = bool(
                room.get("detection_source") == "user"
            )
            source = str(room.get("boundary_source") or "")
            wall_grounded = source in {
                "wall_cell", "wall_only", "wall_geometry", "wall_corrected",
                "model_seed_wall_region", "model_seed_wall_faces", "vector_wall_faces",
            }
            area = float(room.get("area_m2") or 0)
            return (
                1 if protected else 0,
                1 if wall_grounded else 0,
                1 if room.get("measurement_status") == "correct" else 0,
                -area,
            )

        accepted: list[dict] = []
        suppressed = 0
        for room in sorted(rooms, key=priority, reverse=True):
            if not room_overlap_service.conflicts(room, accepted):
                accepted.append(room)
                continue
            protected = bool(
                room.get("detection_source") == "user"
            )
            if protected:
                # Preserve a user decision. Generated records are sorted after
                # protected records, so this branch is only a user/user clash.
                accepted.append(room)
                continue
            floors_repository.supersede_generated_room(project_id, floor_id, str(room["id"]))
            suppressed += 1
        return suppressed

    @staticmethod
    def _match_finish(room: dict, entries: list[dict]) -> str | None:
        room_code = str(room.get("floor_type_code") or "").strip().lower()
        room_type = str(room.get("room_type") or room.get("name") or "").strip().lower()
        for data in entries:
            code = str(data.get("type_code") or data.get("code") or "").strip().lower()
            location = str(data.get("room_type") or data.get("location") or "").strip().lower()
            if code and room_code and code == room_code:
                return str(data.get("finish") or data.get("material") or "") or None
            if location and room_type and (location in room_type or room_type in location):
                return str(data.get("finish") or data.get("material") or "") or None
        if len(entries) == 1:
            return str(entries[0].get("finish") or entries[0].get("material") or "") or None
        return None

    def _prepared_geometry(self, project_id: str, floor_id: str, floor: dict) -> tuple[dict, dict]:
        cache_key = self._geometry_cache_key(floor)
        cached = floors_repository.get_geometry_cache(project_id, floor_id, cache_key)
        if cached and cached.get("payload"):
            payload = cached["payload"]
            return room_line_builder.deserialize(payload.get("prepared") or {}), payload.get("evidence") or {}
        try:
            evidence = vector_floor_geometry_service.extract(project_id, floor_id)
        except Exception:
            evidence = {"segments": [], "wall_pairs": [], "dimensions": []}
        floors_repository.replace_dimension_observations(
            project_id, floor_id, int(floor.get("crop_version") or 0), evidence.get("dimensions") or []
        )
        prepared = room_line_builder.build(
            walls=walls_repository.list_walls(project_id, floor_id),
            openings=walls_repository.list_opening_elements(project_id, floor_id),
            mm_per_pixel=float(floor.get("mm_per_pixel") or 0) or None,
            vector_walls=evidence.get("wall_pairs") or [],
            vector_mode="refine",
        )
        floors_repository.save_geometry_cache(
            project_id=project_id, floor_id=floor_id,
            crop_version=int(floor.get("crop_version") or 0), wall_version=int(floor.get("wall_version") or 0),
            scale_version=int(floor.get("scale_version") or 0), cache_key=cache_key,
            payload={"prepared": room_line_builder.serialize(prepared), "evidence": evidence},
        )
        return prepared, evidence

    @staticmethod
    def _geometry_cache_key(floor: dict) -> str:
        # Include the geometry algorithm revision so existing projects do not
        # reuse caches that contained independent raw PDF vector boundaries.
        source = f"canonical-walls-v2:{floor.get('crop_version',0)}:{floor.get('wall_version',0)}:{floor.get('scale_version',0)}"
        return hashlib.sha256(source.encode("utf-8")).hexdigest()[:24]

    @staticmethod
    def _correct_candidate_dimensions(candidate: dict, observations: list[dict], mm_per_pixel: float) -> dict:
        if str(candidate.get("boundary_source") or "") in {
            "wall_cell", "wall_only", "wall_geometry", "wall_corrected",
            "model_seed_wall_region", "model_seed_wall_faces",
        }:
            # Printed dimensions validate wall-derived geometry; they do not
            # move a floor edge away from the detected inner wall face.
            return candidate
        polygon = room_polygon_builder.points_to_polygon(candidate.get("points") or [])
        if polygon.is_empty or mm_per_pixel <= 0:
            return candidate
        near = []
        for item in observations:
            a, b = item.get("point_a") or {}, item.get("point_b") or {}
            try:
                mid_x = (float(a["x"]) + float(b["x"])) / 2
                mid_y = (float(a["y"]) + float(b["y"])) / 2
            except (KeyError, TypeError, ValueError):
                continue
            from shapely.geometry import Point
            if polygon.buffer(30).contains(Point(mid_x, mid_y)):
                near.append(item)
        horizontal = max((item for item in near if item.get("orientation") == "horizontal"), key=lambda item: float(item.get("confidence") or 0), default=None)
        vertical = max((item for item in near if item.get("orientation") == "vertical"), key=lambda item: float(item.get("confidence") or 0), default=None)
        width_target = float(vertical.get("value_mm") or 0) / mm_per_pixel if vertical else None
        length_target = float(horizontal.get("value_mm") or 0) / mm_per_pixel if horizontal else None
        corrected_points = room_polygon_builder.correct_rectangular_dimensions(
            candidate.get("points") or [], target_width_px=width_target, target_length_px=length_target,
        )
        if corrected_points == candidate.get("points"):
            return candidate
        corrected = room_polygon_builder.points_to_polygon(corrected_points)
        return {
            **candidate,
            "points": corrected_points,
            "area_px": float(corrected.area),
            "perimeter_px": float(corrected.length),
            "geometry_hash": room_polygon_builder.geometry_hash(corrected),
            "dimension_corrected": True,
        }

    @staticmethod
    def _matching_dimensions(width_px: float, length_px: float, observations: list[dict]) -> tuple[float | None, float | None, float | None]:
        if not observations or width_px <= 0 or length_px <= 0:
            return None, None, None
        candidates = []
        for item in observations:
            suggested = float(item.get("suggested_mm_per_pixel") or 0)
            value = float(item.get("value_mm") or 0)
            if suggested <= 0 or value <= 0:
                continue
            for side, pixels in (("width", width_px), ("length", length_px)):
                predicted = pixels * suggested
                diff = abs(predicted - value) / max(value, 1.0) * 100
                candidates.append((diff, side, value))
        candidates.sort(key=lambda item: item[0])
        chosen: dict[str, tuple[float, float]] = {}
        for diff, side, value in candidates:
            if side not in chosen:
                chosen[side] = (value, diff)
        diffs = [item[1] for item in chosen.values()]
        return (
            chosen.get("width", (None, 0))[0], chosen.get("length", (None, 0))[0],
            statistics.mean(diffs) if diffs else None,
        )

    def _enqueue_tasks(
        self,
        project_id: str,
        floor_id: str,
        tasks: tuple[str, ...],
        versions: dict,
        created_by: str | None,
        *,
        payload: dict,
    ) -> list[dict]:
        version_values = self._versions(versions)
        jobs = []
        for task in tasks:
            job, created = job_service.enqueue(
                task_type=task,
                project_id=project_id,
                floor_id=floor_id,
                entity_id=floor_id,
                payload=payload,
                input_versions=version_values,
                created_by=created_by,
            )
            jobs.append({**job, "created": created})
        return jobs

    @staticmethod
    def _versions(versions: dict) -> dict:
        return {key: int(value or 0) for key, value in versions.items() if key.endswith("_version")}

    def _downstream(
        self, project_id: str, floor_id: str, versions: dict, created_by: str | None
    ) -> list[dict]:
        with get_connection() as connection:
            current_versions = workflow_repository.get_versions(connection, project_id, floor_id)
        version_values = self._versions(current_versions or versions)
        jobs = []
        for task in ("review.refresh", "boq.refresh"):
            scoped_floor = floor_id if task == "review.refresh" else None
            entity_id = floor_id if task == "review.refresh" else project_id
            job, created = job_service.enqueue(
                task_type=task, project_id=project_id, floor_id=scoped_floor,
                entity_id=entity_id,
                payload={"entity_type": "floor" if scoped_floor else "project", "floor_id": scoped_floor},
                input_versions=version_values, created_by=created_by,
            )
            jobs.append({**job, "created": created})
        return jobs


floors_service = FloorsService()
