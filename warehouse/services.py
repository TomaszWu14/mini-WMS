"""Logika biznesowa mini-WMS — przyjęcia, alokacje, korekty, picking.

Wszystkie operacje zmieniające stan zapisują ruch w `StockMovement`
(audyt: kto + kiedy) i działają w transakcji.
"""

from __future__ import annotations

from dataclasses import dataclass

from django.db import IntegrityError, transaction
from django.db.models import Case, F, IntegerField, Sum, Value, When
from django.utils import timezone

from .models import (
    AdjustReason,
    HandlingUnit,
    HUNumberingConfig,
    HUStatus,
    IssueDocument,
    IssueStatus,
    Location,
    LocationType,
    Material,
    MovementType,
    StockMovement,
    StocktakeLine,
    StocktakeSheet,
    StocktakeStatus,
)


class WMSError(Exception):
    """Błąd reguły biznesowej (np. brak stanu, zła ilość)."""


def save_with_unique_number(instance, number_fn, *, field="number", attempts=6):
    """Zapisuje obiekt nadając unikalny numer, ponawiając przy kolizji.

    Numeratory oparte na zliczaniu (WZ/SP) nie są w pełni odporne na wyścig —
    dwa równoległe żądania mogą wygenerować ten sam numer i drugi `save()`
    dostanie IntegrityError (pole `number` jest unique). Każda próba działa w
    osobnym savepoincie, więc po kolizji można bezpiecznie spróbować ponownie.
    """
    for _ in range(attempts):
        setattr(instance, field, number_fn())
        try:
            with transaction.atomic():
                instance.save()
            return instance
        except IntegrityError:
            continue
    raise WMSError("Nie udało się nadać unikalnego numeru — spróbuj ponownie.")


# --- Numeracja HU ------------------------------------------------------------


def generate_hu_number() -> str:
    """Zwraca kolejny unikalny numer HU i zwiększa licznik (atomowo)."""
    with transaction.atomic():
        config = HUNumberingConfig.objects.select_for_update().order_by("pk").first()
        if config is None:
            config = HUNumberingConfig.objects.create()
            config = HUNumberingConfig.objects.select_for_update().get(pk=config.pk)
        number = f"{config.prefix}{config.next_number:0{config.padding}d}"
        config.next_number += 1
        config.save(update_fields=["next_number"])
    return number


# --- Podział ilości na palety -------------------------------------------------


def split_quantity(total: int, pallets: int) -> list[int]:
    """Dzieli `total` na `pallets` części równo, resztę dokłada do ostatniej."""
    if pallets < 1:
        raise WMSError("Liczba palet musi być dodatnia.")
    if total < 1:
        raise WMSError("Ilość całkowita musi być dodatnia.")
    base = total // pallets
    remainder = total - base * pallets
    quantities = [base] * pallets
    quantities[-1] += remainder
    if any(q <= 0 for q in quantities):
        raise WMSError(
            "Zbyt wiele palet dla podanej ilości — niektóre palety byłyby puste."
        )
    return quantities


# --- Przyjęcie ---------------------------------------------------------------


@dataclass
class ReceiveResult:
    handling_units: list[HandlingUnit]


@transaction.atomic
def receive_material(
    *,
    material: Material,
    quantities: list[int],
    user,
    lot: str = "",
    expiry_date=None,
    delivery_ref: str = "",
) -> ReceiveResult:
    """Tworzy HU dla zadanego materiału wg listy ilości na palety.

    Każda paleta = jeden HU ze statusem DO_ULOZENIA (czeka na alokację).
    """
    if material.max_per_pallet:
        for qty in quantities:
            if qty > material.max_per_pallet:
                raise WMSError(
                    f"Ilość {qty} przekracza maks. {material.max_per_pallet} "
                    f"na palecie dla materiału {material.index}."
                )

    created: list[HandlingUnit] = []
    for qty in quantities:
        hu = HandlingUnit.objects.create(
            number=generate_hu_number(),
            material=material,
            quantity=qty,
            lot=lot,
            expiry_date=expiry_date,
            status=HUStatus.DO_ULOZENIA,
            delivery_ref=delivery_ref,
            created_by=user,
        )
        StockMovement.objects.create(
            type=MovementType.PRZYJECIE,
            handling_unit=hu,
            material=material,
            quantity_delta=qty,
            note=f"Przyjęcie HU {hu.number}",
            created_by=user,
        )
        created.append(hu)
    return ReceiveResult(handling_units=created)


# --- Alokacja / przesunięcie -------------------------------------------------


@transaction.atomic
def allocate_hu(*, hu: HandlingUnit, location: Location, user) -> HandlingUnit:
    """Ustawia HU w lokalizacji. Pierwsza alokacja lub przesunięcie."""
    if hu.status == HUStatus.PUSTY:
        raise WMSError(f"HU {hu.number} jest pusty — nie można go ulokować.")

    previous = hu.location
    is_move = previous is not None and previous != location

    # Pojemność lokalizacji (gdy >0) — nie pozwól przepełnić miejsca. Liczymy
    # aktywne HU już tam stojące, pomijając samą przenoszoną paletę.
    if location.capacity and (previous != location):
        occupied = (
            location.handling_units.exclude(status=HUStatus.PUSTY)
            .exclude(pk=hu.pk)
            .count()
        )
        if occupied >= location.capacity:
            raise WMSError(
                f"Lokalizacja {location.code} jest pełna "
                f"(pojemność {location.capacity})."
            )

    hu.location = location
    hu.status = HUStatus.ZMAGAZYNOWANY
    hu.save(update_fields=["location", "status"])

    if previous is not None and previous != location:
        note = f"Przesunięcie {previous.code} → {location.code}"
    else:
        note = f"Alokacja do {location.code}"

    StockMovement.objects.create(
        type=MovementType.PRZESUNIECIE if is_move else MovementType.ALOKACJA,
        handling_unit=hu,
        material=hu.material,
        quantity_delta=0,
        location_from=previous,
        location_to=location,
        note=note,
        created_by=user,
    )
    return hu


# --- Korekta ilości ----------------------------------------------------------


@transaction.atomic
def correct_hu_quantity(
    *, hu: HandlingUnit, new_quantity: int, user, note: str = "", reason: str = ""
):
    """Koryguje ilość na HU (np. po inwentaryzacji). Zapisuje ruch korekty."""
    if new_quantity < 0:
        raise WMSError("Ilość nie może być ujemna.")
    delta = new_quantity - hu.quantity
    if delta == 0:
        raise WMSError("Nowa ilość jest taka sama jak obecna — brak korekty.")

    location_before = hu.location
    hu.quantity = new_quantity
    # Korekta z 0 na >0 (np. omyłkowo wyzerowany HU) musi wrócić do obiegu —
    # inaczej zostałby PUSTY z dodatnią ilością (stan-widmo).
    if new_quantity > 0 and hu.status == HUStatus.PUSTY:
        hu.status = HUStatus.DO_ULOZENIA
    _apply_empty_if_zero(hu)
    hu.save(update_fields=["quantity", "status", "location"])

    StockMovement.objects.create(
        type=MovementType.KOREKTA,
        handling_unit=hu,
        material=hu.material,
        quantity_delta=delta,
        reason=reason,
        location_from=location_before,
        location_to=hu.location,
        note=note or f"Korekta ilości HU {hu.number}",
        created_by=user,
    )
    return hu


def _apply_empty_if_zero(hu: HandlingUnit) -> None:
    """Gdy HU osiąga 0 — status PUSTY i zwolnienie lokalizacji."""
    if hu.quantity == 0:
        hu.status = HUStatus.PUSTY
        hu.location = None


# --- Przepakowanie / łączenie HU --------------------------------------------


@transaction.atomic
def repack_hu(*, source: HandlingUnit, target: HandlingUnit, quantity: int, user):
    """Przenosi ilość z jednego HU na drugie — tylko ten sam materiał.

    Łączenie palet (konsolidacja). Gdy źródło zejdzie do zera, staje się
    puste i zwalnia lokalizację.
    """
    source = HandlingUnit.objects.select_for_update().get(pk=source.pk)
    target = HandlingUnit.objects.select_for_update().get(pk=target.pk)

    if source.pk == target.pk:
        raise WMSError("Paleta źródłowa i docelowa są takie same.")
    if source.material_id != target.material_id:
        raise WMSError(
            "Różny materiał — łączyć można tylko ten sam towar "
            f"({source.material.index} ≠ {target.material.index})."
        )
    if target.status == HUStatus.PUSTY:
        raise WMSError(f"Paleta docelowa {target.number} jest pusta/zamknięta.")
    if quantity < 1:
        raise WMSError("Ilość do przepakowania musi być dodatnia.")
    if quantity > source.quantity:
        raise WMSError(
            f"Brak stanu na palecie {source.number}: dostępne {source.quantity}."
        )
    if source.lot and target.lot and source.lot != target.lot:
        raise WMSError(
            f"Różne partie (LOT {source.lot} ≠ {target.lot}) — nie można łączyć."
        )

    source_loc = source.location
    target_loc = target.location

    source.quantity -= quantity
    target.quantity += quantity
    _apply_empty_if_zero(source)
    source.save(update_fields=["quantity", "status", "location"])
    target.save(update_fields=["quantity"])

    StockMovement.objects.create(
        type=MovementType.PRZEPAKOWANIE,
        handling_unit=source,
        material=source.material,
        quantity_delta=-quantity,
        location_from=source_loc,
        location_to=target_loc,
        note=f"Przepakowanie do HU {target.number}",
        created_by=user,
    )
    StockMovement.objects.create(
        type=MovementType.PRZEPAKOWANIE,
        handling_unit=target,
        material=target.material,
        quantity_delta=quantity,
        location_to=target_loc,
        note=f"Przepakowanie z HU {source.number}",
        created_by=user,
    )
    return source, target


# --- Picking / wydania -------------------------------------------------------


def _pickable_hus(material: Material):
    """Aktywne HU danego materiału, uporządkowane wg reguły wydania.

    Kolejność: najpierw lokalizacje PICKING, potem ZAPAS, na końcu bez
    lokalizacji; w obrębie tego FEFO (data ważności rosnąco, puste daty na
    końcu), a następnie FIFO (data przyjęcia rosnąco).
    """
    location_priority = Case(
        When(location__type=LocationType.PICKING, then=Value(0)),
        When(location__type=LocationType.ZAPAS, then=Value(1)),
        default=Value(2),
        output_field=IntegerField(),
    )
    return (
        HandlingUnit.objects.filter(material=material, quantity__gt=0)
        .exclude(status=HUStatus.PUSTY)
        .annotate(_loc_priority=location_priority)
        .order_by(
            "_loc_priority",
            F("expiry_date").asc(nulls_last=True),
            "created_at",
            "number",
        )
    )


def available_quantity(material: Material) -> int:
    """Łączna dostępna ilość materiału na aktywnych HU."""
    return _pickable_hus(material).aggregate(t=Sum("quantity"))["t"] or 0


@transaction.atomic
def pick_from_hu(*, hu: HandlingUnit, quantity: int, user, document=None, line=None):
    """Zdejmuje `quantity` z konkretnego HU. Picking częściowy dozwolony."""
    hu = HandlingUnit.objects.select_for_update().get(pk=hu.pk)
    if quantity < 1:
        raise WMSError("Ilość wydania musi być dodatnia.")
    if hu.status == HUStatus.PUSTY or hu.quantity == 0:
        raise WMSError(f"HU {hu.number} jest pusty.")
    if quantity > hu.quantity:
        raise WMSError(
            f"Brak stanu na HU {hu.number}: dostępne {hu.quantity}, żądane {quantity}."
        )

    location_from = hu.location
    hu.quantity -= quantity
    _apply_empty_if_zero(hu)
    hu.save(update_fields=["quantity", "status", "location"])

    StockMovement.objects.create(
        type=MovementType.WYDANIE,
        handling_unit=hu,
        material=hu.material,
        quantity_delta=-quantity,
        location_from=location_from,
        issue_document=document,
        note=f"Wydanie z HU {hu.number}",
        created_by=user,
    )
    if line is not None:
        line.picked_qty = F("picked_qty") + quantity
        line.save(update_fields=["picked_qty"])
        line.refresh_from_db()
    return hu


@transaction.atomic
def pick_by_material(
    *, material: Material, quantity: int, user, document=None, line=None
):
    """Zdejmuje `quantity` materiału, dobierając HU wg reguły FEFO→FIFO."""
    if quantity < 1:
        raise WMSError("Ilość wydania musi być dodatnia.")
    available = available_quantity(material)
    if quantity > available:
        raise WMSError(
            f"Brak wystarczającego stanu materiału {material.index}: "
            f"dostępne {available}, żądane {quantity}."
        )

    remaining = quantity
    used: list[tuple[HandlingUnit, int]] = []
    for hu in list(_pickable_hus(material)):
        if remaining <= 0:
            break
        take = min(hu.quantity, remaining)
        pick_from_hu(hu=hu, quantity=take, user=user, document=document, line=line)
        used.append((hu, take))
        remaining -= take
    return used


@transaction.atomic
def execute_issue_document(
    *, document: IssueDocument, user, allow_partial: bool = False
) -> IssueDocument:
    """Realizuje dokument wydania.

    allow_partial=False — pełna realizacja, błąd przy braku stanu.
    allow_partial=True  — pobiera ile dostępne, zamyka z brakami (shortage).
    """
    if document.status != IssueStatus.OTWARTY:
        raise WMSError("Dokument nie jest otwarty.")

    lines = list(document.lines.select_related("material", "specific_hu"))
    if not lines:
        raise WMSError("Dokument nie ma pozycji do wydania.")

    for line in lines:
        outstanding = line.requested_qty - line.picked_qty
        if outstanding <= 0:
            continue
        specific = line.specific_hu
        if specific is not None:
            if specific.material_id != line.material_id:
                raise WMSError(
                    f"Wskazany HU {specific.number} ma inny materiał "
                    f"niż pozycja ({line.material.index})."
                )
            available = specific.quantity
            take = min(outstanding, available) if allow_partial else outstanding
            if take > 0:
                pick_from_hu(
                    hu=specific,
                    quantity=take,
                    user=user,
                    document=document,
                    line=line,
                )
        else:
            available = available_quantity(line.material)
            take = min(outstanding, available) if allow_partial else outstanding
            if take > 0:
                pick_by_material(
                    material=line.material,
                    quantity=take,
                    user=user,
                    document=document,
                    line=line,
                )

    document.status = IssueStatus.ZREALIZOWANY
    document.completed_at = timezone.now()
    document.save(update_fields=["status", "completed_at"])
    return document


def picking_plan(material: Material, quantity: int) -> dict:
    """Podpowiedź skąd pobrać (FEFO→FIFO, priorytet PICKING).

    Zwraca listę palet do pobrania i ewentualny brak (shortage).
    """
    remaining = quantity
    plan = []
    for hu in _pickable_hus(material).select_related("location"):
        if remaining <= 0:
            break
        take = min(hu.quantity, remaining)
        plan.append(
            {
                "hu": hu.number,
                "location": hu.location.code if hu.location else None,
                "take": take,
            }
        )
        remaining -= take
    return {"plan": plan, "shortage": max(0, remaining)}


@transaction.atomic
def pack_issue_document(*, document: IssueDocument, user) -> IssueDocument:
    if document.status != IssueStatus.ZREALIZOWANY:
        raise WMSError("Spakować można tylko dokument zrealizowany.")
    document.status = IssueStatus.SPAKOWANY
    document.packed_at = timezone.now()
    document.save(update_fields=["status", "packed_at"])
    return document


@transaction.atomic
def ship_issue_document(
    *, document: IssueDocument, user, carrier: str = "", tracking: str = ""
) -> IssueDocument:
    if document.status not in (IssueStatus.SPAKOWANY, IssueStatus.ZREALIZOWANY):
        raise WMSError("Wysłać można dokument zrealizowany lub spakowany.")
    document.status = IssueStatus.WYSLANY
    document.shipped_at = timezone.now()
    document.carrier = carrier
    document.tracking_number = tracking
    document.save(update_fields=["status", "shipped_at", "carrier", "tracking_number"])
    return document


# --- Numeracja dokumentów wydania -------------------------------------------


def _next_daily_number(model, prefix: str) -> str:
    """Kolejny numer dzienny jako max(istniejący sufiks)+1.

    Odporne na usunięcia (liczenie `count()` po skasowaniu rekordu nadawało
    numer, który już istniał — i ponawianie zapisu trafiało wciąż na ten sam
    zajęty numer). Wraz z save_with_unique_number daje spójną numerację.
    """
    highest = 0
    for num in model.objects.filter(number__startswith=f"{prefix}-").values_list(
        "number", flat=True
    ):
        try:
            highest = max(highest, int(num.rsplit("-", 1)[1]))
        except (ValueError, IndexError):
            continue
    return f"{prefix}-{highest + 1:03d}"


def generate_issue_number() -> str:
    """Numer dokumentu wydania: WZ + data + kolejny licznik dzienny."""
    prefix = f"WZ{timezone.localtime():%Y%m%d}"
    return _next_daily_number(IssueDocument, prefix)


# --- Spis z natury -----------------------------------------------------------


def generate_stocktake_number() -> str:
    prefix = f"SP{timezone.localtime():%Y%m%d}"
    return _next_daily_number(StocktakeSheet, prefix)


@transaction.atomic
def create_stocktake(*, location=None, user) -> StocktakeSheet:
    """Tworzy arkusz spisu z migawką stanu (aktywne HU w zakresie)."""
    sheet = save_with_unique_number(
        StocktakeSheet(location=location, created_by=user),
        generate_stocktake_number,
    )
    hus = HandlingUnit.objects.exclude(status=HUStatus.PUSTY).select_related(
        "material", "location"
    )
    if location is not None:
        hus = hus.filter(location=location)
    lines = [
        StocktakeLine(
            sheet=sheet,
            handling_unit=hu,
            material=hu.material,
            location_code=hu.location.code if hu.location else "",
            expected_qty=hu.quantity,
        )
        for hu in hus
    ]
    StocktakeLine.objects.bulk_create(lines)
    return sheet


@transaction.atomic
def close_stocktake(*, sheet: StocktakeSheet, user) -> dict:
    """Zatwierdza spis: nanosi różnice jako korekty (powód: spis z natury)."""
    # Świeży odczyt pod blokadą — status z obiektu wczytanego w widoku mógłby
    # być nieaktualny (dwa równoległe zamknięcia tego samego arkusza).
    sheet = StocktakeSheet.objects.select_for_update().get(pk=sheet.pk)
    if sheet.status == StocktakeStatus.ZAMKNIETY:
        raise WMSError("Arkusz jest już zamknięty.")

    adjusted = 0
    counted = 0
    for line in sheet.lines.select_for_update().select_related("handling_unit"):
        if line.counted_qty is None:
            continue
        counted += 1
        hu = line.handling_unit
        if hu is None:
            continue
        hu = HandlingUnit.objects.select_for_update().get(pk=hu.pk)
        if line.counted_qty != hu.quantity:
            correct_hu_quantity(
                hu=hu,
                new_quantity=line.counted_qty,
                user=user,
                note=f"Spis z natury {sheet.number}",
                reason=AdjustReason.SPIS,
            )
            adjusted += 1

    sheet.status = StocktakeStatus.ZAMKNIETY
    sheet.closed_at = timezone.now()
    sheet.save(update_fields=["status", "closed_at"])
    return {"counted": counted, "adjusted": adjusted}
