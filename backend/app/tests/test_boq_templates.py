from __future__ import annotations


def test_template_library_duplicate_item_preview_and_selection(foundation_db):
    from app.projects.project_service import project_service
    from app.boq.template_service import boq_template_service

    project = project_service.create_project("Template Test")
    library = boq_template_service.library(project["id"])
    assert {item["name"] for item in library["packages"]} >= {"AutoBOQ Standard", "NRM2 Trade Format", "Floor Breakdown"}
    source = library["packages"][0]
    duplicate = boq_template_service.duplicate_package(project["id"], source["id"], "Company Standard")
    created = boq_template_service.create_item(project["id"], duplicate["id"], {
        "name": "Fire doors", "element_type": "door", "section_code": "5D",
        "section_name": "Doors", "unit": "nr",
        "description_template": "[TYPE_CODE] [FIRE_RATING] fire door [WIDTH] × [HEIGHT] mm.",
        "keywords": ["FD"], "template_mode": "conditional", "conditional_rules": [],
        "formula": {"type": "quantity_x_rate"}, "sort_order": 501, "is_active": True,
    })
    preview = boq_template_service.preview(project["id"], duplicate["id"], created["id"], {})
    assert "D2" in preview["description"] and "FD30" in preview["description"]
    selected = boq_template_service.select(project["id"], duplicate["id"])
    assert selected["is_default"] is True


def test_legacy_branch_template_rules_render_and_select_unit(foundation_db):
    from app.boq.template_engine import boq_template_engine

    item = {
        "description_template": "Standard [TYPE_CODE] door",
        "unit": "nr",
        "template_mode": "conditional",
        "conditional_rules": {
            "branches": [
                {
                    "id": "wide",
                    "branch_type": "if",
                    "conditions": [{"variable": "Width", "operator": ">=", "value": "1200", "value_type": "number"}],
                    "output": {
                        "description_template": "Wide [TYPE_CODE] door [WIDTH] mm",
                        "unit": "set",
                        "amount_formula": {"operation": "value", "variables": ["Quantity"], "constant": None},
                    },
                },
                {
                    "id": "default",
                    "branch_type": "else",
                    "conditions": [],
                    "output": {
                        "description_template": "Standard [TYPE_CODE] door [WIDTH] mm",
                        "unit": "nr",
                        "amount_formula": {"operation": "value", "variables": ["Quantity"], "constant": None},
                    },
                },
            ]
        },
        "formula": {"operation": "value", "variables": ["Quantity"], "constant": None},
    }

    assert boq_template_engine.render(item, {"TYPE_CODE": "D4", "WIDTH": 1500}) == "Wide D4 door 1500 mm"
    assert boq_template_engine.resolve_unit(item, {"WIDTH": 1500}) == "set"
    assert boq_template_engine.render(item, {"TYPE_CODE": "D2", "WIDTH": 900}) == "Standard D2 door 900 mm"
    assert boq_template_engine.resolve_unit(item, {"WIDTH": 900}) == "nr"
