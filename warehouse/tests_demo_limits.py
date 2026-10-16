"""US-016 / DEC-6: limity obiektów i zapisów w demo, reset tylko z harmonogramu."""

import io
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.cache import cache
from django.core.management import call_command
from django.test import TestCase, override_settings

from . import services
from .demo import DEMO_WRITE_RATE_LIMIT
from .forms import ReceiveForm
from .imports import import_locations
from .models import HandlingUnit, Location, Material, Unit
from .receipt_import import import_receipts
from .stock_import import import_stock


def _csv(header, *rows):
    lines = [";".join(header)] + [";".join(map(str, r)) for r in rows]
    return ("\n".join(lines) + "\n").encode()


@override_settings(DEMO_MODE=True)
class _DemoBase(TestCase):
    def setUp(self):
        cache.clear()
        call_command("seed_demo", stdout=io.StringIO())
        self.operator = User.objects.get(username="demo_operator")
        self.client.force_login(self.operator)
        self.material = Material.objects.filter(index__startswith="DEMO-").first()
        self.hus = HandlingUnit.objects.count()
        self.locs = Location.objects.count()


class DemoLimitsTests(_DemoBase):
    """Kryterium 1: przy L_DEMO przyjęcie / import zwiększający liczbę → „limit demo”."""

    def _at_limit(self, hus=0, locs=0):
        return (
            patch.object(services, "DEMO_MAX_HANDLING_UNITS", self.hus + hus),
            patch.object(services, "DEMO_MAX_LOCATIONS", self.locs + locs),
        )

    def test_defaults(self):
        self.assertEqual(services.DEMO_MAX_HANDLING_UNITS, 2000)
        self.assertEqual(services.DEMO_MAX_LOCATIONS, 500)

    def test_receive_form_rejected_at_limit(self):
        hu_limit, loc_limit = self._at_limit(hus=1)
        with hu_limit, loc_limit:
            resp = self.client.post(
                "/przyjecie/",
                {
                    "material": self.material.pk,
                    "mode": ReceiveForm.MODE_TOTAL,
                    "total_quantity": 10,
                    "pallets": 2,
                },
                follow=True,
            )
        self.assertContains(resp, "Limit demo")
        self.assertEqual(HandlingUnit.objects.count(), self.hus)

    def test_receive_within_limit(self):
        hu_limit, loc_limit = self._at_limit(hus=2)
        with hu_limit, loc_limit:
            services.receive_material(
                material=self.material, quantities=[1, 1], user=self.operator
            )
        self.assertEqual(HandlingUnit.objects.count(), self.hus + 2)

    def test_receipt_import_stops_at_limit(self):
        data = _csv(
            ["indeks", "ilosc", "palety"],
            (self.material.index, 1, 1),
            (self.material.index, 1, 1),
        )
        hu_limit, loc_limit = self._at_limit(hus=1)
        with hu_limit, loc_limit:
            result = import_receipts("p.csv", data, self.operator)
        self.assertEqual(HandlingUnit.objects.count(), self.hus + 1, result)
        self.assertTrue(any("Limit demo" in e for e in result["errors"]), result)

    def test_stock_import_counts_hus_and_new_locations(self):
        existing = Location.objects.first().code
        data = _csv(
            ["REF", "lokalizacja", "ilosc"],
            ("MAT-L1", existing, 1),  # HU w istniejącej lokalizacji — mieści się
            ("MAT-L2", "NOWA-01", 1),  # nowa lokalizacja ponad limit
            ("MAT-L3", existing, 1),  # HU ponad limit
        )
        hu_limit, loc_limit = self._at_limit(hus=1, locs=0)
        with hu_limit, loc_limit:
            result = import_stock("s.csv", data, self.operator)
        self.assertEqual(result["created"], 1, result["errors"])
        self.assertFalse(Location.objects.filter(code="NOWA-01").exists())
        self.assertEqual(sum("Limit demo" in e for e in result["errors"]), 2)

    def test_location_import_and_form_rejected_at_limit(self):
        existing = Location.objects.first()
        data = _csv(
            ["kod", "typ", "pojemnosc"],
            (existing.code, "ZAPAS", 3),
            ("NOWA-02", "ZAPAS", 1),
        )
        hu_limit, loc_limit = self._at_limit()
        with hu_limit, loc_limit:
            created, updated, errors = import_locations("l.csv", data)
            resp = self.client.post(
                "/lokalizacje/nowa/",
                {"code": "NOWA-03", "type": "ZAPAS", "capacity": 1},
                follow=True,
            )
        # aktualizacja istniejącej lokalizacji przechodzi, nowa — nie
        self.assertEqual((created, updated), (0, 1))
        self.assertIn("Limit demo", errors[0])
        self.assertContains(resp, "Limit demo")
        self.assertEqual(Location.objects.count(), self.locs)

    @override_settings(DEMO_MODE=False)
    def test_no_limit_outside_demo(self):
        with patch.object(services, "DEMO_MAX_HANDLING_UNITS", 0):
            services.receive_material(
                material=self.material, quantities=[1], user=self.operator
            )
        self.assertEqual(HandlingUnit.objects.count(), self.hus + 1)


class DemoWriteRateLimitTests(_DemoBase):
    """Kryterium 2: > K POST-ów ze ścieżek operatora z jednego IP w oknie W → 429."""

    def _post_many(self, url, n, **extra):
        return [self.client.post(url, {}, **extra).status_code for _ in range(n)]

    def test_over_limit_gets_429(self):
        codes = self._post_many("/przyjecie/", DEMO_WRITE_RATE_LIMIT)
        self.assertNotIn(429, codes)
        resp = self.client.post("/przyjecie/", {})
        self.assertEqual(resp.status_code, 429)
        self.assertContains(resp, "Zbyt wiele operacji", status_code=429)

    def test_scanner_api_gets_json(self):
        self._post_many("/skaner/api/pick/", DEMO_WRITE_RATE_LIMIT)
        resp = self.client.post("/skaner/api/pick/", {})
        self.assertEqual(resp.status_code, 429)
        self.assertFalse(resp.json()["ok"])

    def test_per_ip_and_logout_always_works(self):
        self._post_many(
            "/przyjecie/", DEMO_WRITE_RATE_LIMIT + 1, REMOTE_ADDR="198.51.100.7"
        )
        other = self.client.post("/przyjecie/", {}, REMOTE_ADDR="198.51.100.8")
        self.assertNotEqual(other.status_code, 429)
        resp = self.client.post("/logout/", REMOTE_ADDR="198.51.100.7")
        self.assertEqual(resp.status_code, 302)

    def test_get_not_counted(self):
        for _ in range(DEMO_WRITE_RATE_LIMIT + 5):
            self.client.get("/hu/")
        self.assertNotEqual(self.client.post("/przyjecie/", {}).status_code, 429)

    @override_settings(DEMO_MODE=False)
    def test_off_outside_demo(self):
        user = User.objects.create_superuser("szef", password="x")
        self.client.force_login(user)
        codes = self._post_many("/przyjecie/", DEMO_WRITE_RATE_LIMIT + 2)
        self.assertNotIn(429, codes)


class DemoScheduledResetTests(_DemoBase):
    """Kryterium 3: brak resetu z UI; `seed_demo --reset --keep-users` zachowuje sesje."""

    def test_ui_reset_gone(self):
        self.assertEqual(self.client.post("/demo/przywroc/").status_code, 404)
        self.assertNotContains(self.client.get("/"), "Przywróć dane demo")

    def test_scheduled_reset_restores_data_and_keeps_session(self):
        HandlingUnit.objects.all().delete()
        Material.objects.create(index="OBCY-1", name="Gość", unit=Unit.objects.first())
        call_command("seed_demo", reset=True, keep_users=True, stdout=io.StringIO())
        self.assertEqual(HandlingUnit.objects.count(), self.hus)
        self.assertFalse(Material.objects.filter(index="OBCY-1").exists())
        self.assertEqual(
            User.objects.get(username="demo_operator").pk, self.operator.pk
        )
        resp = self.client.get("/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(int(self.client.session["_auth_user_id"]), self.operator.pk)


class DemoReviewFixTests(_DemoBase):
    """Uwagi z przeglądów [SEC]/[DB] US-016."""

    def test_ipv6_limited_per_64_prefix(self):
        for n in range(DEMO_WRITE_RATE_LIMIT):
            self.client.post("/przyjecie/", {}, REMOTE_ADDR=f"2001:db8:1:1::{n + 1:x}")
        same_64 = self.client.post("/przyjecie/", {}, REMOTE_ADDR="2001:db8:1:1::ffff")
        self.assertEqual(same_64.status_code, 429)
        other_64 = self.client.post("/przyjecie/", {}, REMOTE_ADDR="2001:db8:1:2::1")
        self.assertNotEqual(other_64.status_code, 429)

    def test_receipt_import_counts_once_per_file(self):
        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        rows = [(self.material.index, 1, 1)] * 20
        data = _csv(["indeks", "ilosc", "palety"], *rows)
        with CaptureQueriesContext(connection) as ctx:
            result = import_receipts("p.csv", data, self.operator)
        self.assertEqual(result["created_hus"], 20, result["errors"])
        counts = [
            q["sql"] for q in ctx.captured_queries if "COUNT(*)" in q["sql"].upper()
        ]
        self.assertEqual(len(counts), 1, counts)  # tylko HU, raz na plik
