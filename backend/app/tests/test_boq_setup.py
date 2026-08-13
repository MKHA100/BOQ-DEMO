from __future__ import annotations


def test_document_setup_uses_project_metadata_and_increments_version(foundation_db):
    from app.projects.project_service import project_service
    from app.boq.setup_service import boq_setup_service

    project = project_service.create_project({"name": "Setup Project", "client_name": "Client A", "location": "Colombo"})
    setup = boq_setup_service.get(project)
    assert setup["project_name"] == "Setup Project"
    assert setup["client_name"] == "Client A"
    updated = boq_setup_service.update(project["id"], {
        "project_name": "Tender Package", "client_name": "Client A", "consultant_name": "QS Ltd",
        "location": "Colombo", "boq_title": "Priced Bill of Quantities", "currency": "LKR",
        "vat_percentage": 18, "include_rates": True, "include_amounts": True,
        "include_preliminaries": True, "include_provisional_sums": True,
        "include_signature_section": True, "format_style": "formal_tender",
        "item_numbering_format": "section_sequence", "measurement_unit_style": "metric",
        "description_style": "detailed", "section_order": ["1", "5", "9"],
    })
    assert updated["setup_version"] == setup["setup_version"] + 1
    assert updated["currency"] == "LKR"
    assert updated["include_amounts"] is True
