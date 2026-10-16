"""US-010 / SEC-006: weryfikacja dwuetapowa (TOTP) dla Administratora."""

from io import StringIO

from django.conf import settings
from django.contrib.auth.models import User
from django.core.cache import cache
from django.core.management import CommandError, call_command
from django.test import TestCase
from django_otp.oath import TOTP
from django_otp.plugins.otp_totp.models import TOTPDevice

from .models import LoginEvent, Profile, Role

PASSWORD = "AdminPass123!"


def _token(device):
    totp = TOTP(device.bin_key, device.step, device.t0, device.digits, device.drift)
    return f"{totp.token():0{device.digits}d}"


class _Base(TestCase):
    def setUp(self):
        cache.clear()
        self.admin = User.objects.create_user("szef", password=PASSWORD)
        Profile.objects.filter(user=self.admin).update(role=Role.ADMIN)

    def _enroll(self, user=None):
        return TOTPDevice.objects.create(
            user=user or self.admin, name="aplikacja", confirmed=True
        )

    def _login(self, username="szef", password=PASSWORD):
        return self.client.post("/login/", {"username": username, "password": password})


class AdminTwoFactorTests(_Base):
    def test_password_only_gives_no_access(self):
        """Kryterium 1: samo hasło → przekierowanie na kod (widoki admina, /admin/, pulpit)."""
        self._enroll()
        self._login()
        for url in ("/uzytkownicy/", "/uzytkownicy/dziennik/", "/", "/przyjecie/"):
            with self.subTest(url=url):
                resp = self.client.get(url)
                self.assertEqual(resp.status_code, 302)
                self.assertTrue(resp["Location"].startswith("/2fa/weryfikacja/"))

    def test_admin_site_requires_code(self):
        self.admin.is_staff = True
        self.admin.is_superuser = True
        self.admin.save()
        self._enroll()
        self._login()
        resp = self.client.get("/admin/")
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(resp["Location"].startswith("/2fa/weryfikacja/"))

    def test_correct_code_gives_access(self):
        """Kryterium 2: poprawny kod → pełny dostęp, powrót pod `next`."""
        device = self._enroll()
        self._login()
        resp = self.client.post(
            "/2fa/weryfikacja/", {"token": _token(device), "next": "/uzytkownicy/"}
        )
        self.assertRedirects(resp, "/uzytkownicy/")
        self.assertEqual(self.client.get("/uzytkownicy/").status_code, 200)

    def test_external_next_ignored(self):
        device = self._enroll()
        self._login()
        resp = self.client.post(
            "/2fa/weryfikacja/",
            {"token": _token(device), "next": "https://zly.example/"},
        )
        self.assertRedirects(resp, "/")

    def test_wrong_codes_count_to_account_limit(self):
        """Kryterium 2: nieudane kody liczą się do blokady konta z US-009."""
        self._enroll()
        self._login()
        for _ in range(settings.LOGIN_ACCOUNT_LIMIT):
            resp = self.client.post("/2fa/weryfikacja/", {"token": "000000"})
            self.assertEqual(resp.status_code, 200)
            self.assertContains(resp, "Niepoprawny lub przeterminowany kod")
        self.assertEqual(
            self.client.post("/2fa/weryfikacja/", {"token": "000000"}).status_code, 429
        )
        self.assertEqual(
            LoginEvent.objects.filter(
                kind=LoginEvent.Kind.FAILED, username="szef"
            ).count(),
            settings.LOGIN_ACCOUNT_LIMIT,
        )

    def test_logout_allowed_without_code(self):
        self._enroll()
        self._login()
        resp = self.client.post("/logout/")
        self.assertEqual(resp.status_code, 302)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_admin_without_2fa_unchanged(self):
        self._login()
        self.assertEqual(self.client.get("/uzytkownicy/").status_code, 200)


class OtherRolesTests(_Base):
    def test_operator_and_viewer_unchanged(self):
        """Kryterium 4: Operator i Podgląd logują się bez zmian."""
        for role in (Role.OPERATOR, Role.VIEWER):
            with self.subTest(role=role):
                user = User.objects.create_user(f"u_{role}", password=PASSWORD)
                Profile.objects.filter(user=user).update(role=role)
                self.client.logout()
                self._login(username=f"u_{role}")
                self.assertEqual(self.client.get("/").status_code, 200)

    def test_operator_cannot_enroll(self):
        user = User.objects.create_user("op", password=PASSWORD)
        Profile.objects.filter(user=user).update(role=Role.OPERATOR)
        self._login(username="op")
        self.assertEqual(self.client.get("/2fa/").status_code, 403)
        self.assertFalse(TOTPDevice.objects.exists())


class EnrollmentTests(_Base):
    def test_enroll_with_qr_and_first_code(self):
        self._login()
        resp = self.client.get("/2fa/")
        self.assertContains(resp, "<svg")
        device = TOTPDevice.objects.get(user=self.admin)
        self.assertFalse(device.confirmed)
        # Niepotwierdzone urządzenie nie wymusza kodu.
        self.assertEqual(self.client.get("/uzytkownicy/").status_code, 200)
        resp = self.client.post("/2fa/", {"token": _token(device)})
        self.assertRedirects(resp, "/")
        device.refresh_from_db()
        self.assertTrue(device.confirmed)
        # Ta sesja jest już zweryfikowana; nowe logowanie wymaga kodu.
        self.assertEqual(self.client.get("/uzytkownicy/").status_code, 200)
        self.client.logout()
        self._login()
        self.assertEqual(self.client.get("/uzytkownicy/").status_code, 302)

    def test_wrong_first_code_does_not_enable(self):
        self._login()
        self.client.get("/2fa/")
        resp = self.client.post("/2fa/", {"token": "123456"})
        self.assertContains(resp, "Kod się nie zgadza")
        self.assertFalse(TOTPDevice.objects.get(user=self.admin).confirmed)


class EnrollmentSecretTests(_Base):
    """Uwaga [SEC] US-010: podejrzany sekret nie przeżywa ponownego otwarcia strony."""

    def test_each_visit_generates_new_secret(self):
        self._login()
        self.client.get("/2fa/")
        first = TOTPDevice.objects.get(user=self.admin).key
        resp = self.client.get("/2fa/")
        self.assertEqual(TOTPDevice.objects.filter(user=self.admin).count(), 1)
        self.assertNotEqual(TOTPDevice.objects.get(user=self.admin).key, first)
        self.assertIn("no-store", resp["Cache-Control"])

    def test_next_with_query_preserved(self):
        self._enroll()
        self._login()
        resp = self.client.get("/ruchy/?type=PRZYJECIE&page=2")
        self.assertIn(
            "next=%2Fruchy%2F%3Ftype%3DPRZYJECIE%26page%3D2", resp["Location"]
        )


class ResetCommandTests(_Base):
    def test_reset_after_lost_device(self):
        """Kryterium 3: reset poleceniem → samo hasło, potem nowe urządzenie."""
        self._enroll()
        out = StringIO()
        call_command("reset_2fa", "szef", stdout=out)
        self.assertIn("Usunięto 1", out.getvalue())
        self.assertFalse(TOTPDevice.objects.filter(user=self.admin).exists())
        self._login()
        self.assertEqual(self.client.get("/uzytkownicy/").status_code, 200)
        self.assertContains(self.client.get("/2fa/"), "<svg")

    def test_reset_unknown_user(self):
        with self.assertRaises(CommandError):
            call_command("reset_2fa", "nikt", stdout=StringIO())
