from __future__ import annotations

import re
from typing import Any
from uuid import uuid4

from app.database.session import get_connection, row_to_dict
from app.pdf_upload.repo import pdf_upload_repository
from app.model_review.prediction_processor import ProcessedPrediction
from app.model_review.reconciliation_service import choose_confirmed_match, match_score
from app.workflow.repo_base import dumps, loads, now_iso


class ModelReviewRepository:
    def floor_rows(self, project_id: str) -> list[dict]:
        with get_connection() as connection:
            rows = connection.execute(
                """
                SELECT f.*, fv.crop_version, fv.scale_version, fv.element_version,
                       fc.id AS crop_id, fc.coordinates_json, fc.crop_asset_key,
                       fc.status AS crop_status
                FROM floors f
                LEFT JOIN floor_versions fv ON fv.floor_id=f.id
                LEFT JOIN floor_crops fc ON fc.floor_id=f.id AND fc.project_id=f.project_id AND fc.is_current=1
                WHERE f.project_id=? ORDER BY f.level_index
                """,
                (project_id,),
            ).fetchall()
        return [self._decode(row_to_dict(row) or {}) for row in rows]

    def list_elements(self, project_id: str, floor_id: str) -> list[dict]:
        with get_connection() as connection:
            rows = connection.execute(
                """
                SELECT * FROM elements e
                WHERE e.project_id=? AND e.floor_id=?
                  AND (
                    COALESCE(e.is_manual,0)=1
                    OR (
                      COALESCE(e.generated_status,'current')='current'
                      AND (e.crop_version IS NULL OR e.crop_version=(
                        SELECT fc.crop_version FROM floor_crops fc
                        WHERE fc.project_id=e.project_id AND fc.floor_id=e.floor_id AND fc.is_current=1
                        ORDER BY fc.crop_version DESC LIMIT 1
                      ))
                    )
                  )
                ORDER BY e.item_number, e.created_at
                """,
                (project_id, floor_id),
            ).fetchall()
            items = [self._decode(row_to_dict(row) or {}) for row in rows]
            if not items:
                return []

            ids = [item["id"] for item in items]
            placeholders = ",".join("?" for _ in ids)
            props = connection.execute(
                f"SELECT * FROM element_properties WHERE element_id IN ({placeholders}) ORDER BY property_name",
                ids,
            ).fetchall()
            schedule_rows = connection.execute(
                """
                SELECT * FROM schedule_entries
                WHERE project_id=? AND category IN ('door','window','wall')
                ORDER BY is_accepted DESC, source_priority DESC, created_at
                """,
                (project_id,),
            ).fetchall()

        by_id: dict[str, list[dict]] = {item_id: [] for item_id in ids}
        for row in props:
            decoded = self._decode(row_to_dict(row) or {})
            by_id.setdefault(decoded["element_id"], []).append(decoded)

        schedules = [self._decode(row_to_dict(row) or {}) for row in schedule_rows]
        schedule_by_id = {item["id"]: item for item in schedules}
        schedule_by_code: dict[tuple[str, str], dict] = {}
        for entry in schedules:
            data = entry.get("data") or {}
            code = self._normalize_code(data.get("type_code") or entry.get("entity_key"))
            if code:
                schedule_by_code.setdefault((str(entry.get("category") or ""), code), entry)

        drawing_by_code: dict[tuple[str, str], dict] = {}
        for record in pdf_upload_repository.list_extraction_records(project_id):
            category = str(record.get("extraction_type") or "")
            if category not in {"door", "window", "wall"}:
                continue
            data = record.get("data") or {}
            code = self._normalize_code(data.get("type_code") or data.get("wall_type"))
            if not code:
                continue
            key = (category, code)
            current = drawing_by_code.get(key)
            if current is None or self._data_score(data) > self._data_score(current.get("data") or {}):
                drawing_by_code[key] = record

        for item in items:
            item_props = by_id.get(item["id"], [])
            item["properties"] = item_props
            canonical = {prop["property_name"]: prop.get("value") for prop in item_props}
            sources = {prop["property_name"]: prop.get("source") for prop in item_props}
            confirmed = {prop["property_name"]: bool(prop.get("is_confirmed")) for prop in item_props}

            code = self._normalize_code(item.get("type_code") or item.get("tag_text"))
            assigned = schedule_by_id.get(str(item.get("assigned_schedule_entry_id") or ""))
            schedule = assigned or schedule_by_code.get((str(item.get("element_type") or ""), code))
            drawing = drawing_by_code.get((str(item.get("element_type") or ""), code))
            schedule_data = (schedule or {}).get("data") or {}
            drawing_data = (drawing or {}).get("data") or {}

            resolved: dict[str, Any] = {
                "type_code": item.get("type_code") or item.get("tag_text"),
                "drawing_tag": item.get("tag_text"),
                "item_number": item.get("item_number"),
                "display_number": item.get("display_number"),
            }
            resolved_sources: dict[str, str] = {
                "type_code": "user_confirmed" if item.get("user_confirmed") and item.get("type_code") else ("drawing_note" if item.get("tag_text") else str(item.get("source") or "model")),
            }
            for field in (
                "width_mm", "height_mm", "material", "frame_material", "finish",
                "glass_type", "fire_rating", "quantity", "nominal_thickness_mm",
                "internal_external_hint", "cavity_information", "bond", "mortar",
            ):
                if canonical.get(field) not in (None, ""):
                    resolved[field] = canonical[field]
                    resolved_sources[field] = str(sources.get(field) or "saved")
                elif schedule_data.get(field) not in (None, ""):
                    resolved[field] = schedule_data[field]
                    resolved_sources[field] = "schedule"
                elif drawing_data.get(field) not in (None, ""):
                    resolved[field] = drawing_data[field]
                    resolved_sources[field] = "drawing_note"
                else:
                    resolved[field] = None

            required = ["type_code"]
            if item.get("element_type") in {"door", "window"}:
                required.extend(["width_mm", "height_mm"])
            missing = [field for field in required if resolved.get(field) in (None, "")]
            item["resolved_data"] = resolved
            item["resolved_sources"] = resolved_sources
            item["confirmed_fields"] = confirmed
            # These are BOQ/detail-enrichment fields, not reasons to distrust
            # a correctly classified detection box on Model Review.
            item["detail_missing_fields"] = missing
            item["missing_fields"] = missing
            item["schedule_match"] = {
                "id": schedule.get("id"),
                "category": schedule.get("category"),
                "entity_key": schedule.get("entity_key"),
                "source_kind": schedule.get("source_kind"),
                "review_state": schedule.get("review_state"),
            } if schedule else None
            item["drawing_detail"] = {
                "record_id": drawing.get("id"),
                "document_id": drawing.get("document_id"),
                "page_id": drawing.get("document_page_id"),
                "confidence": drawing.get("confidence"),
                "source_location": drawing.get("source_location") or {},
            } if drawing else None
        return items

    @staticmethod
    def _normalize_code(value: Any) -> str:
        return re.sub(r"[^A-Za-z0-9]", "", str(value or "")).upper()

    @staticmethod
    def _data_score(data: dict) -> int:
        return sum(value not in (None, "", [], {}) for key, value in data.items() if key != "source")

    def floor_element_counts(self, project_id: str) -> dict[str, dict[str, int]]:
        with get_connection() as connection:
            rows = connection.execute(
                """
                SELECT floor_id,
                       COUNT(*) AS total,
                       SUM(CASE WHEN excluded=0 THEN 1 ELSE 0 END) AS active,
                       SUM(CASE WHEN excluded=0 AND status='needs_review' THEN 1 ELSE 0 END) AS needs_review,
                       SUM(CASE WHEN excluded=0 AND status='confirmed' THEN 1 ELSE 0 END) AS confirmed
                FROM elements e
                WHERE project_id=?
                  AND (COALESCE(e.is_manual,0)=1 OR COALESCE(e.generated_status,'current')='current')
                  AND (e.crop_version IS NULL OR e.crop_version=(
                    SELECT fc.crop_version FROM floor_crops fc
                    WHERE fc.project_id=e.project_id AND fc.floor_id=e.floor_id AND fc.is_current=1
                    ORDER BY fc.crop_version DESC LIMIT 1
                  ))
                GROUP BY floor_id
                """,
                (project_id,),
            ).fetchall()
        return {
            row["floor_id"]: {
                "total": int(row["total"] or 0),
                "active": int(row["active"] or 0),
                "needs_review": int(row["needs_review"] or 0),
                "confirmed": int(row["confirmed"] or 0),
            }
            for row in rows
        }

    def get_element(self, project_id: str, floor_id: str, element_id: str) -> dict | None:
        return next((item for item in self.list_elements(project_id, floor_id) if item["id"] == element_id), None)

    def create_element(
        self, *, project_id: str, floor_id: str, element_type: str, geometry: dict,
        type_code: str | None, source: str, confidence: float | None, detection_version: int,
        is_manual: bool, provider_name: str | None, created_by: str | None,
        crop_id: str | None = None, crop_version: int | None = None, detection_run_id: str | None = None,
        model_id: str | None = None, input_hash: str | None = None, analysis_mode: str = "standard",
        generated_status: str = "current",
    ) -> dict:
        now = now_iso()
        element_id = str(uuid4())
        with get_connection() as connection:
            type_count = connection.execute(
                "SELECT COUNT(*) AS total FROM elements WHERE project_id=? AND element_type=?",
                (project_id, element_type),
            ).fetchone()["total"]
            max_item = connection.execute(
                "SELECT MAX(item_number) AS maximum FROM elements WHERE project_id=?",
                (project_id,),
            ).fetchone()["maximum"]
            item_number = int(max_item or 0) + 1
            prefix = {"door": "DR", "window": "WN", "wall": "WL"}.get(element_type, "EL")
            friendly = f"{prefix}-{int(type_count or 0)+1:03d}"
            connection.execute(
                """
                INSERT INTO elements (
                  id,project_id,floor_id,element_type,type_code,geometry_json,source,confidence,status,
                  excluded,user_confirmed,measurement_status,element_version,source_versions_json,
                  created_by,created_at,updated_at,friendly_number,detection_version,is_manual,provider_name,item_number,
                  crop_id,crop_version,detection_run_id,generated_status,detection_model_id,detection_input_hash,analysis_mode
                ) VALUES (?,?,?,?,?,?,?,?,?,0,0,'not_ready',?,?, ?,?,?,?, ?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    element_id,project_id,floor_id,element_type,type_code,dumps(geometry),source,confidence,
                    "needs_review",detection_version,dumps({"detection_version":detection_version,"crop_version":crop_version}),
                    created_by,now,now,friendly,detection_version,1 if is_manual else 0,provider_name,item_number,
                    crop_id,crop_version,detection_run_id,generated_status,model_id,input_hash,analysis_mode,
                ),
            )
            row = connection.execute("SELECT * FROM elements WHERE id=?", (element_id,)).fetchone()
        return self._decode(row_to_dict(row) or {})

    def confirm_elements(
        self, project_id: str, floor_id: str, element_ids: list[str], *, element_version: int
    ) -> list[dict]:
        unique_ids = list(dict.fromkeys(str(item) for item in element_ids if item))
        if not unique_ids:
            return []
        placeholders = ",".join("?" for _ in unique_ids)
        with get_connection() as connection:
            connection.execute(
                f"""
                UPDATE elements SET status='confirmed', user_confirmed=1,
                    element_version=?, updated_at=? WHERE project_id=? AND floor_id=?
                    AND id IN ({placeholders})
                """,
                (element_version, now_iso(), project_id, floor_id, *unique_ids),
            )
        refreshed = {item["id"]: item for item in self.list_elements(project_id, floor_id)}
        return [refreshed[item_id] for item_id in unique_ids if item_id in refreshed]

    def update_element(self, project_id: str, floor_id: str, element_id: str, updates: dict[str, Any], *, element_version: int, user_confirmed: bool | None = None) -> dict:
        allowed = {
            "geometry_json": "geometry_json",
            "type_code": "type_code",
            "status": "status",
            "excluded": "excluded",
            "tag_text": "tag_text",
            "assigned_schedule_entry_id": "assigned_schedule_entry_id",
        }
        parts: list[str] = []
        values: list[Any] = []
        for key, value in updates.items():
            if key not in allowed:
                continue
            parts.append(f"{allowed[key]}=?")
            values.append(dumps(value) if key == "geometry_json" else value)
        parts.extend(["element_version=?", "updated_at=?"])
        values.extend([element_version, now_iso()])
        if user_confirmed is not None:
            parts.append("user_confirmed=?")
            values.append(1 if user_confirmed else 0)
        values.extend([project_id, floor_id, element_id])
        with get_connection() as connection:
            connection.execute(
                f"UPDATE elements SET {','.join(parts)} WHERE project_id=? AND floor_id=? AND id=?",
                values,
            )
            row = connection.execute("SELECT * FROM elements WHERE id=?", (element_id,)).fetchone()
        return self._decode(row_to_dict(row) or {})

    def bulk_assign_schedule_entries(
        self, project_id: str, floor_id: str, assignments: dict[str, str], *, element_version: int
    ) -> int:
        if not assignments:
            return 0
        now = now_iso()
        updated = 0
        with get_connection() as connection:
            for element_id, schedule_entry_id in assignments.items():
                result = connection.execute(
                    """UPDATE elements SET assigned_schedule_entry_id=?, element_version=?, updated_at=?
                       WHERE project_id=? AND floor_id=? AND id=?
                         AND COALESCE(assigned_schedule_entry_id,'')<>?""",
                    (schedule_entry_id, element_version, now, project_id, floor_id, element_id, schedule_entry_id),
                )
                updated += int(result.rowcount or 0)
        return updated

    def detection_run(self, project_id: str, floor_id: str, crop_version: int) -> dict | None:
        return self.get_detection_run(
            project_id=project_id, floor_id=floor_id, crop_version=crop_version,
            model_id="cubicasa5k-2-qpmsa/6", analysis_mode="standard",
        )

    def get_detection_run(
        self, *, project_id: str, floor_id: str, crop_version: int, model_id: str, analysis_mode: str
    ) -> dict | None:
        with get_connection() as connection:
            row = connection.execute(
                """SELECT * FROM floor_element_detection_runs
                   WHERE project_id=? AND floor_id=? AND crop_version=? AND model_id=? AND analysis_mode=?""",
                (project_id, floor_id, crop_version, model_id, analysis_mode),
            ).fetchone()
        return self._decode(row_to_dict(row) or {}) if row else None

    def begin_detection_run(
        self, *, project_id: str, floor_id: str, crop_id: str, crop_version: int,
        provider_name: str, model_id: str, input_hash: str, analysis_mode: str
    ) -> dict:
        now = now_iso()
        with get_connection() as connection:
            existing = connection.execute(
                """SELECT id FROM floor_element_detection_runs
                   WHERE project_id=? AND floor_id=? AND crop_version=? AND model_id=? AND analysis_mode=?""",
                (project_id, floor_id, crop_version, model_id, analysis_mode),
            ).fetchone()
            if existing:
                run_id = str(existing["id"])
                connection.execute(
                    """UPDATE floor_element_detection_runs SET crop_id=?,provider_name=?,input_hash=?,
                       status='processing',error_message=NULL,updated_at=? WHERE id=?""",
                    (crop_id, provider_name, input_hash, now, run_id),
                )
            else:
                run_id = str(uuid4())
                connection.execute(
                    """INSERT INTO floor_element_detection_runs (
                       id,project_id,floor_id,crop_id,crop_version,provider_name,model_id,input_hash,analysis_mode,
                       raw_json,prediction_count,door_count,window_count,wall_count,status,created_at,updated_at
                    ) VALUES (?,?,?,?,?,?,?,?,?,'{}',0,0,0,0,'processing',?,?)""",
                    (run_id,project_id,floor_id,crop_id,crop_version,provider_name,model_id,input_hash,analysis_mode,now,now),
                )
            row = connection.execute("SELECT * FROM floor_element_detection_runs WHERE id=?", (run_id,)).fetchone()
        return self._decode(row_to_dict(row) or {})

    def finish_detection_run_with_error(self, run_id: str, error_message: str, *, status: str = "failed") -> None:
        with get_connection() as connection:
            connection.execute(
                "UPDATE floor_element_detection_runs SET status=?,error_message=?,updated_at=? WHERE id=?",
                (status, error_message[:2000], now_iso(), run_id),
            )

    def reconcile_detection_results(
        self, *, project_id: str, floor_id: str, crop_id: str, crop_version: int, run_id: str,
        model_id: str, input_hash: str, analysis_mode: str, provider_name: str, raw: dict,
        groups: dict[str, list[ProcessedPrediction]], created_by: str | None,
    ) -> dict[str, int]:
        now = now_iso()
        with get_connection() as connection:
            active_crop = connection.execute(
                "SELECT id,crop_version FROM floor_crops WHERE project_id=? AND floor_id=? AND is_current=1",
                (project_id,floor_id),
            ).fetchone()
            if not active_crop or str(active_crop["id"]) != crop_id or int(active_crop["crop_version"] or 0) != crop_version:
                raise RuntimeError("A newer floor crop is already active.")

            versions = connection.execute(
                "SELECT * FROM floor_versions WHERE project_id=? AND floor_id=?", (project_id,floor_id)
            ).fetchone()
            element_version = int(versions["element_version"] or 0) + 1 if versions else 1
            connection.execute(
                "UPDATE floor_versions SET element_version=?,updated_at=? WHERE project_id=? AND floor_id=?",
                (element_version,now,project_id,floor_id),
            )

            rows = connection.execute(
                """SELECT * FROM elements WHERE project_id=? AND floor_id=? AND COALESCE(is_manual,0)=0
                   ORDER BY user_confirmed DESC, updated_at DESC""",
                (project_id,floor_id),
            ).fetchall()
            existing = [self._decode(row_to_dict(row) or {}) for row in rows]
            connection.execute(
                """UPDATE elements SET generated_status='superseded', excluded=1, updated_at=?
                   WHERE project_id=? AND floor_id=? AND COALESCE(is_manual,0)=0""",
                (now,project_id,floor_id),
            )
            used_ids: set[str] = set()
            max_item_row = connection.execute(
                "SELECT COALESCE(MAX(item_number),0) AS maximum FROM elements WHERE project_id=?", (project_id,)
            ).fetchone()
            next_item = int(max_item_row["maximum"] or 0) + 1
            type_counts = {
                key: int(connection.execute(
                    "SELECT COUNT(*) AS total FROM elements WHERE project_id=? AND element_type=?", (project_id,key)
                ).fetchone()["total"] or 0)
                for key in ("door","window","wall")
            }
            counts = {"door":0,"window":0,"wall":0}
            for element_type, predictions in groups.items():
                for prediction in predictions:
                    matched = choose_confirmed_match(
                        existing, element_type=element_type, geometry=prediction.geometry, used_ids=used_ids
                    )
                    if matched is None:
                        possible = [
                            item for item in existing
                            if item.get("element_type")==element_type and str(item.get("id")) not in used_ids
                            and match_score(item,prediction.geometry)>=0.68
                        ]
                        matched = max(possible,key=lambda item:match_score(item,prediction.geometry),default=None)
                    if matched is not None:
                        element_id = str(matched["id"]); used_ids.add(element_id)
                        connection.execute(
                            """UPDATE elements SET geometry_json=?,source='model',confidence=?,
                               status=CASE WHEN COALESCE(user_confirmed,0)=1 THEN 'confirmed' ELSE ? END,excluded=0,
                               crop_id=?,crop_version=?,detection_run_id=?,generated_status='current',
                               detection_model_id=?,detection_input_hash=?,analysis_mode=?,provider_name=?,
                               detection_version=?,element_version=?,measurement_status='not_ready',updated_at=?
                               WHERE id=?""",
                            (dumps(prediction.geometry),prediction.confidence,prediction.status,crop_id,crop_version,run_id,model_id,input_hash,
                             analysis_mode,provider_name,element_version,element_version,now,element_id),
                        )
                    else:
                        element_id = str(uuid4())
                        type_counts[element_type]+=1
                        prefix={"door":"DR","window":"WN","wall":"WL"}[element_type]
                        connection.execute(
                            """INSERT INTO elements (
                              id,project_id,floor_id,element_type,type_code,geometry_json,source,confidence,status,excluded,
                              user_confirmed,measurement_status,element_version,source_versions_json,created_by,created_at,updated_at,
                              friendly_number,detection_version,is_manual,provider_name,item_number,crop_id,crop_version,detection_run_id,
                              generated_status,detection_model_id,detection_input_hash,analysis_mode
                            ) VALUES (?,?,?,?,NULL,?,'model',?,?,0,0,'not_ready',?,?,?,?,?,?,?,0,?,?,?,?,?,'current',?,?,?)""",
                            (element_id,project_id,floor_id,element_type,dumps(prediction.geometry),prediction.confidence,prediction.status,
                             element_version,dumps({"crop_version":crop_version,"detection_run_id":run_id}),created_by,now,now,
                             f"{prefix}-{type_counts[element_type]:03d}",element_version,provider_name,next_item,crop_id,crop_version,run_id,
                             model_id,input_hash,analysis_mode),
                        )
                        next_item += 1
                    counts[element_type]+=1

            prediction_count = sum(counts.values())
            connection.execute(
                """UPDATE floor_element_detection_runs SET raw_json=?,prediction_count=?,door_count=?,window_count=?,
                   wall_count=?,status='ready',error_message=NULL,updated_at=? WHERE id=?""",
                (dumps(raw),prediction_count,counts['door'],counts['window'],counts['wall'],now,run_id),
            )
        return {**counts,"element_version":element_version}

    def reconcile_wall_recovery(
        self, *, project_id: str, floor_id: str, crop_id: str, crop_version: int,
        run_id: str, model_id: str, input_hash: str, provider_name: str, raw: dict,
        predictions: list[ProcessedPrediction] | None = None,
        groups: dict[str, list[ProcessedPrediction]] | None = None,
        created_by: str | None,
    ) -> dict[str, int]:
        """Replace prior precision additions without touching fast-pass results."""
        resolved_groups = groups or {
            "door": [],
            "window": [],
            "wall": list(predictions or []),
        }
        now = now_iso()
        with get_connection() as connection:
            active_crop = connection.execute(
                "SELECT id,crop_version FROM floor_crops WHERE project_id=? AND floor_id=? AND is_current=1",
                (project_id, floor_id),
            ).fetchone()
            if (
                not active_crop
                or str(active_crop["id"]) != crop_id
                or int(active_crop["crop_version"] or 0) != crop_version
            ):
                raise RuntimeError("A newer floor crop is already active.")
            versions = connection.execute(
                "SELECT * FROM floor_versions WHERE project_id=? AND floor_id=?",
                (project_id, floor_id),
            ).fetchone()
            element_version = int(versions["element_version"] or 0) + 1 if versions else 1
            connection.execute(
                "UPDATE floor_versions SET element_version=?,updated_at=? WHERE project_id=? AND floor_id=?",
                (element_version, now, project_id, floor_id),
            )
            # Retire only elements that were originally inserted by a recovery
            # run. Older code could label a matched standard wall as recovery;
            # source_versions_json lets us preserve those standard identities.
            recovery_run_ids = {
                str(row["id"])
                for row in connection.execute(
                    """SELECT id FROM floor_element_detection_runs
                       WHERE project_id=? AND floor_id=? AND analysis_mode='wall_recovery'""",
                    (project_id, floor_id),
                ).fetchall()
            }
            recovery_rows = connection.execute(
                """SELECT id,source_versions_json FROM elements
                   WHERE project_id=? AND floor_id=?
                     AND source IN ('model_recovery','vector_recovery')
                     AND COALESCE(is_manual,0)=0 AND COALESCE(user_confirmed,0)=0
                     AND COALESCE(generated_status,'current')='current'""",
                (project_id, floor_id),
            ).fetchall()
            retired_ids: list[str] = []
            for row in recovery_rows:
                source_versions = loads(row["source_versions_json"]) or {}
                if str(source_versions.get("detection_run_id") or "") in recovery_run_ids:
                    retired_ids.append(str(row["id"]))
            if retired_ids:
                placeholders = ",".join("?" for _ in retired_ids)
                connection.execute(
                    f"""UPDATE elements SET generated_status='superseded',excluded=1,
                        element_version=?,updated_at=? WHERE id IN ({placeholders})""",
                    (element_version, now, *retired_ids),
                )
            rows = connection.execute(
                """SELECT * FROM elements WHERE project_id=? AND floor_id=?
                   AND element_type IN ('door','window','wall') AND excluded=0
                   AND (COALESCE(is_manual,0)=1 OR COALESCE(generated_status,'current')='current')""",
                (project_id, floor_id),
            ).fetchall()
            existing = [self._decode(row_to_dict(row) or {}) for row in rows]
            max_item = int(connection.execute(
                "SELECT COALESCE(MAX(item_number),0) AS maximum FROM elements WHERE project_id=?",
                (project_id,),
            ).fetchone()["maximum"] or 0)
            type_counts = {
                element_type: int(
                    connection.execute(
                        """SELECT COUNT(*) AS total FROM elements
                           WHERE project_id=? AND element_type=?""",
                        (project_id, element_type),
                    ).fetchone()["total"]
                    or 0
                )
                for element_type in ("door", "window", "wall")
            }
            counts = {"door": 0, "window": 0, "wall": 0}
            added = refreshed = protected = 0
            used_ids: set[str] = set()
            for element_type in ("door", "window", "wall"):
                for prediction in resolved_groups.get(element_type) or []:
                    possible = [
                        item
                        for item in existing
                        if item.get("element_type") == element_type
                        and str(item.get("id")) not in used_ids
                        and match_score(item, prediction.geometry) >= 0.68
                    ]
                    matched = max(
                        possible,
                        key=lambda item: match_score(item, prediction.geometry),
                        default=None,
                    )
                    recovery_source = str(
                        prediction.raw.get("recovery_source") or "original_tile"
                    )
                    if matched is not None:
                        used_ids.add(str(matched["id"]))
                        # Precision evidence must never relabel or reshape an
                        # existing standard/manual detection.
                        protected += 1
                        counts[element_type] += 1
                        continue
                    element_id = str(uuid4())
                    type_counts[element_type] += 1
                    max_item += 1
                    prefix = {"door": "DR", "window": "WN", "wall": "WL"}[
                        element_type
                    ]
                    connection.execute(
                        """INSERT INTO elements (
                          id,project_id,floor_id,element_type,type_code,geometry_json,source,confidence,status,
                          excluded,user_confirmed,measurement_status,element_version,source_versions_json,
                          created_by,created_at,updated_at,friendly_number,detection_version,is_manual,
                          provider_name,item_number,crop_id,crop_version,detection_run_id,generated_status,
                          detection_model_id,detection_input_hash,analysis_mode
                        ) VALUES (?,?,?,?,NULL,?,?,?,?,0,0,'not_ready',?,?,?,?,?,?,?,0,?,?,?,?,?,
                                  'current',?,?,'wall_recovery')""",
                        (
                            element_id,
                            project_id,
                            floor_id,
                            element_type,
                            dumps(prediction.geometry),
                            "vector_recovery"
                            if recovery_source == "pdf_vector"
                            else "model_recovery",
                            prediction.confidence,
                            prediction.status,
                            element_version,
                            dumps(
                                {
                                    "crop_version": crop_version,
                                    "detection_run_id": run_id,
                                }
                            ),
                            created_by,
                            now,
                            now,
                            f"{prefix}-{type_counts[element_type]:03d}",
                            element_version,
                            provider_name,
                            max_item,
                            crop_id,
                            crop_version,
                            run_id,
                            model_id,
                            input_hash,
                        ),
                    )
                    existing.append(
                        {
                            "id": element_id,
                            "element_type": element_type,
                            "geometry": prediction.geometry,
                            "confidence": prediction.confidence,
                            "user_confirmed": False,
                            "is_manual": False,
                        }
                    )
                    used_ids.add(element_id)
                    counts[element_type] += 1
                    added += 1
            connection.execute(
                """UPDATE floor_element_detection_runs SET raw_json=?,prediction_count=?,wall_count=?,
                   door_count=?,window_count=?,status='ready',error_message=NULL,updated_at=? WHERE id=?""",
                (
                    dumps(raw),
                    sum(counts.values()),
                    counts["wall"],
                    counts["door"],
                    counts["window"],
                    now,
                    run_id,
                ),
            )
        return {
            **counts,
            "added": added,
            "refreshed": refreshed,
            "protected": protected,
            "element_version": element_version,
        }

    def save_detection_run(self, *, project_id: str, floor_id: str, crop_id: str, crop_version: int, provider_name: str, raw: dict) -> dict:
        run = self.begin_detection_run(project_id=project_id,floor_id=floor_id,crop_id=crop_id,
            crop_version=crop_version,provider_name=provider_name,model_id="cubicasa5k-2-qpmsa/6",
            input_hash=f"legacy-{crop_version}",analysis_mode="standard")
        return run

    def list_schedule_entries(self, project_id: str) -> list[dict]:
        with get_connection() as connection:
            rows = connection.execute(
                "SELECT * FROM schedule_entries WHERE project_id=? AND category IN ('door','window','wall') ORDER BY category,entity_key",
                (project_id,),
            ).fetchall()
        return [self._decode(row_to_dict(row) or {}) for row in rows]

    @staticmethod
    def _decode(record: dict) -> dict:
        result = dict(record)
        for key in list(result):
            if key.endswith("_json"):
                result[key[:-5]] = loads(result.pop(key))
        for key in ("excluded","user_confirmed","is_manual"):
            if key in result:
                result[key] = bool(result[key])
        item_number = result.get("item_number")
        if item_number is not None:
            result["item_number"] = int(item_number)
            result["display_number"] = f"Item {int(item_number):03d}"
        else:
            result["display_number"] = None
        friendly = str(result.get("friendly_number") or "").strip()
        element_type = str(result.get("element_type") or "")
        legacy = re.fullmatch(r"[A-Z](\d+)", friendly)
        if legacy and element_type in {"door", "window", "wall"}:
            prefix = {"door": "DR", "window": "WN", "wall": "WL"}[element_type]
            result["friendly_number"] = f"{prefix}-{int(legacy.group(1)):03d}"
        return result


model_review_repository = ModelReviewRepository()
