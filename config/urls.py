"""Główna konfiguracja URL projektu mini-WMS."""

from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.db import connection
from django.http import JsonResponse
from django.urls import include, path

from warehouse.demo import LoginView

admin.site.site_header = "mini-WMS — administracja"
admin.site.site_title = "mini-WMS"
admin.site.index_title = "Zarządzanie magazynem"


def healthz(request):
    """Lekki healthcheck (bez logowania): sprawdza połączenie z bazą."""
    try:
        with connection.cursor() as cur:
            cur.execute("SELECT 1")
        db_ok = True
    except Exception:
        db_ok = False
    return JsonResponse(
        {"status": "ok" if db_ok else "degraded", "db": db_ok},
        status=200 if db_ok else 503,
    )


urlpatterns = [
    path("healthz", healthz, name="healthz"),
    path("admin/", admin.site.urls),
    path("login/", LoginView.as_view(), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("", include("warehouse.urls")),
]
