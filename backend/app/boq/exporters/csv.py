from __future__ import annotations

import csv
from pathlib import Path


def write_csv(path: Path, report: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow([
            "Bill", "Section", "Item", "Description", "Unit", "Quantity",
            "Rate", "Amount", "Status", "Floors", "Source Items", "Missing Fields",
        ])
        for bill in report.get("bills") or []:
            for section in bill.get("sections") or []:
                for item in section.get("items") or []:
                    writer.writerow([
                        f"{bill.get('bill_no')} {bill.get('name')}",
                        f"{section.get('code')} {section.get('name')}", item.get("item_number"),
                        item.get("description"), item.get("unit"), item.get("quantity"),
                        item.get("rate"), item.get("amount"), item.get("status"),
                        ", ".join(item.get("floor_names") or []),
                        ", ".join(item.get("source_item_numbers") or []),
                        ", ".join(item.get("missing_fields") or []),
                    ])
