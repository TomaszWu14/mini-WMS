"""Palety (HU): lista, szczegóły, etykiety, alokacja, korekty, przepakowanie."""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.http import content_disposition_header

from .. import services
from ..forms import (
    AllocateForm,
    DeliveryDateForm,
    HUCorrectionForm,
    RepackForm,
)
from ..labels import hu_label_pdf, hu_labels_pdf
from ..models import (
    HandlingUnit,
    HUStatus,
    MovementType,
    StockMovement,
)
from ..pagination import paginate
from ..roles import admin_required, operator_required
from ..services import WMSError

# --- HU ----------------------------------------------------------------------


@login_required
def hu_list(request):
    status = request.GET.get("status", "").strip()
    query = request.GET.get("q", "").strip()
    hus = HandlingUnit.objects.select_related("material", "location", "material__unit")
    if status:
        hus = hus.filter(status=status)
    if query:
        hus = hus.filter(
            Q(number__icontains=query)
            | Q(material__index__icontains=query)
            | Q(location__code__icontains=query)
        )
    page, page_query = paginate(request, hus)
    return render(
        request,
        "warehouse/hu_list.html",
        {
            "handling_units": page,
            "page_obj": page,
            "page_query": page_query,
            "status": status,
            "query": query,
            "statuses": HUStatus.choices,
        },
    )


@login_required
def hu_detail(request, pk):
    hu = get_object_or_404(
        HandlingUnit.objects.select_related("material", "location", "material__unit"),
        pk=pk,
    )
    movements = hu.movements.select_related("created_by")[:50]
    return render(
        request,
        "warehouse/hu_detail.html",
        {"hu": hu, "movements": movements},
    )


@login_required
def hu_label(request, pk):
    hu = get_object_or_404(
        HandlingUnit.objects.select_related("material", "material__unit"), pk=pk
    )
    pdf = hu_label_pdf(hu)
    response = HttpResponse(pdf, content_type="application/pdf")
    response["Content-Disposition"] = (
        content_disposition_header(False, f"{hu.number}.pdf") or "inline"
    )
    return response


HU_LABELS_LIMIT = 200


@login_required
def hu_labels(request):
    """Wydruk wielu etykiet HU naraz — wg tych samych filtrów co lista HU."""
    status = request.GET.get("status", "").strip()
    query = request.GET.get("q", "").strip()
    hus = HandlingUnit.objects.select_related("material", "location", "material__unit")
    if status:
        hus = hus.filter(status=status)
    if query:
        hus = hus.filter(
            Q(number__icontains=query)
            | Q(material__index__icontains=query)
            | Q(location__code__icontains=query)
            | Q(delivery_ref__icontains=query)
        )
    # Limit jednej partii wydruku — powyżej nie obcinamy po cichu, tylko prosimy
    # o zawężenie filtra.
    count = hus.count()
    if count > HU_LABELS_LIMIT:
        messages.error(
            request,
            f"Wybrano {count} palet — limit jednego wydruku to {HU_LABELS_LIMIT}. "
            "Zawęź filtr.",
        )
        return redirect(f"{reverse('hu_list')}?{request.GET.urlencode()}")
    pdf = hu_labels_pdf(hus)
    response = HttpResponse(pdf, content_type="application/pdf")
    response["Content-Disposition"] = (
        content_disposition_header(False, "etykiety_hu.pdf") or "inline"
    )
    return response


@operator_required
def hu_allocate(request, pk):
    hu = get_object_or_404(HandlingUnit, pk=pk)
    if hu.status == HUStatus.PUSTY:
        messages.error(request, "Nie można ulokować pustego HU.")
        return redirect("hu_detail", pk=pk)
    if request.method == "POST":
        form = AllocateForm(request.POST)
        if form.is_valid():
            location = form.cleaned_data["location"]
            try:
                services.allocate_hu(
                    hu=hu,
                    location=location,
                    user=request.user,
                )
            except WMSError as exc:
                messages.error(request, str(exc))
            else:
                messages.success(
                    request,
                    f"HU {hu.number} ulokowano w {location.code}.",
                )
                if services.location_over_capacity(location):
                    messages.warning(
                        request,
                        f"Lokalizacja {location.code} ma więcej palet niż "
                        f"pojemność ({location.occupancy}/{location.capacity}).",
                    )
                return redirect("hu_detail", pk=pk)
    else:
        form = AllocateForm()
    return render(
        request,
        "warehouse/hu_allocate.html",
        {"form": form, "hu": hu},
    )


@admin_required
def hu_delivery(request, pk):
    """Zmiana terminu/numeru dostawy — tylko Administrator."""
    hu = get_object_or_404(HandlingUnit, pk=pk)
    if request.method == "POST":
        form = DeliveryDateForm(request.POST)
        if form.is_valid():
            hu.delivery_date = form.cleaned_data.get("delivery_date")
            hu.delivery_ref = form.cleaned_data.get("delivery_ref", "")
            hu.save(update_fields=["delivery_date", "delivery_ref"])
            messages.success(request, f"Zaktualizowano dostawę HU {hu.number}.")
            return redirect("hu_detail", pk=pk)
    else:
        form = DeliveryDateForm(
            initial={
                "delivery_date": hu.delivery_date,
                "delivery_ref": hu.delivery_ref,
            }
        )
    return render(
        request,
        "warehouse/hu_delivery.html",
        {"form": form, "hu": hu},
    )


@operator_required
def hu_correct(request, pk):
    hu = get_object_or_404(HandlingUnit, pk=pk)
    if request.method == "POST":
        form = HUCorrectionForm(request.POST)
        if form.is_valid():
            try:
                services.correct_hu_quantity(
                    hu=hu,
                    new_quantity=form.cleaned_data["new_quantity"],
                    user=request.user,
                    note=form.cleaned_data.get("note", ""),
                    reason=form.cleaned_data["reason"],
                )
            except WMSError as exc:
                messages.error(request, str(exc))
            else:
                messages.success(request, f"Skorygowano ilość HU {hu.number}.")
                return redirect("hu_detail", pk=pk)
    else:
        form = HUCorrectionForm(initial={"new_quantity": hu.quantity})
    return render(
        request,
        "warehouse/hu_correct.html",
        {"form": form, "hu": hu},
    )


# --- Przepakowanie (web) -----------------------------------------------------


@operator_required
def repack_view(request):
    if request.method == "POST":
        form = RepackForm(request.POST)
        if form.is_valid():
            src = HandlingUnit.objects.filter(
                number__iexact=form.cleaned_data["source_number"].strip()
            ).first()
            tgt = HandlingUnit.objects.filter(
                number__iexact=form.cleaned_data["target_number"].strip()
            ).first()
            if src is None:
                form.add_error("source_number", "Nie znaleziono palety źródłowej.")
            elif tgt is None:
                form.add_error("target_number", "Nie znaleziono palety docelowej.")
            else:
                try:
                    services.repack_hu(
                        source=src,
                        target=tgt,
                        quantity=form.cleaned_data["quantity"],
                        user=request.user,
                    )
                except WMSError as exc:
                    messages.error(request, str(exc))
                else:
                    messages.success(
                        request,
                        f"Przepakowano {form.cleaned_data['quantity']} "
                        f"z {src.number} → {tgt.number}.",
                    )
                    return redirect("repack")
    else:
        form = RepackForm(initial={"source_number": request.GET.get("source", "")})

    recent = StockMovement.objects.filter(
        type=MovementType.PRZEPAKOWANIE
    ).select_related("handling_unit", "material", "created_by")[:20]
    return render(request, "warehouse/repack.html", {"form": form, "recent": recent})
