from __future__ import annotations

from app.tests.test_boq import setup_boq_data


def test_export_cache_changes_after_setup_version(foundation_db):
    from app.boq.service import boq_service
    from app.boq.setup_repo import boq_setup_repository

    project, *_ = setup_boq_data(); boq_service.refresh(project["id"])
    first = boq_service.request_export(project["id"], {"format": "csv", "floor_mode": "combined", "floor_id": None}, None)
    duplicate = boq_service.request_export(project["id"], {"format": "csv", "floor_mode": "combined", "floor_id": None}, None)
    assert first["created"] is True and duplicate["created"] is False
    setup = boq_setup_repository.ensure(project)
    boq_setup_repository.update(project["id"], {"currency": "USD", "section_order": setup["section_order"]})
    changed = boq_service.request_export(project["id"], {"format": "csv", "floor_mode": "combined", "floor_id": None}, None)
    assert changed["created"] is True
