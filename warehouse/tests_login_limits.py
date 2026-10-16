"""US-009 / R6: limit nieudanych logowań na konto, wspólny dla workerów."""

from unittest.mock import patch

from django.conf import settings
from django.contrib.auth.models import User
from django.core.cache import cache
from django.db import connection
from django.test import TestCase

from .models import LoginEvent


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
        # Upływ okna = wygaśnięcie klucza w cache.
        from .demo import account_key

        cache.delete(account_key("admin"))
        resp = self._post("admin", "AdminPass123!", "203.0.113.51")
        self.assertEqual(resp.status_code, 302)

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


class SharedCacheTests(TestCase):
    """Kryterium 3: licznik w cache współdzielonym przez wszystkie procesy."""

    def setUp(self):
        cache.clear()

    def test_cache_backend_is_database(self):
        self.assertEqual(
            settings.CACHES["default"]["BACKEND"],
            "django.core.cache.backends.db.DatabaseCache",
        )

    def test_counter_stored_in_database_table(self):
        from .demo import account_key

        User.objects.create_user("admin", password="AdminPass123!")
        self.client.post("/login/", {"username": "admin", "password": "zle"})
        table = settings.CACHES["default"]["LOCATION"]
        with connection.cursor() as cur:
            cur.execute(f"SELECT cache_key FROM {table}")  # nosec B608  # nosemgrep
            keys = [row[0] for row in cur.fetchall()]
        self.assertTrue(any(account_key("admin") in k for k in keys), keys)

    def test_limit_global_across_cache_clients(self):
        """Nowy klient cache (jak inny worker gunicorna) widzi ten sam licznik."""
        from django.core.cache import caches

        from .demo import account_key, account_locked

        User.objects.create_user("admin", password="AdminPass123!")
        for i in range(settings.LOGIN_ACCOUNT_LIMIT):
            self.client.post(
                "/login/",
                {"username": "admin", "password": "zle"},
                REMOTE_ADDR=f"192.0.2.{i + 1}",
            )
        other_worker = caches.create_connection("default")
        self.assertEqual(
            other_worker.get(account_key("admin")), settings.LOGIN_ACCOUNT_LIMIT
        )
        self.assertTrue(account_locked("admin"))
