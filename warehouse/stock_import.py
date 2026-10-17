"""Import stanu początkowego (istniejących palet/HU) z pliku CSV/XLSX.

Obsługiwane kolumny (nazwy nagłówków nieczułe na wielkość liter; elastyczne):
    HU / numer hu      — opcjonalny własny numer palety; pusty → generowany
    REF / indeks       — wymagany indeks materiału
    nazwa / name       — nazwa materiału (używana przy auto-tworzeniu materiału)
    ilosc / quantity   — opcjonalna ilość (pusta → 0, do uzupełnienia korektą)
    lokalizacja        — kod lokalizacji; "Przyjęcia"/"-"/puste → strefa przyjęć
    partia / lot       — opcjonalna partia ("-" = brak)
    data ważności      — opcjonalna data ważności ("-" = brak)
"""

from __future__ import annotations

from datetime import date, datetime

from django.db import transaction
from django.db.models import Count, F, Q

from . import services
from .imports import (
    BAD_NUMBER,
    get_or_create_ci,
    parse_int_cell,
    parse_locations_file,
    too_long,
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


def _over_capacity_codes(location_pks: set[int]) -> list[str]:
    """Kody lokalizacji z przekroczoną pojemnością — jednym zapytaniem
    (ta sama reguła co `Location.occupancy` / `location_over_capacity`)."""
    active = Q(handling_units__quantity__gt=0) & ~Q(
        handling_units__status=HUStatus.PUSTY
    )
    return list(
        Location.objects.filter(pk__in=location_pks, capacity__gt=0)
        .annotate(occ=Count("handling_units", filter=active))
        .filter(occ__gt=F("capacity"))
        .order_by("code")
        .values_list("code", flat=True)
    )


def _import_movement(hu: HandlingUnit, user) -> dict:
    return {
        "type": MovementType.PRZYJECIE,
        "handling_unit": hu,
        "material": hu.material,
        "quantity_delta": hu.quantity,
        "location_to": hu.location,
        "note": (
            "Import stanu początkowego"
            if hu.quantity
            else "Import stanu początkowego (ilość do uzupełnienia)"
        ),
        "created_by": user,
    }


@transaction.atomic
def import_stock(filename: str, data: bytes, user, default_unit_code: str = "PCS"):
    """Importuje stan początkowy. Zwraca słownik z podsumowaniem i błędami."""
    rows = parse_locations_file(filename, data)
    # US-002 / R3: każdy wiersz tworzy jedną paletę — plik ponad limit odrzucamy
    # w całości, zanim powstanie pierwszy HU (blokada licznika numeracji).
    if len(rows) > services.MAX_HU_PER_IMPORT:
        return {
            "created": 0,
            "materials_created": 0,
            "locations_created": 0,
            "zero_qty": 0,
            "over_capacity": [],
            "errors": [
                f"Plik ma {len(rows)} wierszy — limit jednego importu stanów to "
                f"{services.MAX_HU_PER_IMPORT} palet. Podziel plik; nic nie zapisano."
            ],
        }
    unit, _ = Unit.objects.get_or_create(code=default_unit_code)
    budget = services.DemoBudget()

    created = 0
    zero_qty = 0
    touched_locations: set[int] = set()
    materials_created: set[str] = set()
    locations_created: set[str] = set()
    errors: list[str] = []

    pending: list[HandlingUnit] = []

    for i, row in enumerate(rows, start=2):  # wiersz 1 = nagłówek
        ref = _norm(_get(row, "ref", "indeks", "index", "material"))
        if not ref:
            errors.append(f"Wiersz {i}: brak indeksu (REF) — pominięto.")
            continue

        name = _norm(_get(row, "nazwa", "name")) or ref

        # Ilość zwykle nieznana przy imporcie — domyślnie 0, uzupełniana
        # później ręcznie w aplikacji (Korekta ilości). Kolumna opcjonalna.
        qty_raw = _get(row, "ilosc", "ilość", "quantity", "qty")
        try:
            qty = parse_int_cell(qty_raw) or 0
        except ValueError:
            errors.append(
                f"Wiersz {i} ({ref}): {BAD_NUMBER} w kolumnie ilość '{qty_raw}'."
            )
            continue
        if qty < 0:
            qty = 0
        if qty > services.MAX_RECEIPT_QUANTITY:
            errors.append(
                f"Wiersz {i} ({ref}): ilość ponad {services.MAX_RECEIPT_QUANTITY} — "
                "pominięto."
            )
            continue

        loc_raw = _norm(_get(row, "lokalizacja", "location", "lok"))
        lot = _clean_dash(_get(row, "partia", "lot"))
        hu_number = _norm(_get(row, "hu", "numer hu"))
        # US-013: długości sprawdzamy, zanim cokolwiek powstanie (materiał, lokalizacja).
        problem = (
            too_long(Material, "index", ref, "indeks")
            or too_long(Material, "name", name, "nazwa")
            or too_long(Location, "code", loc_raw, "kod lokalizacji")
            or too_long(HandlingUnit, "lot", lot, "partia")
            or too_long(HandlingUnit, "number", hu_number, "numer HU")
        )
        if problem:
            errors.append(f"Wiersz {i} ({ref[:40]}): {problem} — pominięto.")
            continue
        try:
            expiry = _parse_date(_find_expiry(row))
        except ValueError as exc:
            errors.append(f"Wiersz {i} ({ref}): {exc}.")
            continue
        if hu_number:
            if HandlingUnit.objects.filter(number__iexact=hu_number).exists():
                errors.append(f"Wiersz {i}: HU '{hu_number}' już istnieje — pominięto.")
                continue

        receiving = loc_raw.lower() in RECEIVING_TOKENS
        new_location = (
            budget.limited
            and not receiving
            and not Location.objects.filter(code__iexact=loc_raw).exists()
        )
        try:
            budget.take(hus=1, locations=int(new_location))
        except services.WMSError as exc:
            errors.append(f"Wiersz {i}: {exc}")
            continue

        material, m_created = get_or_create_ci(
            Material, "index", ref, {"name": name, "unit": unit}
        )
        if m_created:
            materials_created.add(ref)

        location = None
        status = HUStatus.DO_ULOZENIA
        if not receiving:
            location, l_created = get_or_create_ci(
                Location, "code", loc_raw, {"type": LocationType.ZAPAS}
            )
            if l_created:
                locations_created.add(loc_raw)
            status = HUStatus.ZMAGAZYNOWANY
            touched_locations.add(location.pk)

        hu = HandlingUnit(
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
        if hu_number:
            # Numer z pliku zapisujemy od razu — kolejne wiersze sprawdzają duplikat w bazie.
            hu.save()
            StockMovement.objects.create(**_import_movement(hu, user))
        else:
            # US-050 (przegląd [DB]): numer z licznika nadajemy po pętli jedną
            # rezerwacją — licznik nie jest blokowany przez cały import.
            pending.append(hu)
        created += 1
        if not qty:
            zero_qty += 1

    if pending:
        for hu, number in zip(
            pending, services.reserve_hu_numbers(len(pending)), strict=True
        ):
            hu.number = number
        HandlingUnit.objects.bulk_create(pending)
        StockMovement.objects.bulk_create(
            StockMovement(**_import_movement(hu, user)) for hu in pending
        )

    return {
        "created": created,
        "materials_created": len(materials_created),
        "locations_created": len(locations_created),
        "zero_qty": zero_qty,
        "over_capacity": _over_capacity_codes(touched_locations),
        "errors": errors,
    }
