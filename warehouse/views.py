"""Widoki ekranów operatora mini-WMS."""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.core.paginator import Paginator
from django.db.models import Count, Q, Sum
from django.http import Http404, HttpResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from . import services
from .demo import is_demo_account
from .documents import issue_document_pdf
from .exports import rows_to_csv_response, rows_to_xlsx_response
from .forms import (
    AllocateForm,
    DeliveryDateForm,
    HUCorrectionForm,
    InventoryForm,
    IssueDocumentForm,
    IssueImportForm,
    IssueLineForm,
    LocationForm,
    LocationImportForm,
    MaterialForm,
    ReceiptImportForm,
    ReceiveForm,
    RepackForm,
    ShipForm,
    StockImportForm,
    StocktakeCreateForm,
    UserCreateForm,
    UserEditForm,
)
from .imports import ImportError_, import_locations
from .issue_import import import_issue_orders
from .labels import hu_label_pdf, hu_labels_pdf, location_labels_pdf
from .models import (
    HandlingUnit,
    HUStatus,
    IssueDocument,
    IssueLine,
    IssueStatus,
    Location,
    LoginEvent,
    Material,
    MovementType,
    Profile,
    Role,
    StockMovement,
    StocktakeSheet,
    StocktakeStatus,
)
from .receipt_import import import_receipts
from .roles import admin_required, operator_required
from .services import WMSError
from .stock_import import import_stock

# --- Dashboard ---------------------------------------------------------------


@login_required
def dashboard(request):
    today = timezone.localdate()
    active_hus = HandlingUnit.objects.exclude(status=HUStatus.PUSTY)
    context = {
        "hu_total": active_hus.count(),
        "hu_to_allocate": active_hus.filter(status=HUStatus.DO_ULOZENIA).count(),
        "hu_stored": active_hus.filter(status=HUStatus.ZMAGAZYNOWANY).count(),
        "material_count": Material.objects.count(),
        "location_count": Location.objects.count(),
        "occupied_locations": Location.objects.filter(
            handling_units__status=HUStatus.ZMAGAZYNOWANY
        )
        .distinct()
        .count(),
        "movements_today": StockMovement.objects.filter(created_at__date=today).count(),
        "open_issues": IssueDocument.objects.filter(status=IssueStatus.OTWARTY).count(),
        "recent_movements": StockMovement.objects.select_related(
            "material", "handling_unit", "created_by"
        )[:10],
        "stock_by_material": (
            active_hus.values(
                "material__index", "material__name", "material__unit__code"
            )
            .annotate(qty=Sum("quantity"), hus=Count("id"))
            .order_by("material__index")[:10]
        ),
    }
    return render(request, "warehouse/dashboard.html", context)


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


@login_required
def location_list(request):
    locations = Location.objects.annotate(
        active_hus=Count(
            "handling_units",
            filter=~Q(handling_units__status=HUStatus.PUSTY),
        )
    )
    return render(request, "warehouse/location_list.html", {"locations": locations})


@operator_required
def location_create(request):
    if request.method == "POST":
        form = LocationForm(request.POST)
        if form.is_valid():
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
    response["Content-Disposition"] = f'inline; filename="LOK-{loc.code}.pdf"'
    return response


@login_required
def location_labels(request):
    locations = Location.objects.all()
    loc_type = request.GET.get("type", "").strip()
    if loc_type:
        locations = locations.filter(type=loc_type)
    pdf = location_labels_pdf(locations)
    response = HttpResponse(pdf, content_type="application/pdf")
    response["Content-Disposition"] = 'inline; filename="etykiety_lokalizacji.pdf"'
    return response


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
    return render(
        request,
        "warehouse/hu_list.html",
        {
            "handling_units": hus,
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
    response["Content-Disposition"] = f'inline; filename="{hu.number}.pdf"'
    return response


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
    hus = hus[:200]  # bezpieczny limit jednej partii wydruku
    pdf = hu_labels_pdf(hus)
    response = HttpResponse(pdf, content_type="application/pdf")
    response["Content-Disposition"] = 'inline; filename="etykiety_hu.pdf"'
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
            try:
                services.allocate_hu(
                    hu=hu,
                    location=form.cleaned_data["location"],
                    user=request.user,
                )
            except WMSError as exc:
                messages.error(request, str(exc))
            else:
                messages.success(
                    request,
                    f"HU {hu.number} ulokowano w {hu.location.code}.",
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


# --- Picking / wydania -------------------------------------------------------


@login_required
def issue_list(request):
    documents = IssueDocument.objects.select_related("created_by").annotate(
        line_count=Count("lines")
    )
    return render(request, "warehouse/issue_list.html", {"documents": documents})


@operator_required
def issue_create(request):
    if request.method == "POST":
        form = IssueDocumentForm(request.POST)
        if form.is_valid():
            doc = form.save(commit=False)
            doc.created_by = request.user
            services.save_with_unique_number(doc, services.generate_issue_number)
            messages.success(request, f"Utworzono dokument {doc.number}.")
            return redirect("issue_detail", pk=doc.pk)
    else:
        form = IssueDocumentForm()
    return render(
        request,
        "warehouse/form_generic.html",
        {"form": form, "title": "Nowy dokument wydania", "submit": "Utwórz"},
    )


@login_required
def issue_detail(request, pk):
    doc = get_object_or_404(IssueDocument.objects.select_related("created_by"), pk=pk)
    lines = list(doc.lines.select_related("material", "material__unit", "specific_hu"))
    # Podpowiedź skąd pobrać (FEFO) dla otwartych pozycji z brakiem.
    if doc.status == IssueStatus.OTWARTY:
        for line in lines:
            if line.specific_hu_id or line.outstanding <= 0:
                line.suggestion = None
            else:
                line.suggestion = services.picking_plan(line.material, line.outstanding)
    return render(
        request,
        "warehouse/issue_detail.html",
        {
            "doc": doc,
            "lines": lines,
            "line_form": IssueLineForm(),
            "ship_form": ShipForm(),
            "movements": doc.movements.select_related("handling_unit", "created_by"),
        },
    )


@operator_required
def issue_add_line(request, pk):
    doc = get_object_or_404(IssueDocument, pk=pk)
    if doc.status != IssueStatus.OTWARTY:
        messages.error(request, "Pozycje można zmieniać tylko w otwartym dokumencie.")
        return redirect("issue_detail", pk=pk)
    if request.method == "POST":
        form = IssueLineForm(request.POST)
        if form.is_valid():
            IssueLine.objects.create(
                document=doc,
                material=form.cleaned_data["material"],
                requested_qty=form.cleaned_data["requested_qty"],
                specific_hu=(
                    form.cleaned_data["specific_hu"]
                    if form.cleaned_data["mode"] == IssueLineForm.MODE_HU
                    else None
                ),
            )
            messages.success(request, "Dodano pozycję.")
        else:
            for errs in form.errors.values():
                for err in errs:
                    messages.error(request, err)
    return redirect("issue_detail", pk=pk)


@operator_required
def issue_line_delete(request, pk, line_id):
    doc = get_object_or_404(IssueDocument, pk=pk)
    if doc.status != IssueStatus.OTWARTY:
        messages.error(request, "Pozycje można zmieniać tylko w otwartym dokumencie.")
        return redirect("issue_detail", pk=pk)
    if request.method == "POST":
        get_object_or_404(IssueLine, pk=line_id, document=doc).delete()
        messages.success(request, "Usunięto pozycję.")
    return redirect("issue_detail", pk=pk)


@operator_required
def issue_execute(request, pk):
    doc = get_object_or_404(IssueDocument, pk=pk)
    if request.method == "POST":
        partial = request.POST.get("partial") == "1"
        try:
            services.execute_issue_document(
                document=doc, user=request.user, allow_partial=partial
            )
        except WMSError as exc:
            messages.error(request, str(exc))
        else:
            shortage = sum(line.shortage for line in doc.lines.all())
            if shortage:
                messages.warning(
                    request,
                    f"Dokument {doc.number} zamknięty z brakami: {shortage} szt. "
                    f"niewydanych.",
                )
            else:
                messages.success(
                    request, f"Dokument {doc.number} zrealizowany — stany zdjęte."
                )
    return redirect("issue_detail", pk=pk)


@operator_required
def issue_pack(request, pk):
    doc = get_object_or_404(IssueDocument, pk=pk)
    if request.method == "POST":
        try:
            services.pack_issue_document(document=doc, user=request.user)
        except WMSError as exc:
            messages.error(request, str(exc))
        else:
            messages.success(request, f"Dokument {doc.number} spakowany.")
    return redirect("issue_detail", pk=pk)


@operator_required
def issue_ship(request, pk):
    doc = get_object_or_404(IssueDocument, pk=pk)
    if request.method == "POST":
        form = ShipForm(request.POST)
        if form.is_valid():
            try:
                services.ship_issue_document(
                    document=doc,
                    user=request.user,
                    carrier=form.cleaned_data.get("carrier", ""),
                    tracking=form.cleaned_data.get("tracking", ""),
                )
            except WMSError as exc:
                messages.error(request, str(exc))
            else:
                messages.success(request, f"Dokument {doc.number} wysłany.")
        else:
            for errs in form.errors.values():
                for err in errs:
                    messages.error(request, err)
    return redirect("issue_detail", pk=pk)


@operator_required
def issue_import(request):
    if request.method == "POST":
        form = IssueImportForm(request.POST, request.FILES)
        if form.is_valid():
            upload = form.cleaned_data["file"]
            try:
                result = import_issue_orders(
                    upload.name,
                    upload.read(),
                    request.user,
                    default_reference=form.cleaned_data.get("reference", ""),
                )
            except ImportError_ as exc:
                messages.error(request, f"Błąd importu: {exc}")
            else:
                messages.success(
                    request,
                    f"Zaimportowano {result['documents_count']} dokument(ów), "
                    f"{result['lines']} pozycji.",
                )
                for err in result["errors"][:30]:
                    messages.warning(request, err)
            return redirect("issue_list")
    else:
        form = IssueImportForm()
    return render(
        request,
        "warehouse/issue_import.html",
        {"form": form, "title": "Import zleceń wydania"},
    )


@login_required
def issue_pdf(request, pk):
    doc = get_object_or_404(IssueDocument.objects.select_related("created_by"), pk=pk)
    pdf = issue_document_pdf(doc)
    response = HttpResponse(pdf, content_type="application/pdf")
    response["Content-Disposition"] = f'inline; filename="{doc.number}.pdf"'
    return response


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
    return render(
        request,
        "warehouse/stock_by_location.html",
        {"handling_units": hus, "query": query},
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


# --- Przepakowanie (web) -----------------------------------------------------


@operator_required
def repack_view(request):
    if request.method == "POST":
        form = RepackForm(request.POST)
        if form.is_valid():
            src = HandlingUnit.objects.filter(
                number=form.cleaned_data["source_number"].strip()
            ).first()
            tgt = HandlingUnit.objects.filter(
                number=form.cleaned_data["target_number"].strip()
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
        for line in sheet.lines.all():
            raw = request.POST.get(f"counted_{line.id}", "").strip()
            if raw == "":
                new_val = None
            else:
                try:
                    new_val = max(0, int(raw))
                except ValueError:
                    continue
            if new_val != line.counted_qty:
                line.counted_qty = new_val
                line.save(update_fields=["counted_qty"])
                updated += 1
        messages.success(request, f"Zapisano ({updated} zmian).")
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
            hu = HandlingUnit.objects.filter(number=number).first()
            if hu is None:
                form.add_error("hu_number", f"Nie znaleziono HU „{number}”.")
            else:
                delta = qty if mode == InventoryForm.MODE_ADD else -qty
                new_quantity = hu.quantity + delta
                if new_quantity < 0:
                    form.add_error(
                        "quantity",
                        f"Stan nie może być ujemny (na HU jest {hu.quantity}).",
                    )
                else:
                    try:
                        services.correct_hu_quantity(
                            hu=hu,
                            new_quantity=new_quantity,
                            user=request.user,
                            note=note or "Inwentaryzacja (web)",
                            reason=form.cleaned_data.get("reason", ""),
                        )
                    except WMSError as exc:
                        messages.error(request, str(exc))
                    else:
                        sign = "+" if delta > 0 else "−"
                        messages.success(
                            request,
                            f"HU {hu.number}: {sign}{abs(delta)} → stan "
                            f"{new_quantity} {hu.material.unit.code}.",
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
    ("Edycja / usuwanie ruchów", True, False, False),
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
    paginator = Paginator(qs, 100)
    page = paginator.get_page(request.GET.get("page"))
    return render(
        request, "warehouse/login_log.html", {"events": page, "page_obj": page}
    )


@admin_required
def user_create(request):
    if request.method == "POST":
        form = UserCreateForm(request.POST)
        if form.is_valid():
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
    if is_demo_account(user):
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
                messages.error(request, "Nie możesz dezaktywować własnego konta.")
            elif editing_self and form.cleaned_data["role"] != Role.ADMIN:
                messages.error(
                    request,
                    "Nie możesz odebrać sobie roli Administratora — "
                    "poproś innego administratora.",
                )
            else:
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
    rows = []
    occupied = free_slots = empty_locs = 0
    for loc in locs:
        free = max(0, loc.capacity - loc.active)
        free_slots += free
        if loc.active > 0:
            occupied += 1
        else:
            empty_locs += 1
        rows.append({"loc": loc, "active": loc.active, "free": free})
    summary = {
        "total": len(rows),
        "occupied": occupied,
        "empty": empty_locs,
        "free_slots": free_slots,
    }
    return render(
        request,
        "warehouse/report_locations.html",
        {"rows": rows, "summary": summary},
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
