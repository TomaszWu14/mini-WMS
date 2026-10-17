"""Tryb demo (DEMO_MODE): konta demo, „Wejdź jako demo”, link /demo/, powitanie,
baner, limiter zapisów; do tego limit prób logowania. Reset danych demo — wyłącznie
Scheduled Task `seed_demo --reset --keep-users` (US-016, DEC-6).

Limit logowań działa zawsze; reszta — tylko przy DEMO_MODE.
"""

import hashlib
import ipaddress

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.core.cache import cache
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import redirect
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_GET, require_POST

from .login_limits import account_locked
from .models import LoginEvent, Role
from .signals import _client_ip, log_client

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
# US-016 / DEC-6: POST zalogowanych w demo (przyjęcia, importy, wydania, skaner) —
# decyzja PO 2026-10-16: 60 na 300 s z jednego IP (ok. 1 akcja na 5 s średnio).
DEMO_WRITE_RATE_LIMIT = 60
DEMO_WRITE_RATE_WINDOW = 300
DEMO_WRITE_EXEMPT = ("/logout/",)
DEMO_TOO_MANY_WRITES = (
    "Zbyt wiele operacji z tego adresu w demo. Spróbuj ponownie za kilka minut."
)


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
    """Licznik żądań na IP w oknie `window` s; True, gdy przekroczono `limit`.

    IP w kluczu jest skrótem — tabela cache i jej kopie zapasowe nie trzymają
    jawnych adresów (SEC-035).
    """
    ip_digest = hashlib.sha256(_limit_subject(request).encode()).hexdigest()[:32]
    key = f"{prefix}:{ip_digest}"
    cache.add(key, 0, window)
    try:
        hits = cache.incr(key)
    except ValueError:  # klucz wygasł między add a incr
        hits = 1
    return hits > limit


def _limit_subject(request) -> str:
    """IPv4 — adres; IPv6 — prefiks /64 (przegląd [SEC] US-016: klient zwykle
    dostaje całą /64 i bez tego zmienia adres, by dostać nowy limit)."""
    ip = _client_ip(request)
    if ip and ":" in ip:
        return str(ipaddress.ip_network(f"{ip}/64", strict=False))
    return str(ip)


def _too_many(message: str) -> HttpResponse:
    return HttpResponse(message, status=429, content_type="text/plain; charset=utf-8")


def _demo_entry_limited(request) -> bool:
    return _over_limit(
        "demo-rl", request, DEMO_ENTRY_RATE_LIMIT, DEMO_ENTRY_RATE_WINDOW
    )


DEMO_TOO_MANY_ACCOUNT = (
    "Zbyt wiele nieudanych prób logowania na to konto. Spróbuj ponownie za 15 minut."
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
        return login_guard(request) or super().post(request, *args, **kwargs)


def login_guard(request):
    """Wspólna bramka POST logowania (`/login/` i `/admin/login/`): limit per IP,
    potem blokada konta (US-009). Zwraca odpowiedź 429 albo None.

    Blokada daje 429 także dla poprawnego hasła, do końca okna; ta sama odpowiedź
    dla istniejących i nieistniejących loginów (bez ujawniania kont).
    """
    if _over_limit("login-rl", request, LOGIN_RATE_LIMIT, LOGIN_RATE_WINDOW):
        return _too_many("Zbyt wiele prób logowania. Spróbuj ponownie za kilka minut.")
    username = request.POST.get("username", "")
    if account_locked(username):
        ip, user_agent = log_client(request)
        LoginEvent.objects.create(
            username=str(username)[:150],
            kind=LoginEvent.Kind.BLOCKED,
            ip=ip,
            user_agent=user_agent,
        )
        return _too_many(DEMO_TOO_MANY_ACCOUNT)
    return None


def admin_login(request, extra_context=None):
    """`/admin/login/` z tą samą bramką co `/login/` (przegląd [SEC] US-009)."""
    from django.contrib import admin

    if request.method == "POST":
        blocked = login_guard(request)
        if blocked is not None:
            return blocked
    return admin.site.login(request, extra_context)


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


@login_required
@require_POST
def welcome_dismiss(request):
    """Ukrywa panel „Od czego zacząć” do końca sesji."""
    request.session["welcome_dismissed"] = True
    return redirect("dashboard")


class DemoWriteRateLimitMiddleware:
    """US-016: w demo każdy może być Operatorem — limit POST zalogowanych na IP.

    Logowanie i wejście do demo mają własne limity (anonimowe POST-y tu nie wchodzą);
    wylogowanie zawsze przechodzi. API skanera dostaje JSON jak inne błędy skanera.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if (
            settings.DEMO_MODE
            and request.method == "POST"
            and request.user.is_authenticated
            and request.path not in DEMO_WRITE_EXEMPT
            and _over_limit(
                "demo-write", request, DEMO_WRITE_RATE_LIMIT, DEMO_WRITE_RATE_WINDOW
            )
        ):
            if request.path.startswith("/skaner/api/"):
                return JsonResponse(
                    {"ok": False, "error": DEMO_TOO_MANY_WRITES}, status=429
                )
            return _too_many(DEMO_TOO_MANY_WRITES)
        return self.get_response(request)
