from __future__ import annotations

import re
from typing import Any

from app.boq.placeholders import PLACEHOLDER_KEYS

_TOKEN = re.compile(r"\[([A-Z0-9_]+)\]")


def _display(value: Any) -> str:
    if value in (None, ""):
        return ""
    if isinstance(value, float):
        return f"{value:g}"
    return str(value)


def _key(value: Any) -> str:
    text = str(value or "").strip().replace(" ", "_")
    text = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", text)
    return re.sub(r"_+", "_", text).upper()


class BoqTemplateEngine:
    """Render both the canonical flat rules and the full legacy branch-rule format."""

    def render(self, template_item: dict, values: dict) -> str:
        context = self._context(values)
        output = self.resolve_output(template_item, context)
        template = str(output.get("description_template") or template_item.get("description_template") or "[DESCRIPTION]")
        rendered = _TOKEN.sub(lambda match: _display(context.get(match.group(1))), template)
        rendered = re.sub(r"\s+([,.;:])", r"\1", rendered)
        rendered = re.sub(r"([,;])\s*([,;])", r"\1", rendered)
        rendered = re.sub(r"\s{2,}", " ", rendered).strip(" ,;-")
        return rendered or str(values.get("DESCRIPTION") or values.get("description") or "Item description to confirm")

    def resolve_output(self, template_item: dict, values: dict) -> dict:
        context = self._context(values)
        base = {
            "description_template": str(template_item.get("description_template") or "[DESCRIPTION]"),
            "unit": str(template_item.get("unit") or "item"),
            "amount_formula": template_item.get("formula") or {},
        }
        rules = template_item.get("conditional_rules") or []

        if isinstance(rules, dict) and isinstance(rules.get("branches"), list):
            for branch in rules.get("branches") or []:
                if not isinstance(branch, dict):
                    continue
                branch_type = str(branch.get("branch_type") or "if").lower()
                conditions = branch.get("conditions") or []
                if branch_type == "else" or self._branch_matches(conditions, context):
                    output = branch.get("output") if isinstance(branch.get("output"), dict) else {}
                    return {
                        "description_template": output.get("description_template") or base["description_template"],
                        "unit": output.get("unit") or base["unit"],
                        "amount_formula": output.get("amount_formula") or base["amount_formula"],
                    }
            return base

        template = base["description_template"]
        if isinstance(rules, list):
            for rule in rules:
                if not isinstance(rule, dict) or not self._matches_flat(rule, context):
                    continue
                replacement = rule.get("description_template")
                if replacement:
                    template = str(replacement)
                template = f"{str(rule.get('prefix') or '')}{template}{str(rule.get('suffix') or '')}"
        return base | {"description_template": template}

    def resolve_unit(self, template_item: dict, values: dict) -> str:
        return str(self.resolve_output(template_item, values).get("unit") or template_item.get("unit") or "item")

    def evaluate_formula(self, formula: dict | None, values: dict, default: float | None = None) -> float | None:
        if not isinstance(formula, dict) or not formula:
            return default
        context = self._context(values)
        operation = str(formula.get("operation") or "value").lower()
        variables = [context.get(_key(value)) for value in formula.get("variables") or ["Quantity"]]
        numbers = [self._number(value) for value in variables]
        constant = self._number(formula.get("constant"))
        if operation == "count":
            return constant if constant is not None else 1.0
        usable = [value for value in numbers if value is not None]
        if not usable:
            return default
        if operation == "value":
            result = usable[0]
        elif operation == "multiply":
            result = 1.0
            for value in usable:
                result *= value
        elif operation == "sum":
            result = sum(usable)
        elif operation == "subtract":
            result = usable[0]
            for value in usable[1:]:
                result -= value
        elif operation == "divide":
            result = usable[0]
            for value in usable[1:]:
                if value == 0:
                    return default
                result /= value
        else:
            return default
        if constant is not None:
            result = result * constant if operation == "multiply" else result + constant
        return round(float(result), 6)

    def preview(self, template_item: dict, values: dict | None = None) -> str:
        sample = {
            "TYPE_CODE": "D2", "MATERIAL": "Timber", "FRAME_MATERIAL": "Hardwood",
            "FINISH": "stain and polyurethane varnish", "WIDTH": 990, "HEIGHT": 2130,
            "LENGTH": 10, "AREA": 12.5, "VOLUME": 2.4, "THICKNESS": 215,
            "CLASSIFICATION": "External", "WALL_TYPE": "Brick", "FLOOR_FINISH": "porcelain tile",
            "ROOM_NAME": "Office", "FIRE_RATING": "FD30", "GLASS_TYPE": "4 mm clear float glass",
            "QUANTITY": 5, "UNIT": "nr", "FLOOR": "Ground Floor", "FLOOR_NAMES": "Ground Floor",
            "LEVEL": "Ground Floor", "SIDE_1_FINISH": "plaster and paint", "SIDE_2_FINISH": "plaster and paint",
            "DESCRIPTION": "Manual construction item",
        }
        sample.update({str(key).upper(): value for key, value in (values or {}).items()})
        return self.render(template_item, sample)

    @staticmethod
    def validate_template(template: str) -> list[str]:
        return sorted({token for token in _TOKEN.findall(template or "") if token not in PLACEHOLDER_KEYS and token != "DESCRIPTION"})

    def _context(self, values: dict) -> dict:
        context = {_key(key): value for key, value in (values or {}).items()}
        aliases = {
            "WIDTH": ("WIDTH", "WIDTH_MM"), "HEIGHT": ("HEIGHT", "HEIGHT_MM"),
            "THICKNESS": ("THICKNESS", "THICKNESS_MM"), "WALL_TYPE": ("WALL_TYPE", "TYPE_CODE"),
            "TYPE_CODE": ("TYPE_CODE", "ITEM_CODE"), "FLOOR": ("FLOOR", "FLOOR_NAMES"),
            "LEVEL": ("LEVEL", "FLOOR", "FLOOR_NAMES"), "AREA": ("AREA", "NET_AREA", "QUANTITY"),
        }
        for target, sources in aliases.items():
            if context.get(target) not in (None, ""):
                continue
            context[target] = next((context.get(source) for source in sources if context.get(source) not in (None, "")), None)
        return context

    def _branch_matches(self, conditions: list, context: dict) -> bool:
        if not conditions:
            return True
        return all(self._matches_condition(condition, context) for condition in conditions if isinstance(condition, dict))

    def _matches_condition(self, condition: dict, context: dict) -> bool:
        current = context.get(_key(condition.get("variable")))
        expected = condition.get("value")
        operator = str(condition.get("operator") or "=")
        value_type = str(condition.get("value_type") or "number").lower()
        if value_type == "number":
            left, right = self._number(current), self._number(expected)
            if left is None or right is None:
                return False
        else:
            left, right = str(current or "").strip().lower(), str(expected or "").strip().lower()
        if operator in {"=", "=="}: return left == right
        if operator == "!=": return left != right
        if operator == "<": return left < right
        if operator == "<=": return left <= right
        if operator == ">": return left > right
        if operator == ">=": return left >= right
        return False

    @staticmethod
    def _matches_flat(rule: dict, context: dict) -> bool:
        field = _key(rule.get("field"))
        if not field:
            return False
        current = context.get(field)
        operator = str(rule.get("operator") or "exists")
        expected = rule.get("value")
        if operator == "exists": return current not in (None, "")
        if operator == "missing": return current in (None, "")
        if operator == "equals": return str(current).lower() == str(expected).lower()
        if operator == "contains": return str(expected).lower() in str(current).lower()
        if operator == "not_equals": return str(current).lower() != str(expected).lower()
        return False

    @staticmethod
    def _number(value: Any) -> float | None:
        if value in (None, ""):
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None


boq_template_engine = BoqTemplateEngine()
