"""Tryb demo (DEMO_MODE): konta demo, baner, rate limit logowania.

Bez DEMO_MODE nic z tego modułu nie zmienia zachowania aplikacji.
"""

from django.conf import settings
from django.contrib.auth import views as auth_views
from django.core.cache import cache
from django.http import HttpResponse

from .models import Role
from .signals import _client_ip

# Jawne hasło — konta demo są publiczne z założenia (opisane w README).
DEMO_PASSWORD = "demo1234"
DEMO_ACCOUNTS = {
    "demo_operator": Role.OPERATOR,
    "demo_podglad": Role.VIEWER,
}

LOGIN_RATE_LIMIT = 10  # prób POST
LOGIN_RATE_WINDOW = 300  # sekund


def is_demo_account(user) -> bool:
    return bool(settings.DEMO_MODE) and user.username in DEMO_ACCOUNTS


def demo_context(request):
    """Context processor: baner i loginy demo tylko przy DEMO_MODE."""
    if not settings.DEMO_MODE:
        return {"demo_mode": False}
    return {
        "demo_mode": True,
        "demo_accounts": list(DEMO_ACCOUNTS),
        "demo_password": DEMO_PASSWORD,
    }


class LoginView(auth_views.LoginView):
    """LoginView z prostym limitem prób POST na IP (tylko w DEMO_MODE).

    ponytail: cache domyślny (LocMem) jest per proces gunicorna — przy N
    workerach realny limit to N×10; wspólny cache (Redis) gdy to za mało.
    """

    template_name = "warehouse/login.html"

    def post(self, request, *args, **kwargs):
        if settings.DEMO_MODE:
            key = f"login-rl:{_client_ip(request)}"
            cache.add(key, 0, LOGIN_RATE_WINDOW)
            try:
                attempts = cache.incr(key)
            except ValueError:  # klucz wygasł między add a incr
                attempts = 1
            if attempts > LOGIN_RATE_LIMIT:
                return HttpResponse(
                    "Zbyt wiele prób logowania. Spróbuj ponownie za kilka minut.",
                    status=429,
                    content_type="text/plain; charset=utf-8",
                )
        return super().post(request, *args, **kwargs)
