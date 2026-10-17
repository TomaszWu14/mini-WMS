"""US-021: alert e-mail (`mail_admins`) przy błędzie 500 — bez haseł, tokenów i sesji."""

from django.contrib.auth.models import User
from django.core import mail
from django.http import HttpResponse
from django.test import TestCase, override_settings
from django.urls import path

from config import urls as app_urls


def _boom(request):
    raise RuntimeError("awaria testowa")


def _ok(request):
    return HttpResponse("ok")


# Trasy aplikacji też — middleware 2FA odwołuje się do nich przez reverse().
urlpatterns = [path("boom/", _boom), path("ok/", _ok), *app_urls.urlpatterns]

ADMINS = [("admin@example.com", "admin@example.com")]


@override_settings(ROOT_URLCONF=__name__, ADMINS=ADMINS, DEBUG=False)
class ServerErrorAlertTests(TestCase):
    def setUp(self):
        self.client.raise_request_exception = False

    def test_500_sends_one_email_to_admins(self):
        """Kryterium 1: nieobsłużony wyjątek → e-mail do ADMINS."""
        response = self.client.get("/boom/")
        self.assertEqual(response.status_code, 500)
        self.assertEqual(len(mail.outbox), 1)
        msg = mail.outbox[0]
        self.assertEqual(msg.to, ["admin@example.com"])
        self.assertTrue(msg.subject.startswith("[mini-WMS] "))
        self.assertIn("awaria testowa", msg.body)
        self.assertEqual(msg.alternatives, [])  # bez HTML z pełnymi zmiennymi lokalnymi

    def test_alert_body_hides_password_tokens_and_session(self):
        """Kryterium 2 (SEC-032): wartości haseł, tokenów i ciasteczek nie trafiają do maila."""
        User.objects.create_user("op", password="OpPass123!")
        self.client.login(username="op", password="OpPass123!")
        session_key = self.client.session.session_key
        self.client.post(
            "/boom/",
            {"password": "Tajne-Haslo-1", "otp_token": "123456", "note": "widoczne"},
            HTTP_AUTHORIZATION="Bearer sekretny-token",
        )
        body = mail.outbox[0].body
        for secret in ("Tajne-Haslo-1", "123456", "sekretny-token", session_key):
            self.assertNotIn(secret, body)
        self.assertIn("awaria testowa", body)  # właściwy błąd, nie błąd middleware
        self.assertIn("widoczne", body)  # zwykłe pola zostają — pomagają w diagnozie
        self.assertIn("********************", body)

    def test_no_email_without_admins_or_on_success(self):
        with self.settings(ADMINS=[]):
            self.client.get("/boom/")
        self.client.get("/ok/")
        self.assertEqual(mail.outbox, [])

    @override_settings(DEBUG=True)
    def test_no_email_in_debug(self):
        self.client.get("/boom/")
        self.assertEqual(mail.outbox, [])
