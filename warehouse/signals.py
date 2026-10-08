"""Sygnały — profil użytkownika oraz dziennik logowań."""

from django.conf import settings
from django.contrib.auth.signals import (
    user_logged_in,
    user_logged_out,
    user_login_failed,
)
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
    if request is None:
        return None
    fwd = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


def _user_agent(request):
    if request is None:
        return ""
    return request.META.get("HTTP_USER_AGENT", "")[:300]


@receiver(user_logged_in)
def on_logged_in(sender, request, user, **kwargs):
    LoginEvent.objects.create(
        user=user,
        username=user.get_username(),
        kind=LoginEvent.Kind.LOGIN,
        ip=_client_ip(request),
        user_agent=_user_agent(request),
    )


@receiver(user_logged_out)
def on_logged_out(sender, request, user, **kwargs):
    LoginEvent.objects.create(
        user=user if user is not None else None,
        username=user.get_username() if user is not None else "",
        kind=LoginEvent.Kind.LOGOUT,
        ip=_client_ip(request),
        user_agent=_user_agent(request),
    )


@receiver(user_login_failed)
def on_login_failed(sender, credentials, request=None, **kwargs):
    # .get(key, "") nie chroni, gdy klucz istnieje z wartością None — wtedy
    # zwraca None i None[:150] rzuca TypeError, wywracając ścieżkę logowania.
    raw_username = (credentials or {}).get("username") or ""
    LoginEvent.objects.create(
        username=str(raw_username)[:150],
        kind=LoginEvent.Kind.FAILED,
        ip=_client_ip(request),
        user_agent=_user_agent(request),
    )
