"""Wydania (WZ): dokumenty, pozycje, import zleceń, kompletacja, wysyłka."""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Sum
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.http import content_disposition_header

from .. import services
from ..documents import issue_document_pdf
from ..forms import (
    IssueDocumentForm,
    IssueImportForm,
    IssueLineForm,
    ShipForm,
)
from ..imports import ImportError_
from ..issue_import import import_issue_orders
from ..models import (
    IssueDocument,
    IssueLine,
    IssueStatus,
)
from ..roles import operator_required
from ..services import WMSError

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
            # Atrybut tylko dla szablonu (nie pole modelu).
            if line.specific_hu_id or line.outstanding <= 0:
                line.suggestion = None  # type: ignore[attr-defined]
            else:
                line.suggestion = services.picking_plan(  # type: ignore[attr-defined]
                    line.material, line.outstanding
                )
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
            qty = form.cleaned_data["requested_qty"]
            hu = (
                form.cleaned_data["specific_hu"]
                if form.cleaned_data["mode"] == IssueLineForm.MODE_HU
                else None
            )
            if hu is not None:
                already = (
                    doc.lines.filter(specific_hu=hu).aggregate(s=Sum("requested_qty"))[
                        "s"
                    ]
                    or 0
                )
                if already + qty > hu.quantity:
                    messages.error(
                        request,
                        f"HU {hu.number} ma tylko {hu.quantity} szt., a pozycje "
                        f"dokumentu wskazują już {already}.",
                    )
                    return redirect("issue_detail", pk=pk)
            IssueLine.objects.create(
                document=doc,
                material=form.cleaned_data["material"],
                requested_qty=qty,
                specific_hu=hu,
            )
            messages.success(request, "Dodano pozycję.")
        else:
            for errs in form.errors.values():
                for err in errs:
                    messages.error(request, str(err))
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
                    messages.error(request, str(err))
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
    response["Content-Disposition"] = (
        content_disposition_header(False, f"{doc.number}.pdf") or "inline"
    )
    return response
