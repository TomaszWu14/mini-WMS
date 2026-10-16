"""Testy decyzji do otwartych problemów 1–5 z docs/07-ograniczenia.md."""

from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import RequestFactory, SimpleTestCase, TestCase, override_settings

from . import services
from .models import HandlingUnit, HUStatus, Material, Profile, Role, Unit
from .signals import _client_ip
from .stock_import import import_stock


class StockImportWarningsTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("imp", password="x")
        Unit.objects.get_or_create(code="PCS")

    def test_reports_zero_qty_and_over_capacity(self):
        # Nowa lokalizacja ma domyślną pojemność 1 — dwie palety z ilością ją przekraczają.
        data = (
            b"HU,REF,ilosc,lokalizacja\n"
            b"1,MAT-A,5,A-01\n"
            b"2,MAT-A,3,A-01\n"
            b"3,MAT-A,,Przyjecia\n"
        )
        result = import_stock("stany.csv", data, self.user)
        self.assertEqual(result["created"], 3)
        self.assertEqual(result["zero_qty"], 1)
        self.assertEqual(result["over_capacity"], ["A-01"])

    def test_no_warnings_when_within_capacity(self):
        result = import_stock(
            "stany.csv", b"HU,REF,ilosc,lokalizacja\n1,M,5,B-01\n", self.user
        )
        self.assertEqual(result["zero_qty"], 0)
        self.assertEqual(result["over_capacity"], [])


class _HUSetup(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("operator", password="x")
        Profile.objects.filter(user=self.user).update(role=Role.OPERATOR)
        self.client.login(username="operator", password="x")
        unit = Unit.objects.get_or_create(code="PCS")[0]
        self.material = Material.objects.create(index="MAT-1", name="M", unit=unit)
        for n in ("HU-A1", "HU-A2"):
            HandlingUnit.objects.create(
                number=n,
                material=self.material,
                quantity=5,
                status=HUStatus.DO_ULOZENIA,
            )


class HUNumberCaseTests(_HUSetup):
    def test_scanner_finds_hu_regardless_of_case(self):
        resp = self.client.get("/skaner/api/hu/", {"code": "hu-a1"})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["hu"]["number"], "HU-A1")


class HULabelsLimitTests(_HUSetup):
    def test_over_limit_redirects_with_message_instead_of_truncating(self):
        with patch("warehouse.views.HU_LABELS_LIMIT", 1):
            resp = self.client.get("/hu/etykiety/", {"q": "HU-A"}, follow=True)
        self.assertEqual(resp.redirect_chain[0][0], "/hu/?q=HU-A")
        self.assertContains(resp, "Wybrano 2 palet")

    def test_within_limit_returns_pdf(self):
        resp = self.client.get("/hu/etykiety/", {"q": "HU-A"})
        self.assertEqual(resp["Content-Type"], "application/pdf")


class ClientIPTests(SimpleTestCase):
    def _req(self, xff=None):
        extra = {"HTTP_X_FORWARDED_FOR": xff} if xff else {}
        return RequestFactory().get("/", REMOTE_ADDR="10.0.0.2", **extra)

    @override_settings(TRUSTED_PROXY_COUNT=0)
    def test_header_ignored_without_trusted_proxy(self):
        self.assertEqual(_client_ip(self._req("1.2.3.4")), "10.0.0.2")

    @override_settings(TRUSTED_PROXY_COUNT=1)
    def test_spoofed_first_entry_is_ignored_behind_one_proxy(self):
        # Klient podrobił „6.6.6.6”, proxy dopisało jego prawdziwy adres na końcu.
        self.assertEqual(_client_ip(self._req("6.6.6.6, 5.5.5.5")), "5.5.5.5")

    @override_settings(TRUSTED_PROXY_COUNT=2)
    def test_too_few_hops_falls_back_to_remote_addr(self):
        self.assertEqual(_client_ip(self._req("5.5.5.5")), "10.0.0.2")

    @override_settings(TRUSTED_PROXY_COUNT=1)
    def test_invalid_header_value_falls_back_to_remote_addr(self):
        """US-014 kryterium 1: wartość niebędąca adresem IP → REMOTE_ADDR."""
        for bad in (
            "unknown",
            "1.2.3.4:5678",
            "' OR 1=1",
            "x" * 300,
            "999.1.1.1",
            "[::1]",
        ):
            with self.subTest(bad=bad):
                self.assertEqual(_client_ip(self._req(f"6.6.6.6, {bad}")), "10.0.0.2")

    @override_settings(TRUSTED_PROXY_COUNT=1)
    def test_ipv6_kept_unchanged(self):
        """US-014 kryterium 2."""
        ip = "2001:db8::8a2e:370:7334"
        self.assertEqual(_client_ip(self._req(ip)), ip)

    def test_invalid_remote_addr_gives_none(self):
        req = RequestFactory().get("/", REMOTE_ADDR="nie-ip")
        self.assertIsNone(_client_ip(req))


class ClientIPLoginTests(TestCase):
    """US-014 kryterium 1 end-to-end: logowanie z błędnym nagłówkiem zapisuje dziennik."""

    @override_settings(TRUSTED_PROXY_COUNT=1, DEMO_MODE=False)
    def test_login_with_garbage_forwarded_for(self):
        from django.contrib.auth.models import User
        from django.core.cache import cache

        from .models import LoginEvent

        cache.clear()
        User.objects.create_user("ipuser", password="IpUserPass123!")
        resp = self.client.post(
            "/login/",
            {"username": "ipuser", "password": "IpUserPass123!"},
            REMOTE_ADDR="10.0.0.9",
            HTTP_X_FORWARDED_FOR="unknown",
        )
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(
            LoginEvent.objects.get(kind=LoginEvent.Kind.LOGIN).ip, "10.0.0.9"
        )


class StocktakeOverlapTests(_HUSetup):
    def test_second_open_sheet_skips_hus_already_counted(self):
        first = services.create_stocktake(user=self.user)
        self.assertEqual(first.lines.count(), 2)
        self.assertEqual(first.skipped_in_open, 0)

        second = services.create_stocktake(user=self.user)
        self.assertEqual(second.lines.count(), 0)
        self.assertEqual(second.skipped_in_open, 2)

    def test_line_without_hu_in_open_sheet_does_not_empty_new_sheets(self):
        first = services.create_stocktake(user=self.user)
        # Paleta usunięta w adminie → pozycja arkusza z handling_unit=NULL.
        first.lines.update(handling_unit=None)
        self.assertEqual(services.create_stocktake(user=self.user).lines.count(), 2)

    def test_hus_return_to_scope_after_sheet_is_closed(self):
        first = services.create_stocktake(user=self.user)
        services.close_stocktake(sheet=first, user=self.user)
        self.assertEqual(services.create_stocktake(user=self.user).lines.count(), 2)

    def test_view_warns_about_skipped(self):
        services.create_stocktake(user=self.user)
        resp = self.client.post("/spis/nowy/", {}, follow=True)
        self.assertContains(resp, "Pominięto 2 palet")
