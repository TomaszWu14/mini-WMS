"""US-017: migawka tras — podział `views.py` na moduły nie zmienia nazw, adresów ani widoków.

Wygenerowana z URLconf przed podziałem (poza `DEMO_MODE`, bez tras samego panelu admina).
Nowa trasa = dopisz ją tutaj i w macierzy dostępu (`tests_access_matrix.py`).
"""

from django.test import SimpleTestCase
from django.urls import URLPattern, URLResolver, get_resolver

EXPECTED = {
    "admin_login_guard": ("admin/login/", "admin_login"),
    "dashboard": ("", "dashboard"),
    "demo_login": ("login/demo/", "demo_login"),
    "demo_start": ("demo/", "demo_start"),
    "healthz": ("healthz", "healthz"),
    "hu_allocate": ("hu/<int:pk>/alokacja/", "hu_allocate"),
    "hu_correct": ("hu/<int:pk>/korekta/", "hu_correct"),
    "hu_delivery": ("hu/<int:pk>/dostawa/", "hu_delivery"),
    "hu_detail": ("hu/<int:pk>/", "hu_detail"),
    "hu_label": ("hu/<int:pk>/etykieta/", "hu_label"),
    "hu_labels": ("hu/etykiety/", "hu_labels"),
    "hu_list": ("hu/", "hu_list"),
    "inventory": ("inwentaryzacja/", "inventory_view"),
    "issue_add_line": ("wydania/<int:pk>/pozycja/", "issue_add_line"),
    "issue_create": ("wydania/nowy/", "issue_create"),
    "issue_detail": ("wydania/<int:pk>/", "issue_detail"),
    "issue_execute": ("wydania/<int:pk>/realizuj/", "issue_execute"),
    "issue_import": ("wydania/import/", "issue_import"),
    "issue_line_delete": (
        "wydania/<int:pk>/pozycja/<int:line_id>/usun/",
        "issue_line_delete",
    ),
    "issue_list": ("wydania/", "issue_list"),
    "issue_pack": ("wydania/<int:pk>/spakuj/", "issue_pack"),
    "issue_pdf": ("wydania/<int:pk>/pdf/", "issue_pdf"),
    "issue_ship": ("wydania/<int:pk>/wyslij/", "issue_ship"),
    "location_create": ("lokalizacje/nowa/", "location_create"),
    "location_import": ("lokalizacje/import/", "location_import"),
    "location_label": ("lokalizacje/<int:pk>/etykieta/", "location_label"),
    "location_labels": ("lokalizacje/etykiety/", "location_labels"),
    "location_list": ("lokalizacje/", "location_list"),
    "login": ("login/", "LoginView"),
    "login_log": ("uzytkownicy/dziennik/", "login_log"),
    "logout": ("logout/", "LogoutView"),
    "material_create": ("materialy/nowy/", "material_create"),
    "material_list": ("materialy/", "material_list"),
    "movement_export": ("ruchy/eksport/<str:fmt>/", "movement_export"),
    "movement_list": ("ruchy/", "movement_list"),
    "receive": ("przyjecie/", "receive"),
    "receive_import": ("przyjecie/import/", "receive_import"),
    "repack": ("przepakowanie/", "repack_view"),
    "report_index": ("raporty/", "report_index"),
    "report_locations": ("raporty/lokalizacje/", "report_locations"),
    "report_material": ("raporty/material/", "report_material_history"),
    "scanner_api_allocate": ("skaner/api/rozmiesc/", "api_allocate"),
    "scanner_api_document": ("skaner/api/zlecenie/", "api_document"),
    "scanner_api_hu": ("skaner/api/hu/", "api_hu"),
    "scanner_api_inventory": ("skaner/api/inwentaryzacja/", "api_inventory"),
    "scanner_api_location": ("skaner/api/lokalizacja/", "api_location"),
    "scanner_api_location_contents": (
        "skaner/api/lokalizacja-zawartosc/",
        "api_location_contents",
    ),
    "scanner_api_pick": ("skaner/api/pick/", "api_pick"),
    "scanner_api_repack": ("skaner/api/przepakuj/", "api_repack"),
    "scanner_home": ("skaner/", "scanner_home"),
    "scanner_info": ("skaner/podglad/", "scanner_info"),
    "scanner_inventory": ("skaner/inwentaryzacja/", "scanner_inventory"),
    "scanner_locinfo": ("skaner/lokalizacja/", "scanner_locinfo"),
    "scanner_picking": ("skaner/picking/", "scanner_picking"),
    "scanner_picking_doc": ("skaner/picking/<int:pk>/", "scanner_picking_doc"),
    "scanner_putaway": ("skaner/rozmieszczanie/", "scanner_putaway"),
    "scanner_repack": ("skaner/przepakowanie/", "scanner_repack"),
    "stock_by_location": ("stany/lokalizacje/", "stock_by_location"),
    "stock_export": ("stany/eksport/<str:fmt>/", "stock_export"),
    "stock_import": ("stany/import/", "stock_import_view"),
    "stock_list": ("stany/", "stock_list"),
    "stocktake_close": ("spis/<int:pk>/zamknij/", "stocktake_close"),
    "stocktake_create": ("spis/nowy/", "stocktake_create"),
    "stocktake_detail": ("spis/<int:pk>/", "stocktake_detail"),
    "stocktake_list": ("spis/", "stocktake_list"),
    "stocktake_save": ("spis/<int:pk>/zapisz/", "stocktake_save"),
    "two_factor_setup": ("2fa/", "two_factor_setup"),
    "two_factor_verify": ("2fa/weryfikacja/", "two_factor_verify"),
    "user_create": ("uzytkownicy/nowy/", "user_create"),
    "user_edit": ("uzytkownicy/<int:pk>/", "user_edit"),
    "user_list": ("uzytkownicy/", "user_list"),
    "welcome_dismiss": ("powitanie/ukryj/", "welcome_dismiss"),
}


def _routes(patterns, prefix=""):
    for p in patterns:
        if isinstance(p, URLResolver):
            if getattr(p, "namespace", None) == "admin":
                continue
            yield from _routes(p.url_patterns, prefix + str(p.pattern))
        elif isinstance(p, URLPattern) and p.name:
            cb = p.callback
            view_class = getattr(cb, "view_class", None)
            yield (
                p.name,
                (
                    prefix + str(p.pattern),
                    view_class.__name__ if view_class else cb.__name__,
                ),
            )


class UrlSnapshotTests(SimpleTestCase):
    def test_url_names_unchanged(self):
        self.assertEqual(dict(_routes(get_resolver().url_patterns)), EXPECTED)
