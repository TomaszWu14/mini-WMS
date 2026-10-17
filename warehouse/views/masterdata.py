"""Dane podstawowe: materiały i lokalizacje (lista, import, etykiety)."""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.http import content_disposition_header

from .. import services
from ..forms import (
    LocationForm,
    LocationImportForm,
    MaterialForm,
)
from ..imports import ImportError_, import_locations
from ..labels import location_labels_pdf
from ..models import (
    HUStatus,
    Location,
    LocationType,
    Material,
)
from ..pagination import paginate
from ..roles import operator_required
from ..services import WMSError

# --- Materiały ---------------------------------------------------------------


@login_required
def material_list(request):
    query = request.GET.get("q", "").strip()
    materials = Material.objects.select_related("unit")
    if query:
        materials = materials.filter(
            Q(index__icontains=query) | Q(name__icontains=query)
        )
    return render(
        request,
        "warehouse/material_list.html",
        {"materials": materials, "query": query},
    )


@operator_required
def material_create(request):
    if request.method == "POST":
        form = MaterialForm(request.POST)
        if form.is_valid():
            material = form.save(commit=False)
            material.created_by = request.user
            material.save()
            messages.success(request, f"Dodano materiał {material.index}.")
            return redirect("material_list")
    else:
        form = MaterialForm()
    return render(
        request,
        "warehouse/form_generic.html",
        {"form": form, "title": "Nowy materiał", "submit": "Zapisz"},
    )


# --- Lokalizacje -------------------------------------------------------------


LOCATION_LABELS_LIMIT = 200  # US-015, L_ETYKIET_LOK — jak HU_LABELS_LIMIT (D-11)


def _filtered_locations(request):
    """Filtry listy lokalizacji — te same dla listy i zbiorczego wydruku etykiet."""
    loc_type = request.GET.get("type", "").strip()
    query = request.GET.get("q", "").strip()
    locations = Location.objects.all()
    if loc_type:
        locations = locations.filter(type=loc_type)
    if query:
        locations = locations.filter(code__icontains=query)
    return locations, loc_type, query


@login_required
def location_list(request):
    locations, loc_type, query = _filtered_locations(request)
    locations = locations.annotate(
        active_hus=Count(
            "handling_units",
            filter=~Q(handling_units__status=HUStatus.PUSTY),
        )
    ).order_by("code")  # GROUP BY pomija Meta.ordering — stronicowanie wymaga porządku
    page, page_query = paginate(request, locations)
    return render(
        request,
        "warehouse/location_list.html",
        {
            "locations": page,
            "page_obj": page,
            "page_query": page_query,
            "type": loc_type,
            "query": query,
            "types": LocationType.choices,
        },
    )


@operator_required
def location_create(request):
    if request.method == "POST":
        form = LocationForm(request.POST)
        if form.is_valid():
            try:
                services.DemoBudget().take(locations=1)
            except WMSError as exc:
                messages.error(request, str(exc))
                return redirect("location_list")
            else:
                loc = form.save()
                messages.success(request, f"Dodano lokalizację {loc.code}.")
                return redirect("location_list")
    else:
        form = LocationForm()
    return render(
        request,
        "warehouse/form_generic.html",
        {"form": form, "title": "Nowa lokalizacja", "submit": "Zapisz"},
    )


@operator_required
def location_import(request):
    if request.method == "POST":
        form = LocationImportForm(request.POST, request.FILES)
        if form.is_valid():
            upload = form.cleaned_data["file"]
            try:
                created, updated, errors = import_locations(upload.name, upload.read())
            except ImportError_ as exc:
                messages.error(request, f"Błąd importu: {exc}")
            else:
                messages.success(
                    request,
                    f"Import zakończony: utworzono {created}, "
                    f"zaktualizowano {updated}.",
                )
                for err in errors[:20]:
                    messages.warning(request, err)
            return redirect("location_list")
    else:
        form = LocationImportForm()
    return render(
        request,
        "warehouse/location_import.html",
        {"form": form, "title": "Import lokalizacji"},
    )


@login_required
def location_label(request, pk):
    loc = get_object_or_404(Location, pk=pk)
    pdf = location_labels_pdf([loc])
    response = HttpResponse(pdf, content_type="application/pdf")
    response["Content-Disposition"] = (
        content_disposition_header(False, f"LOK-{loc.code}.pdf") or "inline"
    )
    return response


@login_required
def location_labels(request):
    locations, _, _ = _filtered_locations(request)
    # US-015: jak przy HU — nie obcinamy po cichu, prosimy o zawężenie filtra.
    count = locations.count()
    if count > LOCATION_LABELS_LIMIT:
        messages.error(
            request,
            f"Wybrano {count} lokalizacji — limit jednego wydruku to "
            f"{LOCATION_LABELS_LIMIT}. Zawęź filtr.",
        )
        return redirect(f"{reverse('location_list')}?{request.GET.urlencode()}")
    pdf = location_labels_pdf(locations)
    response = HttpResponse(pdf, content_type="application/pdf")
    response["Content-Disposition"] = (
        content_disposition_header(False, "etykiety_lokalizacji.pdf") or "inline"
    )
    return response
