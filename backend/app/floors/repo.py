from __future__ import annotations

from typing import Any
from uuid import uuid4

from app.database.session import get_connection, row_to_dict
from app.workflow.repo_base import dumps, loads, now_iso


class FloorsRepository:
    def floor_rows(self, project_id: str) -> list[dict]:
        with get_connection() as connection:
            rows = connection.execute(
                """
                SELECT f.*, fv.crop_version, fv.scale_version, fv.element_version,
                       fv.wall_version, fv.room_version,
                       fc.id AS crop_id, fc.coordinates_json, fc.crop_asset_key,
                       fc.preview_asset_key, fc.render_dpi, c.mm_per_pixel
                FROM floors f
                LEFT JOIN floor_versions fv ON fv.floor_id = f.id
                LEFT JOIN floor_crops fc ON fc.floor_id = f.id AND fc.is_current = 1
                LEFT JOIN calibrations c ON c.id = (
                  SELECT id FROM calibrations
                  WHERE floor_id = f.id ORDER BY scale_version DESC LIMIT 1
                )
                WHERE f.project_id = ? ORDER BY f.level_index
                """,
                (project_id,),
            ).fetchall()
        return [self._decode(row_to_dict(row) or {}) for row in rows]

    def get_floor_row(self, project_id: str, floor_id: str) -> dict | None:
        return next((row for row in self.floor_rows(project_id) if row["id"] == floor_id), None)

    def list_floors_needing_analysis(self) -> list[dict]:
        """Return ready floor crops that still have no visible canonical rooms."""
        with get_connection() as connection:
            rows = connection.execute(
                """
                SELECT f.project_id, f.id AS floor_id,
                       COALESCE(fv.crop_version, 0) AS crop_version,
                       COALESCE(fv.schedule_version, 0) AS schedule_version,
                       COALESCE(fv.scale_version, 0) AS scale_version,
                       COALESCE(fv.element_version, 0) AS element_version,
                       COALESCE(fv.wall_version, 0) AS wall_version,
                       COALESCE(fv.room_version, 0) AS room_version,
                       fc.id AS crop_id, fc.crop_asset_key
                FROM floors f
                JOIN floor_crops fc ON fc.floor_id = f.id AND fc.is_current = 1
                LEFT JOIN floor_versions fv ON fv.floor_id = f.id
                WHERE fc.crop_asset_key IS NOT NULL
                  AND fc.crop_asset_key <> ''
                  AND NOT EXISTS (
                    SELECT 1 FROM rooms r
                    WHERE r.project_id = f.project_id
                      AND r.floor_id = f.id
                      AND COALESCE(r.excluded, 0) = 0
                  )
                ORDER BY f.project_id, f.level_index
                """
            ).fetchall()
        return [row_to_dict(row) or {} for row in rows]

    def list_rooms(self, project_id: str, floor_id: str, *, include_excluded: bool = True) -> list[dict]:
        where = "" if include_excluded else " AND excluded = 0"
        with get_connection() as connection:
            rows = connection.execute(
                f"""SELECT * FROM rooms r WHERE project_id=? AND floor_id=?{where}
                    AND COALESCE(r.generated_status,'current')='current'
                    AND (r.source_crop_version IS NULL OR r.source_crop_version=(
                      SELECT crop_version FROM floor_versions fv WHERE fv.project_id=r.project_id AND fv.floor_id=r.floor_id
                    )) ORDER BY friendly_number, created_at""",
                (project_id, floor_id),
            ).fetchall()
            wall_relations = connection.execute(
                "SELECT * FROM room_wall_relations WHERE project_id = ? AND floor_id = ?",
                (project_id, floor_id),
            ).fetchall()
            opening_relations = connection.execute(
                "SELECT * FROM room_opening_relations WHERE project_id = ? AND floor_id = ?",
                (project_id, floor_id),
            ).fetchall()
            cutout_rows = connection.execute(
                "SELECT * FROM room_cutouts WHERE project_id = ? AND floor_id = ? ORDER BY created_at",
                (project_id, floor_id),
            ).fetchall()
        items = [self._decode(row_to_dict(row) or {}) for row in rows]
        walls_by_room: dict[str, list[str]] = {}
        for row in wall_relations:
            walls_by_room.setdefault(str(row["room_id"]), []).append(str(row["wall_id"]))
        openings_by_room: dict[str, list[str]] = {}
        for row in opening_relations:
            openings_by_room.setdefault(str(row["room_id"]), []).append(str(row["element_id"]))
        cutouts_by_room: dict[str, list[dict]] = {}
        for row in cutout_rows:
            decoded = self._decode(row_to_dict(row) or {})
            cutouts_by_room.setdefault(str(decoded.get("room_id")), []).append(decoded)
        for item in items:
            item["wall_ids"] = sorted(walls_by_room.get(item["id"], []))
            item["opening_ids"] = sorted(openings_by_room.get(item["id"], []))
            item["cutouts"] = cutouts_by_room.get(item["id"], [])
            geometry = item.get("geometry") or {}
            raw_geometry = item.get("raw_geometry") or item.get("generated_geometry") or {}
            wall_corrected = item.get("wall_corrected_geometry") or {}
            regularized = item.get("regularized_geometry") or {}
            confirmed_geometry = item.get("confirmed_geometry") or {}
            if item.get("user_confirmed") and (confirmed_geometry.get("points") or []):
                display = confirmed_geometry
            elif wall_corrected.get("points"):
                display = wall_corrected
            elif regularized.get("points"):
                display = regularized
            elif raw_geometry.get("points"):
                display = raw_geometry
            else:
                display = geometry
            boundary = str(item.get("boundary_source") or item.get("detection_source") or "unknown")
            if item.get("user_confirmed") or item.get("status") == "confirmed":
                stage = "confirmed"
            elif item.get("interpretation_status") == "processing":
                stage = "interpreting"
            elif item.get("precision_status") in {"processing", "correcting"}:
                stage = "correcting"
            elif boundary in {"model_only", "roboflow"} or item.get("comparison_status") == "model_provisional":
                stage = "detected"
            elif boundary in {"model_seed_wall_region", "model_seed_wall_faces", "wall_corrected", "hybrid"}:
                stage = "corrected"
            else:
                stage = "check"
            item["model_polygon"] = raw_geometry
            item["wall_corrected_polygon"] = wall_corrected
            item["regularized_polygon"] = regularized
            item["confirmed_polygon"] = confirmed_geometry
            item["display_polygon"] = display
            item["processing_stage"] = stage
            item["point_count"] = len((display or {}).get("points") or [])
        return items

    def list_room_records(
        self,
        project_id: str,
        floor_id: str,
        *,
        generated_status: str | None = None,
    ) -> list[dict]:
        """Return room records including inactive rejection/supersession rows.

        Canonical UI queries deliberately hide these rows. Regeneration needs
        them so a room explicitly deleted by a user is not recreated.
        """
        where = ""
        values: list[Any] = [project_id, floor_id]
        if generated_status:
            where = " AND COALESCE(generated_status,'current')=?"
            values.append(generated_status)
        with get_connection() as connection:
            rows = connection.execute(
                f"SELECT * FROM rooms WHERE project_id=? AND floor_id=?{where} ORDER BY created_at,id",
                tuple(values),
            ).fetchall()
        return [self._decode(row_to_dict(row) or {}) for row in rows]

    def reject_room(self, project_id: str, floor_id: str, room_id: str) -> bool:
        """Soft-delete a room and persist suppression for later analyses."""
        with get_connection() as connection:
            result = connection.execute(
                """UPDATE rooms
                   SET generated_status='rejected',excluded=1,status='rejected',
                       exclusion_reason=COALESCE(exclusion_reason,'Deleted by user'),updated_at=?
                   WHERE project_id=? AND floor_id=? AND id=?""",
                (now_iso(), project_id, floor_id, room_id),
            )
            connection.execute(
                """UPDATE room_suggestions SET status='rejected',updated_at=?
                   WHERE project_id=? AND floor_id=? AND matched_room_id=?""",
                (now_iso(), project_id, floor_id, room_id),
            )
        return bool(result.rowcount)

    def supersede_generated_room(self, project_id: str, floor_id: str, room_id: str) -> bool:
        """Hide an obsolete generated result while preserving its audit row."""
        with get_connection() as connection:
            result = connection.execute(
                """UPDATE rooms
                   SET generated_status='superseded',excluded=1,status='superseded',updated_at=?
                   WHERE project_id=? AND floor_id=? AND id=?
                     AND COALESCE(detection_source,'unknown')<>'user'""",
                (now_iso(), project_id, floor_id, room_id),
            )
        return bool(result.rowcount)

    def create_room(
        self,
        *,
        project_id: str,
        floor_id: str,
        points: list[dict],
        generated: bool,
        room_version: int,
        created_by: str | None,
        wall_ids: list[str] | None = None,
        opening_ids: list[str] | None = None,
        name: str | None = None,
        room_type: str | None = None,
        floor_type_code: str | None = None,
        floor_finish: str | None = None,
        detection_source: str | None = None,
        confidence: float | None = None,
        model_verified: bool = False,
        comparison_status: str = "not_compared",
        geometry_hash: str | None = None,
        geometry_status: str = "needs_review",
        suggestion_geometry: dict | None = None,
        space_kind: str = "internal",
        include_in_boq: bool = True,
        parent_room_id: str | None = None,
        is_finish_zone: bool = False,
        open_plan: bool = False,
        label_candidates: list[str] | None = None,
    ) -> dict:
        room_id = str(uuid4())
        now = now_iso()
        geometry = {"points": points}
        with get_connection() as connection:
            friendly = self._next_friendly(connection, project_id, floor_id)
            crop_version_row = connection.execute(
                "SELECT crop_version FROM floor_versions WHERE project_id=? AND floor_id=?",
                (project_id, floor_id),
            ).fetchone()
            source_crop_version = int(crop_version_row["crop_version"] or 0) if crop_version_row else 0
            connection.execute(
                """
                INSERT INTO rooms (
                  id, project_id, floor_id, name, geometry_json, area_m2, perimeter_m,
                  finish_code, status, is_stale, user_confirmed, room_version,
                  source_versions_json, created_by, created_at, updated_at, friendly_number,
                  room_type, floor_type_code, floor_finish, generated_geometry_json,
                  label_source, finish_source, geometry_status, detection_source,
                  confidence, model_verified, comparison_status, excluded,
                  exclusion_reason, label_confidence, geometry_hash, space_kind,
                  measurement_status, measured_width_m, measured_length_m,
                  printed_width_mm, printed_length_mm, dimension_difference_percent,
                  include_in_boq, parent_room_id, is_finish_zone, open_plan, label_candidates_json,
                  source_crop_version, generated_status
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    room_id,
                    project_id,
                    floor_id,
                    name,
                    dumps(geometry),
                    None,
                    None,
                    None,
                    "needs_review",
                    1,
                    0 if generated else 1,
                    room_version,
                    dumps({"room_version": room_version}),
                    created_by,
                    now,
                    now,
                    friendly,
                    room_type,
                    floor_type_code,
                    floor_finish,
                    dumps(suggestion_geometry or (geometry if generated else {})),
                    "user" if name and not generated else "drawing",
                    "user" if floor_finish and not generated else None,
                    geometry_status,
                    detection_source or ("wall_geometry" if generated else "user"),
                    confidence,
                    1 if model_verified else 0,
                    comparison_status,
                    0,
                    None,
                    1.0 if name and not generated else None,
                    geometry_hash,
                    space_kind,
                    "missing_scale",
                    None,
                    None,
                    None,
                    None,
                    None,
                    1 if include_in_boq else 0,
                    parent_room_id,
                    1 if is_finish_zone else 0,
                    1 if open_plan else 0,
                    dumps(label_candidates or []),
                    source_crop_version,
                    "current",
                ),
            )
            boundary_source = detection_source or ("wall_geometry" if generated else "user")
            wall_corrected = (
                {}
                if generated and boundary_source in {"roboflow", "model_only"}
                else geometry
            )
            connection.execute(
                """UPDATE rooms SET raw_geometry_json=?,wall_corrected_geometry_json=?,
                   regularized_geometry_json=?,confirmed_geometry_json=?,shape_type='polygon',
                   boundary_source=?,precision_status='needs_review',geometry_version=1,
                   interpretation_status='not_started',interpretation_warnings_json='[]',
                   dimension_status='unknown',dimension_source='unknown',
                   validation_details_json='{}',precision_updated_at=? WHERE id=?""",
                (
                    dumps(geometry),
                    dumps(wall_corrected),
                    dumps(geometry),
                    dumps({} if generated else geometry),
                    boundary_source,
                    now,
                    room_id,
                ),
            )
            self._replace_relations(
                connection,
                project_id=project_id,
                floor_id=floor_id,
                room_id=room_id,
                wall_ids=wall_ids or [],
                opening_ids=opening_ids or [],
                room_version=room_version,
            )
            row = connection.execute("SELECT * FROM rooms WHERE id = ?", (room_id,)).fetchone()
        return self._decode(row_to_dict(row) or {})

    def confirm_rooms(
        self, project_id: str, floor_id: str, room_ids: list[str], *, room_version: int
    ) -> int:
        unique_ids=list(dict.fromkeys(str(item) for item in room_ids if item))
        if not unique_ids:return 0
        placeholders=','.join('?' for _ in unique_ids)
        with get_connection() as connection:
            result=connection.execute(f"""UPDATE rooms SET status='confirmed',geometry_status='confirmed',user_confirmed=1,
                confirmed_geometry_json=CASE
                  WHEN COALESCE(wall_corrected_geometry_json,'{{}}')<>'{{}}' THEN wall_corrected_geometry_json
                  WHEN COALESCE(regularized_geometry_json,'{{}}')<>'{{}}' THEN regularized_geometry_json
                  WHEN COALESCE(raw_geometry_json,'{{}}')<>'{{}}' THEN raw_geometry_json
                  ELSE geometry_json END,
                interpretation_status=CASE WHEN interpretation_status='processing' THEN 'confirmed' ELSE interpretation_status END,
                is_stale=0,room_version=?,updated_at=? WHERE project_id=? AND floor_id=?
                AND excluded=0 AND measurement_status='correct' AND id IN ({placeholders})""",
                (room_version,now_iso(),project_id,floor_id,*unique_ids))
        return int(result.rowcount or 0)

    def update_room(
        self,
        project_id: str,
        floor_id: str,
        room_id: str,
        updates: dict[str, Any],
        room_version: int,
        confirmed: bool = True,
        *,
        wall_ids: list[str] | None = None,
        opening_ids: list[str] | None = None,
    ) -> dict:
        allowed = {
            "points": "geometry_json",
            "generated_geometry": "generated_geometry_json",
            "name": "name",
            "room_type": "room_type",
            "floor_type_code": "floor_type_code",
            "floor_finish": "floor_finish",
            "status": "status",
            "area_m2": "area_m2",
            "perimeter_m": "perimeter_m",
            "is_stale": "is_stale",
            "manual_area_override_m2": "manual_area_override_m2",
            "geometry_status": "geometry_status",
            "label_source": "label_source",
            "finish_source": "finish_source",
            "detection_source": "detection_source",
            "confidence": "confidence",
            "model_verified": "model_verified",
            "comparison_status": "comparison_status",
            "excluded": "excluded",
            "exclusion_reason": "exclusion_reason",
            "label_confidence": "label_confidence",
            "geometry_hash": "geometry_hash",
            "space_kind": "space_kind",
            "measurement_status": "measurement_status",
            "measured_width_m": "measured_width_m",
            "measured_length_m": "measured_length_m",
            "printed_width_mm": "printed_width_mm",
            "printed_length_mm": "printed_length_mm",
            "dimension_difference_percent": "dimension_difference_percent",
            "include_in_boq": "include_in_boq",
            "parent_room_id": "parent_room_id",
            "is_finish_zone": "is_finish_zone",
            "open_plan": "open_plan",
            "label_candidates": "label_candidates_json",
            "raw_geometry": "raw_geometry_json",
            "regularized_geometry": "regularized_geometry_json",
            "wall_corrected_geometry": "wall_corrected_geometry_json",
            "confirmed_geometry": "confirmed_geometry_json",
            "shape_type": "shape_type",
            "boundary_source": "boundary_source",
            "precision_status": "precision_status",
            "user_edited": "user_edited",
            "geometry_version": "geometry_version",
            "edit_revision": "edit_revision",
            "validation_details": "validation_details_json",
            "precision_updated_at": "precision_updated_at",
            "interpretation_status": "interpretation_status",
            "interpretation_warnings": "interpretation_warnings_json",
            "interpretation_run_id": "interpretation_run_id",
            "dimension_status": "dimension_status",
            "dimension_source": "dimension_source",
        }
        parts: list[str] = []
        values: list[Any] = []
        for key, value in updates.items():
            column = allowed.get(key)
            if not column:
                continue
            parts.append(f"{column} = ?")
            if key == "points":
                value = dumps({"points": value})
            elif key in {"generated_geometry", "raw_geometry", "wall_corrected_geometry", "regularized_geometry", "confirmed_geometry", "validation_details"}:
                value = dumps(value or {})
            elif key in {"label_candidates", "interpretation_warnings"}:
                value = dumps(value or [])
            elif key in {"model_verified", "excluded", "is_stale", "include_in_boq", "is_finish_zone", "open_plan", "user_edited"}:
                value = 1 if value else 0
            values.append(value)
        parts.extend(["room_version = ?", "user_confirmed = ?", "updated_at = ?"])
        values.extend([room_version, 1 if confirmed else 0, now_iso(), project_id, floor_id, room_id])
        with get_connection() as connection:
            connection.execute(
                f"UPDATE rooms SET {', '.join(parts)} WHERE project_id = ? AND floor_id = ? AND id = ?",
                values,
            )
            if wall_ids is not None or opening_ids is not None:
                current = self._relations(connection, project_id, floor_id, room_id)
                self._replace_relations(
                    connection,
                    project_id=project_id,
                    floor_id=floor_id,
                    room_id=room_id,
                    wall_ids=current["wall_ids"] if wall_ids is None else wall_ids,
                    opening_ids=current["opening_ids"] if opening_ids is None else opening_ids,
                    room_version=room_version,
                )
            row = connection.execute("SELECT * FROM rooms WHERE id = ?", (room_id,)).fetchone()
        return self._decode(row_to_dict(row) or {})

    def delete_room(self, project_id: str, floor_id: str, room_id: str) -> None:
        with get_connection() as connection:
            connection.execute(
                "DELETE FROM rooms WHERE project_id = ? AND floor_id = ? AND id = ?",
                (project_id, floor_id, room_id),
            )

    def get_room(self, project_id: str, floor_id: str, room_id: str) -> dict | None:
        return next(
            (room for room in self.list_rooms(project_id, floor_id) if room["id"] == room_id),
            None,
        )

    def room_ids_for_wall(self, project_id: str, floor_id: str, wall_id: str) -> list[str]:
        with get_connection() as connection:
            rows = connection.execute(
                """
                SELECT room_id FROM room_wall_relations
                WHERE project_id = ? AND floor_id = ? AND wall_id = ?
                ORDER BY room_id
                """,
                (project_id, floor_id, wall_id),
            ).fetchall()
        return [str(row["room_id"]) for row in rows]

    def room_ids_for_opening(self, project_id: str, floor_id: str, element_id: str) -> list[str]:
        with get_connection() as connection:
            rows = connection.execute(
                """
                SELECT room_id FROM room_opening_relations
                WHERE project_id = ? AND floor_id = ? AND element_id = ?
                ORDER BY room_id
                """,
                (project_id, floor_id, element_id),
            ).fetchall()
        return [str(row["room_id"]) for row in rows]

    def restore(self, project_id: str, floor_id: str, room_id: str, room_version: int) -> dict:
        room = self.get_room(project_id, floor_id, room_id)
        points = ((room or {}).get("generated_geometry") or {}).get("points") or []
        return self.update_room(
            project_id,
            floor_id,
            room_id,
            {
                "points": points,
                "is_stale": True,
                "status": "needs_review",
                "geometry_status": "needs_review",
                "excluded": False,
                "exclusion_reason": None,
                "detection_source": "wall_geometry",
            },
            room_version,
            confirmed=False,
        )

    # ---- Room model runs and suggestions ---------------------------------

    def get_segmentation_run(
        self, project_id: str, floor_id: str, crop_version: int, model_id: str
    ) -> dict | None:
        with get_connection() as connection:
            row = connection.execute(
                """
                SELECT * FROM room_segmentation_runs
                WHERE project_id = ? AND floor_id = ? AND crop_version = ? AND model_id = ?
                """,
                (project_id, floor_id, crop_version, model_id),
            ).fetchone()
        return self._decode(row_to_dict(row) or {}) if row else None

    def begin_segmentation_run(
        self,
        *,
        project_id: str,
        floor_id: str,
        crop_id: str,
        crop_version: int,
        model_id: str,
    ) -> dict:
        now = now_iso()
        with get_connection() as connection:
            connection.execute(
                """
                UPDATE room_suggestions
                SET status=CASE WHEN status='accepted' THEN status ELSE 'superseded' END,
                    updated_at=?
                WHERE project_id=? AND floor_id=? AND segmentation_run_id IN (
                  SELECT id FROM room_segmentation_runs
                  WHERE project_id=? AND floor_id=? AND model_id=? AND crop_version<>?
                )
                """,
                (now, project_id, floor_id, project_id, floor_id, model_id, crop_version),
            )
            existing = connection.execute(
                """
                SELECT id FROM room_segmentation_runs
                WHERE project_id=? AND floor_id=? AND crop_version=? AND model_id=?
                """,
                (project_id, floor_id, crop_version, model_id),
            ).fetchone()
            if existing:
                run_id = str(existing["id"])
                connection.execute(
                    """
                    UPDATE room_segmentation_runs
                    SET crop_id=?, status='processing', error_message=NULL, updated_at=?
                    WHERE id=?
                    """,
                    (crop_id, now, run_id),
                )
            else:
                run_id = str(uuid4())
                connection.execute(
                    """
                    INSERT INTO room_segmentation_runs (
                      id,project_id,floor_id,crop_id,crop_version,model_id,status,
                      raw_response_json,prediction_count,created_at,updated_at
                    ) VALUES (?,?,?,?,?,?,'processing','{}',0,?,?)
                    """,
                    (run_id, project_id, floor_id, crop_id, crop_version, model_id, now, now),
                )
            row = connection.execute(
                "SELECT * FROM room_segmentation_runs WHERE id=?", (run_id,)
            ).fetchone()
        return self._decode(row_to_dict(row) or {})

    def complete_segmentation_run(
        self,
        run_id: str,
        *,
        raw_response: dict,
        predictions: list[dict],
        image_width: float,
        image_height: float,
        crop_width: float,
        crop_height: float,
    ) -> dict:
        now = now_iso()
        with get_connection() as connection:
            run = connection.execute(
                "SELECT * FROM room_segmentation_runs WHERE id=?", (run_id,)
            ).fetchone()
            if not run:
                raise RuntimeError("Room segmentation run no longer exists.")
            connection.execute(
                "DELETE FROM room_suggestions WHERE segmentation_run_id=? AND status != 'accepted'",
                (run_id,),
            )
            scale_x = crop_width / image_width if image_width > 0 and crop_width > 0 else 1.0
            scale_y = crop_height / image_height if image_height > 0 and crop_height > 0 else 1.0
            from app.floors.polygon_builder import room_polygon_builder

            count = 0
            for prediction in predictions:
                points = [
                    {"x": float(point["x"]) * scale_x, "y": float(point["y"]) * scale_y}
                    for point in prediction.get("points") or []
                ]
                polygon = room_polygon_builder.points_to_polygon(points)
                if polygon.is_empty:
                    continue
                normalized = room_polygon_builder.polygon_to_points(polygon)
                geometry_hash = room_polygon_builder.geometry_hash(polygon)
                bbox = prediction.get("bounding_box") or {}
                bbox_scaled = {
                    "x": float(bbox.get("x") or 0) * scale_x,
                    "y": float(bbox.get("y") or 0) * scale_y,
                    "width": float(bbox.get("width") or 0) * scale_x,
                    "height": float(bbox.get("height") or 0) * scale_y,
                }
                existing = connection.execute(
                    "SELECT id,status FROM room_suggestions WHERE segmentation_run_id=? AND geometry_hash=?",
                    (run_id, geometry_hash),
                ).fetchone()
                if existing:
                    suggestion_id = str(existing["id"])
                    connection.execute(
                        """
                        UPDATE room_suggestions SET polygon_json=?,bounding_box_json=?,confidence=?,
                          class_name=?,class_source='roboflow',
                          updated_at=? WHERE id=?
                        """,
                        (
                            dumps({"points": normalized}),
                            dumps(bbox_scaled),
                            prediction.get("confidence"),
                            prediction.get("class_name"),
                            now,
                            suggestion_id,
                        ),
                    )
                else:
                    suggestion_id = str(uuid4())
                    connection.execute(
                        """
                        INSERT INTO room_suggestions (
                          id,segmentation_run_id,project_id,floor_id,polygon_json,
                          bounding_box_json,confidence,status,matched_room_id,
                          comparison_score,geometry_hash,class_name,class_source,created_at,updated_at
                        ) VALUES (?,?,?,?,?,?,?,'new',NULL,NULL,?,?,'roboflow',?,?)
                        """,
                        (
                            suggestion_id,
                            run_id,
                            run["project_id"],
                            run["floor_id"],
                            dumps({"points": normalized}),
                            dumps(bbox_scaled),
                            prediction.get("confidence"),
                            geometry_hash,
                            prediction.get("class_name"),
                            now,
                            now,
                        ),
                    )
                count += 1
            connection.execute(
                """
                UPDATE room_segmentation_runs
                SET status='ready',raw_response_json=?,prediction_count=?,image_width=?,
                    image_height=?,error_message=NULL,updated_at=? WHERE id=?
                """,
                (dumps(raw_response), count, image_width, image_height, now, run_id),
            )
            row = connection.execute(
                "SELECT * FROM room_segmentation_runs WHERE id=?", (run_id,)
            ).fetchone()
        return self._decode(row_to_dict(row) or {})

    def fail_segmentation_run(self, run_id: str, message: str) -> None:
        with get_connection() as connection:
            connection.execute(
                """
                UPDATE room_segmentation_runs SET status='failed',error_message=?,updated_at=?
                WHERE id=?
                """,
                (message[:1000], now_iso(), run_id),
            )

    def list_suggestions(
        self, project_id: str, floor_id: str, *, include_rejected: bool = False
    ) -> list[dict]:
        where = "" if include_rejected else " AND rs.status != 'rejected'"
        with get_connection() as connection:
            rows = connection.execute(
                f"""
                SELECT rs.*, rr.crop_version, rr.model_id, rr.status AS run_status
                FROM room_suggestions rs
                JOIN room_segmentation_runs rr ON rr.id=rs.segmentation_run_id
                JOIN floor_crops fc ON fc.id=rr.crop_id AND fc.is_current=1
                WHERE rs.project_id=? AND rs.floor_id=?{where}
                ORDER BY rs.confidence DESC, rs.created_at
                """,
                (project_id, floor_id),
            ).fetchall()
        return [self._decode(row_to_dict(row) or {}) for row in rows]

    def update_suggestion(
        self,
        project_id: str,
        floor_id: str,
        suggestion_id: str,
        *,
        status: str,
        matched_room_id: str | None = None,
        comparison_score: float | None = None,
    ) -> dict | None:
        with get_connection() as connection:
            connection.execute(
                """
                UPDATE room_suggestions SET status=?,matched_room_id=?,comparison_score=?,updated_at=?
                WHERE project_id=? AND floor_id=? AND id=?
                """,
                (
                    status,
                    matched_room_id,
                    comparison_score,
                    now_iso(),
                    project_id,
                    floor_id,
                    suggestion_id,
                ),
            )
            row = connection.execute(
                "SELECT * FROM room_suggestions WHERE id=?", (suggestion_id,)
            ).fetchone()
        return self._decode(row_to_dict(row) or {}) if row else None

    def get_suggestion(self, project_id: str, floor_id: str, suggestion_id: str) -> dict | None:
        return next(
            (
                item
                for item in self.list_suggestions(project_id, floor_id, include_rejected=True)
                if item["id"] == suggestion_id
            ),
            None,
        )

    def clear_suggestion_matches(self, project_id: str, floor_id: str) -> None:
        with get_connection() as connection:
            connection.execute(
                """
                UPDATE room_suggestions
                SET status=CASE WHEN status='accepted' THEN status ELSE 'new' END,
                    matched_room_id=CASE WHEN status='accepted' THEN matched_room_id ELSE NULL END,
                    comparison_score=CASE WHEN status='accepted' THEN comparison_score ELSE NULL END,
                    updated_at=?
                WHERE project_id=? AND floor_id=?
                """,
                (now_iso(), project_id, floor_id),
            )

    def replace_dimension_observations(
        self, project_id: str, floor_id: str, crop_version: int, observations: list[dict[str, Any]]
    ) -> list[dict]:
        now = now_iso()
        with get_connection() as connection:
            connection.execute(
                "DELETE FROM floor_dimension_observations WHERE project_id=? AND floor_id=? AND crop_version=?",
                (project_id, floor_id, crop_version),
            )
            for item in observations:
                connection.execute(
                    """
                    INSERT INTO floor_dimension_observations (
                      id,project_id,floor_id,crop_version,label_text,value_mm,orientation,
                      point_a_json,point_b_json,drawing_distance,suggested_mm_per_pixel,
                      confidence,status,created_at,updated_at
                    ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?, 'suggested',?,?)
                    """,
                    (
                        str(uuid4()), project_id, floor_id, crop_version, item.get("label_text") or str(item.get("value_mm")),
                        float(item.get("value_mm") or 0), item.get("orientation"), dumps(item.get("point_a") or {}),
                        dumps(item.get("point_b") or {}), item.get("drawing_distance"),
                        item.get("suggested_mm_per_pixel"), float(item.get("confidence") or 0), now, now,
                    ),
                )
        return self.list_dimension_observations(project_id, floor_id, crop_version)

    def list_dimension_observations(
        self, project_id: str, floor_id: str, crop_version: int | None = None
    ) -> list[dict]:
        params: list[Any] = [project_id, floor_id]
        where = "project_id=? AND floor_id=?"
        if crop_version is not None:
            where += " AND crop_version=?"
            params.append(crop_version)
        with get_connection() as connection:
            rows = connection.execute(
                f"SELECT * FROM floor_dimension_observations WHERE {where} ORDER BY confidence DESC, created_at",
                tuple(params),
            ).fetchall()
        return [self._decode(row_to_dict(row) or {}) for row in rows]

    def get_geometry_cache(self, project_id: str, floor_id: str, cache_key: str) -> dict | None:
        with get_connection() as connection:
            row = connection.execute(
                "SELECT * FROM floor_geometry_cache WHERE project_id=? AND floor_id=? AND cache_key=?",
                (project_id, floor_id, cache_key),
            ).fetchone()
        return self._decode(row_to_dict(row) or {}) if row else None

    def save_geometry_cache(
        self, *, project_id: str, floor_id: str, crop_version: int, wall_version: int,
        scale_version: int, cache_key: str, payload: dict[str, Any]
    ) -> dict:
        now = now_iso()
        with get_connection() as connection:
            connection.execute(
                """
                INSERT INTO floor_geometry_cache (id,project_id,floor_id,crop_version,wall_version,scale_version,cache_key,payload_json,created_at,updated_at)
                VALUES (?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(project_id,floor_id,cache_key) DO UPDATE SET
                  crop_version=excluded.crop_version,wall_version=excluded.wall_version,scale_version=excluded.scale_version,
                  payload_json=excluded.payload_json,updated_at=excluded.updated_at
                """,
                (str(uuid4()), project_id, floor_id, crop_version, wall_version, scale_version, cache_key, dumps(payload), now, now),
            )
            row = connection.execute(
                "SELECT * FROM floor_geometry_cache WHERE project_id=? AND floor_id=? AND cache_key=?",
                (project_id, floor_id, cache_key),
            ).fetchone()
        return self._decode(row_to_dict(row) or {})

    def child_finish_zones(self, project_id: str, floor_id: str, parent_room_id: str) -> list[dict]:
        with get_connection() as connection:
            rows = connection.execute(
                """SELECT * FROM rooms WHERE project_id=? AND floor_id=? AND parent_room_id=?
                   AND is_finish_zone=1 AND excluded=0 ORDER BY friendly_number,created_at""",
                (project_id, floor_id, parent_room_id),
            ).fetchall()
        return [self._decode(row_to_dict(row) or {}) for row in rows]

    def create_geometry_revision(
        self,
        *,
        project_id: str,
        floor_id: str,
        room_id: str,
        geometry: dict,
        action: str,
        created_by: str | None,
        metadata: dict,
    ) -> dict:
        now = now_iso()
        with get_connection() as connection:
            row = connection.execute(
                "SELECT COALESCE(MAX(revision),0) AS maximum FROM room_geometry_revisions WHERE room_id=?",
                (room_id,),
            ).fetchone()
            revision = int(row["maximum"] or 0) + 1
            revision_id = str(uuid4())
            connection.execute(
                """
                INSERT INTO room_geometry_revisions(
                  id,project_id,floor_id,room_id,revision,action,geometry_json,
                  metadata_json,created_by,created_at
                ) VALUES (?,?,?,?,?,?,?,?,?,?)
                """,
                (revision_id, project_id, floor_id, room_id, revision, action, dumps(geometry or {}), dumps(metadata or {}), created_by, now),
            )
            connection.execute(
                "UPDATE rooms SET edit_revision=?, updated_at=? WHERE id=?",
                (revision, now, room_id),
            )
            saved = connection.execute("SELECT * FROM room_geometry_revisions WHERE id=?", (revision_id,)).fetchone()
        return self._decode(row_to_dict(saved) or {})

    def list_geometry_revisions(self, project_id: str, floor_id: str, room_id: str) -> list[dict]:
        with get_connection() as connection:
            rows = connection.execute(
                """SELECT * FROM room_geometry_revisions
                   WHERE project_id=? AND floor_id=? AND room_id=? ORDER BY revision DESC""",
                (project_id, floor_id, room_id),
            ).fetchall()
        return [self._decode(row_to_dict(row) or {}) for row in rows]

    def get_geometry_revision(self, project_id: str, floor_id: str, room_id: str, revision_id: str) -> dict | None:
        with get_connection() as connection:
            row = connection.execute(
                """SELECT * FROM room_geometry_revisions
                   WHERE id=? AND project_id=? AND floor_id=? AND room_id=?""",
                (revision_id, project_id, floor_id, room_id),
            ).fetchone()
        return self._decode(row_to_dict(row) or {}) if row else None

    def create_cutout(
        self,
        *,
        project_id: str,
        floor_id: str,
        room_id: str,
        points: list[dict],
        name: str | None,
        area_m2: float | None,
        created_by: str | None,
    ) -> dict:
        cutout_id = str(uuid4())
        now = now_iso()
        with get_connection() as connection:
            connection.execute(
                """INSERT INTO room_cutouts(
                   id,project_id,floor_id,room_id,name,geometry_json,area_m2,
                   created_by,created_at,updated_at
                ) VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (cutout_id, project_id, floor_id, room_id, name, dumps({"points": points}), area_m2, created_by, now, now),
            )
            row = connection.execute("SELECT * FROM room_cutouts WHERE id=?", (cutout_id,)).fetchone()
        return self._decode(row_to_dict(row) or {})

    def delete_cutout(self, project_id: str, floor_id: str, room_id: str, cutout_id: str) -> bool:
        with get_connection() as connection:
            result = connection.execute(
                "DELETE FROM room_cutouts WHERE id=? AND project_id=? AND floor_id=? AND room_id=?",
                (cutout_id, project_id, floor_id, room_id),
            )
        return bool(result.rowcount)

    def list_cutouts(self, project_id: str, floor_id: str, room_id: str) -> list[dict]:
        with get_connection() as connection:
            rows = connection.execute(
                "SELECT * FROM room_cutouts WHERE project_id=? AND floor_id=? AND room_id=? ORDER BY created_at",
                (project_id, floor_id, room_id),
            ).fetchall()
        return [self._decode(row_to_dict(row) or {}) for row in rows]

    def begin_precision_run(self, project_id: str, floor_id: str, versions: dict) -> dict:
        now = now_iso()
        run_id = str(uuid4())
        values = (
            project_id,
            floor_id,
            int(versions.get("crop_version") or 0),
            int(versions.get("wall_version") or 0),
            int(versions.get("scale_version") or 0),
        )
        with get_connection() as connection:
            existing = connection.execute(
                """SELECT * FROM room_precision_runs WHERE project_id=? AND floor_id=?
                   AND crop_version=? AND wall_version=? AND scale_version=?""",
                values,
            ).fetchone()
            if existing:
                connection.execute(
                    "UPDATE room_precision_runs SET status='processing', error_message=NULL, started_at=?, completed_at=NULL WHERE id=?",
                    (now, existing["id"]),
                )
                row = connection.execute("SELECT * FROM room_precision_runs WHERE id=?", (existing["id"],)).fetchone()
            else:
                connection.execute(
                    """INSERT INTO room_precision_runs(
                       id,project_id,floor_id,crop_version,wall_version,scale_version,status,started_at
                    ) VALUES (?,?,?,?,?,?,'processing',?)""",
                    (run_id, *values, now),
                )
                row = connection.execute("SELECT * FROM room_precision_runs WHERE id=?", (run_id,)).fetchone()
        return self._decode(row_to_dict(row) or {})

    def complete_precision_run(self, run_id: str, room_count: int, changed_count: int, error: str | None = None) -> None:
        with get_connection() as connection:
            connection.execute(
                """UPDATE room_precision_runs SET status=?,room_count=?,changed_count=?,error_message=?,completed_at=? WHERE id=?""",
                ("failed" if error else "ready", room_count, changed_count, error, now_iso(), run_id),
            )

    @staticmethod
    def _next_friendly(connection: Any, project_id: str, floor_id: str) -> str:
        rows = connection.execute(
            "SELECT friendly_number FROM rooms WHERE project_id=? AND floor_id=?",
            (project_id, floor_id),
        ).fetchall()
        maximum = 0
        for row in rows:
            value = str(row["friendly_number"] or "")
            if value.upper().startswith("R") and value[1:].isdigit():
                maximum = max(maximum, int(value[1:]))
        return f"R{maximum + 1:03d}"

    def _replace_relations(
        self,
        connection: Any,
        *,
        project_id: str,
        floor_id: str,
        room_id: str,
        wall_ids: list[str],
        opening_ids: list[str],
        room_version: int,
    ) -> None:
        now = now_iso()
        connection.execute("DELETE FROM room_wall_relations WHERE room_id=?", (room_id,))
        connection.execute("DELETE FROM room_opening_relations WHERE room_id=?", (room_id,))
        for wall_id in sorted(set(wall_ids)):
            connection.execute(
                """
                INSERT INTO room_wall_relations (
                  id,project_id,floor_id,room_id,wall_id,relation_type,
                  relation_version,created_at,updated_at
                ) VALUES (?,?,?,?,?,'boundary',?,?,?)
                """,
                (str(uuid4()), project_id, floor_id, room_id, wall_id, room_version, now, now),
            )
        for element_id in sorted(set(opening_ids)):
            connection.execute(
                """
                INSERT INTO room_opening_relations (
                  id,project_id,floor_id,room_id,element_id,relation_type,
                  relation_version,created_at,updated_at
                ) VALUES (?,?,?,?,?,'virtual_closure',?,?,?)
                """,
                (str(uuid4()), project_id, floor_id, room_id, element_id, room_version, now, now),
            )

    @staticmethod
    def _relations(connection: Any, project_id: str, floor_id: str, room_id: str) -> dict:
        walls = connection.execute(
            "SELECT wall_id FROM room_wall_relations WHERE project_id=? AND floor_id=? AND room_id=?",
            (project_id, floor_id, room_id),
        ).fetchall()
        openings = connection.execute(
            "SELECT element_id FROM room_opening_relations WHERE project_id=? AND floor_id=? AND room_id=?",
            (project_id, floor_id, room_id),
        ).fetchall()
        return {
            "wall_ids": [str(row["wall_id"]) for row in walls],
            "opening_ids": [str(row["element_id"]) for row in openings],
        }

    @staticmethod
    def _decode(record: dict) -> dict:
        result = dict(record)
        for key in list(result):
            if key.endswith("_json"):
                result[key[:-5]] = loads(result.pop(key))
        for key in (
            "is_stale",
            "user_confirmed",
            "model_verified",
            "excluded",
            "include_in_boq",
            "is_finish_zone",
            "open_plan",
            "user_edited",
        ):
            if key in result:
                result[key] = bool(result[key])
        return result


floors_repository = FloorsRepository()
