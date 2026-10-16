"""Tryb demo (DEMO_MODE): konta demo, „Wejdź jako demo”, link /demo/,
„Przywróć dane demo”, powitanie, baner; do tego limit prób logowania.

Limit logowań działa zawsze; reszta — tylko przy DEMO_MODE.
"""

import io

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.core.cache import cache
from django.core.management import call_command
from django.http import Http404, HttpResponse
from django.shortcuts import redirect
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_GET, require_POST

from .models import Role
from .roles import operator_required
from .signals import _client_ip

# Hasło: settings.DEMO_PASSWORD (env, domyślnie jawne „demo1234” z README).
DEMO_ACCOUNTS = {
    "demo_operator": Role.OPERATOR,
    "demo_podglad": Role.VIEWER,
}

LOGIN_RATE_LIMIT = 10  # prób POST
LOGIN_RATE_WINDOW = 300  # sekund
# US-005 / SEC-040: anonimowe wejścia /demo/ i /login/demo/ (Z-37 — jak logowanie).
DEMO_ENTRY_RATE_LIMIT = 10
DEMO_ENTRY_RATE_WINDOW = 300
DEMO_RESET_COOLDOWN = 60  # sekund między resetami (wspólne dla wszystkich)


def is_demo_account(user) -> bool:
    return bool(settings.DEMO_MODE) and user.username in DEMO_ACCOUNTS


def demo_context(request):
    """Context processor: baner i loginy demo tylko przy DEMO_MODE."""
    if not settings.DEMO_MODE:
        return {"demo_mode": False}
    return {
        "demo_mode": True,
        "demo_accounts": list(DEMO_ACCOUNTS),
        "demo_password": settings.DEMO_PASSWORD,
        "demo_user": settings.DEMO_USER,
    }


def _over_limit(prefix: str, request, limit: int, window: int) -> bool:
    """Licznik żądań na IP w oknie `window` s; True, gdy przekroczono `limit`."""
    key = f"{prefix}:{_client_ip(request)}"
    cache.add(key, 0, window)
    try:
        hits = cache.incr(key)
    except ValueError:  # klucz wygasł między add a incr
        hits = 1
    return hits > limit


def _too_many(message: str) -> HttpResponse:
    return HttpResponse(message, status=429, content_type="text/plain; charset=utf-8")


def _demo_entry_limited(request) -> bool:
    return _over_limit(
        "demo-rl", request, DEMO_ENTRY_RATE_LIMIT, DEMO_ENTRY_RATE_WINDOW
    )


DEMO_TOO_MANY = (
    "Zbyt wiele wejść do demo z tego adresu. Spróbuj ponownie za kilka minut."
)


class LoginView(auth_views.LoginView):
    """LoginView z prostym limitem prób POST na IP (zawsze, nie tylko w demo).

    ponytail: cache domyślny (LocMem) jest per proces gunicorna — przy N
    workerach realny limit to N×10; wspólny cache (Redis) gdy to za mało.
    """

    template_name = "warehouse/login.html"

    def post(self, request, *args, **kwargs):
        if _over_limit("login-rl", request, LOGIN_RATE_LIMIT, LOGIN_RATE_WINDOW):
            return _too_many(
                "Zbyt wiele prób logowania. Spróbuj ponownie za kilka minut."
            )
        return super().post(request, *args, **kwargs)


def _demo_user():
    """Aktywne konto settings.DEMO_USER — tylko z listy DEMO_ACCOUNTS."""
    if settings.DEMO_USER not in DEMO_ACCOUNTS:
        return None
    return User.objects.filter(username=settings.DEMO_USER, is_active=True).first()


@require_POST
def demo_login(request):
    """„Wejdź jako demo” — loguje kontem settings.DEMO_USER bez wpisywania hasła."""
    if not settings.DEMO_MODE:
        raise Http404
    if _demo_entry_limited(request):
        return _too_many(DEMO_TOO_MANY)
    user = _demo_user()
    if user is None:
        messages.error(request, "Konto demo nie jest jeszcze utworzone (seed_demo).")
        return redirect("login")
    login(request, user, backend="django.contrib.auth.backends.ModelBackend")
    target = request.POST.get("next", "")
    if not url_has_allowed_host_and_scheme(
        target, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        target = "dashboard"
    return redirect(target)


@require_GET
def demo_start(request):
    """Link /demo/ (README, YouTube, CV): wejście bez logowania + prezentacja.

    Logowanie na GET to wyjątek od reguły „zmiany tylko na POST” — dopuszczalny,
    bo to jawne, wspólne konto demo i tylko przy DEMO_MODE. Kogoś już
    zalogowanego nie przelogowujemy (link podsunięty adminowi nie zmieni mu sesji).
    """
    if not settings.DEMO_MODE:
        raise Http404
    if not request.user.is_authenticated:
        # Liczymy tylko wejścia, które logują — zalogowany, odświeżając link,
        # nie zużywa limitu innym gościom za tym samym NAT.
        if _demo_entry_limited(request):
            return _too_many(DEMO_TOO_MANY)
        user = _demo_user()
        if user is None:
            messages.error(
                request, "Konto demo nie jest jeszcze utworzone (seed_demo)."
            )
            return redirect("login")
        login(request, user, backend="django.contrib.auth.backends.ModelBackend")
    return redirect("/?demo=1")


@operator_required
@require_POST
def demo_reset(request):
    """„Przywróć dane demo” — seed_demo --reset --keep-users, najwyżej raz na minutę.

    ponytail: blokada w cache domyślnym (LocMem) jest per proces gunicorna —
    przy N workerach do N resetów na minutę; równoległe resety i zapisy
    szereguje LOCK TABLE w seed_demo (PostgreSQL).
    """
    if not settings.DEMO_MODE:
        raise Http404
    if not cache.add("demo-reset-lock", 1, DEMO_RESET_COOLDOWN):
        messages.info(
            request, "Dane demo przywrócono przed chwilą — spróbuj za minutę."
        )
    else:
        call_command("seed_demo", reset=True, keep_users=True, stdout=io.StringIO())
        request.session.pop("welcome_dismissed", None)
        messages.success(request, "Przywrócono dane demo do stanu początkowego.")
    return redirect("dashboard")


@login_required
@require_POST
def welcome_dismiss(request):
    """Ukrywa panel „Od czego zacząć” do końca sesji."""
    request.session["welcome_dismissed"] = True
    return redirect("dashboard")
