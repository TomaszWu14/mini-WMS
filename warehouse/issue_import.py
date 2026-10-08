"""Import zleceń wydania (dokumentów) z pliku CSV/XLSX.

Kolumny (nagłówki nieczułe na wielkość liter):
    indeks / ref       — wymagany indeks materiału (musi istnieć w słowniku)
    ilosc / quantity   — wymagana ilość (>0)
    referencja / dokument — opcjonalna; wiersze o tej samej wartości trafiają
                            do jednego dokumentu (grupowanie). Brak kolumny =
                            jeden dokument z referencją z formularza.
"""

from __future__ import annotations

from django.db import transaction

from . import services
from .imports import parse_int_cell, parse_locations_file
from .models import IssueDocument, IssueLine, Material


def _norm(value) -> str:
    return "" if value is None else str(value).strip()


def _get(row, *keys):
    for key in keys:
        if key in row and row[key] not in (None, ""):
            return row[key]
    return None


@transaction.atomic
def import_issue_orders(filename: str, data: bytes, user, default_reference: str = ""):
    """Tworzy dokumenty wydania z pliku. Zwraca podsumowanie i błędy."""
    rows = parse_locations_file(filename, data)

    groups: dict[str, list] = {}
    order: list[str] = []
    errors: list[str] = []

    for i, row in enumerate(rows, start=2):  # wiersz 1 = nagłówek
        ref = _norm(_get(row, "indeks", "ref", "index", "material"))
        if not ref:
            errors.append(f"Wiersz {i}: brak indeksu — pominięto.")
            continue
        qty_raw = _get(row, "ilosc", "ilość", "quantity", "qty")
        try:
            qty = parse_int_cell(qty_raw)
        except (TypeError, ValueError):
            errors.append(f"Wiersz {i} ({ref}): zła ilość '{qty_raw}'.")
            continue
        if not qty or qty < 1:
            errors.append(f"Wiersz {i} ({ref}): ilość musi być dodatnia.")
            continue
        material = Material.objects.filter(index__iexact=ref).first()
        if material is None:
            errors.append(f"Wiersz {i}: nieznany materiał '{ref}' — pominięto.")
            continue

        doc_key = _norm(_get(row, "referencja", "dokument", "reference"))
        key = doc_key or default_reference or "__single__"
        if key not in groups:
            groups[key] = []
            order.append(key)
        groups[key].append((material, qty, doc_key or default_reference))

    documents = []
    lines_count = 0
    for key in order:
        items = groups[key]
        reference = items[0][2]
        doc = services.save_with_unique_number(
            IssueDocument(reference=reference, created_by=user),
            services.generate_issue_number,
        )
        for material, qty, _ref in items:
            IssueLine.objects.create(document=doc, material=material, requested_qty=qty)
            lines_count += 1
        documents.append(doc)

    return {
        "documents": documents,
        "documents_count": len(documents),
        "lines": lines_count,
        "errors": errors,
    }
