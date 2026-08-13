from __future__ import annotations

from pathlib import Path

from app.boq.exporters import write_csv, write_pdf, write_xlsx

__all__ = ["write_csv", "write_pdf", "write_xlsx", "filter_report_for_floor"]


def filter_report_for_floor(report: dict, floor_name: str | None) -> dict:
    if not floor_name:
        return report
    filtered = dict(report)
    bills = []
    subtotal = 0.0
    for bill in report.get("bills") or []:
        next_bill = dict(bill); sections=[]; bill_subtotal=0.0; count=0
        for section in bill.get("sections") or []:
            items = [dict(item) for item in section.get("items") or [] if floor_name in (item.get("floor_names") or [])]
            if not items: continue
            section_subtotal = round(sum(float(item.get("amount") or 0) for item in items), 2)
            sections.append(dict(section) | {"items": items, "subtotal": section_subtotal})
            count += len(items); bill_subtotal += section_subtotal
        if sections:
            next_bill.update({"sections": sections, "item_count": count, "subtotal": round(bill_subtotal, 2)})
            bills.append(next_bill); subtotal += bill_subtotal
    vat_percentage = float(report.get("vat_percentage") or 0)
    vat = round(subtotal * vat_percentage / 100, 2) if report.get("include_amounts") else 0.0
    trace = [item for item in report.get("source_traceability") or [] if floor_name in (item.get("floors") or [])]
    filtered.update({
        "project_name": f"{report.get('project_name')} – {floor_name}", "bills": bills,
        "source_traceability": trace,
        "needs_review": [item for item in report.get("needs_review") or [] if floor_name in (item.get("floors") or [])],
        "summary": dict(report.get("summary") or {}) | {
            "bill_count": len(bills), "row_count": sum(bill.get("item_count", 0) for bill in bills),
            "subtotal": round(subtotal, 2), "vat": vat, "grand_total": round(subtotal + vat, 2),
        },
    })
    return filtered
