"""Rejestracja czcionek z polskimi znakami (DejaVu Sans) dla PDF."""

import os
from functools import lru_cache

from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

FONT_DIR = os.path.join(os.path.dirname(__file__), "fonts")
REGULAR = "DejaVuSans"
BOLD = "DejaVuSans-Bold"


@lru_cache(maxsize=1)
def register_fonts():
    """Rejestruje czcionki (raz). Zwraca (regular, bold).

    Gdy plików czcionek brakuje, zamiast 500 przy generowaniu PDF wracamy do
    wbudowanej Helvetiki (bez polskich diakrytyków, ale dokument powstanie)."""
    try:
        pdfmetrics.registerFont(
            TTFont(REGULAR, os.path.join(FONT_DIR, "DejaVuSans.ttf"))
        )
        pdfmetrics.registerFont(
            TTFont(BOLD, os.path.join(FONT_DIR, "DejaVuSans-Bold.ttf"))
        )
        return REGULAR, BOLD
    except Exception:
        return "Helvetica", "Helvetica-Bold"
