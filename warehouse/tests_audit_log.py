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
        AuditEvent.objects.all().delete()  # wpisy z przygotowania danych
        self.client.force_login(self.admin)

    def _edit(self, user, **data):
        payload = {"role": Role.OPERATOR, "is_active": "on", **data}
        if payload.get("is_active") is False:
            payload.pop("is_active")
        return self.client.post(f"/uzytkownicy/{user.pk}/", payload)

    def _actions(self):
        return sorted(AuditEvent.objects.values_list("action", flat=True))


class AuditLogTests(_Base):
    """Kryteria 1–2: aktor, cel, akcja, czas, wynik; bez wartości hasła."""

    def test_role_password_status_changes_each_logged(self):
        resp = self._edit(
            self.user, role=Role.ADMIN, is_active=False, new_password=SECRET
        )
        self.assertEqual(resp.status_code, 302)
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
            with self.captureOnCommitCallbacks(execute=True):
                self._edit(self.user, new_password=SECRET)
        rows = list(
            AuditEvent.objects.values_list(
                "detail", "actor_username", "target_username"
            )
        )
        self.assertTrue(rows)
        self.assertNotIn(SECRET, json.dumps(rows))
        formatted = [JsonFormatter().format(r) for r in logs.records]
        self.assertNotIn(SECRET, "\n".join(logs.output + formatted))
        self.assertEqual(json.loads(formatted[0])["audit_target"], "magazynier")

    def test_log_line_only_after_commit(self):
        """Przegląd [DB]: wycofana zmiana nie zostawia linii w logu ani wpisu."""
        from unittest.mock import patch

        with patch(
            "warehouse.audit.AuditEvent.objects.create", side_effect=RuntimeError("db")
        ):
            with self.assertRaises(RuntimeError):
                self._edit(self.user, role=Role.VIEWER)
        self.assertEqual(Profile.objects.get(user=self.user).role, Role.OPERATOR)

    def test_no_change_no_entry(self):
        self._edit(self.user)
        self.assertFalse(AuditEvent.objects.exists())

    def test_user_create_logged(self):
        self.client.post(
            "/uzytkownicy/nowy/",
            {
                "username": "nowy",
                "email": "",
                "role": Role.OPERATOR,
                "password": SECRET,
            },
        )
        create = AuditEvent.objects.get(action=AuditEvent.Action.USER_CREATE)
        self.assertEqual(
            (create.actor_username, create.target_username), ("szef", "nowy")
        )
        role = AuditEvent.objects.get(action=AuditEvent.Action.ROLE_CHANGE)
        self.assertEqual(role.detail, "Podgląd → Operator")
        self.assertNotIn(
            SECRET, json.dumps(list(AuditEvent.objects.values_list("detail")))
        )

    def test_us001_denial_logged_on_post_only(self):
        """Kryterium 2; GET nie tworzy wpisu (przegląd [SEC]: <img src> z obcej strony)."""
        root = User.objects.create_superuser("root", password="RootPass123!")
        AuditEvent.objects.all().delete()
        self.assertEqual(self.client.get(f"/uzytkownicy/{root.pk}/").status_code, 403)
        self.assertFalse(AuditEvent.objects.exists())
        resp = self._edit(root, new_password=SECRET)
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

    def test_changes_outside_the_panel_logged(self):
        """Przegląd [SEC]: /admin/, manage.py changepassword, createsuperuser — sygnały."""
        self.user.set_password(SECRET)
        self.user.is_staff = True
        self.user.save()
        self.assertEqual(
            self._actions(),
            [AuditEvent.Action.PASSWORD_CHANGE, AuditEvent.Action.ROLE_CHANGE],
        )
        event = AuditEvent.objects.first()
        self.assertIsNone(event.actor)
        self.assertTrue(
            event.actor_username
        )  # nazwa procesu, np. „manage.py changepassword”
        User.objects.create_superuser("drugi", password="DrugiPass123!")
        self.assertTrue(
            AuditEvent.objects.filter(
                action=AuditEvent.Action.USER_CREATE, detail__contains="is_superuser"
            ).exists()
        )

    def test_hash_upgrade_and_last_login_not_logged(self):
        """Przelicznie hasha przy logowaniu (setter Django) i last_login to nie zmiany."""
        self.user.set_password("MagPass123!")
        self.user._password = None  # tak robi setter w check_password()
        self.user.save(update_fields=["password"])
        self.client.force_login(self.user)  # aktualizuje last_login
        self.assertFalse(AuditEvent.objects.exists())

    def test_2fa_enable_and_reset_logged(self):
        from django_otp.plugins.otp_totp.models import TOTPDevice

        pending = TOTPDevice.objects.create(user=self.user, confirmed=False, name="x")
        pending.delete()  # ekran /2fa/ kasuje niepotwierdzone — to nie zdarzenie
        self.assertFalse(AuditEvent.objects.exists())
        device = TOTPDevice.objects.create(user=self.user, confirmed=False, name="a")
        device.confirmed = True
        device.save()
        call_command("reset_2fa", "magazynier", stdout=io.StringIO())
        self.assertEqual(
            self._actions(),
            [AuditEvent.Action.TWO_FACTOR_ENABLE, AuditEvent.Action.TWO_FACTOR_RESET],
        )

    def test_delete_logged_and_entry_survives(self):
        self._edit(self.user, role=Role.VIEWER)
        self.user.delete()
        self.assertTrue(
            AuditEvent.objects.filter(action=AuditEvent.Action.USER_DELETE).exists()
        )
        for event in AuditEvent.objects.all():
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

    def test_review_cases_fully_redacted(self):
        """Przegląd [SEC] US-022: spacje, przecinki, cudzysłowy, listy, nagłówki, %3D."""
        from config.log import redact_text

        cases = {
            '{"password": "ab cd ef"}': "ab cd ef",
            "{'new_password': ['p@ss w0rd']}": "w0rd",
            '"password":"a\\"bc"': "bc",
            "password='a,b}c'": "b}c",
            "Authorization: Bearer abcdef": "abcdef",
            "{'token': ['12','34']}": "34",
            "next=%2F&password%3Dsecret123": "secret123",
            "Cookie: sessionid=xyz; csrftoken=qwe": "xyz",
        }
        for text, leaked in cases.items():
            with self.subTest(text=text):
                self.assertNotIn(leaked, redact_text(text))

    def test_no_false_positive_on_plain_sentences(self):
        from config.log import redact_text

        for text in (
            "Password reset tokens: 5 deleted",
            "secret_key_fallbacks: 2",
        ):
            with self.subTest(text=text):
                self.assertEqual(redact_text(text), text)
