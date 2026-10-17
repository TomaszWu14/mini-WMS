"""US-010 / SEC-006: weryfikacja dwuetapowa (TOTP) dla Administratora — ADR-0003.

Włączenie jest dobrowolne (Z-39): Administrator rejestruje aplikację uwierzytelniającą
na `/2fa/`. Od tej chwili po samym haśle sesja jest „niezweryfikowana” i middleware
kieruje każde żądanie (także `/admin/`) na `/2fa/weryfikacja/`, dopóki nie poda kodu.
Nieudane kody liczą się do blokady konta z US-009. Utrata telefonu:
`manage.py reset_2fa <login>` (RUNBOOK §8.3b).
"""

import io
from base64 import b32encode

import qrcode
import qrcode.image.svg
from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme, urlencode
from django.utils.safestring import mark_safe
from django.views.decorators.cache import never_cache
from django_otp import login as otp_login
from django_otp.plugins.otp_totp.models import TOTPDevice

from .audit import Action, record
from .models import LoginEvent
from .roles import admin_required


def confirmed_device(user):
    """Potwierdzone urządzenie TOTP użytkownika albo None."""
    if not user.is_authenticated:
        return None
    return TOTPDevice.objects.filter(user=user, confirmed=True).first()


class TwoFactorRequiredMiddleware:
    """Po samym haśle konto z włączonym 2FA widzi tylko ekran kodu i wylogowanie."""

    ALLOWED_NAMES = ("two_factor_verify", "logout", "healthz")

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, "user", None)
        if (
            user is not None
            and user.is_authenticated
            and not user.is_verified()
            and not self._allowed(request.path)
            and confirmed_device(user) is not None
        ):
            query = urlencode({"next": request.get_full_path()})
            return redirect(f"{reverse('two_factor_verify')}?{query}")
        return self.get_response(request)

    def _allowed(self, path):
        from django.conf import settings

        if path.startswith(settings.STATIC_URL):
            return True
        return any(path == reverse(name) for name in self.ALLOWED_NAMES)


class TokenForm(forms.Form):
    token = forms.CharField(
        label="Kod z aplikacji",
        min_length=6,
        max_length=6,
        widget=forms.TextInput(
            attrs={
                "autocomplete": "one-time-code",
                "inputmode": "numeric",
                "autofocus": True,
            }
        ),
    )

    def clean_token(self):
        token = self.cleaned_data["token"].strip()
        if not token.isdigit():
            raise forms.ValidationError("Kod składa się z 6 cyfr.")
        return token


def _safe_next(request, default="dashboard"):
    target = request.POST.get("next") or request.GET.get("next") or ""
    if url_has_allowed_host_and_scheme(
        target, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        return target
    return default


def _record_failed_code(request):
    """Nieudany kod = nieudane logowanie: licznik konta (US-009) i dziennik."""
    from .login_limits import account_failed
    from .signals import log_client

    username = request.user.get_username()
    account_failed(username)
    ip, user_agent = log_client(request)
    LoginEvent.objects.create(
        user=request.user,
        username=username,
        kind=LoginEvent.Kind.FAILED,
        ip=ip,
        user_agent=user_agent,
    )


@never_cache
@login_required
def two_factor_verify(request):
    """Drugi krok logowania: kod TOTP."""
    from .demo import DEMO_TOO_MANY_ACCOUNT, _too_many
    from .login_limits import account_locked

    device = confirmed_device(request.user)
    if device is None or request.user.is_verified():
        return redirect(_safe_next(request))
    form = TokenForm(request.POST if request.method == "POST" else None)
    if request.method == "POST":
        if account_locked(request.user.get_username()):
            return _too_many(DEMO_TOO_MANY_ACCOUNT)
        if (
            form.is_valid()
            and device.verify_is_allowed()[0]
            and device.verify_token(form.cleaned_data["token"])
        ):
            otp_login(request, device)
            return redirect(_safe_next(request))
        _record_failed_code(request)
        form.add_error(None, "Niepoprawny lub przeterminowany kod. Spróbuj ponownie.")
    return render(
        request,
        "warehouse/two_factor_verify.html",
        {"form": form, "next": _safe_next(request, default="")},
    )


def _qr_svg(url: str) -> str:
    image = qrcode.make(url, image_factory=qrcode.image.svg.SvgPathImage, box_size=8)
    buf = io.BytesIO()
    image.save(buf)
    return buf.getvalue().decode()


@never_cache
@admin_required
def two_factor_setup(request):
    """Włączenie 2FA: kod QR → pierwszy kod z aplikacji potwierdza urządzenie."""
    if confirmed_device(request.user) is not None:
        return render(request, "warehouse/two_factor_setup.html", {"enabled": True})
    pending = TOTPDevice.objects.filter(user=request.user, confirmed=False)
    device = pending.first() if request.method == "POST" else None
    if device is None:
        # Każde wyświetlenie strony = nowy klucz: sekret podejrzany kiedyś (np. przez
        # przejętą sesję) nie zostanie później potwierdzony przez właściciela.
        pending.delete()
        device = TOTPDevice.objects.create(
            user=request.user, confirmed=False, name="aplikacja"
        )
    form = TokenForm(request.POST if request.method == "POST" else None)
    if request.method == "POST":
        if form.is_valid() and device.verify_token(form.cleaned_data["token"]):
            device.confirmed = True
            device.save(update_fields=["confirmed"])
            otp_login(request, device)
            record(Action.TWO_FACTOR_ENABLE, actor=request.user, target=request.user)
            messages.success(
                request,
                "Weryfikacja dwuetapowa włączona. Przy kolejnym logowaniu podasz kod z aplikacji.",
            )
            return redirect("dashboard")
        form.add_error(
            None, "Kod się nie zgadza — sprawdź czas w telefonie i spróbuj ponownie."
        )
    secret = b32encode(device.bin_key).decode()
    return render(
        request,
        "warehouse/two_factor_setup.html",
        {
            "enabled": False,
            "form": form,
            "qr_svg": mark_safe(_qr_svg(device.config_url)),  # nosec B308 B703 — SVG z biblioteki qrcode
            "secret": secret,
        },
    )
