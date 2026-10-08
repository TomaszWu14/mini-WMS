"""Pomocnicze funkcje i dekoratory do kontroli ról."""

from functools import wraps

from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied

from .models import Role


def get_role(user) -> str:
    """Zwraca rolę użytkownika. Superuser zawsze traktowany jak Administrator."""
    if not user.is_authenticated:
        return ""
    if user.is_superuser:
        return Role.ADMIN
    profile = getattr(user, "profile", None)
    return profile.role if profile else Role.VIEWER


def is_admin(user) -> bool:
    return get_role(user) == Role.ADMIN


def is_operator(user) -> bool:
    """Operator lub Administrator — czyli ktoś, kto może wykonywać operacje."""
    return get_role(user) in {Role.OPERATOR, Role.ADMIN}


def role_required(*allowed_roles):
    """Dekorator widoku wymagający jednej z podanych ról."""

    def decorator(view_func):
        @wraps(view_func)
        def _wrapped(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect_to_login(request.get_full_path())
            if get_role(request.user) not in allowed_roles:
                raise PermissionDenied(
                    "Twoja rola nie pozwala na wykonanie tej operacji."
                )
            return view_func(request, *args, **kwargs)

        return _wrapped

    return decorator


# Gotowe skróty
operator_required = role_required(Role.OPERATOR, Role.ADMIN)
admin_required = role_required(Role.ADMIN)
