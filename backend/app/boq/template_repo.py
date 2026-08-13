from __future__ import annotations

from copy import deepcopy
from uuid import uuid4

from app.database.session import get_connection, row_to_dict
from app.workflow.repo_base import dumps, loads, now_iso


BUILTIN_PACKAGES: dict[str, dict] = {
    "AutoBOQ Standard": {
        "description": "Clear construction BOQ descriptions with project item traceability.",
        "category": "standard",
        "items": [
            {"name": "Doors", "element_type": "door", "section_code": "5D", "section_name": "Doors", "unit": "nr", "sort_order": 510, "description_template": "[TYPE_CODE] – [MATERIAL] door, size [WIDTH] × [HEIGHT] mm, including [FRAME_MATERIAL] frame and [FINISH]."},
            {"name": "Windows", "element_type": "window", "section_code": "5E", "section_name": "Windows", "unit": "nr", "sort_order": 520, "description_template": "[TYPE_CODE] – [FRAME_MATERIAL] framed window, size [WIDTH] × [HEIGHT] mm, glazed with [GLASS_TYPE] and finished [FINISH]."},
            {"name": "External walls", "element_type": "wall_external", "section_code": "5A", "section_name": "External walls", "unit": "m²", "sort_order": 530, "description_template": "[THICKNESS] mm thick [MATERIAL] external wall, including [SIDE_1_FINISH] and [SIDE_2_FINISH]."},
            {"name": "Internal walls", "element_type": "wall_internal", "section_code": "5B", "section_name": "Internal walls", "unit": "m²", "sort_order": 540, "description_template": "[THICKNESS] mm thick [MATERIAL] internal wall, including [SIDE_1_FINISH] and [SIDE_2_FINISH]."},
            {"name": "Floor finishes", "element_type": "floor", "section_code": "5J", "section_name": "Floor finishes", "unit": "m²", "sort_order": 550, "description_template": "Provide and lay [FLOOR_FINISH] floor finish to [ROOM_NAME], including preparation and completion."},
            {"name": "Manual items", "element_type": "manual", "section_code": "9A", "section_name": "Other items", "unit": "item", "sort_order": 900, "description_template": "[DESCRIPTION]"},
        ],
    },
    "NRM2 Trade Format": {
        "description": "NRM2-aligned work sections for measured construction work.",
        "category": "nrm2",
        "items": [
            {"name": "Masonry external walls", "element_type": "wall_external", "section_code": "14A", "section_name": "Masonry – external walls", "unit": "m²", "sort_order": 140, "description_template": "[THICKNESS] mm thick [MATERIAL] masonry external wall; [SIDE_1_FINISH]; [SIDE_2_FINISH]."},
            {"name": "Masonry internal walls", "element_type": "wall_internal", "section_code": "14B", "section_name": "Masonry – internal walls", "unit": "m²", "sort_order": 145, "description_template": "[THICKNESS] mm thick [MATERIAL] masonry internal wall; [SIDE_1_FINISH]; [SIDE_2_FINISH]."},
            {"name": "Windows", "element_type": "window", "section_code": "23", "section_name": "Windows, screens and lights", "unit": "nr", "sort_order": 230, "description_template": "[TYPE_CODE] [FRAME_MATERIAL] framed window [WIDTH] × [HEIGHT] mm; [GLASS_TYPE]; [FINISH]."},
            {"name": "Doors", "element_type": "door", "section_code": "24", "section_name": "Doors, shutters and hatches", "unit": "nr", "sort_order": 240, "description_template": "[TYPE_CODE] [MATERIAL] door [WIDTH] × [HEIGHT] mm with [FRAME_MATERIAL] frame; [FIRE_RATING]; [FINISH]."},
            {"name": "Floor finishes", "element_type": "floor", "section_code": "31", "section_name": "Floor finishes", "unit": "m²", "sort_order": 310, "description_template": "[FLOOR_FINISH] floor finish to [ROOM_NAME], including preparation, laying and completion."},
            {"name": "Manual items", "element_type": "manual", "section_code": "90", "section_name": "Other measured work", "unit": "item", "sort_order": 900, "description_template": "[DESCRIPTION]"},
        ],
    },
    "Floor Breakdown": {
        "description": "BOQ arranged by floor while retaining the same canonical quantities.",
        "category": "floor",
        "items": [
            {"name": "Floor doors", "element_type": "door", "section_code": "FD", "section_name": "Doors by floor", "unit": "nr", "sort_order": 110, "description_template": "[FLOOR_NAMES]: [TYPE_CODE] [MATERIAL] door [WIDTH] × [HEIGHT] mm, [FINISH]."},
            {"name": "Floor windows", "element_type": "window", "section_code": "FW", "section_name": "Windows by floor", "unit": "nr", "sort_order": 120, "description_template": "[FLOOR_NAMES]: [TYPE_CODE] [FRAME_MATERIAL] window [WIDTH] × [HEIGHT] mm, [GLASS_TYPE]."},
            {"name": "Floor external walls", "element_type": "wall_external", "section_code": "FEW", "section_name": "External walls by floor", "unit": "m²", "sort_order": 130, "description_template": "[FLOOR_NAMES]: [THICKNESS] mm [MATERIAL] external wall."},
            {"name": "Floor internal walls", "element_type": "wall_internal", "section_code": "FIW", "section_name": "Internal walls by floor", "unit": "m²", "sort_order": 140, "description_template": "[FLOOR_NAMES]: [THICKNESS] mm [MATERIAL] internal wall."},
            {"name": "Floor finishes", "element_type": "floor", "section_code": "FF", "section_name": "Floor finishes by floor", "unit": "m²", "sort_order": 150, "description_template": "[FLOOR_NAMES] – [ROOM_NAME]: [FLOOR_FINISH] floor finish."},
            {"name": "Manual items", "element_type": "manual", "section_code": "FM", "section_name": "Manual items", "unit": "item", "sort_order": 900, "description_template": "[DESCRIPTION]"},
        ],
    },
}


class BoqTemplateRepository:
    def ensure_builtins(self, project_id: str) -> list[dict]:
        now = now_iso()
        with get_connection() as connection:
            selected = connection.execute(
                "SELECT id FROM boq_templates WHERE project_id=? AND is_default=1 LIMIT 1", (project_id,)
            ).fetchone()
            for index, (name, package) in enumerate(BUILTIN_PACKAGES.items()):
                row = connection.execute(
                    "SELECT * FROM boq_templates WHERE project_id=? AND name=? ORDER BY version DESC LIMIT 1",
                    (project_id, name),
                ).fetchone()
                if not row:
                    template_id = str(uuid4())
                    connection.execute(
                        """
                        INSERT INTO boq_templates (
                          id,project_id,name,version,is_default,definition_json,description,
                          category,is_builtin,is_active,created_at,updated_at
                        ) VALUES (?,?,?,1,?,'{}',?,?,1,1,?,?)
                        """,
                        (template_id, project_id, name, 1 if not selected and index == 0 else 0,
                         package["description"], package["category"], now, now),
                    )
                    row = connection.execute("SELECT * FROM boq_templates WHERE id=?", (template_id,)).fetchone()
                    if index == 0 and not selected:
                        selected = row
                else:
                    template_id = row["id"]
                    connection.execute(
                        "UPDATE boq_templates SET is_builtin=1,is_active=1,description=COALESCE(description,?),category=COALESCE(category,?),updated_at=? WHERE id=?",
                        (package["description"], package["category"], now, template_id),
                    )
                existing_count = connection.execute(
                    "SELECT COUNT(*) AS count FROM boq_template_items WHERE template_id=?", (template_id,)
                ).fetchone()["count"]
                if int(existing_count or 0) == 0:
                    for item in package["items"]:
                        self._insert_item(connection, project_id, template_id, item, now)
            rows = connection.execute(
                "SELECT * FROM boq_templates WHERE project_id=? AND is_active=1 ORDER BY is_default DESC,is_builtin DESC,name",
                (project_id,),
            ).fetchall()
        return [self._decode_template(row_to_dict(row) or {}) for row in rows]

    def selected(self, project_id: str) -> dict:
        templates = self.ensure_builtins(project_id)
        return next((item for item in templates if item["is_default"]), templates[0])

    def list_packages(self, project_id: str) -> list[dict]:
        packages = self.ensure_builtins(project_id)
        return [self.get_package(project_id, item["id"]) for item in packages]

    def get_package(self, project_id: str, template_id: str) -> dict:
        with get_connection() as connection:
            row = connection.execute(
                "SELECT * FROM boq_templates WHERE project_id=? AND id=?", (project_id, template_id)
            ).fetchone()
            if not row:
                raise ValueError("Template package not found")
            items = connection.execute(
                "SELECT * FROM boq_template_items WHERE project_id=? AND template_id=? ORDER BY sort_order,name",
                (project_id, template_id),
            ).fetchall()
        result = self._decode_template(row_to_dict(row) or {})
        result["items"] = [self._decode_item(row_to_dict(item) or {}) for item in items]
        return result

    def create_package(self, project_id: str, payload: dict) -> dict:
        now = now_iso(); template_id = str(uuid4())
        with get_connection() as connection:
            connection.execute(
                """
                INSERT INTO boq_templates (
                  id,project_id,name,version,is_default,definition_json,description,category,
                  is_builtin,is_active,created_at,updated_at
                ) VALUES (?,?,?,1,0,'{}',?,?,0,1,?,?)
                """,
                (template_id, project_id, payload["name"], payload.get("description"), payload.get("category") or "custom", now, now),
            )
        return self.get_package(project_id, template_id)

    def update_package(self, project_id: str, template_id: str, payload: dict) -> dict:
        allowed = {"name", "description", "category", "is_active"}; parts=[]; values=[]
        for key, value in payload.items():
            if key not in allowed: continue
            parts.append(f"{key}=?"); values.append(1 if key == "is_active" and value else 0 if key == "is_active" else value)
        parts.extend(["version=version+1", "updated_at=?"]); values.extend([now_iso(), project_id, template_id])
        with get_connection() as connection:
            connection.execute(f"UPDATE boq_templates SET {','.join(parts)} WHERE project_id=? AND id=?", values)
            self._mark_stale(connection, project_id)
        return self.get_package(project_id, template_id)

    def duplicate_package(self, project_id: str, template_id: str, name: str | None = None) -> dict:
        source = self.get_package(project_id, template_id)
        duplicate = self.create_package(project_id, {
            "name": name or f"{source['name']} Copy",
            "description": source.get("description"), "category": "custom",
        })
        with get_connection() as connection:
            now = now_iso()
            for item in source.get("items") or []:
                payload = {key: deepcopy(item.get(key)) for key in (
                    "name", "element_type", "section_code", "section_name", "unit",
                    "description_template", "keywords", "template_mode", "conditional_rules",
                    "formula", "sort_order", "is_active",
                )}
                self._insert_item(connection, project_id, duplicate["id"], payload, now)
        return self.get_package(project_id, duplicate["id"])

    def delete_package(self, project_id: str, template_id: str) -> None:
        package = self.get_package(project_id, template_id)
        if package.get("is_builtin"):
            raise ValueError("Built-in template packages cannot be deleted")
        with get_connection() as connection:
            if package.get("is_default"):
                fallback = connection.execute(
                    "SELECT id FROM boq_templates WHERE project_id=? AND id<>? AND is_active=1 ORDER BY is_builtin DESC,name LIMIT 1",
                    (project_id, template_id),
                ).fetchone()
                if fallback:
                    connection.execute("UPDATE boq_templates SET is_default=1 WHERE id=?", (fallback["id"],))
            connection.execute("DELETE FROM boq_templates WHERE project_id=? AND id=?", (project_id, template_id))
            self._mark_stale(connection, project_id)

    def select(self, project_id: str, template_id: str) -> dict:
        package = self.get_package(project_id, template_id)
        with get_connection() as connection:
            connection.execute("UPDATE boq_templates SET is_default=0,updated_at=? WHERE project_id=?", (now_iso(), project_id))
            connection.execute("UPDATE boq_templates SET is_default=1,updated_at=? WHERE id=?", (now_iso(), template_id))
            connection.execute(
                "UPDATE boqs SET template_id=?,template_version=?,is_stale=1,updated_at=? WHERE project_id=?",
                (template_id, int(package["version"]), now_iso(), project_id),
            )
        return self.get_package(project_id, template_id)

    def create_item(self, project_id: str, template_id: str, payload: dict) -> dict:
        self.get_package(project_id, template_id)
        item_id = str(uuid4()); now = now_iso()
        with get_connection() as connection:
            self._insert_item(connection, project_id, template_id, payload | {"id": item_id}, now)
            self._bump_template(connection, project_id, template_id)
        return self.get_item(project_id, template_id, item_id)

    def get_item(self, project_id: str, template_id: str, item_id: str) -> dict:
        with get_connection() as connection:
            row = connection.execute(
                "SELECT * FROM boq_template_items WHERE project_id=? AND template_id=? AND id=?",
                (project_id, template_id, item_id),
            ).fetchone()
        if not row: raise ValueError("Template item not found")
        return self._decode_item(row_to_dict(row) or {})

    def update_item(self, project_id: str, template_id: str, item_id: str, payload: dict) -> dict:
        allowed = {"name","element_type","section_code","section_name","unit","description_template","keywords","template_mode","conditional_rules","formula","sort_order","is_active"}
        parts=[]; values=[]
        for key,value in payload.items():
            if key not in allowed: continue
            column = f"{key}_json" if key in {"keywords","conditional_rules","formula"} else key
            if key in {"keywords","conditional_rules","formula"}: value=dumps(value)
            elif key == "is_active": value=1 if value else 0
            parts.append(f"{column}=?"); values.append(value)
        parts.append("updated_at=?"); values.extend([now_iso(),project_id,template_id,item_id])
        with get_connection() as connection:
            connection.execute(f"UPDATE boq_template_items SET {','.join(parts)} WHERE project_id=? AND template_id=? AND id=?", values)
            self._bump_template(connection,project_id,template_id)
        return self.get_item(project_id,template_id,item_id)

    def delete_item(self, project_id: str, template_id: str, item_id: str) -> None:
        with get_connection() as connection:
            connection.execute("DELETE FROM boq_template_items WHERE project_id=? AND template_id=? AND id=?",(project_id,template_id,item_id))
            self._bump_template(connection,project_id,template_id)

    def matching_item(self, project_id: str, template_id: str, element_type: str, keywords: list[str] | None = None) -> dict:
        package = self.get_package(project_id, template_id)
        candidates = [item for item in package.get("items") or [] if item.get("is_active") and item.get("element_type") == element_type]
        if not candidates:
            candidates = [item for item in package.get("items") or [] if item.get("is_active") and item.get("element_type") == "manual"]
        keywords_lower = {str(value).lower() for value in (keywords or []) if value}
        candidates.sort(key=lambda item: (-len(keywords_lower & {str(value).lower() for value in item.get("keywords") or []}), int(item.get("sort_order") or 0)))
        if not candidates: raise ValueError(f"No template item for {element_type}")
        return candidates[0]

    @staticmethod
    def _insert_item(connection, project_id: str, template_id: str, payload: dict, now: str) -> str:
        item_id = payload.get("id") or str(uuid4())
        connection.execute(
            """
            INSERT INTO boq_template_items (
              id,project_id,template_id,name,element_type,section_code,section_name,unit,
              description_template,keywords_json,template_mode,conditional_rules_json,
              formula_json,sort_order,is_active,created_at,updated_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (item_id,project_id,template_id,payload.get("name") or payload.get("element_type") or "Template item",
             payload.get("element_type") or "manual",payload.get("section_code"),payload.get("section_name") or "Other items",
             payload.get("unit") or "item",payload.get("description_template") or "[DESCRIPTION]",dumps(payload.get("keywords") or []),
             payload.get("template_mode") or "standard",dumps(payload.get("conditional_rules") or []),dumps(payload.get("formula") or {}),
             int(payload.get("sort_order") or 0),1 if payload.get("is_active",True) else 0,now,now),
        )
        return item_id

    @staticmethod
    def _bump_template(connection, project_id: str, template_id: str) -> None:
        connection.execute("UPDATE boq_templates SET version=version+1,updated_at=? WHERE project_id=? AND id=?",(now_iso(),project_id,template_id))
        BoqTemplateRepository._mark_stale(connection,project_id)

    @staticmethod
    def _mark_stale(connection, project_id: str) -> None:
        connection.execute("UPDATE boqs SET is_stale=1,updated_at=? WHERE project_id=?",(now_iso(),project_id))

    @staticmethod
    def _decode_template(record: dict) -> dict:
        result=dict(record)
        result["definition"]=loads(result.pop("definition_json","{}"))
        for key in ("is_default","is_builtin","is_active"): result[key]=bool(result.get(key))
        return result

    @staticmethod
    def _decode_item(record: dict) -> dict:
        result=dict(record)
        for key in ("keywords","conditional_rules","formula"):
            result[key]=loads(result.pop(f"{key}_json","[]" if key != "formula" else "{}"))
        result["is_active"]=bool(result.get("is_active"))
        return result


boq_template_repository = BoqTemplateRepository()
