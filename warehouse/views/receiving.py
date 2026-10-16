"""Przyjęcie towaru (formularz i import)."""

from django.contrib import messages
from django.shortcuts import redirect, render

from .. import services
from ..forms import (
    ReceiptImportForm,
    ReceiveForm,
)
from ..imports import ImportError_
from ..receipt_import import import_receipts
from ..roles import operator_required
from ..services import WMSError

# --- Przyjęcie ---------------------------------------------------------------


@operator_required
def receive(request):
    if request.method == "POST":
        form = ReceiveForm(request.POST)
        if form.is_valid():
            material = form.cleaned_data["material"]
            total = form.cleaned_data["computed_total"]
            pallets = form.cleaned_data["pallets"]
            try:
                quantities = services.split_quantity(total, pallets)
                result = services.receive_material(
                    material=material,
                    quantities=quantities,
                    user=request.user,
                    lot=form.cleaned_data.get("lot", ""),
                    expiry_date=form.cleaned_data.get("expiry_date"),
                    delivery_ref=form.cleaned_data.get("delivery_ref", ""),
                )
            except WMSError as exc:
                messages.error(request, str(exc))
            else:
                numbers = ", ".join(hu.number for hu in result.handling_units)
                messages.success(
                    request,
                    f"Przyjęto {len(result.handling_units)} palet(y) "
                    f"({total} {material.unit.code}): {numbers}.",
                )
                return redirect("hu_list")
    else:
        form = ReceiveForm()
    return render(request, "warehouse/receive.html", {"form": form})


@operator_required
def receive_import(request):
    if request.method == "POST":
        form = ReceiptImportForm(request.POST, request.FILES)
        if form.is_valid():
            upload = form.cleaned_data["file"]
            try:
                result = import_receipts(upload.name, upload.read(), request.user)
            except ImportError_ as exc:
                messages.error(request, f"Błąd importu: {exc}")
            else:
                messages.success(
                    request,
                    f"Przyjęto {result['created_hus']} palet (HU) z importu.",
                )
                for err in result["errors"][:30]:
                    messages.warning(request, err)
            return redirect("hu_list")
    else:
        form = ReceiptImportForm()
    return render(
        request,
        "warehouse/receive_import.html",
        {"form": form, "title": "Import przyjęć"},
    )
