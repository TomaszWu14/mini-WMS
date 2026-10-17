"""Historia ruchów magazynowych i jej eksport."""

from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import render
from django.utils import timezone

from ..exports import rows_to_csv_response, rows_to_xlsx_response
from ..models import (
    MovementType,
    StockMovement,
)

# --- Ruchy magazynowe --------------------------------------------------------


@login_required
def movement_list(request):
    mtype = request.GET.get("type", "").strip()
    movements = StockMovement.objects.select_related(
        "material", "handling_unit", "created_by", "location_from", "location_to"
    )
    if mtype:
        movements = movements.filter(type=mtype)
    return render(
        request,
        "warehouse/movement_list.html",
        {
            "movements": movements[:500],
            "type": mtype,
            "types": MovementType.choices,
        },
    )


def _movement_export_rows(mtype=""):
    header = [
        "Data",
        "Typ",
        "Materiał",
        "HU",
        "Zmiana ilości",
        "Z lokalizacji",
        "Do lokalizacji",
        "Dokument",
        "Kto",
        "Uwagi",
    ]
    rows = []
    qs = StockMovement.objects.select_related(
        "material",
        "handling_unit",
        "created_by",
        "location_from",
        "location_to",
        "issue_document",
    )
    if mtype:
        qs = qs.filter(type=mtype)
    for m in qs:
        rows.append(
            [
                timezone.localtime(m.created_at).strftime("%Y-%m-%d %H:%M"),
                m.get_type_display(),
                m.material.index,
                m.handling_unit.number if m.handling_unit else "",
                m.quantity_delta,
                m.location_from.code if m.location_from else "",
                m.location_to.code if m.location_to else "",
                m.issue_document.number if m.issue_document else "",
                m.created_by.username if m.created_by else "",
                m.note,
            ]
        )
    return header, rows


@login_required
def movement_export(request, fmt):
    if fmt not in ("csv", "xlsx"):
        raise Http404("Nieobsługiwany format eksportu.")
    header, rows = _movement_export_rows(request.GET.get("type", "").strip())
    if fmt == "xlsx":
        return rows_to_xlsx_response("ruchy_magazynowe", header, rows, "Ruchy")
    return rows_to_csv_response("ruchy_magazynowe", header, rows)
