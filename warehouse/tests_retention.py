"""US-005 / R7: retencja dziennika logowań, czyszczenie sesji, prywatność w demo."""

from datetime import timedelta
from importlib import import_module
from io import StringIO

from django.conf import settings
from django.contrib.auth.models import User
from django.contrib.sessions.models import Session
from django.core.management import CommandError, call_command
from django.test import TestCase, override_settings
from django.utils import timezone

from .models import LoginEvent


def _event(days_ago):
    return LoginEvent.objects.create(
        username="u",
        kind=LoginEvent.Kind.LOGIN,
        created_at=timezone.now() - timedelta(days=days_ago),
    )


class PurgeLoginEventsTests(TestCase):
    def _purge(self, **kwargs):
        out = StringIO()
        call_command("purge_login_events", stdout=out, **kwargs)
        return out.getvalue()

    def test_default_retention_90_days(self):
        _event(100)
        _event(91)
        keep = _event(10)
        self.assertIn("Usunięto 2 ", self._purge())
        self.assertEqual(list(LoginEvent.objects.all()), [keep])
        self.assertIn("Usunięto 0 ", self._purge())

    def test_days_option_overrides_default(self):
        _event(40)
        keep = _event(10)
        self._purge(days=30)
        self.assertEqual(list(LoginEvent.objects.all()), [keep])

    def test_boundary_89_days_kept(self):
        keep = _event(89)
        self._purge()
        self.assertEqual(list(LoginEvent.objects.all()), [keep])

    def test_invalid_days_refused(self):
        _event(100)
        with self.assertRaises(CommandError):
            self._purge(days=0)
        self.assertEqual(LoginEvent.objects.count(), 1)

    def test_default_is_90(self):
        self.assertEqual(settings.LOGIN_EVENT_RETENTION_DAYS, 90)


class ClearSessionsTests(TestCase):
    def _session(self, expire_delta):
        store = import_module(settings.SESSION_ENGINE).SessionStore()
        store["x"] = 1
        store.create()
        Session.objects.filter(session_key=store.session_key).update(
            expire_date=timezone.now() + expire_delta
        )
        return store.session_key

    def test_clearsessions_removes_only_expired(self):
        self._session(timedelta(minutes=-5))
        active = self._session(timedelta(minutes=25))
        call_command("clearsessions")
        self.assertEqual(
            list(Session.objects.values_list("session_key", flat=True)), [active]
        )


class LoginEventPrivacyTests(TestCase):
    def setUp(self):
        from django.core.cache import cache

        cache.clear()
        User.objects.create_user("jan", password="JanPass123!")

    def _login(self, password="JanPass123!"):
        self.client.post(
            "/login/",
            {"username": "jan", "password": password},
            REMOTE_ADDR="203.0.113.7",
            HTTP_USER_AGENT="Przegladarka/1.0",
        )

    @override_settings(DEMO_MODE=True)
    def test_demo_mode_stores_no_ip_or_user_agent(self):
        self._login()
        self._login(password="zle")
        self.assertEqual(LoginEvent.objects.count(), 2)
        for event in LoginEvent.objects.all():
            self.assertIsNone(event.ip)
            self.assertEqual(event.user_agent, "")

    @override_settings(DEMO_MODE=False)
    def test_outside_demo_ip_and_user_agent_kept(self):
        self._login()
        event = LoginEvent.objects.get()
        self.assertEqual(event.ip, "203.0.113.7")
        self.assertEqual(event.user_agent, "Przegladarka/1.0")
