"""US-022: dziennik audytowy akcji administracyjnych i logi bez sekretów."""

import io
import json
import logging
from datetime import timedelta

from django.contrib.auth.models import User
from django.core.cache import cache
from django.core.management import call_command
from django.test import RequestFactory, TestCase, override_settings
from django.utils import timezone

from config.log import REDACTED, JsonFormatter

from .models import AuditEvent, LoginEvent, Profile, Role

SECRET = "Sekretne-Haslo-123!"


class _Base(TestCase):
    def setUp(self):
        cache.clear()
        self.admin = User.objects.create_user("szef", password="SzefPass123!")
        Profile.objects.filter(user=self.admin).update(role=Role.ADMIN)
        self.user = User.objects.create_user("magazynier", password="MagPass123!")
        Profile.objects.filter(user=self.user).update(role=Role.OPERATOR)
        self.client.force_login(self.admin)

    def _edit(self, user, **data):
        payload = {"role": Role.OPERATOR, "is_active": "on", **data}
        if payload.get("is_active") is False:
            payload.pop("is_active")
        return self.client.post(f"/uzytkownicy/{user.pk}/", payload)


class AuditLogTests(_Base):
    """Kryteria 1–2: aktor, cel, akcja, czas, wynik; bez wartości hasła."""

    def test_role_password_status_changes_each_logged(self):
        resp = self._edit(
            self.user,
            role=Role.ADMIN,
            is_active=False,
            new_password=SECRET,
            new_password2=SECRET,
        )
        self.assertEqual(resp.status_code, 302, getattr(resp, "context", None))
        events = {e.action: e for e in AuditEvent.objects.all()}
        self.assertEqual(
            set(events),
            {
                AuditEvent.Action.ROLE_CHANGE,
                AuditEvent.Action.ACTIVE_CHANGE,
                AuditEvent.Action.PASSWORD_CHANGE,
            },
        )
        for event in events.values():
            self.assertEqual(event.actor, self.admin)
            self.assertEqual(event.actor_username, "szef")
            self.assertEqual(event.target_username, "magazynier")
            self.assertEqual(event.result, AuditEvent.Result.OK)
            self.assertLess(timezone.now() - event.created_at, timedelta(minutes=1))
        self.assertIn(
            "Operator → Administrator", events[AuditEvent.Action.ROLE_CHANGE].detail
        )

    def test_password_value_never_stored_or_logged(self):
        with self.assertLogs("warehouse.audit", level="INFO") as logs:
            self._edit(self.user, new_password=SECRET, new_password2=SECRET)
        rows = AuditEvent.objects.values_list(
            "detail", "actor_username", "target_username", "action"
        )
        self.assertTrue(rows)
        self.assertNotIn(SECRET, json.dumps(list(rows)))
        self.assertNotIn(SECRET, "\n".join(logs.output))
        formatted = [JsonFormatter().format(r) for r in logs.records]
        self.assertNotIn(SECRET, "\n".join(formatted))
        self.assertEqual(json.loads(formatted[0])["audit_target"], "magazynier")

    def test_no_change_no_entry(self):
        self._edit(self.user)
        self.assertFalse(AuditEvent.objects.exists())

    def test_user_create_logged(self):
        self.client.post(
            "/uzytkownicy/nowy/",
            {
                "username": "nowy",
                "email": "",
                "role": Role.VIEWER,
                "password": SECRET,
                "password2": SECRET,
            },
        )
        event = AuditEvent.objects.get(action=AuditEvent.Action.USER_CREATE)
        self.assertEqual(event.target_username, "nowy")
        self.assertIn("Podgląd", event.detail)
        self.assertNotIn(SECRET, event.detail)

    def test_us001_denial_logged(self):
        """Kryterium 2: Administrator (nie superuser) próbuje edytować superusera."""
        root = User.objects.create_superuser("root", password="RootPass123!")
        resp = self._edit(root, new_password=SECRET, new_password2=SECRET)
        self.assertEqual(resp.status_code, 403)
        event = AuditEvent.objects.get()
        self.assertEqual(event.action, AuditEvent.Action.ACCESS_DENIED)
        self.assertEqual(event.result, AuditEvent.Result.DENIED)
        self.assertEqual(
            (event.actor_username, event.target_username), ("szef", "root")
        )
        root.refresh_from_db()
        self.assertTrue(root.check_password("RootPass123!"))

    def test_self_protection_denials_logged(self):
        self._edit(self.admin, role=Role.ADMIN, is_active=False)
        self._edit(self.admin, role=Role.VIEWER)
        results = list(AuditEvent.objects.values_list("action", "result"))
        self.assertIn(
            (AuditEvent.Action.ACTIVE_CHANGE, AuditEvent.Result.DENIED), results
        )
        self.assertIn(
            (AuditEvent.Action.ROLE_CHANGE, AuditEvent.Result.DENIED), results
        )

    def test_reset_2fa_command_logged(self):
        call_command("reset_2fa", "magazynier", stdout=io.StringIO())
        event = AuditEvent.objects.get()
        self.assertEqual(event.action, AuditEvent.Action.TWO_FACTOR_RESET)
        self.assertEqual(event.actor_username, "manage.py reset_2fa")
        self.assertIsNone(event.actor)

    def test_entry_survives_user_deletion(self):
        self._edit(self.user, role=Role.VIEWER)
        self.user.delete()
        event = AuditEvent.objects.get()
        self.assertIsNone(event.target)
        self.assertEqual(event.target_username, "magazynier")

    def test_audit_page_admin_only(self):
        self._edit(self.user, role=Role.VIEWER)
        resp = self.client.get("/uzytkownicy/audyt/")
        self.assertContains(resp, "Zmiana roli")
        self.assertContains(resp, "magazynier")
        self.client.force_login(self.user)
        self.assertEqual(self.client.get("/uzytkownicy/audyt/").status_code, 403)

    def test_retention_365_days(self):
        old = AuditEvent.objects.create(
            action=AuditEvent.Action.ROLE_CHANGE,
            result=AuditEvent.Result.OK,
            created_at=timezone.now() - timedelta(days=366),
        )
        recent = AuditEvent.objects.create(
            action=AuditEvent.Action.ROLE_CHANGE,
            result=AuditEvent.Result.OK,
            created_at=timezone.now()
            - timedelta(days=100),  # starszy niż 90 dni logowań
        )
        call_command("purge_login_events", stdout=io.StringIO())
        self.assertFalse(AuditEvent.objects.filter(pk=old.pk).exists())
        self.assertTrue(AuditEvent.objects.filter(pk=recent.pk).exists())


@override_settings(DEMO_MODE=False)
class TypedUsernameTests(TestCase):
    """Kryterium 3 (PYT-09, Z-42): wpisany login przycięty do 150 znaków."""

    def test_unknown_long_login_truncated(self):
        cache.clear()
        typed = "x" * 400
        self.client.post("/login/", {"username": typed, "password": "zle"})
        event = LoginEvent.objects.get(kind=LoginEvent.Kind.FAILED)
        self.assertEqual(event.username, "x" * 150)
        self.assertEqual(LoginEvent._meta.get_field("username").max_length, 150)


class LogRedactionTests(TestCase):
    """Kryterium 4: wyjątek logowany w JSON nie zawiera wartości password / CSRF."""

    def _record(self, msg, *args, **extra):
        logger = logging.getLogger("django.request")
        try:
            raise ValueError(
                f"bad form password={SECRET} csrfmiddlewaretoken=abc123csrf"
            )
        except ValueError:
            import sys

            exc_info = sys.exc_info()
        return logger.makeRecord(
            "django.request",
            logging.ERROR,
            __file__,
            1,
            msg,
            args,
            exc_info,
            extra=extra,
        )

    def test_request_post_and_exception_redacted(self):
        request = RequestFactory().post(
            "/login/",
            {"username": "u", "password": SECRET, "csrfmiddlewaretoken": "abc123csrf"},
        )
        record = self._record(
            "Internal Server Error: %s %s",
            "/login/",
            {"password": SECRET, "csrfmiddlewaretoken": "abc123csrf"},
            request=request,
            status_code=500,
            form_data={
                "password": SECRET,
                "csrfmiddlewaretoken": "abc123csrf",
                "username": "u",
            },
        )
        out = JsonFormatter().format(record)
        self.assertNotIn(SECRET, out)
        self.assertNotIn("abc123csrf", out)
        data = json.loads(out)
        self.assertEqual(data["request"], "POST /login/")
        self.assertEqual(data["form_data"]["password"], REDACTED)
        self.assertEqual(data["form_data"]["username"], "u")
        self.assertIn(REDACTED, data["msg"])
        self.assertIn(REDACTED, data["exc"])

    def test_plain_messages_untouched(self):
        record = logging.makeLogRecord({"msg": "Przyjęto 5 palet", "levelno": 20})
        self.assertEqual(
            json.loads(JsonFormatter().format(record))["msg"], "Przyjęto 5 palet"
        )
