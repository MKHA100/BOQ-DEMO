from __future__ import annotations

from app.boq.placeholders import PLACEHOLDERS
from app.boq.template_engine import boq_template_engine
from app.boq.template_repo import boq_template_repository
from app.core.errors import bad_request, not_found


class BoqTemplateService:
    def library(self, project_id: str) -> dict:
        packages = boq_template_repository.list_packages(project_id)
        selected = next((item for item in packages if item.get("is_default")), packages[0])
        return {"packages": packages, "selected_template_id": selected["id"], "placeholders": list(PLACEHOLDERS)}

    def create_package(self, project_id: str, payload: dict) -> dict:
        return boq_template_repository.create_package(project_id, payload)

    def update_package(self, project_id: str, template_id: str, payload: dict) -> dict:
        try: return boq_template_repository.update_package(project_id, template_id, payload)
        except ValueError as exc: raise not_found(str(exc))

    def duplicate_package(self, project_id: str, template_id: str, name: str | None) -> dict:
        try: return boq_template_repository.duplicate_package(project_id, template_id, name)
        except ValueError as exc: raise not_found(str(exc))

    def delete_package(self, project_id: str, template_id: str) -> None:
        try: boq_template_repository.delete_package(project_id, template_id)
        except ValueError as exc: raise bad_request(str(exc))

    def select(self, project_id: str, template_id: str) -> dict:
        try: return boq_template_repository.select(project_id, template_id)
        except ValueError as exc: raise not_found(str(exc))

    def create_item(self, project_id: str, template_id: str, payload: dict) -> dict:
        self._validate(payload)
        try: return boq_template_repository.create_item(project_id, template_id, payload)
        except ValueError as exc: raise not_found(str(exc))

    def update_item(self, project_id: str, template_id: str, item_id: str, payload: dict) -> dict:
        self._validate(payload)
        try: return boq_template_repository.update_item(project_id, template_id, item_id, payload)
        except ValueError as exc: raise not_found(str(exc))

    def delete_item(self, project_id: str, template_id: str, item_id: str) -> None:
        boq_template_repository.delete_item(project_id, template_id, item_id)

    def preview(self, project_id: str, template_id: str, item_id: str, values: dict) -> dict:
        try: item = boq_template_repository.get_item(project_id, template_id, item_id)
        except ValueError as exc: raise not_found(str(exc))
        return {"description": boq_template_engine.preview(item, values), "item": item}

    @staticmethod
    def _validate(payload: dict) -> None:
        templates: list[str] = []
        template = payload.get("description_template")
        if template is not None:
            templates.append(str(template))
        rules = payload.get("conditional_rules")
        if isinstance(rules, dict):
            for branch in rules.get("branches") or []:
                if not isinstance(branch, dict):
                    continue
                output = branch.get("output")
                if isinstance(output, dict) and output.get("description_template") is not None:
                    templates.append(str(output.get("description_template")))
        elif isinstance(rules, list):
            for rule in rules:
                if isinstance(rule, dict) and rule.get("description_template") is not None:
                    templates.append(str(rule.get("description_template")))
        unknown = sorted({token for current in templates for token in boq_template_engine.validate_template(current)})
        if unknown:
            raise bad_request(f"Unknown placeholders: {', '.join(unknown)}")


boq_template_service = BoqTemplateService()
