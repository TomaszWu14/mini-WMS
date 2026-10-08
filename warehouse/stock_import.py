"""Import stanu początkowego (istniejących palet/HU) z pliku CSV/XLSX.

Obsługiwane kolumny (nazwy nagłówków nieczułe na wielkość liter; elastyczne):
    HU / numer hu      — opcjonalny własny numer palety; pusty → generowany
    REF / indeks       — wymagany indeks materiału
    nazwa / name       — nazwa materiału (używana przy auto-tworzeniu materiału)
    ilosc / quantity   — opcjonalna ilość (pusta → 1)
    lokalizacja        — kod lokalizacji; "Przyjęcia"/"-"/puste → strefa przyjęć
    partia / lot       — opcjonalna partia ("-" = brak)
    data ważności      — opcjonalna data ważności ("-" = brak)
"""

from __future__ import annotations

from datetime import date, datetime

from django.db import transaction

from . import services
from .imports import (
    get_or_create_ci,
    parse_int_cell,
    parse_locations_file,
)
from .models import (
    HandlingUnit,
    HUStatus,
    Location,
    LocationType,
    Material,
    MovementType,
    StockMovement,
    Unit,
)

# Wartości lokalizacji traktowane jako "strefa przyjęć" (HU bez lokalizacji).
RECEIVING_TOKENS = {
    "",
    "-",
    "–",
    "—",
    "przyjecia",
    "przyjęcia",
    "przyjecie",
    "przyjęcie",
    "strefa przyjec",
    "strefa przyjęć",
    "receiving",
    "wejscie",
    "wejście",
}


def _norm(value) -> str:
    return "" if value is None else str(value).strip()


def _clean_dash(value) -> str:
    text = _norm(value)
    return "" if text in {"-", "–", "—"} else text


def _get(row: dict, *keys):
    for key in keys:
        if key in row and row[key] not in (None, ""):
            return row[key]
    return None


def _find_expiry(row: dict):
    for key, value in row.items():
        if key and key.strip().lower().startswith("data"):
            return value
    return _get(row, "expiry", "waznosc", "ważność")


def _parse_date(value):
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = _clean_dash(value)
    if not text:
        return None
    for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%d-%m-%Y", "%Y/%m/%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"nieczytelna data ważności '{text}'")


@transaction.atomic
def import_stock(filename: str, data: bytes, user, default_unit_code: str = "PCS"):
    """Importuje stan początkowy. Zwraca słownik z podsumowaniem i błędami."""
    rows = parse_locations_file(filename, data)
    unit, _ = Unit.objects.get_or_create(code=default_unit_code)

    created = 0
    materials_created: set[str] = set()
    locations_created: set[str] = set()
    errors: list[str] = []

    for i, row in enumerate(rows, start=2):  # wiersz 1 = nagłówek
        ref = _norm(_get(row, "ref", "indeks", "index", "material"))
        if not ref:
            errors.append(f"Wiersz {i}: brak indeksu (REF) — pominięto.")
            continue

        name = _norm(_get(row, "nazwa", "name")) or ref
        material, m_created = get_or_create_ci(
            Material, "index", ref, {"name": name, "unit": unit}
        )
        if m_created:
            materials_created.add(ref)

        # Ilość zwykle nieznana przy imporcie — domyślnie 0, uzupełniana
        # później ręcznie w aplikacji (Korekta ilości). Kolumna opcjonalna.
        qty_raw = _get(row, "ilosc", "ilość", "quantity", "qty")
        try:
            qty = parse_int_cell(qty_raw) or 0
        except ValueError:
            errors.append(f"Wiersz {i} ({ref}): zła ilość '{qty_raw}'.")
            continue
        if qty < 0:
            qty = 0

        loc_raw = _norm(_get(row, "lokalizacja", "location", "lok"))
        location = None
        status = HUStatus.DO_ULOZENIA
        if loc_raw.lower() not in RECEIVING_TOKENS:
            location, l_created = get_or_create_ci(
                Location, "code", loc_raw, {"type": LocationType.ZAPAS}
            )
            if l_created:
                locations_created.add(loc_raw)
            status = HUStatus.ZMAGAZYNOWANY

        lot = _clean_dash(_get(row, "partia", "lot"))
        try:
            expiry = _parse_date(_find_expiry(row))
        except ValueError as exc:
            errors.append(f"Wiersz {i} ({ref}): {exc}.")
            continue

        hu_number = _norm(_get(row, "hu", "numer hu"))
        if hu_number:
            if HandlingUnit.objects.filter(number__iexact=hu_number).exists():
                errors.append(f"Wiersz {i}: HU '{hu_number}' już istnieje — pominięto.")
                continue
        else:
            hu_number = services.generate_hu_number()

        hu = HandlingUnit.objects.create(
            number=hu_number,
            material=material,
            quantity=qty,
            lot=lot,
            expiry_date=expiry,
            status=status,
            location=location,
            delivery_ref="IMPORT",
            created_by=user,
        )
        StockMovement.objects.create(
            type=MovementType.PRZYJECIE,
            handling_unit=hu,
            material=material,
            quantity_delta=qty,
            location_to=location,
            note=(
                "Import stanu początkowego"
                if qty
                else "Import stanu początkowego (ilość do uzupełnienia)"
            ),
            created_by=user,
        )
        created += 1

    return {
        "created": created,
        "materials_created": len(materials_created),
        "locations_created": len(locations_created),
        "errors": errors,
    }
