"""Kontekst szablonów — flagi ról dostępne we wszystkich widokach."""

from .roles import get_role, is_admin, is_operator


def role_flags(request):
    user = getattr(request, "user", None)
    if user is None:
        return {}
    return {
        "user_role": get_role(user),
        "is_admin_role": is_admin(user),
        "is_operator_role": is_operator(user),
    }
