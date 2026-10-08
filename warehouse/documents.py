"""Wydruk dokumentu wydania (WZ) do PDF."""

from io import BytesIO

from django.utils import timezone
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

from .pdf_fonts import register_fonts


def issue_document_pdf(doc) -> bytes:
    """Zwraca bajty PDF dokumentu wydania (WZ) z pozycjami."""
    regular, bold = register_fonts()
    buffer = BytesIO()
    width, height = A4
    c = canvas.Canvas(buffer, pagesize=A4)
    margin = 18 * mm
    y = height - margin

    # Marka cobaltSPORT
    c.setFont(bold, 14)
    c.setFillColor(colors.HexColor("#0047ab"))
    c.drawString(margin, y, "cobalt")
    yw = c.stringWidth("cobalt", bold, 14)
    c.setFillColor(colors.black)
    c.drawString(margin + yw, y, "SPORT")
    y -= 9 * mm

    # Nagłówek
    c.setFont(bold, 20)
    c.drawString(margin, y, "WZ — Wydanie zewnętrzne")
    c.setFont(bold, 14)
    c.drawRightString(width - margin, y, doc.number)
    y -= 10 * mm

    c.setFont(regular, 10)
    created = timezone.localtime(doc.created_at).strftime("%Y-%m-%d %H:%M")
    info = [
        f"Numer: {doc.number}",
        f"Referencja: {doc.reference or '—'}",
        f"Status: {doc.get_status_display()}",
        f"Utworzono: {created}",
        f"Operator: {doc.created_by.username if doc.created_by else '—'}",
    ]
    if doc.completed_at:
        info.append(
            f"Zrealizowano: {timezone.localtime(doc.completed_at):%Y-%m-%d %H:%M}"
        )
    for line in info:
        c.drawString(margin, y, line)
        y -= 6 * mm

    y -= 4 * mm

    # Nagłówek tabeli
    cols_x = [
        margin,
        margin + 14 * mm,
        margin + 70 * mm,
        margin + 120 * mm,
        margin + 150 * mm,
    ]
    headers = ["Lp.", "Indeks", "Nazwa", "Żądane", "Wydane"]

    def draw_table_header(top):
        c.setFont(bold, 10)
        c.setFillColor(colors.HexColor("#e2e8f0"))
        c.rect(margin, top - 2 * mm, width - 2 * margin, 8 * mm, fill=1, stroke=0)
        c.setFillColor(colors.black)
        for x, h in zip(cols_x, headers, strict=True):
            c.drawString(x + 1 * mm, top, h)
        c.setFont(regular, 10)
        return top - 9 * mm

    y = draw_table_header(y)
    for i, line in enumerate(
        doc.lines.select_related("material", "material__unit"), start=1
    ):
        if y < margin + 30 * mm:
            c.showPage()
            y = height - margin
            # Nowa strona — powtórz nagłówek kolumn (inaczej dalsze strony są
            # nieczytelne: dane bez kontekstu kolumn).
            y = draw_table_header(y)
        unit = line.material.unit.code
        c.drawString(cols_x[0] + 1 * mm, y, str(i))
        c.drawString(cols_x[1] + 1 * mm, y, line.material.index[:22])
        c.drawString(cols_x[2] + 1 * mm, y, line.material.name[:28])
        c.drawRightString(cols_x[4] - 4 * mm, y, f"{line.requested_qty} {unit}")
        c.drawRightString(width - margin - 1 * mm, y, f"{line.picked_qty} {unit}")
        y -= 6.5 * mm

    # Podpisy
    y = max(y, margin + 25 * mm)
    y -= 14 * mm
    c.line(margin, y, margin + 60 * mm, y)
    c.line(width - margin - 60 * mm, y, width - margin, y)
    c.setFont(regular, 8)
    c.drawString(margin, y - 4 * mm, "Wydał (podpis)")
    c.drawRightString(width - margin, y - 4 * mm, "Odebrał (podpis)")

    c.setFont(regular, 8)
    c.drawCentredString(width / 2, margin - 4 * mm, "cobaltSPORT · mini-WMS")
    c.showPage()
    c.save()
    buffer.seek(0)
    return buffer.read()
