from __future__ import annotations

import json

from app.boq.export import filter_report_for_floor, write_csv, write_pdf, write_xlsx
from app.boq.repo import boq_repository
from app.boq.service import boq_service
from app.database.session import get_connection
from app.jobs.worker import register_processor
from app.storage.storage_paths import boq_export_path, relative_storage_key
from app.storage.storage_service import storage_service


def _payload(job: dict) -> dict:
    value = job.get("payload_json")
    if isinstance(value, dict):
        return value
    try:
        parsed = json.loads(value or "{}")
        return parsed if isinstance(parsed, dict) else {}
    except Exception:
        return {}


def refresh(job: dict) -> dict:
    payload = _payload(job)
    result = boq_service.refresh(
        str(job["project_id"]), grouping_mode=str(payload.get("grouping_mode") or "item")
    )
    return {
        "message": "BOQ ready", "updated": result["updated"],
        "boq_id": result["boq"]["id"], "report_hash": result["boq"].get("report_hash"),
    }


def export(job: dict) -> dict:
    payload = _payload(job)
    project_id = str(job["project_id"]); export_id = str(payload.get("export_id") or "")
    record = boq_repository.get_export(project_id, export_id)
    if not record:
        raise RuntimeError("Export request not found.")
    grouping_mode = "floor" if record.get("floor_mode") in {"floor_breakdown", "selected_floor"} else "item"
    boq, report = boq_service.current_report(project_id, grouping_mode=grouping_mode)
    record = boq_repository.sync_export_snapshot(export_id, boq)
    report = dict(report)
    report["export_floor_mode"] = record.get("floor_mode") or "combined"
    if record.get("floor_mode") == "selected_floor":
        with get_connection() as connection:
            floor = connection.execute(
                "SELECT name FROM floors WHERE project_id=? AND id=?", (project_id, record.get("floor_id"))
            ).fetchone()
        if not floor:
            raise RuntimeError("Selected floor not found.")
        report = filter_report_for_floor(report, floor["name"])
        report["export_floor_mode"] = "selected_floor"
        report["selected_floor_name"] = floor["name"]
    path = boq_export_path(project_id, boq["id"], record["filename"])
    try:
        if record["format"] == "csv":
            write_csv(path, report)
        elif record["format"] == "xlsx":
            write_xlsx(path, report)
        elif record["format"] == "pdf":
            write_pdf(path, report)
        else:
            raise RuntimeError("Unsupported export format.")
        storage_service.upload_file(path)
        key = relative_storage_key(path)
        boq_repository.finish_export(export_id, key, "ready")
        return {"message": "Export ready", "export_id": export_id, "object_key": key}
    except Exception as exc:
        boq_repository.finish_export(export_id, None, "failed", str(exc))
        raise


def register_boq_processors() -> None:
    register_processor("boq.refresh", refresh, category="boq", label="BOQ refresh", floor_scoped=False)
    register_processor("export.generate", export, category="export", label="Export generation", retry_limit=2, floor_scoped=False)
