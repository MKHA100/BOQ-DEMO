from __future__ import annotations

from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    BaseDocTemplate, Frame, PageTemplate, Paragraph, PageBreak, Spacer, Table, TableStyle,
)


class _NumberedDocument(BaseDocTemplate):
    def __init__(self, filename: str, report: dict):
        super().__init__(
            filename, pagesize=A4, rightMargin=14 * mm, leftMargin=14 * mm,
            topMargin=18 * mm, bottomMargin=16 * mm,
            title=report.get("title") or "Bill of Quantities",
            author="AutoBOQ",
        )
        self.report = report
        frame = Frame(self.leftMargin, self.bottomMargin, self.width, self.height, id="normal")
        self.addPageTemplates(PageTemplate(id="boq", frames=frame, onPage=self._header_footer))

    def _header_footer(self, canvas, document):
        canvas.saveState()
        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColor(colors.HexColor("#475569"))
        if document.page > 1:
            canvas.drawString(14 * mm, A4[1] - 10 * mm, str(self.report.get("project_name") or "Project"))
            canvas.drawRightString(A4[0] - 14 * mm, A4[1] - 10 * mm, str(self.report.get("title") or "Bill of Quantities"))
            canvas.setStrokeColor(colors.HexColor("#CBD5E1"))
            canvas.line(14 * mm, A4[1] - 12 * mm, A4[0] - 14 * mm, A4[1] - 12 * mm)
        canvas.drawCentredString(A4[0] / 2, 8 * mm, f"Page {document.page}")
        canvas.restoreState()


def _styles():
    styles = getSampleStyleSheet()
    return {
        "title": ParagraphStyle("title", parent=styles["Title"], fontName="Helvetica-Bold", fontSize=22, leading=27, alignment=TA_CENTER, textColor=colors.HexColor("#0F172A"), spaceAfter=10),
        "subtitle": ParagraphStyle("subtitle", parent=styles["Normal"], fontSize=10, leading=14, alignment=TA_CENTER, textColor=colors.HexColor("#475569")),
        "h1": ParagraphStyle("h1", parent=styles["Heading1"], fontName="Helvetica-Bold", fontSize=15, leading=19, textColor=colors.HexColor("#0F172A"), spaceBefore=4, spaceAfter=8),
        "h2": ParagraphStyle("h2", parent=styles["Heading2"], fontName="Helvetica-Bold", fontSize=11, leading=14, textColor=colors.HexColor("#1E3A8A"), spaceBefore=6, spaceAfter=5),
        "body": ParagraphStyle("body", parent=styles["BodyText"], fontSize=8.3, leading=11, textColor=colors.HexColor("#1F2937")),
        "small": ParagraphStyle("small", parent=styles["BodyText"], fontSize=7, leading=9, textColor=colors.HexColor("#475569")),
        "right": ParagraphStyle("right", parent=styles["BodyText"], fontSize=8, leading=10, alignment=TA_RIGHT),
        "cell": ParagraphStyle("cell", parent=styles["BodyText"], fontSize=7.3, leading=9),
        "cell_review": ParagraphStyle("cell_review", parent=styles["BodyText"], fontSize=7.3, leading=9, textColor=colors.HexColor("#92400E")),
    }


def _table(data, widths, *, header=True, font_size=7.2):
    table = Table(data, colWidths=widths, repeatRows=1 if header else 0, hAlign="LEFT")
    style = [
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#94A3B8")),
        ("LEFTPADDING", (0, 0), (-1, -1), 3.5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 3.5),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), font_size),
    ]
    if header:
        style.extend([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E2E8F0")),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#0F172A")),
        ])
    table.setStyle(TableStyle(style))
    return table


def _money(value, currency: str) -> str:
    return "" if value in (None, "") else f"{currency} {float(value):,.2f}"



def _floor_items(report: dict) -> dict[str, list[dict]]:
    floors: dict[str, list[dict]] = {}
    for bill in report.get("bills") or []:
        for section in bill.get("sections") or []:
            for item in section.get("items") or []:
                for floor in item.get("floor_names") or ["Unassigned"]:
                    floors.setdefault(str(floor), []).append({
                        **item,
                        "bill_no": bill.get("bill_no"),
                        "section_code": section.get("code"),
                    })
    return floors

def write_pdf(path: Path, report: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    styles = _styles(); story = []
    story.extend([
        Spacer(1, 35 * mm),
        Paragraph(str(report.get("title") or "Bill of Quantities"), styles["title"]),
        Paragraph(str(report.get("project_name") or "Project"), styles["subtitle"]),
        Spacer(1, 12 * mm),
    ])
    metadata = [
        ["Project number", report.get("project_number") or "—"],
        ["Client", report.get("client_name") or "—"],
        ["Consultant", report.get("consultant_name") or "—"],
        ["Location", report.get("location") or "—"],
        ["Template", report.get("template_name") or "—"],
        ["Generated", str(report.get("generated_at") or "")[:19].replace("T", " ")],
    ]
    story.append(_table([[Paragraph(str(a), styles["body"]), Paragraph(str(b), styles["body"])] for a, b in metadata], [42 * mm, 116 * mm], header=False, font_size=8))
    story.append(PageBreak())

    story.append(Paragraph("Main Summary", styles["h1"]))
    currency = str(report.get("currency") or "Rs")
    summary_rows = [["Bill", "Description", "Items", "Amount"]]
    for bill in report.get("bills") or []:
        summary_rows.append([bill.get("bill_no"), bill.get("name"), bill.get("item_count"), _money(bill.get("subtotal"), currency)])
    totals = report.get("summary") or {}
    summary_rows.extend([
        ["", "Subtotal", "", _money(totals.get("subtotal"), currency)],
        ["", f"VAT ({float(report.get('vat_percentage') or 0):g}%)", "", _money(totals.get("vat"), currency)],
        ["", "Grand Total", "", _money(totals.get("grand_total"), currency)],
    ])
    story.append(_table(summary_rows, [18 * mm, 93 * mm, 18 * mm, 35 * mm]))
    story.append(Spacer(1, 7 * mm))
    story.append(Paragraph(f"Ready rows: {totals.get('ready_count', 0)} &nbsp;&nbsp; Needs Review: {totals.get('needs_review_count', 0)} &nbsp;&nbsp; Excluded: {totals.get('excluded_count', 0)}", styles["body"]))

    if report.get("include_preliminaries"):
        story.append(PageBreak()); story.append(Paragraph("Preliminaries", styles["h1"]))
        for note in report.get("preliminaries", {}).get("notes") or []:
            story.append(Paragraph(f"• {note}", styles["body"])); story.append(Spacer(1, 2 * mm))
        story.append(Spacer(1, 3 * mm)); story.append(Paragraph("Mode of payment", styles["h2"]))
        payment = [["Category", "Description"]] + [[row.get("category"), Paragraph(str(row.get("description") or ""), styles["cell"])] for row in report.get("preliminaries", {}).get("mode_of_payment") or []]
        story.append(_table(payment, [20 * mm, 144 * mm]))

    include_rates = bool(report.get("include_rates")); include_amounts = bool(report.get("include_amounts"))
    for bill in report.get("bills") or []:
        story.append(PageBreak())
        story.append(Paragraph(f"Bill {bill.get('bill_no')} – {bill.get('name')}", styles["h1"]))
        for section in bill.get("sections") or []:
            story.append(Paragraph(f"{section.get('code')} – {section.get('name')}", styles["h2"]))
            headers = ["Item", "Description", "Unit", "Qty"]
            widths = [16 * mm, 105 * mm, 14 * mm, 18 * mm]
            if include_rates:
                headers.append("Rate"); widths.append(24 * mm)
            if include_amounts:
                headers.append("Amount"); widths.append(28 * mm)
            data = [headers]
            for item in section.get("items") or []:
                style = styles["cell_review"] if item.get("status") == "needs_review" else styles["cell"]
                description = str(item.get("description") or "")
                if item.get("status") == "needs_review": description += "<br/><b>Needs Review</b>"
                row = [item.get("item_number"), Paragraph(description, style), item.get("unit"), f"{float(item.get('quantity') or 0):,.3f}".rstrip("0").rstrip(".")]
                if include_rates: row.append(_money(item.get("rate"), currency))
                if include_amounts: row.append(_money(item.get("amount"), currency))
                data.append(row)
            if include_amounts:
                data.append(["", Paragraph("<b>Section subtotal</b>", styles["cell"]), "", ""] + ([""] if include_rates else []) + [_money(section.get("subtotal"), currency)])
            story.append(_table(data, widths))
            story.append(Spacer(1, 4 * mm))

    if report.get("export_floor_mode") == "floor_breakdown":
        for floor_name, items in sorted(_floor_items(report).items()):
            story.append(PageBreak()); story.append(Paragraph(f"Floor Breakdown – {floor_name}", styles["h1"]))
            headers = ["Bill", "Section", "Item", "Description", "Unit", "Qty"]
            widths = [12 * mm, 18 * mm, 17 * mm, 88 * mm, 13 * mm, 16 * mm]
            if include_rates:
                headers.append("Rate"); widths.append(23 * mm)
            if include_amounts:
                headers.append("Amount"); widths.append(27 * mm)
            data = [headers]
            for item in items:
                style = styles["cell_review"] if item.get("status") == "needs_review" else styles["cell"]
                row = [item.get("bill_no"), item.get("section_code"), item.get("item_number"), Paragraph(str(item.get("description") or ""), style), item.get("unit"), f"{float(item.get('quantity') or 0):,.3f}".rstrip("0").rstrip(".")]
                if include_rates: row.append(_money(item.get("rate"), currency))
                if include_amounts: row.append(_money(item.get("amount"), currency))
                data.append(row)
            story.append(_table(data, widths))
            if include_amounts:
                total = sum(float(item.get("amount") or 0) for item in items)
                story.append(Spacer(1, 3 * mm)); story.append(Paragraph(f"Floor total: <b>{_money(total, currency)}</b>", styles["right"]))

    if report.get("needs_review"):
        story.append(PageBreak()); story.append(Paragraph("Needs Review", styles["h1"]))
        data = [["BOQ item", "Description", "Missing fields", "Source items"]]
        for item in report.get("needs_review") or []:
            data.append([
                item.get("boq_item_number"), Paragraph(str(item.get("description") or ""), styles["cell"]),
                ", ".join(item.get("missing_fields") or []), ", ".join(item.get("source_items") or []),
            ])
        story.append(_table(data, [22 * mm, 82 * mm, 34 * mm, 28 * mm]))

    if report.get("source_traceability"):
        story.append(PageBreak()); story.append(Paragraph("Source Traceability", styles["h1"]))
        data = [["BOQ item", "Source items", "Floor", "Status"]]
        for item in report.get("source_traceability") or []:
            data.append([item.get("boq_item_number"), ", ".join(item.get("source_items") or []), ", ".join(item.get("floors") or []), str(item.get("status") or "").replace("_", " ").title()])
        story.append(_table(data, [25 * mm, 70 * mm, 45 * mm, 26 * mm]))

    if report.get("include_signature_section"):
        story.append(PageBreak()); story.append(Paragraph("Certification", styles["h1"]))
        story.append(Spacer(1, 22 * mm))
        story.append(_table([
            ["Prepared by", "Checked by", "Approved by"],
            ["\n\nName / Signature\nDate", "\n\nName / Signature\nDate", "\n\nName / Signature\nDate"],
        ], [55 * mm, 55 * mm, 55 * mm]))

    document = _NumberedDocument(str(path), report)
    document.build(story)
