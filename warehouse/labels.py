"""Etykiety HU i lokalizacji w PDF (A4, logo Cobalt-Sport, polskie czcionki)."""

import os
from io import BytesIO

import qrcode
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas

from .pdf_fonts import register_fonts

_GREY = colors.HexColor("#8a8f98")
_LINE = colors.HexColor("#d7dbe0")
_ACCENT = colors.HexColor("#0047ab")

# Opcjonalne logo — jeśli wgrasz plik, zostanie użyte zamiast napisu.
_LOGO_PATH = os.path.join(os.path.dirname(__file__), "static", "warehouse", "logo.png")


def _qr_image(data: str) -> ImageReader:
    qr = qrcode.QRCode(box_size=10, border=2)
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buffer = BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)
    return ImageReader(buffer)


def _fit_font(text, font, max_size, max_width, min_size=12):
    size = max_size
    while size > min_size and stringWidth(text, font, size) > max_width:
        size -= 1
    return size


def _ellipsize(text, font, size, max_width):
    """Skraca tekst wielokropkiem, gdy nie mieści się w `max_width` —
    inaczej długie nazwy/kody są ucinane krawędzią strony (drawString nie zawija)."""
    if stringWidth(text, font, size) <= max_width:
        return text
    ell = "…"
    while text and stringWidth(text + ell, font, size) > max_width:
        text = text[:-1]
    return (text + ell) if text else ell


def _draw_brand(c, x, y, bold, height=12 * mm):
    """Rysuje logo (jeśli jest plik) albo napis cobaltSPORT z akcentem marki."""
    if os.path.exists(_LOGO_PATH):
        try:
            img = ImageReader(_LOGO_PATH)
            iw, ih = img.getSize()
            w = height * iw / ih
            c.drawImage(img, x, y, w, height, preserveAspectRatio=True, mask="auto")
            return
        except Exception:
            pass
    c.setFont(bold, 18)
    c.setFillColor(_ACCENT)
    c.drawString(x, y + 2 * mm, "cobalt")
    yw = stringWidth("cobalt", bold, 18)
    c.setFillColor(colors.black)
    c.drawString(x + yw, y + 2 * mm, "SPORT")


def _draw_hu_label(c, hu, width, height, regular, bold):
    margin = 18 * mm
    content_w = width - 2 * margin

    # Najpierw zbieramy wypełnione wiersze opisowe — ich liczba decyduje o tym,
    # jak duży może być kod QR i jak gęsto rozłożyć sekcje, aby NIC nie wyszło
    # poza stronę A4 (regresja: etykieta z kompletem pól wychodziła pod stopkę).
    rows = [("Ilość", f"{hu.quantity} {hu.material.unit.code}")]
    if hu.lot:
        rows.append(("Partia", hu.lot))
    if hu.delivery_ref:
        rows.append(("Dostawa", hu.delivery_ref))
    if getattr(hu, "delivery_date", None):
        rows.append(("Termin dostawy", f"{hu.delivery_date:%Y-%m-%d}"))
    if hu.expiry_date:
        rows.append(("Ważność", f"{hu.expiry_date:%Y-%m-%d}"))
    rows.append(("Przyjęto", f"{hu.created_at:%Y-%m-%d %H:%M}"))

    # Marka u góry
    _draw_brand(c, margin, height - margin - 10 * mm, bold)

    top = height - margin - 22 * mm

    # Numer HU
    num_size = _fit_font(hu.number, bold, 90, content_w, 30)
    c.setFillColor(colors.black)
    c.setFont(bold, num_size)
    number_bottom = top - num_size * 0.9
    c.drawString(margin, number_bottom, hu.number)

    # Rozmiary wartości w sekcjach zależą od długości tekstu.
    val1 = _fit_font(hu.material.index, bold, 48, content_w, 22)
    val2 = _fit_font(hu.material.name, bold, 42, content_w, 22)

    # Stopka jest na wysokości `margin`; nad nią zostawiamy zapas.
    floor = margin + 12 * mm
    # Pionowy budżet od dołu numeru HU do podłogi na: QR + 2 sekcje + N wierszy.
    budget = (number_bottom - 8 * mm) - floor
    n = len(rows)

    # Drabinka presetów od najbardziej przestronnego do najciaśniejszego:
    # (QR mm, odstęp etykieta→wartość mm, odstęp sekcji mm, krok wiersza mm, font wiersza).
    # Wybieramy PIERWSZY, który mieści całość — dzięki temu etykieta nigdy nie
    # wychodzi pod stopkę, niezależnie od liczby wypełnionych pól.
    presets = [
        (78, 12, 11, 14, 22),
        (72, 11, 10, 13, 21),
        (66, 10, 9, 12, 19),
        (60, 9, 8, 11, 18),
        (54, 8, 7, 10, 16),
        (48, 7, 7, 9, 15),
        (42, 6, 6, 8, 14),
    ]

    def pt_to_mm(pt):
        return pt * 25.4 / 72.0

    def total_needed(qr, label_gap, gap, step):
        # Musi odpowiadać kolejności rysowania poniżej.
        sec = (label_gap + pt_to_mm(val1 * 0.2) + 2 * gap) + (
            label_gap + pt_to_mm(val2 * 0.2) + 2 * gap
        )
        # qr + odstęp pod QR (12mm) + sekcje + (n-1) kroków do ostatniej linii bazowej
        return qr + 12 + sec + max(0, n - 1) * step

    chosen = presets[-1]
    for p in presets:
        qr, label_gap, gap, step, _font = p
        if total_needed(qr, label_gap, gap, step) <= budget / mm:
            chosen = p
            break
    qr_size = chosen[0] * mm
    sec_label_gap = chosen[1] * mm
    sec_gap = chosen[2] * mm
    row_step = chosen[3] * mm
    row_font = chosen[4]

    # QR wyśrodkowany
    qr_y = number_bottom - 8 * mm - qr_size
    c.drawImage(
        _qr_image(hu.number),
        (width - qr_size) / 2,
        qr_y,
        qr_size,
        qr_size,
        preserveAspectRatio=True,
    )

    y = qr_y - 12 * mm

    def section(label, value, size):
        nonlocal y
        c.setFillColor(_GREY)
        c.setFont(regular, 15)
        c.drawString(margin, y, label.upper())
        y -= sec_label_gap
        c.setFillColor(colors.black)
        c.setFont(bold, size)
        c.drawString(margin, y - size * 0.2, _ellipsize(value, bold, size, content_w))
        y -= size * 0.2 + sec_gap
        c.setStrokeColor(_LINE)
        c.setLineWidth(1)
        c.line(margin, y, width - margin, y)
        y -= sec_gap

    section("Materiał", hu.material.index, val1)
    section("Nazwa", hu.material.name, val2)

    def info_row(key, value):
        nonlocal y
        c.setFont(regular, row_font)
        c.setFillColor(_GREY)
        c.drawString(margin, y, f"{key}: ")
        kw = stringWidth(f"{key}: ", regular, row_font)
        c.setFillColor(colors.black)
        c.drawString(
            margin + kw,
            y,
            _ellipsize(str(value), regular, row_font, content_w - kw),
        )
        y -= row_step

    for key, value in rows:
        info_row(key, value)

    c.setFillColor(_GREY)
    c.setFont(regular, 10)
    c.drawString(margin, margin, "cobaltSPORT · mini-WMS")


def hu_label_pdf(hu) -> bytes:
    """Etykieta jednego HU (A4)."""
    return hu_labels_pdf([hu])


def hu_labels_pdf(handling_units) -> bytes:
    """Etykiety wielu HU — po jednej na stronę A4."""
    regular, bold = register_fonts()
    buffer = BytesIO()
    width, height = A4
    c = canvas.Canvas(buffer, pagesize=A4)
    items = list(handling_units)
    if not items:
        c.setFont(regular, 14)
        c.drawString(20 * mm, height - 30 * mm, "Brak HU do wydruku.")
        c.showPage()
    for hu in items:
        _draw_hu_label(c, hu, width, height, regular, bold)
        c.showPage()
    c.save()
    buffer.seek(0)
    return buffer.read()


def location_labels_pdf(locations) -> bytes:
    """Etykiety lokalizacji (kod + QR) na arkuszach A4, 2 kolumny × 5 wierszy."""
    regular, bold = register_fonts()
    buffer = BytesIO()
    width, height = A4
    c = canvas.Canvas(buffer, pagesize=A4)

    cols, rows = 2, 5
    margin = 12 * mm
    gap = 6 * mm
    cell_w = (width - 2 * margin - (cols - 1) * gap) / cols
    cell_h = (height - 2 * margin - (rows - 1) * gap) / rows

    per_page = cols * rows
    items = list(locations)
    if not items:
        # Early-return — bez tego końcowe showPage() dorzucałoby pustą stronę.
        c.setFont(regular, 12)
        c.drawString(margin, height - margin - 10, "Brak lokalizacji do wydruku.")
        c.showPage()
        c.save()
        buffer.seek(0)
        return buffer.read()

    for index, loc in enumerate(items):
        pos = index % per_page
        if index and pos == 0:
            c.showPage()
        col = pos % cols
        row = pos // cols
        x = margin + col * (cell_w + gap)
        y = height - margin - (row + 1) * cell_h - row * gap

        c.rect(x, y, cell_w, cell_h)
        qr_size = cell_h - 12 * mm
        c.drawImage(
            _qr_image(loc.code),
            x + 5 * mm,
            y + 6 * mm,
            qr_size,
            qr_size,
            preserveAspectRatio=True,
        )
        text_x = x + qr_size + 10 * mm
        # Dostępna szerokość na tekst — długie kody skalujemy, by nie wychodziły
        # poza komórkę ani nie nachodziły na sąsiednią etykietę.
        text_w = x + cell_w - text_x - 4 * mm
        c.setFillColor(colors.black)
        c.setFont(bold, _fit_font(loc.code, bold, 18, text_w, 8))
        c.drawString(text_x, y + cell_h - 14 * mm, loc.code)
        type_label = loc.get_type_display()
        c.setFont(regular, _fit_font(type_label, regular, 11, text_w, 7))
        c.drawString(text_x, y + cell_h - 22 * mm, type_label)

    c.showPage()
    c.save()
    buffer.seek(0)
    return buffer.read()
