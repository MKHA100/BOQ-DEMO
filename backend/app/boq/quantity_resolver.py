from __future__ import annotations

from collections import defaultdict

from app.database.session import get_connection
from app.model_review.repo import model_review_repository


class BoqQuantityResolver:
    """Read canonical element/wall/room records and return grouped BOQ facts."""

    def resolve(self, project_id: str, grouping_mode: str = "item") -> tuple[list[dict], dict[str, str]]:
        with get_connection() as connection:
            floor_rows = connection.execute(
                "SELECT id,name,level_index FROM floors WHERE project_id=? ORDER BY level_index", (project_id,)
            ).fetchall()
            walls = connection.execute(
                """SELECT * FROM walls w WHERE project_id=? AND net_area_m2 IS NOT NULL
                   AND COALESCE(w.generated_status,'current')='current'
                   AND (COALESCE(w.user_confirmed,0)=1 OR w.status='confirmed')
                   AND (w.source_crop_version IS NULL OR w.source_crop_version=(SELECT crop_version FROM floor_versions fv
                        WHERE fv.project_id=w.project_id AND fv.floor_id=w.floor_id))""", (project_id,)
            ).fetchall()
            rooms = connection.execute(
                """SELECT * FROM rooms r WHERE project_id=? AND excluded=0 AND area_m2 IS NOT NULL
                   AND COALESCE(include_in_boq,1)=1 AND COALESCE(r.generated_status,'current')='current'
                   AND (
                     COALESCE(r.user_confirmed,0)=1 OR (
                       r.boundary_source IN (
                         'wall_corrected','wall_cell','wall_geometry',
                         'model_seed_wall_region','model_seed_wall_faces'
                       )
                       AND COALESCE(r.measurement_status,'invalid')='correct'
                       AND (
                         COALESCE(r.precision_status,'invalid')='ready' OR (
                           r.boundary_source='wall_corrected'
                           AND r.dimension_status IN ('exact','partial')
                           AND r.interpretation_status='ready'
                         )
                       )
                     )
                   )
                   AND (COALESCE(r.user_confirmed,0)=1 OR COALESCE(r.measurement_status,'invalid')='correct')
                   AND COALESCE(r.geometry_status,'invalid')<>'invalid'
                   AND (r.source_crop_version IS NULL OR r.source_crop_version=(SELECT crop_version FROM floor_versions fv
                        WHERE fv.project_id=r.project_id AND fv.floor_id=r.floor_id))""", (project_id,)
            ).fetchall()
        floor_names = {row["id"]: row["name"] for row in floor_rows}
        elements: list[dict] = []
        for floor in floor_rows:
            elements.extend(
                item for item in model_review_repository.list_elements(project_id, floor["id"])
                if item.get("element_type") in {"door", "window"} and not item.get("excluded")
            )

        groups: dict[str, dict] = {}
        for element in elements:
            values = element.get("resolved_data") or {}
            kind = str(element["element_type"])
            code = values.get("type_code") or element.get("type_code") or element.get("tag_text")
            missing = set(element.get("missing_fields") or [])
            floor_prefix = f"floor:{element['floor_id']}:" if grouping_mode == "floor" else ""
            identity = code or f"item-{element.get('item_number') or element['id']}"
            key = f"{floor_prefix}{kind}:{identity}:{values.get('width_mm')}:{values.get('height_mm')}:{values.get('material') or values.get('frame_material')}"
            group = groups.setdefault(key, {
                "group_key": key, "kind": kind, "item_code": code, "quantity": 0,
                "unit": "nr", "sources": [], "floors": set(), "missing": set(),
                "needs_review": False, "values": dict(values), "keywords": [code] if code else [],
            })
            group["quantity"] += 1
            group["sources"].append(element["id"])
            group["floors"].add(element["floor_id"])
            group["missing"].update(missing)
            group["needs_review"] = bool(group["needs_review"] or missing or element.get("status") == "needs_review")

        for wall in walls:
            classification = str(wall["classification"] or "internal").lower()
            kind = "wall_external" if classification == "external" else "wall_internal"
            floor_prefix = f"floor:{wall['floor_id']}:" if grouping_mode == "floor" else ""
            identity = wall["wall_type"] or f"item-{wall['item_number'] or wall['id']}"
            key = f"{floor_prefix}{kind}:{identity}:{wall['thickness_mm']}:{wall['side_1_finish']}:{wall['side_2_finish']}"
            missing = {name for name, value in {
                "classification": wall["classification"], "thickness_mm": wall["thickness_mm"],
                "height_mm": wall["height_mm"], "net_area_m2": wall["net_area_m2"],
            }.items() if value in (None, "")}
            group = groups.setdefault(key, {
                "group_key": key, "kind": kind, "item_code": wall["wall_type"], "quantity": 0.0,
                "unit": "m²", "sources": [], "floors": set(), "missing": set(),
                "needs_review": False,
                "values": {
                    "type_code": wall["wall_type"], "thickness_mm": wall["thickness_mm"],
                    "classification": wall["classification"], "material": wall["wall_type"] or "masonry",
                    "side_1_finish": wall["side_1_finish"], "side_2_finish": wall["side_2_finish"],
                },
                "keywords": [wall["wall_type"], wall["classification"]],
            })
            group["quantity"] += float(wall["net_area_m2"] or 0)
            group["sources"].append(wall["id"])
            group["floors"].add(wall["floor_id"])
            group["missing"].update(missing)
            group["needs_review"] = bool(group["needs_review"] or missing or wall["status"] == "needs_review")

        finish_zone_parents = {str(room["parent_room_id"]) for room in rooms if bool(room["is_finish_zone"]) and room["parent_room_id"]}
        for room in rooms:
            if not bool(room["is_finish_zone"]) and str(room["id"]) in finish_zone_parents:
                # Child finish zones replace the open-plan parent for BOQ area,
                # preventing double counting.
                continue
            if str(room["space_kind"] or "internal") in {"void", "circulation"}:
                continue
            # Floor finishes are always floor-specific. This preserves QS
            # traceability and lets Floor Breakdown exports use the same rows.
            floor_prefix = f"floor:{room['floor_id']}:"
            finish = room["floor_finish"] or room["finish_code"]
            identity = room["floor_type_code"] or finish or room["room_type"] or "unclassified"
            space_kind = str(room["space_kind"] or "internal")
            key = f"{floor_prefix}floor:{space_kind}:{identity}:{finish or 'missing'}"
            missing = {name for name, value in {"floor_finish": finish, "area_m2": room["area_m2"]}.items() if value in (None, "")}
            group = groups.setdefault(key, {
                "group_key": key, "kind": "floor", "item_code": room["floor_type_code"], "quantity": 0.0,
                "unit": "m²", "sources": [], "floors": set(), "missing": set(),
                "needs_review": False,
                "values": {
                    "type_code": room["floor_type_code"],
                    "floor_finish": finish,
                    "finish": finish,
                    "room_name": room["name"],
                    "room_type": room["room_type"],
                    "space_kind": space_kind,
                    "detection_source": room["detection_source"],
                },
                "keywords": [room["floor_type_code"], finish, room["room_type"], room["name"]],
            })
            group["quantity"] += float(room["area_m2"] or 0)
            group["sources"].append(room["id"])
            group["floors"].add(room["floor_id"])
            group["missing"].update(missing)
            group["needs_review"] = bool(
                group["needs_review"] or missing or room["status"] == "needs_review"
                or str(room["measurement_status"] or "check") != "correct"
            )

        resolved: list[dict] = []
        for group in groups.values():
            floors = sorted(group.pop("floors"))
            group["floor_ids"] = floors
            group["floor_id"] = floors[0] if len(floors) == 1 else None
            group["floor_names"] = [floor_names.get(floor_id, floor_id) for floor_id in floors]
            group["missing"] = sorted(group["missing"])
            group["quantity"] = int(group["quantity"]) if group["unit"] == "nr" else round(float(group["quantity"]), 3)
            resolved.append(group)
        return resolved, floor_names


boq_quantity_resolver = BoqQuantityResolver()
