# DANE FIKCYJNE — wygenerowane na potrzeby demo, nie pochodzą z żadnego
# rzeczywistego magazynu ani firmy.
"""Zasiewa dane demo: materiały, lokalizacje, HU, wydania, ruchy, spis, konta.

Deterministyczne (stałe ziarno) i oparte na funkcjach z services.py, więc
ruchy i numeracja HU/WZ/SP są prawdziwe.

    python manage.py seed_demo           # gdy baza nie ma jeszcze danych demo
    python manage.py seed_demo --reset   # czyści dane domenowe + konta demo
"""

import random
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from warehouse import services
from warehouse.demo import DEMO_ACCOUNTS, DEMO_PASSWORD
from warehouse.models import (
    AdjustReason,
    HandlingUnit,
    HUNumberingConfig,
    IssueDocument,
    IssueLine,
    Location,
    LocationType,
    Material,
    Profile,
    StockMovement,
    StocktakeSheet,
    Unit,
)

SEED = 20240501

MATERIALS = [
    ("DEMO-001", "Rękawice nitrylowe M"),
    ("DEMO-002", "Rękawice nitrylowe L"),
    ("DEMO-003", "Taśma pakowa 48 mm"),
    ("DEMO-004", "Folia stretch 23 µm"),
    ("DEMO-005", "Karton klapowy 400×300×300"),
    ("DEMO-006", "Wypełniacz papierowy"),
    ("DEMO-007", "Etykiety termiczne 100×150"),
    ("DEMO-008", "Ręcznik papierowy rolka"),
    ("DEMO-009", "Płyn do dezynfekcji 1 l"),
    ("DEMO-010", "Worki na odpady 120 l"),
    ("DEMO-011", "Kamizelka odblaskowa"),
    ("DEMO-012", "Opaska zaciskowa 200 mm"),
    ("DEMO-013", "Narożnik ochronny tekturowy"),
    ("DEMO-014", "Maseczka ochronna FFP2"),
    ("DEMO-015", "Baterie AA (opak. 4 szt.)"),
]


class Command(BaseCommand):
    help = "Zasiewa fikcyjne dane demo (deterministycznie)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Usuń dane domenowe i konta demo, potem zasiej od nowa "
            "(wymaga DEMO_MODE).",
        )

    def handle(self, *args, reset=False, **options):
        if reset:
            # Bezpiecznik: --reset kasuje WSZYSTKIE dane magazynowe.
            if not settings.DEMO_MODE:
                raise CommandError("--reset działa tylko przy DEMO_MODE=1.")
            self._reset()
        elif Material.objects.filter(index__startswith="DEMO-").exists():
            self.stdout.write("Dane demo już istnieją — pomijam (użyj --reset).")
            return
        self._seed()
        self.stdout.write(self.style.SUCCESS("Dane demo zasiane."))

    @transaction.atomic
    def _reset(self):
        StockMovement.objects.all().delete()
        StocktakeSheet.objects.all().delete()  # kaskadowo pozycje
        IssueDocument.objects.all().delete()  # kaskadowo pozycje
        HandlingUnit.objects.all().delete()
        Location.objects.all().delete()
        Material.objects.all().delete()
        HUNumberingConfig.objects.update(next_number=1)
        User.objects.filter(username__in=DEMO_ACCOUNTS).delete()

    @transaction.atomic
    def _seed(self):
        rng = random.Random(SEED)
        today = timezone.localdate()

        users = {}
        for username, role in DEMO_ACCOUNTS.items():
            user = User.objects.create_user(username, password=DEMO_PASSWORD)
            Profile.objects.update_or_create(user=user, defaults={"role": role})
            users[username] = user
        op = users["demo_operator"]

        unit = Unit.objects.get_or_create(code="PCS", defaults={"name": "sztuki"})[0]
        materials = [
            Material.objects.create(index=idx, name=name, unit=unit, created_by=op)
            for idx, name in MATERIALS
        ]

        picking = [
            Location.objects.create(
                code=f"A01-{i:02d}-01", type=LocationType.PICKING, capacity=1
            )
            for i in range(1, 13)
        ]
        zapas = [
            Location.objects.create(
                code=f"R02-{i:02d}-{lvl}", type=LocationType.ZAPAS, capacity=2
            )
            for i in range(1, 7)
            for lvl in ("10", "20")
        ]

        # 2 palety na materiał, każda z inną datą ważności → FEFO widoczne.
        hus = []
        for n, mat in enumerate(materials, start=1):
            for pallet in range(2):
                days = rng.choice([20, 45, 90, 180, 365])
                expiry = None if n % 5 == 0 else today + timedelta(days=days)
                qty = rng.choice([24, 36, 48, 60, 96, 120])
                hus += services.receive_material(
                    material=mat,
                    quantities=[qty],
                    user=op,
                    lot=f"L{n:03d}{pallet + 1}",
                    expiry_date=expiry,
                    delivery_ref=f"DST-{n:03d}",
                ).handling_units

        # Alokacja: najpierw PICKING, potem ZAPAS; 3 ostatnie czekają na ułożenie.
        slots = picking + [loc for loc in zapas for _ in range(2)]
        for hu, loc in zip(hus[:-3], slots, strict=False):
            services.allocate_hu(hu=hu, location=loc, user=op)

        # Kilka ruchów: przesunięcie i korekta.
        moved = hus[12]
        services.allocate_hu(hu=moved, location=zapas[-1], user=op)
        services.correct_hu_quantity(
            hu=hus[5],
            new_quantity=hus[5].quantity - 2,
            user=op,
            reason=AdjustReason.USZKODZENIE,
            note="Uszkodzone opakowania (demo)",
        )

        # Wydania: wysłane, zrealizowane, otwarte.
        def new_doc(ref, lines):
            doc = services.save_with_unique_number(
                IssueDocument(reference=ref, created_by=op),
                services.generate_issue_number,
            )
            for mat, qty in lines:
                IssueLine.objects.create(document=doc, material=mat, requested_qty=qty)
            return doc

        shipped = new_doc("Zamówienie demo 1", [(materials[0], 30), (materials[2], 12)])
        services.execute_issue_document(document=shipped, user=op)
        services.pack_issue_document(document=shipped, user=op)
        services.ship_issue_document(
            document=shipped, user=op, carrier="Kurier", tracking="DEMO000001"
        )
        done = new_doc("Zamówienie demo 2", [(materials[3], 20)])
        services.execute_issue_document(document=done, user=op)
        new_doc("Zamówienie demo 3", [(materials[1], 40), (materials[6], 10)])

        # Otwarty spis z natury na jednej lokalizacji zapasu.
        services.create_stocktake(location=zapas[0], user=op)
