"""Sygnały — profil użytkownika oraz dziennik logowań."""

from django.conf import settings
from django.contrib.auth.signals import (
    user_logged_in,
    user_logged_out,
    user_login_failed,
)
from django.core.cache import cache
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import LoginEvent, Profile, Role


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def ensure_profile(sender, instance, created, **kwargs):
    """Każdy użytkownik dostaje profil. Superuser z rolą Administrator."""
    if created:
        role = Role.ADMIN if instance.is_superuser else Role.VIEWER
        Profile.objects.create(user=instance, role=role)
    else:
        profile, _ = Profile.objects.get_or_create(user=instance)
        # Awans na superusera musi zsynchronizować rolę profilu (inaczej w UI
        # widnieje stara, niższa rola, mimo że superuser i tak ma uprawnienia).
        if instance.is_superuser and profile.role != Role.ADMIN:
            profile.role = Role.ADMIN
            profile.save(update_fields=["role"])


def _client_ip(request):
    """IP klienta. X-Forwarded-For tylko za zaufanymi proxy.

    Każde proxy dopisuje na końcu adres, od którego dostało żądanie — klient
    wpisuje, co chce, na początku. Ufamy więc wpisowi N-temu od końca, gdzie
    N = TRUSTED_PROXY_COUNT; bez proxy nagłówek jest ignorowany.
    """
    if request is None:
        return None
    count = settings.TRUSTED_PROXY_COUNT
    if count > 0:
        hops = [
            h.strip()
            for h in request.META.get("HTTP_X_FORWARDED_FOR", "").split(",")
            if h.strip()
        ]
        if len(hops) >= count:
            return hops[-count]
    return request.META.get("REMOTE_ADDR")


def _user_agent(request):
    if request is None:
        return ""
    return request.META.get("HTTP_USER_AGENT", "")[:300]


def log_client(request):
    """(ip, user_agent) do dziennika logowań.

    US-005 / SEC-035: publiczne demo odwiedzają anonimowe osoby — nie zapisujemy
    ich IP ani przeglądarki (Z-38). Limit prób działa na IP z żądania, nie z bazy.
    """
    if settings.DEMO_MODE:
        return None, ""
    return _client_ip(request), _user_agent(request)


def _count_account_failure(username):
    """US-009: licznik nieudanych logowań konta, wspólny dla workerów (cache w bazie)."""
    from .demo import account_key  # import cykliczny: demo importuje signals

    key = account_key(username)
    cache.add(key, 0, settings.LOGIN_ACCOUNT_WINDOW)
    try:
        cache.incr(key)
    except ValueError:  # klucz wygasł między add a incr
        cache.set(key, 1, settings.LOGIN_ACCOUNT_WINDOW)


@receiver(user_logged_in)
def on_logged_in(sender, request, user, **kwargs):
    from .demo import account_key

    # Udane logowanie przed blokadą zeruje licznik konta.
    cache.delete(account_key(user.get_username()))
    ip, user_agent = log_client(request)
    LoginEvent.objects.create(
        user=user,
        username=user.get_username(),
        kind=LoginEvent.Kind.LOGIN,
        ip=ip,
        user_agent=user_agent,
    )


@receiver(user_logged_out)
def on_logged_out(sender, request, user, **kwargs):
    ip, user_agent = log_client(request)
    LoginEvent.objects.create(
        user=user if user is not None else None,
        username=user.get_username() if user is not None else "",
        kind=LoginEvent.Kind.LOGOUT,
        ip=ip,
        user_agent=user_agent,
    )


@receiver(user_login_failed)
def on_login_failed(sender, credentials, request=None, **kwargs):
    # .get(key, "") nie chroni, gdy klucz istnieje z wartością None — wtedy
    # zwraca None i None[:150] rzuca TypeError, wywracając ścieżkę logowania.
    raw_username = (credentials or {}).get("username") or ""
    if raw_username:
        _count_account_failure(raw_username)
    ip, user_agent = log_client(request)
    LoginEvent.objects.create(
        username=str(raw_username)[:150],
        kind=LoginEvent.Kind.FAILED,
        ip=ip,
        user_agent=user_agent,
    )
