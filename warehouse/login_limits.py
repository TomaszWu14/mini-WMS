"""US-009: blokada konta po nieudanych logowaniach — licznik w bazie, atomowy.

Licznik żyje w tabeli `LoginFailureCounter` (nie w cache): `UPDATE … SET count = count + 1`
jest atomowy dla wszystkich workerów, okno ma dokładnie `LOGIN_ACCOUNT_WINDOW` s, a culling
cache nie może go wyczyścić (przegląd [SEC]/[DB] US-009).
"""

import hashlib
import unicodedata
from datetime import timedelta

from django.conf import settings
from django.db import IntegrityError, transaction
from django.db.models import F
from django.utils import timezone

from .models import LoginFailureCounter


def normalize_username(username) -> str:
    """Jak `AuthenticationForm` (NFKC + strip) i bez wielkości liter — warianty
    unicode (`ａｄｍｉｎ`, `𝐚dmin`) trafiają w ten sam licznik co `admin`."""
    return unicodedata.normalize("NFKC", str(username)).strip().casefold()


def account_key(username) -> str:
    digest = hashlib.sha256(normalize_username(username).encode()).hexdigest()
    return digest[:40]


def is_lock_exempt(username) -> bool:
    """Publiczne konta demo (hasło jawne na stronie logowania) nie są blokowane —
    inaczej każdy gość mógłby je zablokować pozostałym (pitfalls/auth #8)."""
    from .demo import DEMO_ACCOUNTS

    return bool(settings.DEMO_MODE) and normalize_username(username) in DEMO_ACCOUNTS


def _window_start():
    return timezone.now() - timedelta(seconds=settings.LOGIN_ACCOUNT_WINDOW)


def account_failed(username) -> None:
    """Nieudana próba: +1 w bieżącym oknie albo nowe okno od 1."""
    if not username or is_lock_exempt(username):
        return
    key = account_key(username)
    now = timezone.now()
    counters = LoginFailureCounter.objects.filter(key=key)
    if counters.filter(window_start__gte=_window_start()).update(count=F("count") + 1):
        return
    if counters.update(count=1, window_start=now):  # okno minęło — zaczynamy od nowa
        return
    try:
        with transaction.atomic():
            LoginFailureCounter.objects.create(key=key, count=1, window_start=now)
    except IntegrityError:  # równoległa pierwsza próba utworzyła wiersz
        counters.update(count=F("count") + 1)


def account_locked(username) -> bool:
    if not username or is_lock_exempt(username):
        return False
    return LoginFailureCounter.objects.filter(
        key=account_key(username),
        window_start__gte=_window_start(),
        count__gte=settings.LOGIN_ACCOUNT_LIMIT,
    ).exists()


def account_reset(username) -> None:
    """Udane logowanie przed blokadą zeruje licznik konta."""
    LoginFailureCounter.objects.filter(key=account_key(username)).delete()


def purge_expired() -> int:
    deleted, _ = LoginFailureCounter.objects.filter(
        window_start__lt=_window_start()
    ).delete()
    return deleted
