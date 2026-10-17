"""Dziennik audytowy akcji administracyjnych (US-022, SEC-033).

Zmiany kont zapisują sygnały na modelach (`User`, `Profile`, `TOTPDevice`), więc
ślad zostawia każda ścieżka: panel aplikacji, `/admin/`, `manage.py changepassword` /
`createsuperuser` / `reset_2fa`, `entrypoint.sh`, `seed_demo`. Kto zmienił — z żądania
(`AuditActorMiddleware`) albo nazwa komendy `manage.py`. Odmowy zapisują widoki
wprost (`record(..., result=DENIED)`).

Zapis trafia do tabeli `AuditEvent` (przeglądanej na /uzytkownicy/audyt/) i — po
zatwierdzeniu transakcji — jako linia logu JSON (logger `warehouse.audit`). Wartości
hasła ani kodu 2FA nigdy tu nie ma: `detail` mówi, co się zmieniło, nie na co.
"""

import contextvars
import logging
import sys

from django.conf import settings
from django.db import transaction
from django.db.models.signals import post_delete, post_save, pre_delete, pre_save
from django.dispatch import receiver
from django_otp.plugins.otp_totp.models import TOTPDevice

from .models import AuditEvent, Profile, Role

logger = logging.getLogger("warehouse.audit")

Action = AuditEvent.Action
Result = AuditEvent.Result

_current_actor: contextvars.ContextVar = contextvars.ContextVar(
    "audit_actor", default=None
)

# Pola konta, których zmiana jest zdarzeniem audytowym.
_USER_FIELDS = ("password", "is_active", "is_staff", "is_superuser")


def _name(user) -> str:
    return str(getattr(user, "username", "") or "")[:150]


def _process_name() -> str:
    """Kto działa poza żądaniem HTTP: `manage.py <komenda>` albo „system”."""
    argv = sys.argv or [""]
    if argv[0].endswith("manage.py") and len(argv) > 1:
        return f"manage.py {argv[1]}"[:150]
    return "system"


def record(
    action, *, actor=None, target=None, result=Result.OK, detail="", actor_name=""
):
    """Zapisuje zdarzenie. Bez `actor` — bieżący użytkownik żądania albo nazwa procesu."""
    if actor is None:
        actor = _current_actor.get()
    actor_obj = actor if getattr(actor, "pk", None) else None
    event = AuditEvent.objects.create(
        actor=actor_obj,
        actor_username=_name(actor) or (actor_name or _process_name())[:150],
        target=target if getattr(target, "pk", None) else None,
        target_username=_name(target),
        action=action,
        result=result,
        detail=str(detail)[:300],
    )
    fields = {
        "audit_actor": event.actor_username,
        "audit_target": event.target_username,
        "audit_action": event.action,
        "audit_result": event.result,
        "audit_detail": event.detail,
    }
    # Log dopiero po zatwierdzeniu — wycofana zmiana nie zostawia fałszywej linii.
    transaction.on_commit(
        lambda: logger.info("audit %s %s", action, result, extra=fields)
    )
    return event


class AuditActorMiddleware:
    """Udostępnia sygnałom użytkownika bieżącego żądania (po AuthenticationMiddleware)."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, "user", None)
        token = _current_actor.set(
            user if getattr(user, "is_authenticated", False) else None
        )
        try:
            return self.get_response(request)
        finally:
            _current_actor.reset(token)


# --- Sygnały: konto -----------------------------------------------------------


def _yes_no(value) -> str:
    return "tak" if value else "nie"


@receiver(pre_save, sender=settings.AUTH_USER_MODEL)
def _user_before(sender, instance, update_fields=None, raw=False, **kwargs):
    instance._audit_old = None
    if raw or instance.pk is None:
        return
    if update_fields is not None and not set(update_fields) & set(_USER_FIELDS):
        return  # np. last_login przy każdym logowaniu — bez dodatkowego zapytania
    instance._audit_old = (
        sender.objects.filter(pk=instance.pk).values(*_USER_FIELDS).first()
    )


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def _user_after(sender, instance, created, raw=False, **kwargs):
    if raw:
        return
    if created:
        flags = [f for f in ("is_superuser", "is_staff") if getattr(instance, f)]
        record(Action.USER_CREATE, target=instance, detail=", ".join(flags))
        return
    old = getattr(instance, "_audit_old", None)
    if not old:
        return
    # Django przy logowaniu przelicza hash (np. PBKDF2 → argon2) i zeruje `_password` —
    # to nie jest zmiana hasła. Prawdziwa zmiana idzie przez set_password().
    if (
        old["password"] != instance.password
        and getattr(instance, "_password", None) is not None
    ):
        record(
            Action.PASSWORD_CHANGE, target=instance, detail="hasło ustawione na nowo"
        )
    if old["is_active"] != instance.is_active:
        record(
            Action.ACTIVE_CHANGE,
            target=instance,
            detail="aktywne" if instance.is_active else "nieaktywne",
        )
    for field, label in (
        ("is_superuser", "superuser"),
        ("is_staff", "dostęp do /admin/"),
    ):
        if old[field] != getattr(instance, field):
            record(
                Action.ROLE_CHANGE,
                target=instance,
                detail=f"{label}: {_yes_no(old[field])} → {_yes_no(getattr(instance, field))}",
            )


@receiver(pre_delete, sender=settings.AUTH_USER_MODEL)
def _user_deleted(sender, instance, **kwargs):
    record(
        Action.USER_DELETE, target=instance, detail=f"usunięto konto {_name(instance)}"
    )


@receiver(pre_save, sender=Profile)
def _profile_before(sender, instance, raw=False, **kwargs):
    instance._audit_old_role = None
    if not raw and instance.pk is not None:
        instance._audit_old_role = (
            sender.objects.filter(pk=instance.pk).values_list("role", flat=True).first()
        )


@receiver(post_save, sender=Profile)
def _profile_after(sender, instance, created, raw=False, **kwargs):
    old = getattr(instance, "_audit_old_role", None)
    if raw or created or old is None or old == instance.role:
        return
    record(
        Action.ROLE_CHANGE,
        target=instance.user,
        detail=f"{Role(old).label} → {Role(instance.role).label}",
    )


# --- Sygnały: 2FA -------------------------------------------------------------


@receiver(pre_save, sender=TOTPDevice)
def _totp_before(sender, instance, raw=False, **kwargs):
    instance._audit_was_confirmed = bool(
        not raw
        and instance.pk is not None
        and sender.objects.filter(pk=instance.pk, confirmed=True).exists()
    )


@receiver(post_save, sender=TOTPDevice)
def _totp_after(sender, instance, raw=False, **kwargs):
    if (
        not raw
        and instance.confirmed
        and not getattr(instance, "_audit_was_confirmed", False)
    ):
        record(Action.TWO_FACTOR_ENABLE, target=instance.user)


@receiver(post_delete, sender=TOTPDevice)
def _totp_deleted(sender, instance, **kwargs):
    # Niepotwierdzone urządzenia usuwa sam ekran /2fa/ przy każdym wyświetleniu — to nie zdarzenie.
    if instance.confirmed:
        record(
            Action.TWO_FACTOR_RESET,
            target=instance.user,
            detail="usunięto urządzenie TOTP",
        )
