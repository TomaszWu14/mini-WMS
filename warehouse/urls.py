"""Trasy URL aplikacji magazynowej."""

from django.urls import path

from . import scanner_views, views

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    # Skaner (kolektor / telefon)
    path("skaner/", scanner_views.scanner_home, name="scanner_home"),
    path(
        "skaner/rozmieszczanie/", scanner_views.scanner_putaway, name="scanner_putaway"
    ),
    path("skaner/picking/", scanner_views.scanner_picking, name="scanner_picking"),
    path(
        "skaner/picking/<int:pk>/",
        scanner_views.scanner_picking_doc,
        name="scanner_picking_doc",
    ),
    path(
        "skaner/inwentaryzacja/",
        scanner_views.scanner_inventory,
        name="scanner_inventory",
    ),
    path("skaner/przepakowanie/", scanner_views.scanner_repack, name="scanner_repack"),
    path("skaner/podglad/", scanner_views.scanner_info, name="scanner_info"),
    path("skaner/lokalizacja/", scanner_views.scanner_locinfo, name="scanner_locinfo"),
    path("skaner/api/hu/", scanner_views.api_hu, name="scanner_api_hu"),
    path(
        "skaner/api/lokalizacja/",
        scanner_views.api_location,
        name="scanner_api_location",
    ),
    path(
        "skaner/api/zlecenie/", scanner_views.api_document, name="scanner_api_document"
    ),
    path(
        "skaner/api/rozmiesc/", scanner_views.api_allocate, name="scanner_api_allocate"
    ),
    path("skaner/api/pick/", scanner_views.api_pick, name="scanner_api_pick"),
    path(
        "skaner/api/inwentaryzacja/",
        scanner_views.api_inventory,
        name="scanner_api_inventory",
    ),
    path("skaner/api/przepakuj/", scanner_views.api_repack, name="scanner_api_repack"),
    path(
        "skaner/api/lokalizacja-zawartosc/",
        scanner_views.api_location_contents,
        name="scanner_api_location_contents",
    ),
    # Materiały
    path("materialy/", views.material_list, name="material_list"),
    path("materialy/nowy/", views.material_create, name="material_create"),
    # Lokalizacje
    path("lokalizacje/", views.location_list, name="location_list"),
    path("lokalizacje/nowa/", views.location_create, name="location_create"),
    path("lokalizacje/import/", views.location_import, name="location_import"),
    path("lokalizacje/etykiety/", views.location_labels, name="location_labels"),
    path("lokalizacje/<int:pk>/etykieta/", views.location_label, name="location_label"),
    # Przyjęcie
    path("przyjecie/", views.receive, name="receive"),
    path("przyjecie/import/", views.receive_import, name="receive_import"),
    # Raporty
    path("raporty/", views.report_index, name="report_index"),
    path("raporty/lokalizacje/", views.report_locations, name="report_locations"),
    path("raporty/material/", views.report_material_history, name="report_material"),
    # HU
    path("hu/", views.hu_list, name="hu_list"),
    path("hu/etykiety/", views.hu_labels, name="hu_labels"),
    path("hu/<int:pk>/", views.hu_detail, name="hu_detail"),
    path("hu/<int:pk>/etykieta/", views.hu_label, name="hu_label"),
    path("hu/<int:pk>/alokacja/", views.hu_allocate, name="hu_allocate"),
    path("hu/<int:pk>/korekta/", views.hu_correct, name="hu_correct"),
    path("hu/<int:pk>/dostawa/", views.hu_delivery, name="hu_delivery"),
    # Wydania / picking
    path("wydania/", views.issue_list, name="issue_list"),
    path("wydania/nowy/", views.issue_create, name="issue_create"),
    path("wydania/import/", views.issue_import, name="issue_import"),
    path("wydania/<int:pk>/", views.issue_detail, name="issue_detail"),
    path("wydania/<int:pk>/pozycja/", views.issue_add_line, name="issue_add_line"),
    path(
        "wydania/<int:pk>/pozycja/<int:line_id>/usun/",
        views.issue_line_delete,
        name="issue_line_delete",
    ),
    path("wydania/<int:pk>/realizuj/", views.issue_execute, name="issue_execute"),
    path("wydania/<int:pk>/spakuj/", views.issue_pack, name="issue_pack"),
    path("wydania/<int:pk>/wyslij/", views.issue_ship, name="issue_ship"),
    path("wydania/<int:pk>/pdf/", views.issue_pdf, name="issue_pdf"),
    # Inwentaryzacja (web)
    path("inwentaryzacja/", views.inventory_view, name="inventory"),
    # Przepakowanie (web)
    path("przepakowanie/", views.repack_view, name="repack"),
    # Spis z natury
    path("spis/", views.stocktake_list, name="stocktake_list"),
    path("spis/nowy/", views.stocktake_create, name="stocktake_create"),
    path("spis/<int:pk>/", views.stocktake_detail, name="stocktake_detail"),
    path("spis/<int:pk>/zapisz/", views.stocktake_save, name="stocktake_save"),
    path("spis/<int:pk>/zamknij/", views.stocktake_close, name="stocktake_close"),
    # Stany
    path("stany/", views.stock_list, name="stock_list"),
    path("stany/lokalizacje/", views.stock_by_location, name="stock_by_location"),
    path("stany/import/", views.stock_import_view, name="stock_import"),
    path("stany/eksport/<str:fmt>/", views.stock_export, name="stock_export"),
    # Ruchy
    path("ruchy/", views.movement_list, name="movement_list"),
    path("ruchy/eksport/<str:fmt>/", views.movement_export, name="movement_export"),
    # Użytkownicy (Admin)
    path("uzytkownicy/", views.user_list, name="user_list"),
    path("uzytkownicy/dziennik/", views.login_log, name="login_log"),
    path("uzytkownicy/nowy/", views.user_create, name="user_create"),
    path("uzytkownicy/<int:pk>/", views.user_edit, name="user_edit"),
]
