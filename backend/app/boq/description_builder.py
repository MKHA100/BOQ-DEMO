from __future__ import annotations

from app.boq.template_engine import boq_template_engine


class BoqDescriptionBuilder:
    def build(self, template_item: dict, group: dict) -> str:
        return self.build_details(template_item, group)["description"]

    def build_details(self, template_item: dict, group: dict) -> dict:
        values = self.values(group)
        output = boq_template_engine.resolve_output(template_item, values)
        return {
            "description": boq_template_engine.render(template_item, values),
            "unit": output.get("unit") or template_item.get("unit") or group.get("unit") or "item",
            "formula": output.get("amount_formula") or template_item.get("formula") or {},
            "formula_preview": boq_template_engine.evaluate_formula(
                output.get("amount_formula") or template_item.get("formula") or {}, values, default=group.get("quantity")
            ),
            "values": values,
        }

    @staticmethod
    def values(group: dict) -> dict:
        values = dict(group.get("values") or {})
        values.update({
            "TYPE_CODE": group.get("item_code") or values.get("type_code") or group.get("kind", "").replace("_", " ").title(),
            "ITEM_CODE": group.get("item_code"),
            "MATERIAL": values.get("material") or values.get("frame_material") or "material to confirm",
            "FRAME_MATERIAL": values.get("frame_material") or values.get("material") or "frame material to confirm",
            "FINISH": values.get("finish") or "finish to confirm",
            "WIDTH": values.get("width_mm") or "width to confirm", "WIDTH_MM": values.get("width_mm"),
            "HEIGHT": values.get("height_mm") or "height to confirm", "HEIGHT_MM": values.get("height_mm"),
            "LENGTH": values.get("length_mm") or values.get("length_m"),
            "AREA": values.get("area_m2") or values.get("net_area_m2") or group.get("quantity"),
            "VOLUME": values.get("volume_m3"),
            "THICKNESS": values.get("thickness_mm") or "thickness to confirm", "THICKNESS_MM": values.get("thickness_mm"),
            "CLASSIFICATION": values.get("classification") or "classification to confirm",
            "WALL_TYPE": values.get("wall_type") or values.get("type_code") or group.get("item_code"),
            "FLOOR_FINISH": values.get("floor_finish") or values.get("finish") or "finish to confirm",
            "ROOM_NAME": values.get("room_name") or "room", "FIRE_RATING": values.get("fire_rating") or "fire rating where required",
            "GLASS_TYPE": values.get("glass_type") or "glazing to confirm", "QUANTITY": group.get("quantity"),
            "UNIT": group.get("unit"), "FLOOR": ", ".join(group.get("floor_names") or []),
            "FLOOR_NAMES": ", ".join(group.get("floor_names") or []), "LEVEL": ", ".join(group.get("floor_names") or []),
            "SIDE_1_FINISH": values.get("side_1_finish") or "finish to confirm",
            "SIDE_2_FINISH": values.get("side_2_finish") or "finish to confirm",
            "DESCRIPTION": values.get("description") or "Manual construction item",
        })
        return values


boq_description_builder = BoqDescriptionBuilder()
