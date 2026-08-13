from __future__ import annotations

DEFAULT_BILLS: dict[str, tuple[str, str]] = {
    "1": ("01", "Preliminaries"),
    "2": ("02", "Substructure"),
    "3": ("03", "Superstructure"),
    "4": ("04", "Finishes"),
    "5": ("05", "Openings, walls and finishes"),
    "6": ("06", "Services"),
    "7": ("07", "External works"),
    "8": ("08", "Provisional sums"),
    "9": ("09", "Other items"),
}


def map_bill(section_code: str | None, element_type: str | None) -> dict[str, str]:
    code = str(section_code or "")
    first = code[:1] if code[:1].isdigit() else "5" if element_type in {"door","window","wall_external","wall_internal","floor"} else "9"
    bill_no, bill_name = DEFAULT_BILLS.get(first, DEFAULT_BILLS["9"])
    return {"bill_no": bill_no, "bill_name": bill_name}
