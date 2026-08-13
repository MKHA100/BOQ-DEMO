from __future__ import annotations

from typing import Any

from app.core.errors import bad_request, not_found
from app.database.session import get_connection
from app.jobs.job_service import job_service
from app.floors.service import floors_service
from app.model_review.service import model_review_service
from app.model_review.repo import model_review_repository
from app.model_review.tag_service import model_review_tag_service
from app.review.repo import review_repository
from app.walls.service import walls_service
from app.workflow.repo import workflow_repository
from app.workflow.repo_base import loads, now_iso
from app.pdf_upload.repo import pdf_upload_repository


class ReviewService:
    def _reconcile_walls(self, project_id: str, floor_id: str) -> None:
        """Fill missing wall measures from drawing evidence, scale and project defaults."""
        records = [
            row for row in pdf_upload_repository.list_extraction_records(project_id)
            if row.get("extraction_type") == "wall"
        ]
        evidence = max(records, key=lambda row: sum(value not in (None, "", [], {}) for value in (row.get("data") or {}).values()), default=None)
        wall_data = (evidence or {}).get("data") or {}
        with get_connection() as connection:
            floor = connection.execute(
                """
                SELECT f.wall_height_mm,p.default_wall_height_mm,c.mm_per_pixel
                FROM floors f JOIN projects p ON p.id=f.project_id
                LEFT JOIN calibrations c ON c.id=(
                  SELECT id FROM calibrations WHERE project_id=f.project_id AND floor_id=f.id
                  ORDER BY scale_version DESC,updated_at DESC LIMIT 1
                )
                WHERE f.project_id=? AND f.id=?
                """,
                (project_id, floor_id),
            ).fetchone()
            if not floor:
                return
            mm_per_pixel = float(floor["mm_per_pixel"] or 0)
            default_height = float(floor["wall_height_mm"] or floor["default_wall_height_mm"] or 2700)
            walls = connection.execute("""SELECT * FROM walls w WHERE project_id=? AND floor_id=?
                AND COALESCE(w.generated_status,'current')='current'
                AND (w.source_crop_version IS NULL OR w.source_crop_version=(SELECT crop_version FROM floor_versions fv
                     WHERE fv.project_id=w.project_id AND fv.floor_id=w.floor_id))""", (project_id, floor_id)).fetchall()
            for wall in walls:
                geometry = loads(wall["geometry_json"]) or {}
                length_mm = wall["length_mm"]
                if not length_mm and mm_per_pixel > 0:
                    points = geometry.get("points") or geometry.get("centerline") or []
                    if isinstance(points, list) and len(points) >= 2:
                        import math
                        length_mm = sum(math.dist((float(a.get("x",0)),float(a.get("y",0))), (float(b.get("x",0)),float(b.get("y",0)))) for a,b in zip(points,points[1:])) * mm_per_pixel
                    else:
                        length_mm = max(abs(float(geometry.get("width") or 0)), abs(float(geometry.get("height") or 0))) * mm_per_pixel
                thickness = wall["thickness_mm"] or wall_data.get("nominal_thickness_mm")
                height = wall["height_mm"] or default_height
                classification = wall["classification"] or wall_data.get("internal_external_hint")
                if classification in (None, "", "unknown"):
                    classification = "internal"
                wall_type = wall["wall_type"] or wall_data.get("wall_type") or wall_data.get("material")
                gross = float(length_mm or 0) * float(height or 0) / 1_000_000 if length_mm and height else wall["gross_area_m2"]
                deduction = float(wall["deduction_area_m2"] or 0)
                net = max(0.0, float(gross or 0) - deduction) if gross is not None else wall["net_area_m2"]
                complete = bool(length_mm and height and thickness and classification)
                connection.execute(
                    """
                    UPDATE walls SET length_mm=?,height_mm=?,thickness_mm=?,classification=?,wall_type=?,
                      gross_area_m2=?,net_area_m2=?,status=?,updated_at=? WHERE id=?
                    """,
                    (length_mm,height,thickness,classification,wall_type,gross,net,"confirmed" if complete else "needs_review",now_iso(),wall["id"]),
                )

    def refresh(self, project_id: str, floor_id: str | None = None) -> dict:
        with get_connection() as connection:
            project_versions = workflow_repository.increment_project_version(connection, project_id, "review_version")
            floors = connection.execute(
                "SELECT id,name,level_index FROM floors WHERE project_id=? ORDER BY level_index",
                (project_id,),
            ).fetchall()
        valid: set[tuple[str, str]] = set()
        updated = 0
        for floor in floors:
            if floor_id and floor["id"] != floor_id:
                continue
            # Review is a read model only. Expensive drawing/tag and wall
            # reconciliation runs in its own background jobs before this step.
            # Keeping refresh read-only makes navigation and SQLite writes fast.
            with get_connection() as connection:
                versions = workflow_repository.increment_floor_version(connection, project_id, floor["id"], "review_version")
                opening_rows = connection.execute(
                    "SELECT * FROM wall_openings WHERE project_id=? AND floor_id=?",
                    (project_id, floor["id"]),
                ).fetchall()
                walls = connection.execute(
                    """SELECT * FROM walls w WHERE project_id=? AND floor_id=?
                AND COALESCE(w.generated_status,'current')='current'
                AND (w.source_crop_version IS NULL OR w.source_crop_version=(SELECT crop_version FROM floor_versions fv
                     WHERE fv.project_id=w.project_id AND fv.floor_id=w.floor_id))""",
                    (project_id, floor["id"]),
                ).fetchall()
                rooms = connection.execute(
                    """SELECT * FROM rooms r WHERE project_id=? AND floor_id=? AND excluded=0
                AND COALESCE(r.generated_status,'current')='current'
                AND (COALESCE(r.user_confirmed,0)=1 OR
                     COALESCE(r.boundary_source,r.detection_source,'unknown') NOT IN ('model_only','roboflow','unknown'))
                AND (r.source_crop_version IS NULL OR r.source_crop_version=(SELECT crop_version FROM floor_versions fv
                     WHERE fv.project_id=r.project_id AND fv.floor_id=r.floor_id))""",
                    (project_id, floor["id"]),
                ).fetchall()
            opening_map = {row["element_id"]: row["wall_id"] for row in opening_rows}

            for element in model_review_repository.list_elements(project_id, floor["id"]):
                if element.get("excluded") or element.get("element_type") not in {"door", "window"}:
                    continue
                values = element.get("resolved_data") or {}
                sources = element.get("resolved_sources") or {}
                missing_fields = list(element.get("missing_fields") or [])
                assigned_wall_id = opening_map.get(element["id"])
                # An opening can be reviewed before wall assignment, but it is highlighted as incomplete.
                warnings: list[str] = []
                if not assigned_wall_id:
                    warnings.append("Wall assignment is not ready")
                if element.get("schedule_match") and element["schedule_match"].get("review_state") == "needs_review":
                    warnings.append("Schedule values need review")
                critical = bool(missing_fields)
                display_number = element.get("display_number") or element.get("friendly_number")
                type_code = values.get("type_code") or element.get("type_code") or element.get("tag_text")
                status = (
                    "confirmed"
                    if not critical and element.get("status") == "confirmed"
                    else "needs_review"
                    if critical
                    else "confirmed"
                )
                data = {
                    "floor": floor["name"],
                    "item_number": element.get("item_number"),
                    "display_number": display_number,
                    "element_type": element.get("element_type"),
                    "type_code": type_code,
                    "drawing_tag": element.get("tag_text"),
                    "width_mm": values.get("width_mm"),
                    "height_mm": values.get("height_mm"),
                    "material": values.get("material"),
                    "frame_material": values.get("frame_material"),
                    "finish": values.get("finish"),
                    "glass_type": values.get("glass_type"),
                    "fire_rating": values.get("fire_rating"),
                    "quantity": values.get("quantity"),
                    "assigned_wall_id": assigned_wall_id,
                    "source": element.get("source"),
                    "value_sources": sources,
                    "missing_fields": missing_fields,
                    "warnings": warnings,
                    "schedule_match": element.get("schedule_match"),
                    "drawing_detail": element.get("drawing_detail"),
                    "confidence": element.get("confidence"),
                }
                title = f"{display_number} · {type_code}" if display_number and type_code else (display_number or type_code or str(element.get("element_type") or "Element").title())
                review_repository.upsert(
                    project_id=project_id, floor_id=floor["id"], entity_type=element["element_type"],
                    entity_id=element["id"], display_number=display_number, title=title, data=data,
                    status=status, critical=critical, source_version=int(element.get("element_version") or 0),
                    review_version=int(versions["review_version"]),
                )
                valid.add((element["element_type"], element["id"]))
                updated += 1

            for wall in walls:
                critical = not wall["length_mm"] or not wall["height_mm"] or not wall["classification"] or not wall["thickness_mm"]
                display_number = f"Item {int(wall['item_number']):03d}" if wall["item_number"] is not None else wall["friendly_number"]
                missing_fields = [name for name, value in {
                    "length_mm": wall["length_mm"], "height_mm": wall["height_mm"],
                    "classification": wall["classification"], "thickness_mm": wall["thickness_mm"],
                }.items() if value in (None, "")]
                data = {
                    "floor": floor["name"], "item_number": wall["item_number"],
                    "classification": wall["classification"], "wall_type": wall["wall_type"],
                    "thickness_mm": wall["thickness_mm"], "height_mm": wall["height_mm"],
                    "length_mm": wall["length_mm"], "gross_area_m2": wall["gross_area_m2"],
                    "deduction_area_m2": wall["deduction_area_m2"], "net_area_m2": wall["net_area_m2"],
                    "side_1_finish": wall["side_1_finish"], "side_2_finish": wall["side_2_finish"],
                    "missing_fields": missing_fields, "warnings": [],
                }
                status = "needs_review" if critical else "confirmed"
                review_repository.upsert(
                    project_id=project_id, floor_id=floor["id"], entity_type="wall", entity_id=wall["id"],
                    display_number=display_number, title=display_number or "Wall", data=data, status=status,
                    critical=critical, source_version=int(wall["wall_version"] or 0), review_version=int(versions["review_version"]),
                )
                valid.add(("wall", wall["id"]))
                updated += 1

            for room in rooms:
                measurement_status = room["measurement_status"] if "measurement_status" in room.keys() else "check"
                critical = measurement_status in {"missing_scale", "invalid"} or not room["area_m2"]
                missing_fields = [
                    name
                    for name, value in {
                        "area_m2": room["area_m2"],
                        "room_name": room["name"],
                    }.items()
                    if value in (None, "")
                ]
                include_in_boq = bool(room["include_in_boq"]) if "include_in_boq" in room.keys() else True
                warnings = [] if (room["floor_finish"] or not include_in_boq) else ["Floor finish is not assigned"]
                if measurement_status == "missing_scale": warnings.append("Drawing scale is missing")
                elif measurement_status == "check": warnings.append("Boundary or printed dimensions need checking")
                if room["comparison_status"] in {"different", "regenerated_differs", "regeneration_missing", "model_only_accepted"}:
                    warnings.append("Room boundary needs review")
                interpretation_warnings = (
                    loads(room["interpretation_warnings_json"])
                    if "interpretation_warnings_json" in room.keys()
                    else []
                )
                if not isinstance(interpretation_warnings, list):
                    interpretation_warnings = []
                warnings.extend(str(value) for value in interpretation_warnings if str(value))
                data = {
                    "floor": floor["name"],
                    "room_name": room["name"],
                    "room_type": room["room_type"],
                    "floor_type_code": room["floor_type_code"],
                    "floor_finish": room["floor_finish"],
                    "area_m2": room["area_m2"],
                    "perimeter_m": room["perimeter_m"],
                    "source": room["detection_source"],
                    "model_verified": bool(room["model_verified"]),
                    "comparison_status": room["comparison_status"],
                    "confidence": room["confidence"],
                    "space_kind": room["space_kind"] if "space_kind" in room.keys() else "internal",
                    "measurement_status": measurement_status,
                    "measured_width_m": room["measured_width_m"] if "measured_width_m" in room.keys() else None,
                    "measured_length_m": room["measured_length_m"] if "measured_length_m" in room.keys() else None,
                    "dimension_difference_percent": room["dimension_difference_percent"] if "dimension_difference_percent" in room.keys() else None,
                    "dimension_status": room["dimension_status"] if "dimension_status" in room.keys() else "unknown",
                    "dimension_source": room["dimension_source"] if "dimension_source" in room.keys() else "unknown",
                    "interpretation_status": room["interpretation_status"] if "interpretation_status" in room.keys() else "not_started",
                    "interpretation_warnings": interpretation_warnings,
                    "boundary_source": room["boundary_source"] if "boundary_source" in room.keys() else room["detection_source"],
                    "is_finish_zone": bool(room["is_finish_zone"]) if "is_finish_zone" in room.keys() else False,
                    "parent_room_id": room["parent_room_id"] if "parent_room_id" in room.keys() else None,
                    "include_in_boq": include_in_boq,
                    "missing_fields": missing_fields,
                    "warnings": warnings,
                }
                status = "confirmed" if room["user_confirmed"] and not critical and not warnings else ("needs_review" if critical or warnings else "ready")
                review_repository.upsert(
                    project_id=project_id, floor_id=floor["id"], entity_type="floor", entity_id=room["id"],
                    display_number=room["friendly_number"], title=room["name"] or room["friendly_number"] or "Room",
                    data=data, status=status, critical=critical, source_version=int(room["room_version"] or 0),
                    review_version=int(versions["review_version"]),
                )
                valid.add(("floor", room["id"]))
                updated += 1
        if not floor_id:
            review_repository.delete_missing(project_id, valid)
        return {"updated": updated, "review_version": int(project_versions["review_version"])}

    def state(self, project: dict, floor_id: str | None = None, category: str = "all", needs_review: bool = False) -> dict:
        with get_connection() as connection:
            summary = connection.execute(
                """
                SELECT COUNT(*) AS total,
                       SUM(CASE WHEN is_stale=1 OR display_number IS NULL OR display_number NOT LIKE 'Item %' THEN 1 ELSE 0 END) AS refresh_needed
                FROM review_items WHERE project_id=?
                """,
                (project["id"],),
            ).fetchone()
        refresh_needed = int((summary["refresh_needed"] if summary else 0) or 0)
        items = review_repository.list(
            project["id"], floor_id=floor_id,
            category=None if category == "needs_review" else category,
            needs_review=needs_review or category == "needs_review",
        )
        with get_connection() as connection:
            floors = [dict(row) for row in connection.execute(
                "SELECT id,name,level_index FROM floors WHERE project_id=? ORDER BY level_index",
                (project["id"],),
            ).fetchall()]
        all_items = review_repository.list(project["id"])
        summaries = []
        for floor in floors:
            scoped = [item for item in all_items if item["floor_id"] == floor["id"]]
            summaries.append({
                **floor, "total": len(scoped),
                "confirmed": sum(item["status"] == "confirmed" for item in scoped),
                "ready": sum(item["status"] == "ready" for item in scoped),
                "needs_review": sum(item["status"] == "needs_review" for item in scoped),
            })
        counts = {name: sum(item["entity_type"] == name for item in all_items) for name in ("door", "window", "wall", "floor")}
        counts.update({
            "all": len(all_items),
            "ready": sum(item["status"] == "ready" for item in all_items),
            "confirmed": sum(item["status"] == "confirmed" for item in all_items),
            "needs_review": sum(item["status"] == "needs_review" for item in all_items),
        })
        active_jobs = [job for job in job_service.list_project_jobs(project_id=project["id"], active_only=True, limit=50) if job.get("task_type") == "review.refresh"]
        return {"project_id": project["id"], "floors": summaries, "counts": counts, "items": items, "stale": bool(refresh_needed), "active_jobs": active_jobs}

    def update_field(self, project_id: str, item_id: str, field: str, value: Any, user_id: str | None) -> dict:
        item = review_repository.get(project_id, item_id)
        if not item: raise not_found("Review item not found.")
        if item["entity_type"] in {"door", "window"}:
            allowed = {"type_code", "width_mm", "height_mm", "material", "frame_material", "glass_type", "finish"}
            if field not in allowed: raise bad_request("Edit this field from Model Review.")
            if field == "type_code": model_review_service.update(project_id=project_id,floor_id=item["floor_id"],element_id=item["entity_id"],payload={"type_code": value},created_by=user_id)
            else: model_review_service.update_property(project_id=project_id,floor_id=item["floor_id"],element_id=item["entity_id"],property_name=field,value=value,unit="mm" if field.endswith("_mm") else None,confirm=True,created_by=user_id)
        elif item["entity_type"] == "wall":
            allowed = {"classification", "wall_type", "thickness_mm", "height_override_mm", "side_1_finish", "side_2_finish"}
            if field not in allowed: raise bad_request("Edit wall geometry from Walls.")
            walls_service.update(project_id=project_id,floor_id=item["floor_id"],wall_id=item["entity_id"],payload={field: value},created_by=user_id)
        elif item["entity_type"] == "floor":
            allowed = {"name", "room_type", "floor_type_code", "floor_finish"}
            if field not in allowed: raise bad_request("Edit room geometry from Floors.")
            floors_service.update(project_id,item["floor_id"],item["entity_id"],{field:value},user_id)
        return {"item": next((row for row in review_repository.list(project_id, floor_id=item["floor_id"]) if row["id"] == item_id), None), "refreshing": True}

    def confirm(self, project_id: str, item_ids: list[str], scope: str, floor_id: str | None, user_id: str | None) -> dict:
        items = review_repository.list(project_id, floor_id=floor_id)
        if scope == "selected":
            selected_ids = set(item_ids)
            items = [item for item in items if item["id"] in selected_ids]
        valid = [item for item in items if not item["critical"]]
        now = now_iso()
        affected_floors = sorted({str(item["floor_id"]) for item in valid if item.get("floor_id")})
        with get_connection() as connection:
            for affected_floor in affected_floors:
                element_ids = [item["entity_id"] for item in valid if item["floor_id"] == affected_floor and item["entity_type"] in {"door","window"}]
                wall_ids = [item["entity_id"] for item in valid if item["floor_id"] == affected_floor and item["entity_type"] == "wall"]
                room_ids = [item["entity_id"] for item in valid if item["floor_id"] == affected_floor and item["entity_type"] == "floor"]
                if element_ids:
                    versions = workflow_repository.increment_floor_version(connection, project_id, affected_floor, "element_version")
                    placeholders = ",".join("?" for _ in element_ids)
                    connection.execute(
                        f"UPDATE elements SET status='confirmed',user_confirmed=1,element_version=?,updated_at=? WHERE id IN ({placeholders})",
                        (int(versions["element_version"]), now, *element_ids),
                    )
                if wall_ids:
                    versions = workflow_repository.increment_floor_version(connection, project_id, affected_floor, "wall_version")
                    placeholders = ",".join("?" for _ in wall_ids)
                    connection.execute(
                        f"UPDATE walls SET status='confirmed',user_confirmed=1,wall_version=?,updated_at=? WHERE id IN ({placeholders})",
                        (int(versions["wall_version"]), now, *wall_ids),
                    )
                if room_ids:
                    versions = workflow_repository.increment_floor_version(connection, project_id, affected_floor, "room_version")
                    placeholders = ",".join("?" for _ in room_ids)
                    connection.execute(
                        f"""UPDATE rooms SET status='confirmed',user_confirmed=1,
                            confirmed_geometry_json=CASE
                              WHEN COALESCE(wall_corrected_geometry_json,'{{}}')<>'{{}}' THEN wall_corrected_geometry_json
                              WHEN COALESCE(regularized_geometry_json,'{{}}')<>'{{}}' THEN regularized_geometry_json
                              WHEN COALESCE(raw_geometry_json,'{{}}')<>'{{}}' THEN raw_geometry_json
                              ELSE geometry_json END,
                            room_version=?,updated_at=? WHERE id IN ({placeholders})""",
                        (int(versions["room_version"]), now, *room_ids),
                    )
                workflow_repository.increment_floor_version(connection, project_id, affected_floor, "review_version")
            if valid:
                placeholders = ",".join("?" for _ in valid)
                connection.execute(
                    f"UPDATE review_items SET status='confirmed',updated_at=? WHERE id IN ({placeholders})",
                    (now, *(item["id"] for item in valid)),
                )
                project_versions = workflow_repository.increment_project_version(connection, project_id, "review_version")
            else:
                project_versions = workflow_repository.ensure_project_versions(connection, project_id)

        jobs = []
        if valid:
            versions = {key: int(project_versions[key] or 0) for key in project_versions.keys() if key.endswith("_version")}
            for task_type in ("review.refresh","boq.refresh"):
                job, created = job_service.enqueue(
                    task_type=task_type, project_id=project_id, floor_id=None,
                    payload={"entity_type":"bulk_confirm","count":len(valid)},
                    input_versions=versions, created_by=user_id,
                )
                jobs.append({**job,"created":created})
        return {"confirmed": len(valid), "blocked": len(items) - len(valid), "jobs": jobs}

    @staticmethod
    def _json(value: Any) -> Any:
        import json
        try: return json.loads(value) if isinstance(value, str) else value
        except Exception: return value


review_service = ReviewService()
