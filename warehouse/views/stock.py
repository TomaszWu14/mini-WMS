"""Stany magazynowe: wg materiału, wg lokalizacji, import i eksport stanów."""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q, Sum
from django.http import Http404
from django.shortcuts import redirect, render

from ..exports import rows_to_csv_response, rows_to_xlsx_response
from ..forms import (
    StockImportForm,
)
from ..imports import ImportError_
from ..models import (
    HandlingUnit,
    HUStatus,
)
from ..pagination import paginate
from ..roles import operator_required
from ..stock_import import import_stock

# --- Stany magazynowe --------------------------------------------------------


@login_required
def stock_list(request):
    rows = (
        HandlingUnit.objects.exclude(status=HUStatus.PUSTY)
        .values("material__index", "material__name", "material__unit__code")
        .annotate(qty=Sum("quantity"), hus=Count("id"))
        .order_by("material__index")
    )
    return render(request, "warehouse/stock_list.html", {"rows": rows})


@login_required
def stock_by_location(request):
    """Gdzie jest materiał — stan w rozbiciu na lokalizacje i palety."""
    query = request.GET.get("q", "").strip()
    hus = HandlingUnit.objects.exclude(status=HUStatus.PUSTY).select_related(
        "material", "location", "material__unit"
    )
    if query:
        hus = hus.filter(
            Q(material__index__icontains=query)
            | Q(material__name__icontains=query)
            | Q(location__code__icontains=query)
            | Q(number__icontains=query)
        )
    hus = hus.order_by("location__code", "material__index", "number")
    page, page_query = paginate(request, hus)
    return render(
        request,
        "warehouse/stock_by_location.html",
        {
            "handling_units": page,
            "page_obj": page,
            "page_query": page_query,
            "query": query,
        },
    )


@operator_required
def stock_import_view(request):
    if request.method == "POST":
        form = StockImportForm(request.POST, request.FILES)
        if form.is_valid():
            upload = form.cleaned_data["file"]
            try:
                result = import_stock(upload.name, upload.read(), request.user)
            except ImportError_ as exc:
                messages.error(request, f"Błąd importu: {exc}")
            else:
                messages.success(
                    request,
                    f"Zaimportowano {result['created']} palet (HU). "
                    f"Nowych materiałów: {result['materials_created']}, "
                    f"nowych lokalizacji: {result['locations_created']}.",
                )
                if result["zero_qty"]:
                    messages.warning(
                        request,
                        f"{result['zero_qty']} palet ma ilość 0 — uzupełnij ją "
                        "korektą ilości.",
                    )
                if result["over_capacity"]:
                    messages.warning(
                        request,
                        "Przekroczona pojemność lokalizacji: "
                        + ", ".join(result["over_capacity"]),
                    )
                for err in result["errors"][:30]:
                    messages.warning(request, err)
            return redirect("stock_list")
    else:
        form = StockImportForm()
    return render(
        request,
        "warehouse/stock_import.html",
        {"form": form, "title": "Import stanów początkowych"},
    )


def _stock_export_rows():
    header = ["Indeks", "Nazwa", "Jednostka", "Ilość", "Liczba HU"]
    data = (
        HandlingUnit.objects.exclude(status=HUStatus.PUSTY)
        .values("material__index", "material__name", "material__unit__code")
        .annotate(qty=Sum("quantity"), hus=Count("id"))
        .order_by("material__index")
    )
    rows = [
        [
            r["material__index"],
            r["material__name"],
            r["material__unit__code"],
            r["qty"],
            r["hus"],
        ]
        for r in data
    ]
    return header, rows


@login_required
def stock_export(request, fmt):
    if fmt not in ("csv", "xlsx"):
        raise Http404("Nieobsługiwany format eksportu.")
    header, rows = _stock_export_rows()
    if fmt == "xlsx":
        return rows_to_xlsx_response("stany_magazynowe", header, rows, "Stany")
    return rows_to_csv_response("stany_magazynowe", header, rows)
