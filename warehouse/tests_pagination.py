"""US-015: stronicowanie list i limit zbiorczego wydruku etykiet lokalizacji."""

import csv
import io
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase

from .models import (
    HandlingUnit,
    HUStatus,
    Location,
    LocationType,
    Material,
    Profile,
    Role,
    Unit,
)
from .pagination import PAGE_SIZE
from .views import LOCATION_LABELS_LIMIT

N = PAGE_SIZE + 5


class _Base(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.viewer = User.objects.create_user("podglad", password="ViewPass123!")
        Profile.objects.filter(user=cls.viewer).update(role=Role.VIEWER)
        unit = Unit.objects.get_or_create(code="PCS")[0]
        cls.material = Material.objects.create(index="MAT-P", name="Strony", unit=unit)
        Location.objects.bulk_create(
            Location(code=f"P-{i:04d}", type=LocationType.ZAPAS, capacity=2)
            for i in range(N)
        )
        Location.objects.create(code="K-0001", type=LocationType.PICKING, capacity=1)
        loc = Location.objects.get(code="P-0000")
        HandlingUnit.objects.bulk_create(
            HandlingUnit(
                number=f"HU-P-{i:04d}",
                material=cls.material,
                quantity=1,
                status=HUStatus.ZMAGAZYNOWANY,
                location=loc,
            )
            for i in range(N)
        )

    def setUp(self):
        self.client.force_login(self.viewer)


class PaginationTests(_Base):
    """Kryterium 2: ≤ ROZMIAR_STRONY wierszy, nawigacja, filtry działają."""

    LISTS = (
        ("/hu/", "handling_units"),
        ("/lokalizacje/", "locations"),
        ("/stany/lokalizacje/", "handling_units"),
        ("/raporty/lokalizacje/", "rows"),
    )

    def test_first_page_limited_with_navigation(self):
        for url, key in self.LISTS:
            with self.subTest(url=url):
                resp = self.client.get(url)
                self.assertEqual(resp.status_code, 200)
                self.assertEqual(len(resp.context[key]), PAGE_SIZE)
                self.assertContains(resp, "Strona 1 z 2")
                self.assertContains(resp, "page=2")

    def test_second_page_has_rest(self):
        resp = self.client.get("/hu/", {"page": 2})
        self.assertEqual(len(resp.context["handling_units"]), N - PAGE_SIZE)

    def test_bad_page_param_is_not_an_error(self):
        for value in ("abc", "-1", "0", "99999", "1e9", "²"):
            with self.subTest(value=value):
                self.assertEqual(
                    self.client.get("/hu/", {"page": value}).status_code, 200
                )

    def test_filter_kept_in_page_links(self):
        resp = self.client.get("/hu/", {"q": "HU-P", "status": HUStatus.ZMAGAZYNOWANY})
        self.assertContains(resp, "q=HU-P&amp;status=ZMAGAZYNOWANY&amp;page=2")
        resp = self.client.get(
            "/hu/", {"q": "HU-P", "status": HUStatus.ZMAGAZYNOWANY, "page": 2}
        )
        self.assertEqual(len(resp.context["handling_units"]), N - PAGE_SIZE)

    def test_filter_narrows_to_single_page(self):
        resp = self.client.get("/lokalizacje/", {"type": LocationType.PICKING})
        self.assertEqual([loc.code for loc in resp.context["locations"]], ["K-0001"])
        self.assertNotContains(resp, "page=2")
        resp = self.client.get("/stany/lokalizacje/", {"q": "HU-P-0001"})
        self.assertEqual(len(resp.context["handling_units"]), 1)

    def test_report_summary_counts_all_locations(self):
        resp = self.client.get("/raporty/lokalizacje/")
        summary = resp.context["summary"]
        self.assertEqual(summary["total"], N + 1)
        self.assertEqual(summary["occupied"], 1)
        self.assertEqual(summary["empty"], N)
        # P-0000 przepełniona (N palet przy pojemności 2) → 0 wolnych; reszta po 2, K-0001 1.
        self.assertEqual(summary["free_slots"], (N - 1) * 2 + 1)


class ExportCompletenessTests(_Base):
    """Kryterium 3: eksport nie jest stronicowany — zawiera wszystkie rekordy."""

    def test_stock_export_all_rows(self):
        unit = Unit.objects.get(code="PCS")
        Material.objects.bulk_create(
            Material(index=f"MAT-E{i:04d}", name="E", unit=unit) for i in range(N)
        )
        hus = [
            HandlingUnit(number=f"HU-E-{m.pk}", material=m, quantity=1)
            for m in Material.objects.filter(index__startswith="MAT-E")
        ]
        HandlingUnit.objects.bulk_create(hus)
        resp = self.client.get("/stany/eksport/csv/")
        body = b"".join(resp.streaming_content) if resp.streaming else resp.content
        rows = list(csv.reader(io.StringIO(body.decode("utf-8-sig")), delimiter=";"))
        self.assertEqual(len(rows) - 1, N + 1)  # nagłówek; MAT-P + N materiałów

    def test_movement_export_not_paginated(self):
        resp = self.client.get("/ruchy/eksport/xlsx/")
        self.assertEqual(resp.status_code, 200)


class LocationLabelsLimitTests(_Base):
    """Kryterium 1: powyżej L_ETYKIET_LOK — przekierowanie „Zawęź filtr”, bez PDF."""

    def test_over_limit_redirects_without_pdf(self):
        with (
            patch("warehouse.views.LOCATION_LABELS_LIMIT", 10),
            patch("warehouse.views.location_labels_pdf") as pdf,
        ):
            resp = self.client.get(
                "/lokalizacje/etykiety/", {"type": LocationType.ZAPAS}, follow=True
            )
        pdf.assert_not_called()
        self.assertEqual(resp.redirect_chain[0][0], "/lokalizacje/?type=ZAPAS")
        self.assertContains(resp, f"Wybrano {N} lokalizacji")
        self.assertContains(resp, "Zawęź filtr")

    def test_default_limit_is_200(self):
        self.assertEqual(LOCATION_LABELS_LIMIT, 200)

    def test_narrowed_filter_prints_pdf(self):
        resp = self.client.get("/lokalizacje/etykiety/", {"q": "P-000"})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp["Content-Type"], "application/pdf")

    def test_labels_link_carries_list_filters(self):
        resp = self.client.get("/lokalizacje/", {"type": LocationType.PICKING})
        self.assertContains(resp, "/lokalizacje/etykiety/?type=PICKING")


class ReportQueryCountTests(_Base):
    """Przegląd [DB] US-015: raport nie liczy COUNT po JOIN — liczba z podsumowania."""

    def test_report_page_reuses_summary_total(self):
        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        with CaptureQueriesContext(connection) as ctx:
            resp = self.client.get("/raporty/lokalizacje/", {"page": 2})
        self.assertEqual(len(resp.context["rows"]), N + 1 - PAGE_SIZE)
        counts = [
            q["sql"] for q in ctx.captured_queries if "COUNT(*)" in q["sql"].upper()
        ]
        self.assertFalse(any("handlingunit" in sql.lower() for sql in counts), counts)
