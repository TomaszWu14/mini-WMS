"""Odcisk danych do porównania produkcji z kopią odtworzoną (US-012, RUNBOOK §5.4).

Wypisuje liczby rekordów i sumę kontrolną stanów — uruchom na produkcji i na środowisku
odtworzonym z kopii; wiersze mają być identyczne (poza danymi dopisanymi po godzinie kopii).
"""

from django.core.management.base import BaseCommand
from django.db.models import Max, Sum

from warehouse.models import (
    HandlingUnit,
    IssueDocument,
    Location,
    Material,
    StockMovement,
    StocktakeSheet,
)


class Command(BaseCommand):
    help = "Liczby rekordów i suma stanów — do porównania z kopią odtworzoną."

    def handle(self, *args, **options):
        rows = [
            ("materiały", Material.objects.count()),
            ("lokalizacje", Location.objects.count()),
            ("palety (HU)", HandlingUnit.objects.count()),
            (
                "suma ilości na paletach",
                HandlingUnit.objects.aggregate(s=Sum("quantity"))["s"] or 0,
            ),
            ("dokumenty WZ", IssueDocument.objects.count()),
            ("arkusze spisu", StocktakeSheet.objects.count()),
            ("ruchy", StockMovement.objects.count()),
            (
                "ostatni ruch",
                StockMovement.objects.aggregate(m=Max("created_at"))["m"] or "—",
            ),
        ]
        for label, value in rows:
            self.stdout.write(f"{label}: {value}")
