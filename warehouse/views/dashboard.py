"""Pulpit i jego wykresy."""

from datetime import timedelta

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q, Sum
from django.db.models.functions import TruncDate
from django.shortcuts import render
from django.urls import reverse
from django.utils import timezone

from ..models import (
    HandlingUnit,
    HUStatus,
    IssueDocument,
    IssueLine,
    IssueStatus,
    Location,
    Material,
    StockMovement,
    StocktakeSheet,
    StocktakeStatus,
)

# --- Dashboard ---------------------------------------------------------------


@login_required
def dashboard(request):
    today = timezone.localdate()
    show_welcome = settings.DEMO_MODE and not request.session.get("welcome_dismissed")
    active_hus = HandlingUnit.objects.exclude(status=HUStatus.PUSTY)
    context = {
        "show_welcome": show_welcome,
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
        "location_heat": _location_heat(),
        "movement_days": _movement_days(today),
        "issue_progress": _issue_progress(today),
        "today_plan": _today_plan(),
    }
    if context["location_count"]:
        context["occupancy_pct"] = round(
            100 * context["occupied_locations"] / context["location_count"]
        )
    return render(request, "warehouse/dashboard.html", context)


HEAT_CELLS_MAX = 240


def _heat_level(occupied, capacity):
    """Poziom wypełnienia lokalizacji 0–4 (0 = pusta, 4 = pełna)."""
    if not occupied:
        return 0
    if not capacity:  # 0 = bez limitu — tylko „zajęta”
        return 2
    ratio = occupied / capacity
    if ratio >= 1:
        return 4
    if ratio > 2 / 3:
        return 3
    if ratio > 1 / 3:
        return 2
    return 1


def _location_heat():
    """Komórki mapy obłożenia: kod, poziom 0–4 i opis do podpowiedzi."""
    locations = Location.objects.annotate(
        occupied=Count(
            "handling_units",
            filter=Q(handling_units__quantity__gt=0)
            & ~Q(handling_units__status=HUStatus.PUSTY),
        )
    ).order_by("code")[:HEAT_CELLS_MAX]
    cells = []
    for loc in locations:
        limit = loc.capacity if loc.capacity else "∞"
        cells.append(
            {
                "code": loc.code,
                "level": _heat_level(loc.occupied, loc.capacity),
                "title": f"{loc.code}: {loc.occupied}/{limit} HU",
            }
        )
    return cells


def _issue_progress(today):
    """Realizacja wydań w toku: dokumenty niewysłane oraz wysłane dzisiaj.

    `pct` to udział pobranych sztuk w żądanych (nadwyżki pozycji nie liczą się
    ponad 100%), `lines_done` — pozycje pobrane w całości.
    """
    docs = IssueDocument.objects.filter(
        ~Q(status=IssueStatus.WYSLANY) | Q(shipped_at__date=today)
    )
    lines = IssueLine.objects.filter(document__in=docs).values_list(
        "requested_qty", "picked_qty"
    )
    requested = picked = lines_done = 0
    for req, got in lines:
        requested += req
        picked += min(req, got)
        lines_done += got >= req
    doc_count = docs.count()
    if not doc_count:
        return None
    return {
        "pct": round(100 * picked / requested) if requested else 0,
        "lines_done": lines_done,
        "lines_total": len(lines),
        "packed": docs.filter(
            status__in=[IssueStatus.SPAKOWANY, IssueStatus.WYSLANY]
        ).count(),
        "docs": doc_count,
        "shipped_today": docs.filter(status=IssueStatus.WYSLANY).count(),
    }


PLAN_MAX_ITEMS = 6

# Kolejność kroków na hali: najpierw picking, potem pakowanie i wysyłka.
_PLAN_STEPS = [
    (IssueStatus.OTWARTY, "Wydanie · picking", "pick"),
    (IssueStatus.ZREALIZOWANY, "Wydanie · pakowanie", "pack"),
    (IssueStatus.SPAKOWANY, "Wydanie · wysyłka", "ship"),
]


def _today_plan():
    """Kolejka zadań na dziś wyliczona ze stanów dokumentów i palet."""
    items = []
    hu_waiting = HandlingUnit.objects.filter(status=HUStatus.DO_ULOZENIA)
    hu_count = hu_waiting.count()
    oldest = hu_waiting.order_by("created_at").first() if hu_count else None
    if oldest is not None:  # paleta mogła zostać ułożona między count() a first()
        items.append(
            {
                "kind": "alert",
                "tag": "Rozmieszczenie",
                "title": f"{hu_count} HU do ułożenia",
                "meta": f"najstarsza: {oldest.number}",
                "time": timezone.localtime(oldest.created_at),
                "url": reverse("hu_list") + f"?status={HUStatus.DO_ULOZENIA}",
            }
        )
    for status, tag, kind in _PLAN_STEPS:
        docs = (
            IssueDocument.objects.filter(status=status)
            .annotate(line_count=Count("lines"))
            .order_by("created_at")
        )
        for doc in docs[:PLAN_MAX_ITEMS]:
            items.append(
                {
                    "kind": kind,
                    "tag": tag,
                    "title": f"{doc.number}"
                    + (f" — {doc.reference}" if doc.reference else ""),
                    "meta": f"{doc.line_count} poz.",
                    "time": timezone.localtime(doc.created_at),
                    "url": reverse("issue_detail", args=[doc.pk]),
                }
            )
    for sheet in StocktakeSheet.objects.filter(
        status=StocktakeStatus.OTWARTY
    ).select_related("location")[:PLAN_MAX_ITEMS]:
        scope = sheet.location.code if sheet.location else "cały magazyn"
        items.append(
            {
                "kind": "count",
                "tag": "Spis z natury",
                "title": f"{sheet.number} — {scope}",
                "meta": "arkusz otwarty",
                "time": timezone.localtime(sheet.created_at),
                "url": reverse("stocktake_detail", args=[sheet.pk]),
            }
        )
    return items[:PLAN_MAX_ITEMS]


def _movement_days(today, days=14):
    """Liczba ruchów dziennie z ostatnich `days` dni (z dniem dzisiejszym)."""
    start = today - timedelta(days=days - 1)
    counts = dict(
        StockMovement.objects.filter(created_at__date__gte=start)
        .annotate(day=TruncDate("created_at"))
        .values_list("day")
        .annotate(n=Count("id"))
    )
    peak = max(counts.values(), default=0) or 1
    result = []
    for offset in range(days):
        day = start + timedelta(days=offset)
        n = counts.get(day, 0)
        result.append(
            {
                "day": day,
                "count": n,
                "pct": round(100 * n / peak),
                "is_today": day == today,
            }
        )
    return result
