from __future__ import annotations

from typing import Any
from uuid import uuid4

from app.database.session import get_connection, row_to_dict
from app.workflow.repo_base import dumps, loads, now_iso


class WallsRepository:
    def floor_rows(self, project_id: str) -> list[dict]:
        with get_connection() as connection:
            rows = connection.execute(
                """
                SELECT f.*, fv.crop_version, fv.scale_version, fv.element_version, fv.wall_version,
                       fc.coordinates_json, fc.crop_asset_key,
                       c.mm_per_pixel, c.status AS calibration_status
                FROM floors f
                LEFT JOIN floor_versions fv ON fv.floor_id = f.id
                LEFT JOIN floor_crops fc ON fc.floor_id = f.id AND fc.is_current = 1
                LEFT JOIN calibrations c ON c.id = (
                  SELECT c2.id FROM calibrations c2
                  WHERE c2.floor_id = f.id
                  ORDER BY c2.scale_version DESC LIMIT 1
                )
                WHERE f.project_id = ?
                ORDER BY f.level_index
                """,
                (project_id,),
            ).fetchall()
        return [self._decode(row_to_dict(row) or {}) for row in rows]

    def list_walls(self, project_id: str, floor_id: str) -> list[dict]:
        with get_connection() as connection:
            rows = connection.execute(
                """SELECT * FROM walls w WHERE project_id=? AND floor_id=?
                   AND COALESCE(w.generated_status,'current')='current'
                   AND (w.source_crop_version IS NULL OR w.source_crop_version=(
                     SELECT crop_version FROM floor_versions fv WHERE fv.project_id=w.project_id AND fv.floor_id=w.floor_id
                   )) ORDER BY item_number, created_at""",
                (project_id, floor_id),
            ).fetchall()
            items = [self._decode(row_to_dict(row) or {}) for row in rows]
            openings = connection.execute(
                """
                SELECT wo.*, e.friendly_number AS element_number, e.item_number AS element_item_number,
                       e.type_code, e.geometry_json, e.element_type
                FROM wall_openings wo
                JOIN elements e ON e.id = wo.element_id
                WHERE wo.project_id = ? AND wo.floor_id = ?
                  AND (COALESCE(e.is_manual,0)=1 OR COALESCE(e.generated_status,'current')='current')
                  AND (e.crop_version IS NULL OR e.crop_version=(SELECT crop_version FROM floor_versions fv
                       WHERE fv.project_id=e.project_id AND fv.floor_id=e.floor_id))
                ORDER BY e.item_number, e.created_at
                """,
                (project_id, floor_id),
            ).fetchall()
        by_wall: dict[str, list[dict]] = {item["id"]: [] for item in items}
        for row in openings:
            decoded = self._decode(row_to_dict(row) or {})
            by_wall.setdefault(decoded["wall_id"], []).append(decoded)
        for item in items:
            item["openings"] = by_wall.get(item["id"], [])
        return items

    def list_wall_records(
        self,
        project_id: str,
        floor_id: str,
        *,
        include_inactive: bool = False,
    ) -> list[dict]:
        """Return wall rows without hiding rejected/superseded source records.

        The automatic reconciliation path needs these hidden records so a wall
        explicitly removed by a user is not recreated on the next model run.
        """
        where = ["project_id = ?", "floor_id = ?"]
        values: list[Any] = [project_id, floor_id]
        if not include_inactive:
            where.append("COALESCE(generated_status, 'current') = 'current'")
        with get_connection() as connection:
            rows = connection.execute(
                f"SELECT * FROM walls WHERE {' AND '.join(where)} ORDER BY item_number, created_at",
                values,
            ).fetchall()
        return [self._decode(row_to_dict(row) or {}) for row in rows]

    def list_opening_elements(self, project_id: str, floor_id: str) -> list[dict]:
        with get_connection() as connection:
            rows = connection.execute(
                """
                SELECT e.*, wo.wall_id
                FROM elements e
                LEFT JOIN wall_openings wo ON wo.element_id = e.id
                WHERE e.project_id = ? AND e.floor_id = ?
                  AND e.element_type IN ('door', 'window') AND e.excluded = 0
                  AND (COALESCE(e.is_manual,0)=1 OR COALESCE(e.generated_status,'current')='current')
                  AND (e.crop_version IS NULL OR e.crop_version=(SELECT crop_version FROM floor_versions fv
                       WHERE fv.project_id=e.project_id AND fv.floor_id=e.floor_id))
                ORDER BY e.item_number, e.created_at
                """,
                (project_id, floor_id),
            ).fetchall()
            props = connection.execute(
                """
                SELECT * FROM element_properties
                WHERE project_id = ? AND floor_id = ?
                  AND property_name IN ('width_mm', 'height_mm')
                """,
                (project_id, floor_id),
            ).fetchall()
        by_element: dict[str, dict] = {}
        for row in props:
            decoded = self._decode(row_to_dict(row) or {})
            by_element.setdefault(decoded["element_id"], {})[decoded["property_name"]] = decoded.get("value")
        items = []
        for row in rows:
            item = self._decode(row_to_dict(row) or {})
            item["dimensions"] = by_element.get(item["id"], {})
            items.append(item)
        return items

    def geometry_context(self, project_id: str, floor_id: str) -> dict[str, Any]:
        """Expose versioned wall faces/openings for room geometry consumers."""
        from app.floors.line_builder import room_line_builder

        floor = next(
            (item for item in self.floor_rows(project_id) if item.get("id") == floor_id),
            None,
        )
        if not floor:
            return {
                "wall_version": 0,
                "wall_footprints": [],
                "inner_wall_faces": [],
                "opening_relations": [],
                "room_facing_sides": [],
            }
        openings = self.list_opening_elements(project_id, floor_id)
        prepared = room_line_builder.build(
            walls=self.list_walls(project_id, floor_id),
            openings=openings,
            mm_per_pixel=float(floor.get("mm_per_pixel") or 0) or None,
        )
        serialized = room_line_builder.serialize(prepared)
        with get_connection() as connection:
            facing = connection.execute(
                """SELECT room_id,wall_id,relation_type FROM room_wall_relations
                   WHERE project_id=? AND floor_id=? ORDER BY wall_id,room_id""",
                (project_id, floor_id),
            ).fetchall()
        footprints = [
            {"wall_id": item.get("id"), "points": item.get("footprint") or []}
            for item in serialized.get("wall_segments") or []
        ]
        return {
            "wall_version": int(floor.get("wall_version") or 0),
            "wall_footprints": footprints,
            "inner_wall_faces": footprints,
            "opening_relations": [
                {
                    "element_id": item.get("id"),
                    "wall_id": item.get("wall_id"),
                    "element_type": item.get("element_type"),
                }
                for item in openings
            ],
            "room_facing_sides": [row_to_dict(row) or {} for row in facing],
        }

    def create_wall(
        self,
        *,
        project_id: str,
        floor_id: str,
        centerline: dict,
        wall_type: str | None,
        classification: str | None,
        thickness_mm: float | None,
        height_mm: float | None,
        wall_version: int,
        created_by: str | None,
        source_versions: dict,
        source_element_id: str | None = None,
        item_number: int | None = None,
        status: str = "confirmed",
        user_confirmed: bool = True,
        generated_centerline: dict | None = None,
    ) -> dict:
        now = now_iso()
        wall_id = str(uuid4())
        with get_connection() as connection:
            if item_number is None:
                maximum = connection.execute(
                    "SELECT MAX(item_number) AS maximum FROM walls WHERE project_id = ?",
                    (project_id,),
                ).fetchone()["maximum"]
                element_maximum = connection.execute(
                    "SELECT MAX(item_number) AS maximum FROM elements WHERE project_id = ?",
                    (project_id,),
                ).fetchone()["maximum"]
                item_number = max(int(maximum or 0), int(element_maximum or 0)) + 1
            friendly = f"Wall {int(item_number):03d}"
            values = (
                wall_id, project_id, floor_id, dumps({}), wall_type, classification,
                thickness_mm, height_mm, None, 0.0, None, status, 1, 1 if user_confirmed else 0,
                wall_version, dumps(source_versions), created_by, now, now, friendly,
                dumps(centerline), dumps(generated_centerline or centerline), "floor", source_element_id, int(item_number),
                int(source_versions.get("crop_version") or 0), "current",
            )
            connection.execute(
                """
                INSERT INTO walls (
                  id, project_id, floor_id, geometry_json, wall_type, classification,
                  thickness_mm, height_mm, gross_area_m2, deduction_area_m2, net_area_m2,
                  status, is_stale, user_confirmed, wall_version, source_versions_json,
                  created_by, created_at, updated_at, friendly_number, centerline_json,
                  generated_centerline_json, height_source, source_element_id, item_number,
                  source_crop_version, generated_status
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                values,
            )
            row = connection.execute("SELECT * FROM walls WHERE id = ?", (wall_id,)).fetchone()
        return self._decode(row_to_dict(row) or {})

    def reconcile_generated_wall(
        self,
        *,
        project_id: str,
        floor_id: str,
        wall_id: str,
        generated_centerline: dict,
        centerline: dict | None,
        thickness_mm: float | None,
        height_mm: float | None,
        wall_version: int,
        source_versions: dict,
        item_number: int | None,
        preserve_user_confirmation: bool = False,
    ) -> dict:
        """Refresh model provenance while optionally preserving edited geometry."""
        assignments = [
            "generated_centerline_json = ?",
            "thickness_mm = COALESCE(?, thickness_mm)",
            "height_mm = COALESCE(?, height_mm)",
            "wall_version = ?",
            "source_versions_json = ?",
            "source_crop_version = ?",
            "generated_status = 'current'",
            "user_confirmed = CASE WHEN ?=1 THEN user_confirmed ELSE 0 END",
            "status = CASE WHEN ?=1 AND COALESCE(user_confirmed,0)=1 THEN 'confirmed' ELSE 'ready' END",
            "updated_at = ?",
        ]
        values: list[Any] = [
            dumps(generated_centerline),
            thickness_mm,
            height_mm,
            wall_version,
            dumps(source_versions),
            int(source_versions.get("crop_version") or 0),
            1 if preserve_user_confirmation else 0,
            1 if preserve_user_confirmation else 0,
            now_iso(),
        ]
        if centerline is not None:
            assignments.insert(1, "centerline_json = ?")
            values.insert(1, dumps(centerline))
        if item_number is not None:
            assignments.append("item_number = ?")
            values.append(int(item_number))
        values.extend([project_id, floor_id, wall_id])
        with get_connection() as connection:
            connection.execute(
                f"UPDATE walls SET {', '.join(assignments)} WHERE project_id = ? AND floor_id = ? AND id = ?",
                values,
            )
            row = connection.execute("SELECT * FROM walls WHERE id = ?", (wall_id,)).fetchone()
        return self._decode(row_to_dict(row) or {})

    def supersede_missing_generated(
        self,
        project_id: str,
        floor_id: str,
        active_source_ids: set[str],
    ) -> int:
        with get_connection() as connection:
            rows = connection.execute(
                """SELECT id, source_element_id FROM walls
                   WHERE project_id = ? AND floor_id = ?
                     AND source_element_id IS NOT NULL
                     AND COALESCE(generated_status, 'current') = 'current'""",
                (project_id, floor_id),
            ).fetchall()
            stale_ids = [
                row["id"] for row in rows
                if str(row["source_element_id"] or "") not in active_source_ids
            ]
            for wall_id in stale_ids:
                connection.execute(
                    "UPDATE walls SET generated_status = 'superseded', updated_at = ? WHERE id = ?",
                    (now_iso(), wall_id),
                )
        return len(stale_ids)

    def mark_merged(
        self,
        project_id: str,
        floor_id: str,
        wall_id: str,
        survivor_id: str,
    ) -> None:
        """Hide an automatically merged segment and retain its provenance."""
        with get_connection() as connection:
            connection.execute(
                """UPDATE wall_openings
                   SET wall_id = ?, relation_version = relation_version + 1, updated_at = ?
                   WHERE project_id = ? AND floor_id = ? AND wall_id = ?""",
                (survivor_id, now_iso(), project_id, floor_id, wall_id),
            )
            connection.execute(
                """UPDATE walls
                   SET generated_status = 'merged', status = 'merged', updated_at = ?
                   WHERE project_id = ? AND floor_id = ? AND id = ?""",
                (now_iso(), project_id, floor_id, wall_id),
            )

    def update_wall(
        self,
        project_id: str,
        floor_id: str,
        wall_id: str,
        updates: dict[str, Any],
        wall_version: int,
        user_confirmed: bool = True,
    ) -> dict:
        allowed = {
            "centerline": "centerline_json", "wall_type": "wall_type",
            "classification": "classification", "thickness_mm": "thickness_mm",
            "height_mm": "height_mm", "height_source": "height_source",
            "height_override_mm": "height_override_mm", "side_1_finish": "side_1_finish",
            "side_2_finish": "side_2_finish", "status": "status", "length_mm": "length_mm",
            "gross_area_m2": "gross_area_m2", "deduction_area_m2": "deduction_area_m2",
            "net_area_m2": "net_area_m2", "is_stale": "is_stale", "boundary_role": "boundary_role",
        }
        parts: list[str] = []
        values: list[Any] = []
        for key, value in updates.items():
            column = allowed.get(key)
            if not column:
                continue
            parts.append(f"{column} = ?")
            values.append(dumps(value) if key == "centerline" else value)
        parts.extend(["wall_version = ?", "user_confirmed = ?", "updated_at = ?"])
        values.extend([wall_version, 1 if user_confirmed else 0, now_iso(), project_id, floor_id, wall_id])
        with get_connection() as connection:
            connection.execute(
                f"UPDATE walls SET {', '.join(parts)} WHERE project_id = ? AND floor_id = ? AND id = ?",
                values,
            )
            row = connection.execute("SELECT * FROM walls WHERE id = ?", (wall_id,)).fetchone()
        return self._decode(row_to_dict(row) or {})

    def get_wall(self, project_id: str, floor_id: str, wall_id: str) -> dict | None:
        return next((wall for wall in self.list_walls(project_id, floor_id) if wall["id"] == wall_id), None)

    def delete_wall(self, project_id: str, floor_id: str, wall_id: str) -> None:
        """Soft-delete walls so automatic regeneration respects user intent."""
        with get_connection() as connection:
            connection.execute(
                """UPDATE walls
                   SET generated_status = 'rejected', status = 'rejected',
                       user_confirmed = 1, updated_at = ?
                   WHERE project_id = ? AND floor_id = ? AND id = ?""",
                (now_iso(), project_id, floor_id, wall_id),
            )

    def confirm_all(self, project_id: str, floor_id: str, wall_version: int) -> int:
        with get_connection() as connection:
            result = connection.execute(
                """UPDATE walls
                   SET status = 'confirmed', user_confirmed = 1, is_stale = 0,
                       wall_version = ?, updated_at = ?
                   WHERE project_id = ? AND floor_id = ?
                     AND COALESCE(generated_status, 'current') = 'current'""",
                (wall_version, now_iso(), project_id, floor_id),
            )
        return int(getattr(result, "rowcount", 0) or 0)

    def assign_opening(
        self,
        *,
        project_id: str,
        floor_id: str,
        wall_id: str,
        element: dict,
        width_mm: float | None,
        height_mm: float | None,
        opening_area_m2: float | None,
        deduction_area_m2: float,
        created_by: str | None,
    ) -> dict:
        now = now_iso()
        with get_connection() as connection:
            existing = connection.execute(
                "SELECT * FROM wall_openings WHERE project_id = ? AND floor_id = ? AND element_id = ?",
                (project_id, floor_id, element["id"]),
            ).fetchone()
            relation_id = existing["id"] if existing else str(uuid4())
            if existing:
                connection.execute(
                    """
                    UPDATE wall_openings
                    SET wall_id = ?, opening_type = ?, width_mm = ?, height_mm = ?,
                        opening_area_m2 = ?, deduction_area_m2 = ?, status = 'ready',
                        relation_version = relation_version + 1, updated_at = ?
                    WHERE id = ?
                    """,
                    (wall_id, element["element_type"], width_mm, height_mm, opening_area_m2, deduction_area_m2, now, relation_id),
                )
            else:
                connection.execute(
                    """
                    INSERT INTO wall_openings (
                      id, project_id, floor_id, wall_id, element_id, opening_type,
                      width_mm, height_mm, opening_area_m2, deduction_area_m2,
                      status, relation_version, created_by, created_at, updated_at
                    ) VALUES (?,?,?,?,?,?,?,?,?,?,'ready',1,?,?,?)
                    """,
                    (relation_id, project_id, floor_id, wall_id, element["id"], element["element_type"],
                     width_mm, height_mm, opening_area_m2, deduction_area_m2, created_by, now, now),
                )
            row = connection.execute("SELECT * FROM wall_openings WHERE id = ?", (relation_id,)).fetchone()
        return self._decode(row_to_dict(row) or {})

    def move_openings(self, project_id: str, floor_id: str, from_wall_id: str, to_wall_id: str) -> None:
        with get_connection() as connection:
            connection.execute(
                "UPDATE wall_openings SET wall_id = ?, relation_version = relation_version + 1, updated_at = ? WHERE project_id = ? AND floor_id = ? AND wall_id = ?",
                (to_wall_id, now_iso(), project_id, floor_id, from_wall_id),
            )

    def restore_generated(self, project_id: str, floor_id: str, wall_id: str, wall_version: int) -> dict:
        wall = self.get_wall(project_id, floor_id, wall_id)
        if not wall:
            return {}
        return self.update_wall(
            project_id, floor_id, wall_id,
            {"centerline": wall.get("generated_centerline") or {}, "is_stale": 1, "status": "needs_review"},
            wall_version,
        )

    @staticmethod
    def _decode(record: dict) -> dict:
        result = dict(record)
        for key in list(result):
            if key.endswith("_json"):
                result[key[:-5]] = loads(result.pop(key))
        for key in ("is_stale", "user_confirmed", "excluded"):
            if key in result:
                result[key] = bool(result[key])
        item_number = result.get("item_number")
        if item_number is not None:
            result["item_number"] = int(item_number)
            result["display_number"] = f"Item {int(item_number):03d}"
        element_item_number = result.get("element_item_number")
        if element_item_number is not None:
            result["element_item_number"] = int(element_item_number)
            result["element_display_number"] = f"Item {int(element_item_number):03d}"
        return result


walls_repository = WallsRepository()
