"""Testy trybu demo: seed_demo, baner, loginy demo, rate limit, ochrona kont."""

from io import StringIO

from django.contrib.auth.models import User
from django.core.cache import cache
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings

from .demo import DEMO_PASSWORD, LOGIN_RATE_LIMIT
from .models import (
    HandlingUnit,
    HUStatus,
    IssueDocument,
    IssueStatus,
    Material,
    Profile,
    Role,
    StockMovement,
    StocktakeSheet,
    StocktakeStatus,
)

BANNER = "DEMO — dane przykładowe"


def seed(*args):
    call_command("seed_demo", *args, stdout=StringIO())


class SeedDemoTests(TestCase):
    def test_seed_creates_data(self):
        seed()
        self.assertEqual(Material.objects.count(), 15)
        self.assertEqual(HandlingUnit.objects.count(), 30)
        self.assertTrue(
            HandlingUnit.objects.filter(status=HUStatus.DO_ULOZENIA).exists()
        )
        self.assertEqual(
            set(IssueDocument.objects.values_list("status", flat=True)),
            {IssueStatus.OTWARTY, IssueStatus.ZREALIZOWANY, IssueStatus.WYSLANY},
        )
        self.assertTrue(
            StocktakeSheet.objects.filter(status=StocktakeStatus.OTWARTY).exists()
        )
        self.assertEqual(
            User.objects.get(username="demo_operator").profile.role, Role.OPERATOR
        )
        self.assertEqual(
            User.objects.get(username="demo_podglad").profile.role, Role.VIEWER
        )
        self.assertFalse(User.objects.filter(is_superuser=True).exists())

    def test_seed_twice_is_noop(self):
        seed()
        movements = StockMovement.objects.count()
        seed()
        self.assertEqual(StockMovement.objects.count(), movements)

    @override_settings(DEMO_MODE=True)
    def test_reset_is_idempotent_and_deterministic(self):
        seed()
        first = list(
            HandlingUnit.objects.order_by("number").values_list(
                "number", "material__index", "quantity", "expiry_date"
            )
        )
        seed("--reset")
        second = list(
            HandlingUnit.objects.order_by("number").values_list(
                "number", "material__index", "quantity", "expiry_date"
            )
        )
        self.assertEqual(first, second)
        self.assertEqual(User.objects.filter(username__startswith="demo_").count(), 2)

    def test_reset_refused_without_demo_mode(self):
        with self.assertRaises(CommandError):
            seed("--reset")


class DemoModeViewTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user("demo_operator", password=DEMO_PASSWORD)
        Profile.objects.filter(user=self.user).update(role=Role.OPERATOR)

    def test_no_banner_or_logins_without_demo_mode(self):
        resp = self.client.get("/login/")
        self.assertNotContains(resp, BANNER)
        self.assertNotContains(resp, DEMO_PASSWORD)

    @override_settings(DEMO_MODE=True)
    def test_banner_and_logins_on_login_page(self):
        resp = self.client.get("/login/")
        self.assertContains(resp, BANNER)
        self.assertContains(resp, "demo_podglad")
        self.assertContains(resp, DEMO_PASSWORD)

    @override_settings(DEMO_MODE=True)
    def test_banner_on_app_and_scanner(self):
        self.client.login(username="demo_operator", password=DEMO_PASSWORD)
        self.assertContains(self.client.get("/"), BANNER)
        self.assertContains(self.client.get("/skaner/"), BANNER)

    @override_settings(DEMO_MODE=True)
    def test_login_rate_limit(self):
        data = {"username": "x", "password": "zle"}
        for _ in range(LOGIN_RATE_LIMIT):
            self.assertEqual(self.client.post("/login/", data).status_code, 200)
        self.assertEqual(self.client.post("/login/", data).status_code, 429)

    def test_no_rate_limit_without_demo_mode(self):
        data = {"username": "x", "password": "zle"}
        for _ in range(LOGIN_RATE_LIMIT + 2):
            self.assertEqual(self.client.post("/login/", data).status_code, 200)

    @override_settings(DEMO_MODE=True)
    def test_demo_account_cannot_change_password(self):
        # Sam operator demo nie ma dostępu do zarządzania kontami...
        self.client.login(username="demo_operator", password=DEMO_PASSWORD)
        resp = self.client.post(
            f"/uzytkownicy/{self.user.pk}/",
            {"role": Role.OPERATOR, "is_active": "on", "new_password": "Inne123!x"},
        )
        self.assertEqual(resp.status_code, 403)
        # ...a administrator nie zmieni hasła konta demo w trybie demo.
        User.objects.create_superuser("szef", password="x")
        self.client.login(username="szef", password="x")
        resp = self.client.post(
            f"/uzytkownicy/{self.user.pk}/",
            {"role": Role.OPERATOR, "is_active": "on", "new_password": "Inne123!x"},
        )
        self.assertEqual(resp.status_code, 403)
        self.assertContains(resp, "Konta demo są chronione", status_code=403)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(DEMO_PASSWORD))
