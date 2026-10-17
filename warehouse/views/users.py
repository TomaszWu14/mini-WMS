"""Użytkownicy, role, mapa uprawnień i dziennik logowań (Administrator)."""

from django.contrib import messages
from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render

from ..audit import Action, Result, record
from ..demo import is_demo_account
from ..forms import (
    UserCreateForm,
    UserEditForm,
)
from ..models import (
    AuditEvent,
    LoginEvent,
    Profile,
    Role,
)
from ..pagination import paginate
from ..roles import admin_required

# --- Użytkownicy i mapa uprawnień (Admin) -----------------------------------

# Mapa uprawnień: dla każdej możliwości — które role mają dostęp.
PERMISSION_MATRIX = [
    ("Pulpit, stany, raporty (podgląd)", True, True, True),
    ("Eksport CSV / XLSX", True, True, True),
    ("Etykiety i dokument WZ (PDF)", True, True, True),
    ("Przyjęcie i generowanie HU", True, True, False),
    ("Alokacja / przesunięcie HU", True, True, False),
    ("Korekta ilości", True, True, False),
    ("Picking / realizacja wydań", True, True, False),
    ("Inwentaryzacja", True, True, False),
    ("Przepakowanie HU", True, True, False),
    ("Spis z natury (tworzenie/zamykanie)", True, True, False),
    ("Import lokalizacji / stanów", True, True, False),
    ("Tryb skanera", True, True, False),
    ("Zmiana terminu dostawy", True, False, False),
    ("Edycja / usuwanie ruchów (panel Django — tylko superuser)", True, False, False),
    ("Zarządzanie użytkownikami", True, False, False),
]


@admin_required
def user_list(request):
    users = User.objects.select_related("profile").order_by("username")
    rows = []
    for u in users:
        role = (
            Role.ADMIN
            if u.is_superuser
            else getattr(getattr(u, "profile", None), "role", Role.VIEWER)
        )
        rows.append({"user": u, "role": role})
    return render(
        request,
        "warehouse/user_list.html",
        {"rows": rows, "matrix": PERMISSION_MATRIX, "roles": Role.choices},
    )


@admin_required
def login_log(request):
    qs = LoginEvent.objects.select_related("user")
    page, page_query = paginate(request, qs)
    return render(
        request,
        "warehouse/login_log.html",
        {"events": page, "page_obj": page, "page_query": page_query},
    )


@admin_required
def audit_log(request):
    """US-022: dziennik audytowy (zmiany kont, odmowy dostępu)."""
    qs = AuditEvent.objects.all()
    page, page_query = paginate(request, qs)
    return render(
        request,
        "warehouse/audit_log.html",
        {"events": page, "page_obj": page, "page_query": page_query},
    )


@admin_required
def user_create(request):
    if request.method == "POST":
        form = UserCreateForm(request.POST)
        if form.is_valid():
            # US-022: konto, profil i wpisy audytowe (sygnały) — jedna transakcja.
            with transaction.atomic():
                user = User.objects.create_user(
                    username=form.cleaned_data["username"],
                    email=form.cleaned_data.get("email", ""),
                    password=form.cleaned_data["password"],
                )
                Profile.objects.update_or_create(
                    user=user, defaults={"role": form.cleaned_data["role"]}
                )
            messages.success(request, f"Utworzono użytkownika {user.username}.")
            return redirect("user_list")
    else:
        form = UserCreateForm()
    return render(
        request,
        "warehouse/form_generic.html",
        {"form": form, "title": "Nowy użytkownik", "submit": "Utwórz"},
    )


@admin_required
def user_edit(request, pk):
    user = get_object_or_404(User, pk=pk)
    # US-001 / R1: konta z dostępem do /admin/ (superuser, staff) zmienia tylko
    # superuser — inaczej rola Administrator przejęłaby je resetem hasła.
    if (user.is_superuser or user.is_staff) and not request.user.is_superuser:
        # Tylko POST: GET da się wywołać z obcej strony (<img src>) albo prefetchem —
        # podrobione wpisy zagłuszyłyby dziennik (przegląd [SEC] US-022).
        if request.method == "POST":
            record(
                Action.ACCESS_DENIED,
                actor=request.user,
                target=user,
                result=Result.DENIED,
                detail="próba zmiany konta z dostępem do /admin/",
            )
        raise PermissionDenied(
            "Konto z dostępem do panelu administracyjnego może edytować tylko "
            "superuser (panel /admin/ albo `manage.py changepassword`)."
        )
    if is_demo_account(user):
        if request.method == "POST":
            record(
                Action.ACCESS_DENIED,
                actor=request.user,
                target=user,
                result=Result.DENIED,
                detail="edycja chronionego konta demo",
            )
        return HttpResponseForbidden(
            "Konta demo są chronione — w trybie demo nie można zmieniać ich "
            "hasła, roli ani statusu."
        )
    profile, _ = Profile.objects.get_or_create(user=user)
    if request.method == "POST":
        form = UserEditForm(request.POST, edited_user=user)
        if form.is_valid():
            editing_self = user == request.user
            if editing_self and not form.cleaned_data["is_active"]:
                record(
                    Action.ACTIVE_CHANGE,
                    actor=request.user,
                    target=user,
                    result=Result.DENIED,
                    detail="próba dezaktywacji własnego konta",
                )
                messages.error(request, "Nie możesz dezaktywować własnego konta.")
            elif editing_self and form.cleaned_data["role"] != Role.ADMIN:
                record(
                    Action.ROLE_CHANGE,
                    actor=request.user,
                    target=user,
                    result=Result.DENIED,
                    detail="próba odebrania sobie roli Administratora",
                )
                messages.error(
                    request,
                    "Nie możesz odebrać sobie roli Administratora — "
                    "poproś innego administratora.",
                )
            else:
                # US-022: zmiana i jej wpisy audytowe (sygnały User/Profile) — razem albo wcale.
                with transaction.atomic():
                    profile.role = form.cleaned_data["role"]
                    profile.save(update_fields=["role"])
                    user.is_active = form.cleaned_data["is_active"]
                    new_pw = form.cleaned_data.get("new_password")
                    if new_pw:
                        user.set_password(new_pw)
                    user.save()
                messages.success(request, f"Zaktualizowano {user.username}.")
                return redirect("user_list")
    else:
        form = UserEditForm(
            initial={"role": profile.role, "is_active": user.is_active},
            edited_user=user,
        )
    return render(
        request,
        "warehouse/user_edit.html",
        {"form": form, "edited_user": user},
    )
