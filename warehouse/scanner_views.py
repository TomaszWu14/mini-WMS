"""Widok skanerowy (kolektor / telefon) — rozmieszczanie, picking, inwentaryzacja.

Lekki interfejs webowy: pełnoekranowe ekrany prowadzące krok po kroku,
obsługa skanera jako klawiatury (kod + Enter), JSON API dla akcji.
"""

from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from . import services
from .models import (
    HandlingUnit,
    HUStatus,
    IssueDocument,
    IssueStatus,
    Location,
)
from .roles import operator_required
from .services import WMSError


def _hu_payload(hu: HandlingUnit) -> dict:
    return {
        "number": hu.number,
        "material_index": hu.material.index,
        "material_name": hu.material.name,
        "quantity": hu.quantity,
        "unit": hu.material.unit.code,
        "status": hu.status,
        "status_label": hu.get_status_display(),
        "lot": hu.lot,
        "location": hu.location.code if hu.location else None,
    }


def _location_payload(loc: Location) -> dict:
    return {
        "code": loc.code,
        "type": loc.type,
        "type_label": loc.get_type_display(),
        "occupancy": loc.occupancy,
        "capacity": loc.capacity,
    }


def _doc_lines(doc: IssueDocument):
    lines = []
    for line in doc.lines.select_related("material", "material__unit").all():
        remaining = max(0, line.requested_qty - line.picked_qty)
        lines.append(
            {
                "id": line.id,
                "material_index": line.material.index,
                "material_name": line.material.name,
                "unit": line.material.unit.code,
                "requested": line.requested_qty,
                "picked": line.picked_qty,
                "remaining": remaining,
            }
        )
    return lines


def _doc_payload(doc: IssueDocument) -> dict:
    lines = _doc_lines(doc)
    return {
        "id": doc.id,
        "number": doc.number,
        "reference": doc.reference,
        "status": doc.status,
        "lines": lines,
        "remaining_total": sum(ln["remaining"] for ln in lines),
        "completed": doc.status == IssueStatus.ZREALIZOWANY,
    }


# --- Ekrany -----------------------------------------------------------------


@operator_required
def scanner_home(request):
    return render(request, "warehouse/scanner/home.html")


@operator_required
def scanner_putaway(request):
    return render(request, "warehouse/scanner/putaway.html")


@operator_required
def scanner_picking(request):
    """Lista otwartych zleceń do skompletowania."""
    docs = []
    for doc in (
        IssueDocument.objects.filter(status=IssueStatus.OTWARTY)
        .prefetch_related("lines")
        .order_by("created_at")
    ):
        remaining = sum(
            max(0, ln.requested_qty - ln.picked_qty) for ln in doc.lines.all()
        )
        docs.append(
            {
                "id": doc.id,
                "number": doc.number,
                "reference": doc.reference,
                "lines": doc.lines.count(),
                "remaining": remaining,
            }
        )
    return render(request, "warehouse/scanner/picking_list.html", {"docs": docs})


@operator_required
def scanner_picking_doc(request, pk):
    doc = get_object_or_404(IssueDocument, pk=pk)
    return render(request, "warehouse/scanner/picking_doc.html", {"doc": doc})


@operator_required
def scanner_inventory(request):
    return render(request, "warehouse/scanner/inventory.html")


@operator_required
def scanner_repack(request):
    return render(request, "warehouse/scanner/repack.html")


@operator_required
def scanner_info(request):
    return render(request, "warehouse/scanner/info.html")


@operator_required
def scanner_locinfo(request):
    return render(request, "warehouse/scanner/locinfo.html")


# --- JSON API ---------------------------------------------------------------


@operator_required
@require_GET
def api_hu(request):
    code = (request.GET.get("code") or "").strip()
    if not code:
        return JsonResponse({"ok": False, "error": "Pusty kod."}, status=400)
    hu = (
        HandlingUnit.objects.select_related("material", "location", "material__unit")
        .filter(number=code)
        .first()
    )
    if hu is None:
        return JsonResponse(
            {"ok": False, "error": f"Nie znaleziono HU „{code}”."}, status=404
        )
    return JsonResponse({"ok": True, "hu": _hu_payload(hu)})


@operator_required
@require_GET
def api_location(request):
    code = (request.GET.get("code") or "").strip()
    if not code:
        return JsonResponse({"ok": False, "error": "Pusty kod."}, status=400)
    loc = Location.objects.filter(code=code).first()
    if loc is None:
        return JsonResponse(
            {"ok": False, "error": f"Nie znaleziono lokalizacji „{code}”."},
            status=404,
        )
    return JsonResponse({"ok": True, "location": _location_payload(loc)})


@operator_required
@require_GET
def api_location_contents(request):
    """Zwraca listę palet (HU) w danej lokalizacji — „co tu leży”."""
    code = (request.GET.get("code") or "").strip()
    if not code:
        return JsonResponse({"ok": False, "error": "Pusty kod."}, status=400)
    loc = Location.objects.filter(code=code).first()
    if loc is None:
        return JsonResponse(
            {"ok": False, "error": f"Nie znaleziono lokalizacji „{code}”."},
            status=404,
        )
    hus = (
        loc.handling_units.exclude(status=HUStatus.PUSTY)
        .select_related("material", "material__unit")
        .order_by("material__index", "number")
    )
    items = [
        {
            "number": hu.number,
            "material_index": hu.material.index,
            "material_name": hu.material.name,
            "quantity": hu.quantity,
            "unit": hu.material.unit.code,
            "status": hu.status,
        }
        for hu in hus
    ]
    return JsonResponse({"ok": True, "location": _location_payload(loc), "hus": items})


@operator_required
@require_GET
def api_document(request):
    """Szczegóły zlecenia (po id lub numerze) — do odświeżenia ekranu."""
    doc_id = (request.GET.get("id") or "").strip()
    number = (request.GET.get("number") or "").strip()
    doc = None
    if doc_id.isdigit():
        doc = IssueDocument.objects.filter(pk=doc_id).first()
    elif number:
        doc = IssueDocument.objects.filter(number=number).first()
    if doc is None:
        return JsonResponse(
            {"ok": False, "error": "Nie znaleziono zlecenia."}, status=404
        )
    return JsonResponse({"ok": True, "document": _doc_payload(doc)})


@operator_required
@require_POST
def api_allocate(request):
    hu_code = (request.POST.get("hu") or "").strip()
    loc_code = (request.POST.get("location") or "").strip()
    hu = HandlingUnit.objects.filter(number=hu_code).first()
    loc = Location.objects.filter(code=loc_code).first()
    if hu is None:
        return JsonResponse({"ok": False, "error": "Nieznany HU."}, status=404)
    if loc is None:
        return JsonResponse({"ok": False, "error": "Nieznana lokalizacja."}, status=404)
    try:
        services.allocate_hu(hu=hu, location=loc, user=request.user)
    except WMSError as exc:
        return JsonResponse({"ok": False, "error": str(exc)}, status=400)
    return JsonResponse(
        {
            "ok": True,
            "message": f"HU {hu.number} → {loc.code}",
            "hu": _hu_payload(
                HandlingUnit.objects.select_related(
                    "material", "location", "material__unit"
                ).get(pk=hu.pk)
            ),
        }
    )


@operator_required
@require_POST
def api_pick(request):
    hu_code = (request.POST.get("hu") or "").strip()
    qty_raw = (request.POST.get("quantity") or "").strip()
    doc_id = (request.POST.get("document") or "").strip()

    hu = HandlingUnit.objects.filter(number=hu_code).first()
    if hu is None:
        return JsonResponse({"ok": False, "error": "Nieznany HU."}, status=404)
    try:
        quantity = int(qty_raw)
    except ValueError:
        return JsonResponse({"ok": False, "error": "Niepoprawna ilość."}, status=400)

    doc = None
    line = None
    if doc_id:
        doc = (
            IssueDocument.objects.filter(pk=doc_id, status=IssueStatus.OTWARTY).first()
            if doc_id.isdigit()
            else None
        )
        if doc is None:
            return JsonResponse(
                {"ok": False, "error": "Zlecenie zamknięte lub nieznane."},
                status=404,
            )
        line = next(
            (
                ln
                for ln in doc.lines.filter(material=hu.material)
                if ln.requested_qty - ln.picked_qty > 0
            ),
            None,
        )
        if line is None:
            return JsonResponse(
                {
                    "ok": False,
                    "error": f"Materiał {hu.material.index} nie jest na tym "
                    f"zleceniu albo już skompletowany.",
                },
                status=400,
            )
        remaining = line.requested_qty - line.picked_qty
        if quantity > remaining:
            return JsonResponse(
                {"ok": False, "error": f"Na zleceniu pozostało {remaining}."},
                status=400,
            )

    try:
        services.pick_from_hu(
            hu=hu, quantity=quantity, user=request.user, document=doc, line=line
        )
    except WMSError as exc:
        return JsonResponse({"ok": False, "error": str(exc)}, status=400)

    response = {
        "ok": True,
        "message": f"Wydano {quantity} z HU {hu.number}",
        "hu": _hu_payload(
            HandlingUnit.objects.select_related(
                "material", "location", "material__unit"
            ).get(pk=hu.pk)
        ),
    }
    if doc is not None:
        doc.refresh_from_db()
        payload = _doc_payload(doc)
        if payload["remaining_total"] == 0 and doc.status == IssueStatus.OTWARTY:
            doc.status = IssueStatus.ZREALIZOWANY
            doc.completed_at = timezone.now()
            doc.save(update_fields=["status", "completed_at"])
            payload = _doc_payload(doc)
        response["document"] = payload
    return JsonResponse(response)


@operator_required
@require_POST
def api_repack(request):
    """Przepakowanie/łączenie ilości z HU źródłowego na docelowy (ten sam towar)."""
    source_code = (request.POST.get("source") or "").strip()
    target_code = (request.POST.get("target") or "").strip()
    qty_raw = (request.POST.get("quantity") or "").strip()

    source = HandlingUnit.objects.filter(number=source_code).first()
    target = HandlingUnit.objects.filter(number=target_code).first()
    if source is None:
        return JsonResponse({"ok": False, "error": "Nieznany HU źródłowy."}, status=404)
    if target is None:
        return JsonResponse({"ok": False, "error": "Nieznany HU docelowy."}, status=404)
    try:
        quantity = int(qty_raw)
    except ValueError:
        return JsonResponse({"ok": False, "error": "Niepoprawna ilość."}, status=400)
    try:
        services.repack_hu(
            source=source, target=target, quantity=quantity, user=request.user
        )
    except WMSError as exc:
        return JsonResponse({"ok": False, "error": str(exc)}, status=400)

    src = HandlingUnit.objects.select_related(
        "material", "location", "material__unit"
    ).get(pk=source.pk)
    tgt = HandlingUnit.objects.select_related(
        "material", "location", "material__unit"
    ).get(pk=target.pk)
    return JsonResponse(
        {
            "ok": True,
            "message": f"Przepakowano {quantity} z {src.number} → {tgt.number}",
            "source": _hu_payload(src),
            "target": _hu_payload(tgt),
        }
    )


@operator_required
@require_POST
def api_inventory(request):
    """Inwentaryzacja — dodanie/odjęcie ilości na HU (ruch korekty)."""
    hu_code = (request.POST.get("hu") or "").strip()
    delta_raw = (request.POST.get("delta") or "").strip()

    hu = HandlingUnit.objects.filter(number=hu_code).first()
    if hu is None:
        return JsonResponse({"ok": False, "error": "Nieznany HU."}, status=404)
    try:
        delta = int(delta_raw)
    except ValueError:
        return JsonResponse({"ok": False, "error": "Niepoprawna ilość."}, status=400)
    if delta == 0:
        return JsonResponse({"ok": False, "error": "Podaj ilość."}, status=400)

    new_quantity = hu.quantity + delta
    if new_quantity < 0:
        return JsonResponse(
            {
                "ok": False,
                "error": f"Nie można zejść poniżej zera (stan {hu.quantity}).",
            },
            status=400,
        )
    try:
        services.correct_hu_quantity(
            hu=hu,
            new_quantity=new_quantity,
            user=request.user,
            note="Inwentaryzacja (skaner)",
        )
    except WMSError as exc:
        return JsonResponse({"ok": False, "error": str(exc)}, status=400)

    updated = HandlingUnit.objects.select_related(
        "material", "location", "material__unit"
    ).get(pk=hu.pk)
    sign = "+" if delta > 0 else "−"
    return JsonResponse(
        {
            "ok": True,
            "message": f"{sign}{abs(delta)} → HU {hu.number}: {updated.quantity} {updated.material.unit.code}",
            "hu": _hu_payload(updated),
        }
    )
