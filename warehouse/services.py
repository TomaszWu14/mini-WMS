"""Logika biznesowa mini-WMS — przyjęcia, alokacje, korekty, picking.

Wszystkie operacje zmieniające stan zapisują ruch w `StockMovement`
(audyt: kto + kiedy) i działają w transakcji.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from django.conf import settings
from django.db import IntegrityError, transaction
from django.db.models import Case, F, IntegerField, Sum, Value, When
from django.db.models.functions import Upper
from django.utils import timezone

from .models import (
    AdjustReason,
    HandlingUnit,
    HUNumberingConfig,
    HUStatus,
    IssueDocument,
    IssueLine,
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


# --- Limity wejścia (US-002 / R3; wartości startowe — założenia Z-23, Z-35) ---
# Jedno przyjęcie ani jeden import nie mogą utworzyć tylu palet, by zająć workera
# na minuty. Uwaga: blokada licznika HU trwa do końca transakcji wołającego (import
# przyjęć = cały plik), więc limit skraca ją, ale nie usuwa — rezerwacja zakresu
# numerów jednym UPDATE to osobna historyjka (US-050).
MAX_PALLETS_PER_RECEIPT = 500
MAX_RECEIPT_QUANTITY = 1_000_000
# US-013 / L_QTY: ta sama granica dla każdej ilości wpisywanej przez użytkownika
# (korekta, pozycja WZ, przepakowanie, spis, API skanera) — daleko poniżej 2^31−1.
MAX_QUANTITY = MAX_RECEIPT_QUANTITY
MAX_LOCATION_CAPACITY = 10_000  # palet w jednej lokalizacji
MAX_HU_PER_IMPORT = 2_000


def _lock_and_sync(obj):
    """Blokuje wiersz (`select_for_update`) i odświeża PRZEKAZANY obiekt w
    miejscu — ta sama tożsamość Pythona, świeże dane z bazy.

    Widoki/testy wołają serwis przekazując obiekt i czytają jego atrybuty
    (np. ``hu.location.code``) PO wywołaniu, bez przechwytywania zwróconej
    wartości. Zwykłe `select_for_update().get(pk=...)` tworzy nowy obiekt i
    zostawia oryginał z nieaktualnymi danymi — stąd kopiujemy pola świeżo
    zablokowanego wiersza z powrotem na oryginał, zamiast podmieniać
    referencję. Relacje zostają do leniwego pobrania (bez dodatkowych zapytań).
    """
    obj.refresh_from_db(from_queryset=type(obj).objects.select_for_update())
    return obj


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


def reserve_hu_numbers(count: int) -> list[str]:
    """US-050: rezerwuje `count` kolejnych numerów HU jednym zapisem licznika.

    Licznik blokowany raz; numery już zajęte (nadane ręcznie w imporcie stanów,
    przegląd [DB] US-013) pomijane — jedno zapytanie na paczkę kandydatów, nie na
    numer. Rezerwacja w transakcji wywołującego: wycofanie przyjęcia cofa też licznik
    (bez dziur w numeracji), więc zapis palet po rezerwacji ma być krótki (`bulk_create`).
    """
    if count < 1:
        return []
    with transaction.atomic():
        config = HUNumberingConfig.objects.select_for_update().order_by("pk").first()
        if config is None:
            # Brak konfiguracji (usunięta w adminie): stały pk=1 — dwa równoległe
            # przyjęcia nie założą dwóch liczników (drugie dostaje IntegrityError
            # i czeka na blokadę wiersza pierwszego).
            try:
                with transaction.atomic():
                    HUNumberingConfig.objects.create(pk=1)
            except IntegrityError:
                pass
            config = HUNumberingConfig.objects.select_for_update().get(pk=1)
        numbers: list[str] = []
        while len(numbers) < count:
            need = count - len(numbers)
            start = config.next_number
            candidates = [
                f"{config.prefix}{n:0{config.padding}d}"
                for n in range(start, start + need)
            ]
            taken = {
                n.upper()
                for n in HandlingUnit.objects.annotate(_u=Upper("number"))
                .filter(_u__in=[c.upper() for c in candidates])
                .values_list("number", flat=True)
            }
            numbers += [c for c in candidates if c.upper() not in taken]
            config.next_number = start + need
        config.save(update_fields=["next_number"])
    return numbers


def generate_hu_number() -> str:
    """Zwraca kolejny unikalny numer HU i zwiększa licznik (atomowo)."""
    return reserve_hu_numbers(1)[0]


# --- Podział ilości na palety -------------------------------------------------


def split_quantity(total: int, pallets: int) -> list[int]:
    """Dzieli `total` na `pallets` części, resztę rozkłada po jednej na
    ostatnie palety (np. 10/4 → [2,2,3,3]) — tak samo liczy `forms.py`
    ceil(total/pallets) przy walidacji limitu na paletę."""
    if pallets < 1:
        raise WMSError("Liczba palet musi być dodatnia.")
    if pallets > MAX_PALLETS_PER_RECEIPT:
        raise WMSError(f"Najwyżej {MAX_PALLETS_PER_RECEIPT} palet w jednym przyjęciu.")
    if total < 1:
        raise WMSError("Ilość całkowita musi być dodatnia.")
    if total > MAX_RECEIPT_QUANTITY:
        raise WMSError(f"Ilość w jednym przyjęciu najwyżej {MAX_RECEIPT_QUANTITY}.")
    base = total // pallets
    remainder = total - base * pallets
    quantities = [base] * pallets
    for i in range(pallets - remainder, pallets):
        quantities[i] += 1
    if any(q <= 0 for q in quantities):
        raise WMSError(
            "Zbyt wiele palet dla podanej ilości — niektóre palety byłyby puste."
        )
    return quantities


# --- Przyjęcie ---------------------------------------------------------------


@dataclass
class ReceiveResult:
    handling_units: list[HandlingUnit]


# US-016 / DEC-6: publiczne demo — łączna liczba obiektów (L_DEMO, decyzja PO 2026-10-16).
DEMO_MAX_HANDLING_UNITS = 2000
DEMO_MAX_LOCATIONS = 500
DEMO_LIMIT_SUFFIX = "Dane demo wracają do stanu początkowego codziennie o 03:00."


class DemoBudget:
    """Ile palet (HU) i lokalizacji można jeszcze utworzyć w demo; poza demo bez limitu.

    Każdy rodzaj liczony najwyżej raz na budżet i tylko gdy operacja go dotyczy
    (import — jeden budżet na plik). COUNT nic nie blokuje: N równoległych operacji
    może przekroczyć limit łącznie o N × rozmiar operacji — bezpiecznik na boty,
    nie księgowość (przegląd [DB] US-016).
    """

    def __init__(self):
        self.limited = bool(settings.DEMO_MODE)
        self._left: dict[str, int] = {}

    def _remaining(self, kind: str) -> int:
        if kind not in self._left:
            if kind == "hus":
                self._left[kind] = (
                    DEMO_MAX_HANDLING_UNITS - HandlingUnit.objects.count()
                )
            else:
                self._left[kind] = DEMO_MAX_LOCATIONS - Location.objects.count()
        return self._left[kind]

    def take(self, *, hus: int = 0, locations: int = 0) -> None:
        if not self.limited:
            return
        if hus and hus > self._remaining("hus"):
            raise WMSError(
                f"Limit demo: najwyżej {DEMO_MAX_HANDLING_UNITS} palet (HU). "
                + DEMO_LIMIT_SUFFIX
            )
        if locations and locations > self._remaining("locations"):
            raise WMSError(
                f"Limit demo: najwyżej {DEMO_MAX_LOCATIONS} lokalizacji. "
                + DEMO_LIMIT_SUFFIX
            )
        if hus:
            self._left["hus"] -= hus
        if locations:
            self._left["locations"] -= locations


@transaction.atomic
def receive_material(
    *,
    material: Material,
    quantities: list[int],
    user,
    lot: str = "",
    expiry_date=None,
    delivery_ref: str = "",
    budget: DemoBudget | None = None,
) -> ReceiveResult:
    """Tworzy HU dla zadanego materiału wg listy ilości na palety.

    Każda paleta = jeden HU ze statusem DO_ULOZENIA (czeka na alokację).
    Limity sprawdzane przed pobraniem pierwszego numeru HU (US-002).
    """
    plan = ReceiptPlan(material, quantities, lot, expiry_date, delivery_ref)
    validate_receipt(plan, budget=budget)
    return ReceiveResult(handling_units=create_received_hus([plan], user=user))


@dataclass
class ReceiptPlan:
    material: Material
    quantities: list[int]
    lot: str = ""
    expiry_date: date | None = None
    delivery_ref: str = ""


def validate_receipt(plan: ReceiptPlan, *, budget: DemoBudget | None = None) -> None:
    """Limity jednego przyjęcia (US-002) i budżet demo (US-016) — bez zapisu."""
    material, quantities = plan.material, plan.quantities
    if not quantities or len(quantities) > MAX_PALLETS_PER_RECEIPT:
        raise WMSError(f"Przyjęcie musi mieć od 1 do {MAX_PALLETS_PER_RECEIPT} palet.")
    if any(q < 1 for q in quantities) or sum(quantities) > MAX_RECEIPT_QUANTITY:
        raise WMSError(
            "Ilość na palecie musi być dodatnia, a łącznie najwyżej "
            f"{MAX_RECEIPT_QUANTITY}."
        )
    if material.max_per_pallet:
        for qty in quantities:
            if qty > material.max_per_pallet:
                raise WMSError(
                    f"Ilość {qty} przekracza maks. {material.max_per_pallet} "
                    f"na palecie dla materiału {material.index}."
                )
    (budget or DemoBudget()).take(hus=len(quantities))


@transaction.atomic
def create_received_hus(plans: list[ReceiptPlan], *, user) -> list[HandlingUnit]:
    """US-050: zapis zwalidowanych przyjęć — jedna rezerwacja numerów i `bulk_create`.

    Liczba zapytań nie zależy od liczby palet (poza dzieleniem paczek przez bazę),
    więc blokada licznika numerów trwa chwilę także przy imporcie 2 000 palet.
    """
    total = sum(len(p.quantities) for p in plans)
    numbers = iter(reserve_hu_numbers(total))
    hus = [
        HandlingUnit(
            number=next(numbers),
            material=p.material,
            quantity=qty,
            lot=p.lot,
            expiry_date=p.expiry_date,
            status=HUStatus.DO_ULOZENIA,
            delivery_ref=p.delivery_ref,
            created_by=user,
        )
        for p in plans
        for qty in p.quantities
    ]
    HandlingUnit.objects.bulk_create(hus)
    StockMovement.objects.bulk_create(
        StockMovement(
            type=MovementType.PRZYJECIE,
            handling_unit=hu,
            material=hu.material,
            quantity_delta=hu.quantity,
            note=f"Przyjęcie HU {hu.number}",
            created_by=user,
        )
        for hu in hus
    )
    return hus


# --- Alokacja / przesunięcie -------------------------------------------------


def location_over_capacity(location: Location) -> bool:
    """True, gdy lokalizacja ma limit (>0) i jest przekroczony.

    Informacyjne — nie blokuje alokacji (W-08). Wołane przez widoki po
    alokacji, aby pokazać ostrzeżenie."""
    return bool(location.capacity) and location.occupancy > location.capacity


@transaction.atomic
def allocate_hu(*, hu: HandlingUnit, location: Location, user) -> HandlingUnit:
    """Ustawia HU w lokalizacji. Pierwsza alokacja lub przesunięcie.

    Pojemność lokalizacji jest informacyjna (W-08) — nie blokuje alokacji;
    `location_over_capacity` daje wołającemu sygnał do ostrzeżenia.
    """
    # Lokalizacji celowo nie blokujemy: pojemność nie jest już warunkiem
    # alokacji, więc ostrzeżenie (`location_over_capacity`) jest „best effort”.
    _lock_and_sync(hu)
    if hu.status == HUStatus.PUSTY:
        raise WMSError(f"HU {hu.number} jest pusty — nie można go ulokować.")

    previous = hu.location
    is_move = previous is not None and previous != location

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
    *, hu: HandlingUnit, new_quantity: int, user, reason: str, note: str = ""
):
    """Koryguje ilość na HU (np. po inwentaryzacji). Zapisuje ruch korekty.

    Każda korekta ma powód z `AdjustReason` (W-26) — pilnowane tu, nie tylko w
    formularzach, żeby żadna ścieżka (web, skaner, spis) go nie pominęła.
    """
    if reason not in AdjustReason.values:
        raise WMSError("Wybierz powód korekty.")
    _lock_and_sync(hu)
    if new_quantity < 0:
        raise WMSError("Ilość nie może być ujemna.")
    if new_quantity > MAX_QUANTITY:  # US-013: stan palety, nie tylko pojedyncza zmiana
        raise WMSError(f"Stan palety nie może przekroczyć {MAX_QUANTITY}.")
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


@transaction.atomic
def adjust_hu_quantity(
    *, hu: HandlingUnit, delta: int, user, reason: str, note: str = ""
):
    """Koryguje ilość na HU względem AKTUALNEGO (zablokowanego) stanu.

    Zastępuje wzorzec liczenia nowej ilości z nieaktualnego odczytu w
    widoku/skanerze — `delta` liczymy tu, pod blokadą wiersza.
    """
    _lock_and_sync(hu)
    new_quantity = hu.quantity + delta
    if delta == 0:
        raise WMSError("Podaj ilość różną od zera.")
    if new_quantity < 0:
        raise WMSError(
            f"Stan nie może być ujemny (na HU {hu.number} jest {hu.quantity})."
        )
    return correct_hu_quantity(
        hu=hu, new_quantity=new_quantity, user=user, note=note, reason=reason
    )


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
    # Blokady zawsze w kolejności pk — dwa równoległe przepakowania A→B i B→A
    # nie zakleszczą się na PostgreSQL.
    locked = {
        h.pk: h
        for h in HandlingUnit.objects.select_for_update()
        .filter(pk__in=[source.pk, target.pk])
        .order_by("pk")
    }
    source, target = locked[source.pk], locked[target.pk]

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
    if target.quantity + quantity > MAX_QUANTITY:
        raise WMSError(
            f"Stan palety {target.number} przekroczyłby {MAX_QUANTITY} — przepakuj mniej."
        )
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


def _lock_hus(pks) -> dict[int, HandlingUnit]:
    """US-053: blokuje palety jednym zapytaniem, rosnąco po pk — ta sama kolejność we
    wszystkich ścieżkach (realizacja WZ, przepakowanie, zamknięcie spisu), więc dwie
    transakcje nie czekają na siebie nawzajem. Zwraca świeże obiekty po blokadzie."""
    ids = sorted({pk for pk in pks if pk})
    if not ids:
        return {}
    return {
        hu.pk: hu
        for hu in HandlingUnit.objects.select_for_update()
        .filter(pk__in=ids)
        .order_by("pk")
    }


def _fefo_prefix(material: Material, quantity: int) -> list[int]:
    """US-053 (przegląd [DB]): pk palet z początku kolejki FEFO, które pokrywają
    `quantity` wg odczytu bez blokady — blokujemy tylko je, nie wszystkie palety
    materiału. Brak stanu → wszystkie aktywne palety."""
    pks: list[int] = []
    total = 0
    for pk, qty in _pickable_hus(material).values_list("pk", "quantity"):
        if total >= quantity:
            break
        pks.append(pk)
        total += qty
    return pks


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


def first_pickable_hu(material: Material) -> HandlingUnit | None:
    """Pierwsza paleta w kolejce FEFO/FIFO (lub None) — do ostrzeżenia w
    skanerze, gdy operator pobiera inną paletę niż podpowiadana (W-11)."""
    return _pickable_hus(material).first()


def available_quantity(material: Material) -> int:
    """Łączna dostępna ilość materiału na aktywnych HU."""
    return _pickable_hus(material).aggregate(t=Sum("quantity"))["t"] or 0


@transaction.atomic
def pick_from_hu(*, hu: HandlingUnit, quantity: int, user, document=None, line=None):
    """Zdejmuje `quantity` z konkretnego HU. Picking częściowy dozwolony.

    Pozycja WZ (z dokumentem) jest blokowana PRZED paletą — ta sama kolejność
    blokad co w `execute_issue_document` (dokument → pozycja → HU). Dzięki temu
    skaner i „Realizuj” na tym samym dokumencie nie pobiorą ponad żądaną ilość.
    """
    if quantity < 1:
        raise WMSError("Ilość wydania musi być dodatnia.")
    if line is not None:
        # US-018: najpierw dokument, potem pozycja — osobnymi zapytaniami.
        # `select_for_update().select_related("document")` blokował oba wiersze
        # jednym zapytaniem w nieustalonej kolejności → deadlock z „Realizuj”.
        locked_doc = (
            IssueDocument.objects.select_for_update()
            .filter(pk=line.document_id)
            .first()
        )
        locked_line = IssueLine.objects.select_for_update().filter(pk=line.pk).first()
        # US-052: pozycję mógł usunąć ktoś inny, gdy czekaliśmy na blokadę — komunikat, nie 500.
        if locked_doc is None or locked_line is None:
            raise WMSError("Pozycja została w międzyczasie usunięta z dokumentu.")
        if locked_doc.status != IssueStatus.OTWARTY:
            raise WMSError(f"Dokument {locked_doc.number} nie jest otwarty.")
        remaining = locked_line.requested_qty - locked_line.picked_qty
        if quantity > remaining:
            raise WMSError(f"Na pozycji pozostało {remaining}, żądane {quantity}.")
    hu = HandlingUnit.objects.select_for_update().get(pk=hu.pk)
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
    *,
    material: Material,
    quantity: int,
    user,
    document=None,
    line=None,
    allow_partial: bool = False,
):
    """Zdejmuje `quantity` materiału, dobierając HU wg reguły FEFO→FIFO.

    US-053: palety blokowane rosnąco po pk, a ilości liczone z wierszy już pod
    blokadą — równoległe pobranie nie wywróci realizacji („HU jest pusty”).
    `allow_partial=True` — pobiera tyle, ile jest (może zero).
    """
    if quantity < 1:
        raise WMSError("Ilość wydania musi być dodatnia.")
    if line is not None:
        # Przegląd [DB] US-053: dokument → pozycja → HU także przy wywołaniu spoza
        # `execute_issue_document` (w nim to ponowna blokada już trzymanych wierszy).
        IssueDocument.objects.select_for_update().filter(pk=line.document_id).first()
        IssueLine.objects.select_for_update().filter(pk=line.pk).first()

    def locked_hus(pks: list[int]) -> list[HandlingUnit]:
        locked = _lock_hus(pks)
        return [
            locked[pk]
            for pk in pks
            if pk in locked
            and locked[pk].quantity > 0
            and locked[pk].status != HUStatus.PUSTY
        ]

    order = _fefo_prefix(material, quantity)
    hus = locked_hus(order)
    available = sum(hu.quantity for hu in hus)
    if available < quantity:
        # Ktoś pobrał w międzyczasie — dobieramy kolejne palety (rzadkie; dokładamy
        # blokady do już trzymanych, kolejność po pk tylko w obrębie tego zapytania).
        order = list(_pickable_hus(material).values_list("pk", flat=True))
        hus = locked_hus(order)
        available = sum(hu.quantity for hu in hus)
    if allow_partial:
        quantity = min(quantity, available)
    elif quantity > available:
        raise WMSError(
            f"Brak wystarczającego stanu materiału {material.index}: "
            f"dostępne {available}, żądane {quantity}."
        )

    remaining = quantity
    used: list[tuple[HandlingUnit, int]] = []
    for hu in hus:
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
    # Świeży odczyt pod blokadą — dwa równoległe kliknięcia "realizuj" na
    # tym samym (nieaktualnym w Pythonie) obiekcie nie zrealizują dokumentu
    # dwa razy.
    _lock_and_sync(document)
    if document.status != IssueStatus.OTWARTY:
        raise WMSError("Dokument nie jest otwarty.")

    lines = list(document.lines.select_related("material", "specific_hu"))
    if not lines:
        raise WMSError("Dokument nie ma pozycji do wydania.")

    # US-053: palety, z których realizacja będzie pobierać, blokujemy od razu,
    # rosnąco po pk — niezależnie od kolejności pozycji i FEFO. Dwa „Realizuj” na WZ
    # z materiałami X, Y i Y, X nie zakleszczą się (`deadlock detected` = 500).
    open_lines = [ln for ln in lines if ln.requested_qty - ln.picked_qty > 0]
    needed: dict[int, int] = {}
    by_id: dict[int, Material] = {}
    for ln in open_lines:
        if ln.specific_hu_id is None:
            needed[ln.material_id] = (
                needed.get(ln.material_id, 0) + ln.requested_qty - ln.picked_qty
            )
            by_id[ln.material_id] = ln.material
    candidates = [ln.specific_hu_id for ln in open_lines if ln.specific_hu_id]
    # Przegląd [DB]: tylko palety, które FEFO faktycznie użyje, nie wszystkie palety materiału.
    for material_id, qty in needed.items():
        candidates += _fefo_prefix(by_id[material_id], qty)
    _lock_hus(candidates)

    for line in open_lines:
        outstanding = line.requested_qty - line.picked_qty
        if line.specific_hu_id is not None:
            # Paleta już zablokowana — świeży odczyt per pozycja (dwie pozycje na tym
            # samym HU widzą stan po pobraniu pierwszej).
            specific = HandlingUnit.objects.filter(pk=line.specific_hu_id).first()
            if specific is None:
                raise WMSError("Wskazany HU został w międzyczasie usunięty.")
            if specific.material_id != line.material_id:
                raise WMSError(
                    f"Wskazany HU {specific.number} ma inny materiał "
                    f"niż pozycja ({line.material.index})."
                )
            # Stan palety z wiersza pod blokadą, nie z obiektu wczytanego wcześniej.
            available = specific.quantity if specific.status != HUStatus.PUSTY else 0
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
            pick_by_material(
                material=line.material,
                quantity=outstanding,
                user=user,
                document=document,
                line=line,
                allow_partial=allow_partial,
            )

    document.status = IssueStatus.ZREALIZOWANY
    document.completed_at = timezone.now()
    document.save(update_fields=["status", "completed_at"])
    return document


LINES_ONLY_IN_OPEN = "Pozycje można zmieniać tylko w otwartym dokumencie."


@transaction.atomic
def add_issue_line(
    *, document: IssueDocument, material: Material, requested_qty: int, specific_hu=None
) -> IssueLine:
    """US-052: dodaje pozycję WZ pod blokadą dokumentu (kolejność: dokument → pozycja → HU).

    Status i rezerwacja palety sprawdzane na świeżych danych pod blokadą — „Realizuj”
    albo skaner domykający dokument równolegle nie zostawi zrealizowanego WZ
    z niepobraną pozycją.
    """
    _lock_and_sync(document)
    if document.status != IssueStatus.OTWARTY:
        raise WMSError(LINES_ONLY_IN_OPEN)
    if specific_hu is not None:
        # Przegląd [DB] US-052: rezerwuje tylko niepobrana część pozycji (pobrana już zeszła
        # z palety), a stan palety czytamy świeży — bez blokady HU (kolejność blokad bez zmian;
        # przy pobraniu i tak sprawdza go `pick_from_hu` pod blokadą palety).
        already = (
            document.lines.filter(specific_hu=specific_hu).aggregate(
                s=Sum(F("requested_qty") - F("picked_qty"))
            )["s"]
            or 0
        )
        on_hu = HandlingUnit.objects.values_list("quantity", flat=True).get(
            pk=specific_hu.pk
        )
        if already + requested_qty > on_hu:
            raise WMSError(
                f"HU {specific_hu.number} ma tylko {on_hu} szt., a pozycje "
                f"dokumentu wskazują już {already}."
            )
    return IssueLine.objects.create(
        document=document,
        material=material,
        requested_qty=requested_qty,
        specific_hu=specific_hu,
    )


@transaction.atomic
def delete_issue_line(*, document: IssueDocument, line_id) -> None:
    """US-052: usuwa pozycję otwartego WZ — dokument, potem pozycja pod blokadą."""
    _lock_and_sync(document)
    if document.status != IssueStatus.OTWARTY:
        raise WMSError(LINES_ONLY_IN_OPEN)
    line = (
        IssueLine.objects.select_for_update()
        .filter(pk=line_id, document=document)
        .first()
    )
    if line is None:
        raise WMSError("Pozycja nie istnieje albo została już usunięta.")
    # Przegląd [DB] US-052: towar z tej pozycji fizycznie wyszedł (ruch WYDANIE) — usunięcie
    # pozycji rozjechałoby dokument z historią ruchów.
    if line.picked_qty > 0:
        raise WMSError(
            f"Z tej pozycji pobrano już {line.picked_qty} — nie można jej usunąć. "
            "Zrealizuj dokument z brakami albo zwróć towar korektą."
        )
    line.delete()
    # Pozostałe pozycje mogą być już w pełni pobrane — dokument zamyka się od razu
    # (inaczej skaner nie miałby czego pobrać, by go domknąć).
    complete_if_picked(document)


@transaction.atomic
def complete_if_picked(document: IssueDocument) -> bool:
    """Zamyka WZ („Zrealizowany”), gdy wszystkie pozycje są w pełni pobrane (D-05, US-018).

    Jedno miejsce zmiany stanu po pobraniu ze skanera: dokument blokowany jak w
    `execute_issue_document`, warunek sprawdzany na świeżych danych pod blokadą.
    Idempotentne — dokument już zamknięty (np. równolegle przez „Realizuj”) zostaje
    bez zmian i bez błędu. Zwraca True tylko wtedy, gdy to wywołanie go zamknęło.
    """
    _lock_and_sync(document)
    if document.status != IssueStatus.OTWARTY:
        return False
    lines = document.lines.all()
    if not lines.exists() or lines.filter(picked_qty__lt=F("requested_qty")).exists():
        return False
    document.status = IssueStatus.ZREALIZOWANY
    document.completed_at = timezone.now()
    document.save(update_fields=["status", "completed_at"])
    return True


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
    # Blokada + świeży odczyt — jak w execute_issue_document, chroni przed
    # dwukrotnym spakowaniem tego samego dokumentu z dwóch kliknięć.
    _lock_and_sync(document)
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
    _lock_and_sync(document)
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
    """Tworzy arkusz spisu z migawką stanu (aktywne HU w zakresie).

    Palety, które są już w innym otwartym arkuszu, są pomijane — ich liczba
    trafia do `sheet.skipped_in_open` (komunikat w widoku).

    ponytail: dwa arkusze tworzone w tej samej chwili mogą jeszcze objąć tę samą
    paletę (brak blokady); wystarczy przy ręcznym zakładaniu spisów.
    """
    sheet = save_with_unique_number(
        StocktakeSheet(location=location, created_by=user),
        generate_stocktake_number,
    )
    hus = HandlingUnit.objects.exclude(status=HUStatus.PUSTY).select_related(
        "material", "location"
    )
    if location is not None:
        hus = hus.filter(location=location)
    # isnull=False: pozycja po usuniętej palecie ma NULL, a NOT IN z NULL-em
    # odrzuciłby wszystkie palety.
    in_open = StocktakeLine.objects.filter(
        sheet__status=StocktakeStatus.OTWARTY, handling_unit__isnull=False
    ).values("handling_unit")
    sheet.skipped_in_open = hus.filter(pk__in=in_open).count()
    hus = hus.exclude(pk__in=in_open)
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
    lines = list(sheet.lines.select_for_update(of=("self",)))
    # US-053: palety arkusza blokowane rosnąco po pk (nie w kolejności lokalizacji) —
    # ta sama kolejność co realizacja WZ i przepakowanie.
    locked = _lock_hus(
        ln.handling_unit_id for ln in lines if ln.counted_qty is not None
    )
    for line in lines:
        if line.counted_qty is None:
            continue
        counted += 1
        hu = locked.get(line.handling_unit_id) if line.handling_unit_id else None
        if hu is None:
            continue
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
