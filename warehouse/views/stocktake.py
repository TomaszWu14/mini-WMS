"""Spis z natury i inwentaryzacja palety (web)."""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count
from django.shortcuts import get_object_or_404, redirect, render

from .. import services
from ..forms import (
    InventoryForm,
    StocktakeCreateForm,
)
from ..models import (
    HandlingUnit,
    MovementType,
    StockMovement,
    StocktakeSheet,
    StocktakeStatus,
)
from ..roles import operator_required
from ..services import WMSError

# --- Spis z natury -----------------------------------------------------------


@login_required
def stocktake_list(request):
    sheets = StocktakeSheet.objects.select_related("location", "created_by").annotate(
        line_count=Count("lines")
    )
    form = StocktakeCreateForm()
    return render(
        request,
        "warehouse/stocktake_list.html",
        {"sheets": sheets, "form": form},
    )


@operator_required
def stocktake_create(request):
    if request.method == "POST":
        form = StocktakeCreateForm(request.POST)
        if form.is_valid():
            sheet = services.create_stocktake(
                location=form.cleaned_data.get("location"), user=request.user
            )
            messages.success(
                request,
                f"Utworzono arkusz {sheet.number} ({sheet.lines.count()} pozycji).",
            )
            if sheet.skipped_in_open:
                messages.warning(
                    request,
                    f"Pominięto {sheet.skipped_in_open} palet, które są już "
                    "w innym otwartym arkuszu spisu.",
                )
            return redirect("stocktake_detail", pk=sheet.pk)
        else:
            for errs in form.errors.values():
                for err in errs:
                    messages.error(request, err)
    return redirect("stocktake_list")


@login_required
def stocktake_detail(request, pk):
    sheet = get_object_or_404(
        StocktakeSheet.objects.select_related("location", "created_by"), pk=pk
    )
    lines = sheet.lines.select_related("handling_unit", "material", "material__unit")
    return render(
        request,
        "warehouse/stocktake_detail.html",
        {"sheet": sheet, "lines": lines},
    )


@operator_required
def stocktake_save(request, pk):
    """Zapis policzonych ilości (bez zamykania)."""
    sheet = get_object_or_404(StocktakeSheet, pk=pk)
    if sheet.status == StocktakeStatus.ZAMKNIETY:
        messages.error(request, "Arkusz jest zamknięty.")
        return redirect("stocktake_detail", pk=pk)
    if request.method == "POST":
        updated = 0
        skipped = 0
        for line in sheet.lines.all():
            raw = request.POST.get(f"counted_{line.id}", "").strip()
            if raw == "":
                new_val = None
            else:
                try:
                    new_val = max(0, int(raw))
                except ValueError:
                    skipped += 1
                    continue
                if new_val > services.MAX_QUANTITY:  # US-013
                    skipped += 1
                    continue
            if new_val != line.counted_qty:
                line.counted_qty = new_val
                line.save(update_fields=["counted_qty"])
                updated += 1
        messages.success(request, f"Zapisano ({updated} zmian).")
        if skipped:
            messages.warning(
                request,
                f"Pominięto {skipped} wartości, które nie są liczbą całkowitą "
                f"od 0 do {services.MAX_QUANTITY}.",
            )
    return redirect("stocktake_detail", pk=pk)


@operator_required
def stocktake_close(request, pk):
    sheet = get_object_or_404(StocktakeSheet, pk=pk)
    if request.method == "POST":
        try:
            result = services.close_stocktake(sheet=sheet, user=request.user)
        except WMSError as exc:
            messages.error(request, str(exc))
        else:
            messages.success(
                request,
                f"Spis {sheet.number} zamknięty. Policzono {result['counted']} "
                f"pozycji, naniesiono {result['adjusted']} korekt.",
            )
    return redirect("stocktake_detail", pk=pk)


# --- Inwentaryzacja (web) ----------------------------------------------------


@operator_required
def inventory_view(request):
    if request.method == "POST":
        form = InventoryForm(request.POST)
        if form.is_valid():
            number = form.cleaned_data["hu_number"].strip()
            qty = form.cleaned_data["quantity"]
            mode = form.cleaned_data["mode"]
            note = form.cleaned_data.get("note", "")
            hu = HandlingUnit.objects.filter(number__iexact=number).first()
            if hu is None:
                form.add_error("hu_number", f"Nie znaleziono HU „{number}”.")
            else:
                delta = qty if mode == InventoryForm.MODE_ADD else -qty
                try:
                    services.adjust_hu_quantity(
                        hu=hu,
                        delta=delta,
                        user=request.user,
                        note=note or "Inwentaryzacja (web)",
                        reason=form.cleaned_data["reason"],
                    )
                except WMSError as exc:
                    form.add_error("quantity", str(exc))
                else:
                    sign = "+" if delta > 0 else "−"
                    messages.success(
                        request,
                        f"HU {hu.number}: {sign}{abs(delta)} → stan "
                        f"{hu.quantity} {hu.material.unit.code}.",
                    )
                    return redirect("inventory")
    else:
        form = InventoryForm()

    recent = StockMovement.objects.filter(type=MovementType.KOREKTA).select_related(
        "handling_unit", "material", "created_by"
    )[:20]
    return render(
        request,
        "warehouse/inventory.html",
        {"form": form, "recent": recent},
    )
