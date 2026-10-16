"""Usuwa wpisy dziennika logowań starsze niż retencja (US-005 / SEC-036)."""

from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from warehouse.models import LoginEvent


class Command(BaseCommand):
    help = (
        "Usuwa wpisy dziennika logowań starsze niż LOGIN_EVENT_RETENTION_DAYS "
        "(domyślnie 90 dni). Uruchamiać codziennie (Scheduled Task)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--days",
            type=int,
            default=None,
            help="Retencja w dniach (nadpisuje LOGIN_EVENT_RETENTION_DAYS).",
        )

    def handle(self, *args, days=None, **options):
        days = settings.LOGIN_EVENT_RETENTION_DAYS if days is None else days
        if days < 1:
            raise CommandError("--days musi być liczbą dni ≥ 1.")
        cutoff = timezone.now() - timedelta(days=days)
        deleted, _ = LoginEvent.objects.filter(created_at__lt=cutoff).delete()
        self.stdout.write(
            f"Usunięto {deleted} wpisów dziennika logowań starszych niż {days} dni."
        )
