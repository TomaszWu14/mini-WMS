"""Dziennik audytowy akcji administracyjnych (US-022, SEC-032).

Jedno wejście: `record(...)` — zapis w tabeli `AuditEvent` (przeglądany na
/uzytkownicy/audyt/, trafia do backupu) i ta sama treść jako linia logu JSON
(logger `warehouse.audit`). Nigdy nie przekazuj tu wartości hasła ani kodu 2FA —
`detail` opisuje, co się zmieniło („hasło zmienione”), a nie na co.
"""

import logging

from .models import AuditEvent

logger = logging.getLogger("warehouse.audit")

Action = AuditEvent.Action
Result = AuditEvent.Result


def _name(user) -> str:
    return str(getattr(user, "username", "") or "")[:150]


def record(
    action, *, actor=None, target=None, result=Result.OK, detail="", actor_name=""
):
    """Zapisuje zdarzenie. `actor_name` — gdy akcję wykonuje proces, nie konto
    (np. `manage.py reset_2fa`)."""
    actor_obj = actor if getattr(actor, "pk", None) else None
    event = AuditEvent.objects.create(
        actor=actor_obj,
        actor_username=_name(actor) or actor_name[:150],
        target=target if getattr(target, "pk", None) else None,
        target_username=_name(target),
        action=action,
        result=result,
        detail=str(detail)[:300],
    )
    logger.info(
        "audit %s %s",
        action,
        result,
        extra={
            "audit_actor": event.actor_username,
            "audit_target": event.target_username,
            "audit_action": event.action,
            "audit_result": event.result,
            "audit_detail": event.detail,
        },
    )
    return event
