"""Raporty: zajętość lokalizacji, kartoteka materiału."""

from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q, Sum
from django.shortcuts import render

from ..models import (
    HandlingUnit,
    HUStatus,
    Location,
    Material,
    StockMovement,
)
from ..pagination import paginate

# --- Raporty -----------------------------------------------------------------


@login_required
def report_index(request):
    return render(request, "warehouse/report_index.html")


@login_required
def report_locations(request):
    """Raport zajętości lokalizacji."""
    locs = Location.objects.annotate(
        active=Count("handling_units", filter=~Q(handling_units__status=HUStatus.PUSTY))
    ).order_by("code")
    # US-015: podsumowanie liczone ze wszystkich lokalizacji (dwie liczby na wiersz),
    # tabela — tylko bieżąca strona.
    total = occupied = free_slots = 0
    for capacity, active in locs.values_list("capacity", "active"):
        total += 1
        free_slots += max(0, capacity - active)
        if active > 0:
            occupied += 1
    summary = {
        "total": total,
        "occupied": occupied,
        "empty": total - occupied,
        "free_slots": free_slots,
    }
    page, page_query = paginate(request, locs, count=total)
    rows = [
        {"loc": loc, "active": loc.active, "free": max(0, loc.capacity - loc.active)}
        for loc in page
    ]
    return render(
        request,
        "warehouse/report_locations.html",
        {"rows": rows, "summary": summary, "page_obj": page, "page_query": page_query},
    )


@login_required
def report_material_history(request):
    """Kartoteka materiału — pełna historia ruchów wybranego indeksu."""
    index = request.GET.get("material", "").strip()
    material = None
    movements = []
    current = 0
    if index:
        material = Material.objects.filter(index=index).first()
        if material is not None:
            movements = StockMovement.objects.filter(material=material).select_related(
                "handling_unit", "created_by", "location_from", "location_to"
            )[:500]
            current = (
                HandlingUnit.objects.filter(material=material)
                .exclude(status=HUStatus.PUSTY)
                .aggregate(s=Sum("quantity"))["s"]
                or 0
            )
    materials = Material.objects.select_related("unit").order_by("index")
    return render(
        request,
        "warehouse/report_material.html",
        {
            "materials": materials,
            "material": material,
            "selected": index,
            "movements": movements,
            "current": current,
        },
    )
