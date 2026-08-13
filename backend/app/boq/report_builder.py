from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.boq.section_mapper import map_bill

PRELIMINARY_NOTES = [
    "Dimensions and quantities are generated from the reviewed project records and must be read with the drawings and specifications.",
    "Items marked Needs Review remain included so missing or conflicting information is not silently omitted.",
    "Rates and amounts are included only when enabled in Document Setup.",
]

MODE_OF_PAYMENT = [
    {"category": "A", "description": "Actual cost supported by acceptable documents, plus the agreed attendance percentage."},
    {"category": "C", "description": "Paid progressively in accordance with the approved programme and completed temporary works."},
    {"category": "D", "description": "Paid on satisfactory completion of the item."},
    {"category": "E", "description": "Paid in equal instalments over the contract period."},
    {"category": "G", "description": "Paid on completion of the work."},
]


class FormalBoqReportBuilder:
    def build(self, *, project: dict, setup: dict, template: dict, boq: dict, rows: list[dict]) -> dict:
        visible = [dict(row) for row in rows if not row.get("excluded")]
        excluded = [dict(row) for row in rows if row.get("excluded")]
        bills_by_key: dict[tuple[str, str], dict] = {}
        counters: dict[str, int] = {}
        source_traceability: list[dict] = []
        element_properties: dict[str, dict] = {}

        for simple_index, row in enumerate(visible, start=1):
            bill = map_bill(row.get("subcategory_code") or row.get("section"), row.get("entity_type"))
            bill_no = row.get("bill_no") or bill["bill_no"]
            bill_name = row.get("bill_name") or bill["bill_name"]
            bill_key = (str(bill_no), str(bill_name))
            bill_record = bills_by_key.setdefault(bill_key, {
                "bill_no": str(bill_no), "name": str(bill_name), "sections": {},
                "subtotal": 0.0, "item_count": 0,
            })
            section_code = str(row.get("subcategory_code") or row.get("item_code") or "GEN")
            section_name = str(row.get("subcategory_name") or row.get("section") or "General")
            section = bill_record["sections"].setdefault(section_code, {
                "code": section_code, "name": section_name, "items": [], "subtotal": 0.0,
            })
            counters[section_code] = counters.get(section_code, 0) + 1
            item_number = self._item_number(setup, row, simple_index, section_code, counters[section_code])
            quantity = float(row.get("quantity") or 0)
            rate = row.get("rate")
            amount = row.get("amount")
            if rate not in (None, ""):
                rate = float(rate)
                amount = round(quantity * rate, 2)
            else:
                rate = None
                amount = None
            line = {
                "id": row.get("id"), "item_number": item_number,
                "source_item_numbers": [item.get("display_number") for item in row.get("source_items") or [] if item.get("display_number")],
                "description": row.get("description") or "Description to confirm",
                "unit": row.get("unit") or "item", "quantity": quantity,
                "rate": rate, "amount": amount, "status": row.get("status") or "needs_review",
                "missing_fields": list(row.get("missing_fields") or []),
                "floor_names": list(row.get("floor_names") or []),
                "entity_type": row.get("entity_type"), "manual": bool(row.get("manual")),
            }
            section["items"].append(line)
            bill_record["item_count"] += 1
            if amount is not None:
                section["subtotal"] = round(section["subtotal"] + amount, 2)
                bill_record["subtotal"] = round(bill_record["subtotal"] + amount, 2)

            source_traceability.append({
                "boq_item_number": item_number, "description": line["description"],
                "source_items": line["source_item_numbers"], "floors": line["floor_names"],
                "status": line["status"], "missing_fields": line["missing_fields"],
            })
            for source in row.get("source_items") or []:
                source_id = str(source.get("id") or "")
                if source_id and source_id not in element_properties:
                    element_properties[source_id] = {
                        "source_item": source.get("display_number") or source.get("type_code") or source_id,
                        "element_type": source.get("element_type"), "type_code": source.get("type_code"),
                        "floor": source.get("floor"), "width_mm": source.get("width_mm"),
                        "height_mm": source.get("height_mm"), "material": source.get("material"),
                        "quantity": source.get("quantity"), "finish": source.get("finish"),
                    }

        bills = []
        for _, bill in sorted(bills_by_key.items(), key=lambda pair: (pair[0][0], pair[0][1])):
            bill["sections"] = [bill["sections"][key] for key in sorted(bill["sections"], key=lambda value: (min((item.get("sort_order", 0) for item in visible if str(item.get("subcategory_code") or item.get("item_code") or "GEN") == value), default=0), value))]
            bills.append(bill)

        subtotal = round(sum(float(bill.get("subtotal") or 0) for bill in bills), 2)
        vat_percentage = float(setup.get("vat_percentage") or 0)
        vat = round(subtotal * vat_percentage / 100, 2) if setup.get("include_amounts") else 0.0
        grand_total = round(subtotal + vat, 2)
        needs_review = [item for item in source_traceability if item["status"] == "needs_review" or item["missing_fields"]]

        return {
            "project_id": project["id"], "boq_id": boq["id"], "boq_version": boq.get("boq_version") or 0,
            "template_id": template["id"], "template_name": template["name"], "template_version": template.get("version") or 1,
            "setup_version": setup.get("setup_version") or 1,
            "title": setup.get("boq_title") or boq.get("name") or "Bill of Quantities",
            "project_name": setup.get("project_name") or project.get("name") or "Project",
            "project_number": project.get("project_number") or "", "client_name": setup.get("client_name") or project.get("client_name") or "",
            "consultant_name": setup.get("consultant_name") or "", "location": setup.get("location") or project.get("location") or "",
            "currency": setup.get("currency") or "Rs", "vat_percentage": vat_percentage,
            "include_rates": bool(setup.get("include_rates")), "include_amounts": bool(setup.get("include_amounts")),
            "include_preliminaries": bool(setup.get("include_preliminaries", True)),
            "include_provisional_sums": bool(setup.get("include_provisional_sums")),
            "include_signature_section": bool(setup.get("include_signature_section", True)),
            "format_style": setup.get("format_style") or "formal_tender",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "summary": {
                "bill_count": len(bills), "row_count": len(visible), "ready_count": sum(item.get("status") == "ready" for item in visible),
                "needs_review_count": len(needs_review), "excluded_count": len(excluded),
                "subtotal": subtotal, "vat": vat, "grand_total": grand_total,
            },
            "bills": bills,
            "preliminaries": {"notes": list(PRELIMINARY_NOTES), "mode_of_payment": list(MODE_OF_PAYMENT)},
            "element_properties": list(element_properties.values()), "source_traceability": source_traceability,
            "needs_review": needs_review,
            "excluded_items": [{"description": row.get("description"), "section": row.get("section"), "source_items": [item.get("display_number") for item in row.get("source_items") or []]} for row in excluded],
        }

    @staticmethod
    def _item_number(setup: dict, row: dict, simple_index: int, section_code: str, section_index: int) -> str:
        mode = setup.get("item_numbering_format") or "section_sequence"
        if mode == "source_item_number":
            source = next((item.get("display_number") for item in row.get("source_items") or [] if item.get("display_number")), None)
            return str(source or simple_index)
        if mode == "simple_sequence":
            return str(simple_index)
        return f"{section_code}{section_index}"


formal_boq_report_builder = FormalBoqReportBuilder()
