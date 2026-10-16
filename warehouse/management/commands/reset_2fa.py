"""Usuwa urządzenia 2FA użytkownika po utracie telefonu (US-010, RUNBOOK §8.3b)."""

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django_otp.plugins.otp_totp.models import TOTPDevice


class Command(BaseCommand):
    help = "Wyłącza weryfikację dwuetapową konta (usuwa urządzenia TOTP)."

    def add_arguments(self, parser):
        parser.add_argument("username", help="Login konta.")

    def handle(self, *args, username, **options):
        user = get_user_model().objects.filter(username=username).first()
        if user is None:
            raise CommandError(f"Nie ma konta „{username}”.")
        deleted, _ = TOTPDevice.objects.filter(user=user).delete()
        self.stdout.write(
            f"Usunięto {deleted} urządzeń 2FA konta {username}. Przy następnym logowaniu "
            "wystarczy hasło; nowe urządzenie rejestruje się na /2fa/."
        )
