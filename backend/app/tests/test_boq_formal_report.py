from __future__ import annotations

from app.tests.test_boq import setup_boq_data


def test_formal_report_contains_bills_traceability_and_totals(foundation_db):
    from app.boq.service import boq_service
    from app.boq.setup_repo import boq_setup_repository

    project, *_ = setup_boq_data()
    boq_setup_repository.ensure(project)
    boq_setup_repository.update(project["id"], {
        "include_rates": True, "include_amounts": True, "vat_percentage": 15,
    })
    result = boq_service.refresh(project["id"])
    door = next(row for row in result["rows"] if row["entity_type"] == "door")
    boq_service.update_row(project["id"], door["id"], {"rate": 25000})
    result = boq_service.refresh(project["id"])
    report = result["report"]

    assert report["bills"]
    assert report["source_traceability"]
    assert any(item["item_number"].startswith("5D") for bill in report["bills"] for section in bill["sections"] for item in section["items"] if item["entity_type"] == "door")
    assert report["summary"]["subtotal"] >= 25000
    assert report["summary"]["vat"] == round(report["summary"]["subtotal"] * 0.15, 2)
