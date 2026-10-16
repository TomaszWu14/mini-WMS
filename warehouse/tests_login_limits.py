"""US-009 / R6: limit nieudanych logowań na konto, wspólny dla workerów."""

from datetime import timedelta
from io import StringIO
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth.models import User
from django.core.cache import cache
from django.core.management import call_command
from django.db import connection
from django.test import TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from .login_limits import account_failed, account_key, account_locked
from .models import LoginEvent, LoginFailureCounter


class AccountLockoutTests(TestCase):
    def setUp(self):
        cache.clear()
        self.admin = User.objects.create_user("admin", password="AdminPass123!")
        User.objects.create_user("operator_b", password="OperatorB123!")
        self.limit = settings.LOGIN_ACCOUNT_LIMIT

    def _post(self, username, password, ip):
        return self.client.post(
            "/login/",
            {"username": username, "password": password},
            REMOTE_ADDR=ip,
        )

    def _fail_from_many_ips(self, username="admin", n=None):
        for i in range(n if n is not None else self.limit):
            resp = self._post(username, "zle-haslo", f"198.51.100.{i + 1}")
            self.assertEqual(resp.status_code, 200)

    def test_lockout_from_many_ips_blocks_correct_password(self):
        """Kryterium 1: N prób z różnych IP → 429 także z poprawnym hasłem."""
        self._fail_from_many_ips()
        resp = self._post("admin", "AdminPass123!", "203.0.113.50")
        self.assertEqual(resp.status_code, 429)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_login_works_after_window(self):
        self._fail_from_many_ips()
        # Upływ okna: przesuwamy początek okna o 15 min + 1 s wstecz.
        LoginFailureCounter.objects.update(
            window_start=timezone.now()
            - timedelta(seconds=settings.LOGIN_ACCOUNT_WINDOW + 1)
        )
        resp = self._post("admin", "AdminPass123!", "203.0.113.51")
        self.assertEqual(resp.status_code, 302)

    def test_still_locked_just_before_window_end(self):
        """Uwaga [DB] US-009: okno ma pełne 15 min (nie 5 z domyślnego TIMEOUT cache)."""
        self._fail_from_many_ips()
        LoginFailureCounter.objects.update(
            window_start=timezone.now()
            - timedelta(seconds=settings.LOGIN_ACCOUNT_WINDOW - 30)
        )
        self.assertEqual(
            self._post("admin", "AdminPass123!", "203.0.113.59").status_code, 429
        )

    def test_unicode_variants_hit_same_counter(self):
        """Uwaga [SEC] US-009: warianty NFKC loginu nie omijają blokady."""
        self._fail_from_many_ips()
        for variant in ("ａｄｍｉｎ", "𝐚dmin", " admin ", "ADMIN"):
            with self.subTest(variant=variant):
                resp = self._post(variant, "AdminPass123!", "203.0.113.60")
                self.assertEqual(resp.status_code, 429)

    def test_unicode_failures_counted_on_canonical_login(self):
        for i in range(self.limit):
            self._post("ａｄｍｉｎ", "zle", f"198.51.100.{i + 1}")
        self.assertEqual(
            self._post("admin", "AdminPass123!", "203.0.113.61").status_code, 429
        )

    def test_lockout_is_case_insensitive(self):
        self._fail_from_many_ips(username="ADMIN")
        self.assertEqual(
            self._post("admin", "AdminPass123!", "203.0.113.52").status_code, 429
        )

    def test_other_account_not_blocked(self):
        """Kryterium 2: brak globalnej blokady."""
        self._fail_from_many_ips()
        resp = self._post("operator_b", "OperatorB123!", "203.0.113.53")
        self.assertEqual(resp.status_code, 302)

    def test_below_limit_and_success_resets_counter(self):
        self._fail_from_many_ips(n=self.limit - 1)
        self.assertEqual(
            self._post("admin", "AdminPass123!", "203.0.113.54").status_code, 302
        )
        self.client.logout()
        self._fail_from_many_ips(n=self.limit - 1)
        self.assertEqual(
            self._post("admin", "AdminPass123!", "203.0.113.55").status_code, 302
        )

    def test_unknown_account_gets_same_response(self):
        """Blokada nie ujawnia, czy konto istnieje."""
        self._fail_from_many_ips(username="nie_ma_takiego")
        resp = self._post("nie_ma_takiego", "cokolwiek", "203.0.113.56")
        self.assertEqual(resp.status_code, 429)

    def test_blocked_attempt_logged_without_password(self):
        """Kryterium 4: wpis „Zablokowana próba” bez hasła."""
        self._fail_from_many_ips()
        self._post("admin", "AdminPass123!", "203.0.113.57")
        event = LoginEvent.objects.get(kind=LoginEvent.Kind.BLOCKED)
        self.assertEqual(event.username, "admin")
        self.assertEqual(event.ip, "203.0.113.57")
        for field in ("username", "user_agent"):
            self.assertNotIn("AdminPass123!", getattr(event, field))

    def test_blocked_attempt_does_not_check_password(self):
        self._fail_from_many_ips()
        with patch("django.contrib.auth.forms.authenticate") as auth:
            self._post("admin", "AdminPass123!", "203.0.113.58")
        auth.assert_not_called()


class SharedCounterTests(TestCase):
    """Kryterium 3: licznik w bazie, wspólny dla procesów, zwiększany atomowo."""

    def setUp(self):
        cache.clear()
        User.objects.create_user("admin", password="AdminPass123!")

    def test_counter_row_in_database(self):
        for i in range(settings.LOGIN_ACCOUNT_LIMIT):
            self.client.post(
                "/login/",
                {"username": "admin", "password": "zle"},
                REMOTE_ADDR=f"192.0.2.{i + 1}",
            )
        row = LoginFailureCounter.objects.get(key=account_key("admin"))
        self.assertEqual(row.count, settings.LOGIN_ACCOUNT_LIMIT)
        self.assertTrue(account_locked("admin"))

    def test_increment_is_single_update(self):
        """`count = count + 1` w jednym UPDATE (bez odczytu i zapisu z Pythona)."""
        account_failed("admin")
        with CaptureQueriesContext(connection) as ctx:
            account_failed("admin")
        sql = " ".join(q["sql"] for q in ctx.captured_queries)
        self.assertEqual(len(ctx.captured_queries), 1, sql)
        self.assertIn("UPDATE", sql.upper())

    def test_cache_flood_cannot_reset_counter(self):
        """Uwaga [SEC]/[DB] US-009: zalanie cache nie kasuje licznika konta."""
        for _ in range(settings.LOGIN_ACCOUNT_LIMIT):
            account_failed("admin")
        cache.clear()
        self.assertTrue(account_locked("admin"))

    def test_cache_has_large_max_entries(self):
        self.assertGreaterEqual(
            settings.CACHES["default"]["OPTIONS"]["MAX_ENTRIES"], 100_000
        )

    def test_ip_not_stored_in_cache_keys(self):
        self.client.post(
            "/login/", {"username": "x", "password": "zle"}, REMOTE_ADDR="203.0.113.99"
        )
        table = settings.CACHES["default"]["LOCATION"]
        with connection.cursor() as cur:
            cur.execute(f"SELECT cache_key FROM {table}")  # nosec B608  # nosemgrep
            keys = " ".join(row[0] for row in cur.fetchall())
        self.assertIn("login-rl:", keys)
        self.assertNotIn("203.0.113.99", keys)

    def test_purge_removes_expired_counters(self):
        account_failed("stary")
        LoginFailureCounter.objects.update(
            window_start=timezone.now() - timedelta(days=1)
        )
        account_failed("admin")
        call_command("purge_login_events", stdout=StringIO())
        self.assertEqual(
            list(LoginFailureCounter.objects.values_list("key", flat=True)),
            [account_key("admin")],
        )


class AdminLoginGuardTests(TestCase):
    """Uwaga [SEC] US-009: /admin/login/ ma ten sam limit i blokadę co /login/."""

    def setUp(self):
        cache.clear()
        User.objects.create_superuser("root", password="RootPass123!")

    def _post(self, password, ip):
        return self.client.post(
            "/admin/login/?next=/admin/",
            {"username": "root", "password": password},
            REMOTE_ADDR=ip,
        )

    def test_account_lock_applies_to_admin_login(self):
        for i in range(settings.LOGIN_ACCOUNT_LIMIT):
            self.assertEqual(self._post("zle", f"198.51.100.{i + 1}").status_code, 200)
        self.assertEqual(self._post("RootPass123!", "203.0.113.70").status_code, 429)
        self.assertTrue(
            LoginEvent.objects.filter(
                kind=LoginEvent.Kind.BLOCKED, username="root"
            ).exists()
        )

    def test_ip_limit_applies_to_admin_login(self):
        from .demo import LOGIN_RATE_LIMIT

        for _ in range(LOGIN_RATE_LIMIT):
            self._post("zle", "203.0.113.71")
        self.assertEqual(self._post("zle", "203.0.113.71").status_code, 429)

    def test_admin_login_still_works(self):
        resp = self._post("RootPass123!", "203.0.113.72")
        self.assertEqual(resp.status_code, 302)


@override_settings(DEMO_MODE=True)
class DemoAccountsExemptTests(TestCase):
    """Uwaga [SEC] US-009: gość nie zablokuje publicznych kont demo."""

    def setUp(self):
        cache.clear()
        call_command("seed_demo", stdout=StringIO())

    def test_demo_account_never_locked(self):
        for i in range(settings.LOGIN_ACCOUNT_LIMIT + 2):
            self.client.post(
                "/login/",
                {"username": "demo_podglad", "password": "zle"},
                REMOTE_ADDR=f"198.51.100.{i + 1}",
            )
        resp = self.client.post(
            "/login/",
            {"username": "demo_podglad", "password": settings.DEMO_PASSWORD},
            REMOTE_ADDR="203.0.113.80",
        )
        self.assertEqual(resp.status_code, 302)
        self.assertFalse(LoginFailureCounter.objects.exists())
