"""Import przyjęć z pliku CSV/XLSX — masowe przyjęcie z generowaniem HU.

Każdy wiersz = jedna pozycja przyjęcia; system dzieli ilość na palety i tworzy
HU (z ruchem PRZYJECIE).

Kolumny (nagłówki nieczułe na wielkość liter):
    indeks / ref       — wymagany indeks materiału (musi istnieć w słowniku)
    ilosc / quantity   — wymagana ilość całkowita (>0)
    palety / pallets   — liczba palet (domyślnie 1)
    lot / partia       — opcjonalna partia
    data_waznosci      — opcjonalna data ważności
    dostawa            — opcjonalny numer dostawy
"""

from __future__ import annotations

from django.db import transaction

from . import services
from .imports import parse_int_cell, parse_locations_file
from .models import Material
from .stock_import import _clean_dash, _find_expiry, _get, _norm, _parse_date


@transaction.atomic
def import_receipts(filename: str, data: bytes, user):
    """Tworzy przyjęcia (HU) z pliku. Zwraca podsumowanie i błędy."""
    rows = parse_locations_file(filename, data)
    created_hus = 0
    pallets_total = 0
    errors: list[str] = []

    for i, row in enumerate(rows, start=2):  # wiersz 1 = nagłówek
        ref = _norm(_get(row, "indeks", "ref", "index", "material"))
        if not ref:
            errors.append(f"Wiersz {i}: brak indeksu — pominięto.")
            continue
        material = Material.objects.filter(index__iexact=ref).first()
        if material is None:
            errors.append(f"Wiersz {i}: nieznany materiał '{ref}' — pominięto.")
            continue

        try:
            total = parse_int_cell(_get(row, "ilosc", "ilość", "quantity", "qty"))
        except (TypeError, ValueError):
            errors.append(f"Wiersz {i} ({ref}): zła ilość.")
            continue
        if not total or total < 1:
            errors.append(f"Wiersz {i} ({ref}): ilość musi być dodatnia.")
            continue

        pallets_raw = _get(row, "palety", "pallets", "liczba palet")
        try:
            pallets = parse_int_cell(pallets_raw) or 1
        except (TypeError, ValueError):
            errors.append(f"Wiersz {i} ({ref}): zła liczba palet.")
            continue
        if pallets < 1:
            pallets = 1

        lot = _clean_dash(_get(row, "lot", "partia"))
        delivery = _clean_dash(_get(row, "dostawa", "delivery"))
        try:
            expiry = _parse_date(_find_expiry(row))
        except ValueError as exc:
            errors.append(f"Wiersz {i} ({ref}): {exc}.")
            continue

        try:
            quantities = services.split_quantity(total, pallets)
            result = services.receive_material(
                material=material,
                quantities=quantities,
                user=user,
                lot=lot,
                expiry_date=expiry,
                delivery_ref=delivery,
            )
        except services.WMSError as exc:
            errors.append(f"Wiersz {i} ({ref}): {exc}")
            continue

        created_hus += len(result.handling_units)
        pallets_total += pallets

    return {
        "created_hus": created_hus,
        "pallets": pallets_total,
        "errors": errors,
    }
