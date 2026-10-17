"""Import przyjęć z pliku CSV/XLSX — masowe przyjęcie z generowaniem HU.

Każdy wiersz = jedna pozycja przyjęcia; system dzieli ilość na palety i tworzy
HU (z ruchem PRZYJECIE).

Kolumny (nagłówki nieczułe na wielkość liter):
    indeks / ref       — wymagany indeks materiału (musi istnieć w słowniku)
    ilosc / quantity   — wymagana ilość całkowita (>0)
    palety / pallets   — liczba palet (domyślnie 1; limity: services.MAX_*)
    lot / partia       — opcjonalna partia
    data_waznosci      — opcjonalna data ważności
    dostawa            — opcjonalny numer dostawy
"""

from __future__ import annotations

from django.db import transaction

from . import services
from .imports import BAD_NUMBER, parse_int_cell, parse_locations_file, too_long
from .models import HandlingUnit, Material
from .stock_import import _clean_dash, _find_expiry, _get, _norm, _parse_date


@transaction.atomic
def import_receipts(filename: str, data: bytes, user):
    """Tworzy przyjęcia (HU) z pliku. Zwraca podsumowanie i błędy.

    Dwa przebiegi (US-002): najpierw walidacja wszystkich wierszy i limitu palet
    na plik, dopiero potem zapis — plik ponad limit nie zużywa numerów HU.
    """
    rows = parse_locations_file(filename, data)
    errors: list[str] = []
    planned = []

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
            errors.append(f"Wiersz {i} ({ref}): {BAD_NUMBER} w kolumnie ilość.")
            continue
        if not total or total < 1:
            errors.append(f"Wiersz {i} ({ref}): ilość musi być dodatnia.")
            continue

        pallets_raw = _get(row, "palety", "pallets", "liczba palet")
        try:
            pallets = parse_int_cell(pallets_raw) or 1
        except (TypeError, ValueError):
            errors.append(f"Wiersz {i} ({ref}): {BAD_NUMBER} w kolumnie palety.")
            continue
        if pallets < 1:
            pallets = 1

        lot = _clean_dash(_get(row, "lot", "partia"))
        delivery = _clean_dash(_get(row, "dostawa", "delivery"))
        problem = too_long(HandlingUnit, "lot", lot, "partia") or too_long(
            HandlingUnit, "delivery_ref", delivery, "numer dostawy"
        )
        if problem:
            errors.append(f"Wiersz {i} ({ref}): {problem} — pominięto.")
            continue
        try:
            expiry = _parse_date(_find_expiry(row))
        except ValueError as exc:
            errors.append(f"Wiersz {i} ({ref}): {exc}.")
            continue

        try:
            quantities = services.split_quantity(total, pallets)
        except services.WMSError as exc:
            errors.append(f"Wiersz {i} ({ref}): {exc}")
            continue
        planned.append((i, ref, material, quantities, lot, expiry, delivery))

    pallets_total = sum(len(p[3]) for p in planned)
    limit = services.hu_per_import_limit()
    if pallets_total > limit:
        errors.insert(
            0,
            f"Plik tworzyłby {pallets_total} palet — limit jednego importu to "
            f"{limit}. Podziel plik; nic nie zapisano.",
        )
        return {"created_hus": 0, "pallets": 0, "errors": errors}

    # Materiały blokujemy i odczytujemy na nowo przed zapisem: między przebiegami
    # ktoś mógł zmienić limit na paletę albo usunąć materiał bez palet.
    # US-050: `no_key` (FOR NO KEY UPDATE) — nadal blokuje zmianę i usunięcie materiału,
    # ale nie wstawianie palet z kluczem obcym (FOR KEY SHARE). Zwykłe FOR UPDATE dawało
    # deadlock z równoległym przyjęciem: licznik → materiał kontra materiał → licznik.
    fresh = {
        m.pk: m
        for m in Material.objects.select_for_update(no_key=True).filter(
            pk__in={p[2].pk for p in planned}
        )
    }
    budget = services.DemoBudget()  # US-016: jedno liczenie na plik, nie na wiersz
    valid: list[services.ReceiptPlan] = []
    for i, ref, stale, quantities, lot, expiry, delivery in planned:
        material = fresh.get(stale.pk)
        if material is None:
            errors.append(f"Wiersz {i}: materiał '{ref}' został usunięty — pominięto.")
            continue
        plan = services.ReceiptPlan(material, quantities, lot, expiry, delivery)
        try:
            services.validate_receipt(plan, budget=budget)
        except services.WMSError as exc:
            errors.append(f"Wiersz {i} ({ref}): {exc}")
            continue
        valid.append(plan)
    # US-050: cały plik jednym zapisem — licznik numerów HU blokowany raz i krótko.
    created_hus = len(services.create_received_hus(valid, user=user)) if valid else 0

    return {
        "created_hus": created_hus,
        "pallets": created_hus,
        "errors": errors,
    }
