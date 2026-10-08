"""Modele danych mini-WMS."""

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone

# --- Role użytkowników -------------------------------------------------------


class Role(models.TextChoices):
    ADMIN = "ADMIN", "Administrator"
    OPERATOR = "OPERATOR", "Operator"
    VIEWER = "VIEWER", "Podgląd"


class Profile(models.Model):
    """Rola przypisana do konta użytkownika (Admin / Operator / Viewer)."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="profile",
        verbose_name="użytkownik",
    )
    role = models.CharField(
        "rola", max_length=10, choices=Role.choices, default=Role.VIEWER
    )

    class Meta:
        verbose_name = "profil użytkownika"
        verbose_name_plural = "profile użytkowników"

    def __str__(self):
        return f"{self.user.username} ({self.get_role_display()})"


# --- Słowniki ----------------------------------------------------------------


class Unit(models.Model):
    """Jednostka miary (słownik, domyślnie PCS)."""

    code = models.CharField("kod", max_length=10, unique=True)
    name = models.CharField("nazwa", max_length=50, blank=True)

    class Meta:
        verbose_name = "jednostka miary"
        verbose_name_plural = "jednostki miary"
        ordering = ["code"]

    def __str__(self):
        return self.code


class Material(models.Model):
    """Materiał w słowniku — zakładany zanim trafi na magazyn."""

    index = models.CharField("indeks", max_length=40, unique=True)
    name = models.CharField("nazwa", max_length=200)
    unit = models.ForeignKey(
        Unit,
        on_delete=models.PROTECT,
        related_name="materials",
        verbose_name="jednostka",
    )
    max_per_pallet = models.PositiveIntegerField(
        "maks. ilość na palecie",
        null=True,
        blank=True,
        help_text="Sztywny limit ilości na jednej palecie (opcjonalny).",
    )
    created_at = models.DateTimeField("utworzono", default=timezone.now)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        verbose_name="utworzył",
    )

    class Meta:
        verbose_name = "materiał"
        verbose_name_plural = "materiały"
        ordering = ["index"]
        constraints = [
            # Limit na paletę, jeśli ustawiony, musi być dodatni — inaczej
            # przyjęcie odrzucałoby każdą ilość.
            models.CheckConstraint(
                check=models.Q(max_per_pallet__isnull=True)
                | models.Q(max_per_pallet__gte=1),
                name="material_max_per_pallet_positive",
            ),
        ]

    def __str__(self):
        return f"{self.index} — {self.name}"


class LocationType(models.TextChoices):
    PICKING = "PICKING", "Picking"
    ZAPAS = "ZAPAS", "Zapas"


class Location(models.Model):
    """Miejsce składowania (np. B0-81-301A)."""

    code = models.CharField("kod", max_length=40, unique=True)
    type = models.CharField(
        "typ", max_length=10, choices=LocationType.choices, default=LocationType.ZAPAS
    )
    capacity = models.PositiveIntegerField(
        "pojemność (liczba HU)",
        default=1,
        help_text="Maksymalna liczba HU. 0 = bez limitu. Alokacja pilnuje limitu.",
    )
    created_at = models.DateTimeField("utworzono", default=timezone.now)

    class Meta:
        verbose_name = "lokalizacja"
        verbose_name_plural = "lokalizacje"
        ordering = ["code"]

    def __str__(self):
        return self.code

    @property
    def occupancy(self):
        """Liczba aktywnych HU w lokalizacji (niepuste i z dodatnią ilością)."""
        return (
            self.handling_units.exclude(status=HUStatus.PUSTY)
            .filter(quantity__gt=0)
            .count()
        )


# --- Numeracja HU ------------------------------------------------------------


class HUNumberingConfig(models.Model):
    """Konfiguracja numeracji HU: prefiks + licznik + długość numeru."""

    prefix = models.CharField("prefiks", max_length=10, default="HU")
    next_number = models.PositiveIntegerField("następny numer", default=1)
    padding = models.PositiveSmallIntegerField("liczba cyfr", default=8)

    class Meta:
        verbose_name = "konfiguracja numeracji HU"
        verbose_name_plural = "konfiguracja numeracji HU"

    def __str__(self):
        return f"{self.prefix} (następny: {self.next_number})"

    @classmethod
    def get_solo(cls):
        obj = cls.objects.first()
        if obj is None:
            obj = cls.objects.create()
        return obj


# --- Handling Unit (paleta) --------------------------------------------------


class HUStatus(models.TextChoices):
    DO_ULOZENIA = "DO_ULOZENIA", "Do ułożenia"
    ZMAGAZYNOWANY = "ZMAGAZYNOWANY", "Zmagazynowany"
    PUSTY = "PUSTY", "Pusty"


class HandlingUnit(models.Model):
    """Paleta / jednostka logistyczna z unikalnym numerem."""

    number = models.CharField("numer HU", max_length=30, unique=True)
    material = models.ForeignKey(
        Material,
        on_delete=models.PROTECT,
        related_name="handling_units",
        verbose_name="materiał",
    )
    quantity = models.PositiveIntegerField("ilość", default=0)
    lot = models.CharField("partia / LOT", max_length=50, blank=True)
    expiry_date = models.DateField("data ważności", null=True, blank=True)
    status = models.CharField(
        "status", max_length=15, choices=HUStatus.choices, default=HUStatus.DO_ULOZENIA
    )
    location = models.ForeignKey(
        Location,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="handling_units",
        verbose_name="lokalizacja",
    )
    delivery_ref = models.CharField("numer dostawy", max_length=50, blank=True)
    delivery_date = models.DateField("termin dostawy", null=True, blank=True)
    created_at = models.DateTimeField("przyjęto", default=timezone.now)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        verbose_name="przyjął",
    )

    class Meta:
        verbose_name = "HU (paleta)"
        verbose_name_plural = "HU (palety)"
        ordering = ["-created_at", "number"]
        constraints = [
            # Twarda gwarancja na poziomie bazy — ilość HU nigdy ujemna,
            # nawet przy operacjach z pominięciem warstwy aplikacji.
            models.CheckConstraint(
                check=models.Q(quantity__gte=0), name="hu_quantity_nonneg"
            ),
        ]
        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["material", "status"]),
        ]

    def __str__(self):
        return self.number


# --- Dokument wydania (picking) ---------------------------------------------


class IssueStatus(models.TextChoices):
    OTWARTY = "OTWARTY", "Otwarty"
    ZREALIZOWANY = "ZREALIZOWANY", "Zrealizowany"
    SPAKOWANY = "SPAKOWANY", "Spakowany"
    WYSLANY = "WYSLANY", "Wysłany"


class IssueDocument(models.Model):
    """Dokument wydania (zlecenie pickingu) z pozycjami."""

    number = models.CharField("numer dokumentu", max_length=30, unique=True)
    reference = models.CharField("referencja", max_length=100, blank=True)
    status = models.CharField(
        "status",
        max_length=15,
        choices=IssueStatus.choices,
        default=IssueStatus.OTWARTY,
    )
    created_at = models.DateTimeField("utworzono", default=timezone.now)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        verbose_name="utworzył",
    )
    completed_at = models.DateTimeField("zrealizowano", null=True, blank=True)
    packed_at = models.DateTimeField("spakowano", null=True, blank=True)
    shipped_at = models.DateTimeField("wysłano", null=True, blank=True)
    carrier = models.CharField("przewoźnik", max_length=80, blank=True)
    tracking_number = models.CharField("nr przesyłki", max_length=80, blank=True)

    class Meta:
        verbose_name = "dokument wydania"
        verbose_name_plural = "dokumenty wydania"
        ordering = ["-created_at", "number"]

    def __str__(self):
        return self.number


class IssueLine(models.Model):
    """Pozycja dokumentu wydania."""

    document = models.ForeignKey(
        IssueDocument,
        on_delete=models.CASCADE,
        related_name="lines",
        verbose_name="dokument",
    )
    material = models.ForeignKey(
        Material,
        on_delete=models.PROTECT,
        related_name="+",
        verbose_name="materiał",
    )
    requested_qty = models.PositiveIntegerField(
        "ilość żądana", validators=[MinValueValidator(1)]
    )
    picked_qty = models.PositiveIntegerField("ilość wydana", default=0)
    # Opcjonalne wskazanie konkretnego HU (gdy operator wybiera ręcznie).
    specific_hu = models.ForeignKey(
        HandlingUnit,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        verbose_name="konkretny HU",
    )

    class Meta:
        verbose_name = "pozycja wydania"
        verbose_name_plural = "pozycje wydania"
        ordering = ["id"]

    def __str__(self):
        return f"{self.material.index} × {self.requested_qty}"

    @property
    def outstanding(self):
        return max(0, self.requested_qty - self.picked_qty)

    @property
    def shortage(self):
        """Brak — ile nie wydano. Ma sens dopiero po realizacji dokumentu;
        dla otwartego dokumentu to wciąż „do pobrania", a nie brak."""
        if self.document.status == IssueStatus.OTWARTY:
            return 0
        return max(0, self.requested_qty - self.picked_qty)


# --- Rejestr ruchów magazynowych --------------------------------------------


class MovementType(models.TextChoices):
    PRZYJECIE = "PRZYJECIE", "Przyjęcie"
    ALOKACJA = "ALOKACJA", "Alokacja"
    PRZESUNIECIE = "PRZESUNIECIE", "Przesunięcie"
    KOREKTA = "KOREKTA", "Korekta"
    WYDANIE = "WYDANIE", "Wydanie"
    PRZEPAKOWANIE = "PRZEPAKOWANIE", "Przepakowanie"


class AdjustReason(models.TextChoices):
    USZKODZENIE = "USZKODZENIE", "Uszkodzenie"
    STRATA = "STRATA", "Strata / ubytek"
    NADWYZKA = "NADWYZKA", "Nadwyżka"
    POMYLKA = "POMYLKA", "Pomyłka ewidencji"
    SPIS = "SPIS", "Spis z natury"
    INNE = "INNE", "Inne"


class StockMovement(models.Model):
    """Pojedynczy ruch magazynowy — pełna historia operacji."""

    type = models.CharField("typ", max_length=15, choices=MovementType.choices)
    handling_unit = models.ForeignKey(
        HandlingUnit,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="movements",
        verbose_name="HU",
    )
    material = models.ForeignKey(
        Material,
        on_delete=models.PROTECT,
        related_name="movements",
        verbose_name="materiał",
    )
    quantity_delta = models.IntegerField(
        "zmiana ilości",
        help_text="Dodatnia dla przyjęcia, ujemna dla wydania, 0 dla przesunięcia.",
    )
    location_from = models.ForeignKey(
        Location,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        verbose_name="z lokalizacji",
    )
    location_to = models.ForeignKey(
        Location,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        verbose_name="do lokalizacji",
    )
    issue_document = models.ForeignKey(
        IssueDocument,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="movements",
        verbose_name="dokument wydania",
    )
    reason = models.CharField(
        "powód korekty", max_length=12, choices=AdjustReason.choices, blank=True
    )
    note = models.CharField("uwagi", max_length=255, blank=True)
    created_at = models.DateTimeField("kiedy", default=timezone.now)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="movements",
        verbose_name="kto",
    )

    class Meta:
        verbose_name = "ruch magazynowy"
        verbose_name_plural = "ruchy magazynowe"
        ordering = ["-created_at", "-id"]

    def __str__(self):
        return f"{self.get_type_display()} {self.material.index} ({self.quantity_delta:+d})"


# --- Spis z natury (inwentaryzacja) -----------------------------------------


class StocktakeStatus(models.TextChoices):
    OTWARTY = "OTWARTY", "Otwarty"
    ZAMKNIETY = "ZAMKNIETY", "Zamknięty"


class StocktakeSheet(models.Model):
    """Arkusz spisu z natury — migawka stanu do policzenia i zatwierdzenia."""

    number = models.CharField("numer arkusza", max_length=30, unique=True)
    location = models.ForeignKey(
        Location,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        verbose_name="lokalizacja (zakres)",
        help_text="Puste = cały magazyn.",
    )
    status = models.CharField(
        "status",
        max_length=10,
        choices=StocktakeStatus.choices,
        default=StocktakeStatus.OTWARTY,
    )
    created_at = models.DateTimeField("utworzono", default=timezone.now)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        verbose_name="utworzył",
    )
    closed_at = models.DateTimeField("zamknięto", null=True, blank=True)

    class Meta:
        verbose_name = "arkusz spisu"
        verbose_name_plural = "arkusze spisu"
        ordering = ["-created_at", "number"]

    def __str__(self):
        return self.number


class StocktakeLine(models.Model):
    """Pozycja arkusza spisu — jedna paleta (HU)."""

    sheet = models.ForeignKey(
        StocktakeSheet,
        on_delete=models.CASCADE,
        related_name="lines",
        verbose_name="arkusz",
    )
    handling_unit = models.ForeignKey(
        HandlingUnit,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        verbose_name="HU",
    )
    material = models.ForeignKey(
        Material, on_delete=models.PROTECT, related_name="+", verbose_name="materiał"
    )
    location_code = models.CharField("lokalizacja", max_length=40, blank=True)
    expected_qty = models.IntegerField("stan ewidencyjny")
    counted_qty = models.IntegerField("policzono", null=True, blank=True)

    class Meta:
        verbose_name = "pozycja spisu"
        verbose_name_plural = "pozycje spisu"
        ordering = ["location_code", "id"]
        constraints = [
            # Ten sam HU nie może wystąpić dwa razy w jednym arkuszu spisu
            # (inaczej różnice byłyby liczone podwójnie).
            models.UniqueConstraint(
                fields=["sheet", "handling_unit"],
                name="uniq_stocktake_sheet_hu",
            ),
        ]

    def __str__(self):
        return f"{self.sheet.number} · {self.material.index}"

    @property
    def variance(self):
        if self.counted_qty is None:
            return None
        return self.counted_qty - self.expected_qty


# --- Dziennik logowań / aktywności ------------------------------------------


class LoginEvent(models.Model):
    """Zdarzenie logowania: udane, wylogowanie, nieudana próba."""

    class Kind(models.TextChoices):
        LOGIN = "LOGIN", "Logowanie"
        LOGOUT = "LOGOUT", "Wylogowanie"
        FAILED = "FAILED", "Nieudane logowanie"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        verbose_name="użytkownik",
    )
    username = models.CharField("login", max_length=150, blank=True)
    kind = models.CharField("zdarzenie", max_length=10, choices=Kind.choices)
    ip = models.GenericIPAddressField("adres IP", null=True, blank=True)
    user_agent = models.CharField("przeglądarka", max_length=300, blank=True)
    created_at = models.DateTimeField("kiedy", default=timezone.now)

    class Meta:
        verbose_name = "zdarzenie logowania"
        verbose_name_plural = "dziennik logowań"
        ordering = ["-created_at", "-id"]

    def __str__(self):
        return f"{self.get_kind_display()} {self.username} ({self.created_at:%Y-%m-%d %H:%M})"
