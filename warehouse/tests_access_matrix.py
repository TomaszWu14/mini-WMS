"""US-007 / SEC-008: macierz dostępu rola × trasa (AUDYT, Załącznik A).

Każda nazwana trasa aplikacji musi mieć wpis w `MATRIX` z rolą minimalną.
Nowa trasa bez wpisu = czerwony test z nazwą trasy (pitfalls/auth #1: widok
bez dekoratora jest publiczny). Dla każdej roli i metody GET / POST:

* rola poniżej minimum → 302 na `/login/` (anonim), 403 albo 405 (zła metoda
  przed sprawdzeniem roli) — nigdy 200 ani 5xx;
* rola spełniająca minimum → nie 403 i nie 5xx (404 dla nieistniejącego `pk`,
  405 dla złej metody i 400/200 z błędem formularza są w porządku).
"""

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import URLPattern, URLResolver, get_resolver, reverse

from .models import Profile, Role

# Rola minimalna: publiczne, zalogowany (każda rola), Operator, Administrator.
PUBLIC, LOGGED_IN, OPERATOR, ADMIN = "P", "L", "O", "A"
LEVEL = {PUBLIC: 0, LOGGED_IN: 1, OPERATOR: 2, ADMIN: 3}

MATRIX = {
    # publiczne
    "healthz": PUBLIC,
    "login": PUBLIC,
    "logout": PUBLIC,
    "admin_login_guard": PUBLIC,  # /admin/login/ z limitem (US-009)
    "demo_login": PUBLIC,  # tylko DEMO_MODE (inaczej 404)
    "demo_start": PUBLIC,  # tylko DEMO_MODE (inaczej 404)
    # każdy zalogowany (także Podgląd)
    "dashboard": LOGGED_IN,
    "welcome_dismiss": LOGGED_IN,
    "material_list": LOGGED_IN,
    "location_list": LOGGED_IN,
    "location_labels": LOGGED_IN,
    "location_label": LOGGED_IN,
    "report_index": LOGGED_IN,
    "report_locations": LOGGED_IN,
    "report_material": LOGGED_IN,
    "hu_list": LOGGED_IN,
    "hu_labels": LOGGED_IN,
    "hu_detail": LOGGED_IN,
    "hu_label": LOGGED_IN,
    "issue_list": LOGGED_IN,
    "issue_detail": LOGGED_IN,
    "issue_pdf": LOGGED_IN,
    "stocktake_list": LOGGED_IN,
    "stocktake_detail": LOGGED_IN,
    "stock_list": LOGGED_IN,
    "stock_by_location": LOGGED_IN,
    "stock_export": LOGGED_IN,
    "movement_list": LOGGED_IN,
    "movement_export": LOGGED_IN,
    # Operator i Administrator
    "scanner_home": OPERATOR,
    "scanner_putaway": OPERATOR,
    "scanner_picking": OPERATOR,
    "scanner_picking_doc": OPERATOR,
    "scanner_inventory": OPERATOR,
    "scanner_repack": OPERATOR,
    "scanner_info": OPERATOR,
    "scanner_locinfo": OPERATOR,
    "scanner_api_hu": OPERATOR,
    "scanner_api_location": OPERATOR,
    "scanner_api_document": OPERATOR,
    "scanner_api_allocate": OPERATOR,
    "scanner_api_pick": OPERATOR,
    "scanner_api_inventory": OPERATOR,
    "scanner_api_repack": OPERATOR,
    "scanner_api_location_contents": OPERATOR,
    "material_create": OPERATOR,
    "location_create": OPERATOR,
    "location_import": OPERATOR,
    "receive": OPERATOR,
    "receive_import": OPERATOR,
    "hu_allocate": OPERATOR,
    "hu_correct": OPERATOR,
    "issue_create": OPERATOR,
    "issue_import": OPERATOR,
    "issue_add_line": OPERATOR,
    "issue_line_delete": OPERATOR,
    "issue_execute": OPERATOR,
    "issue_pack": OPERATOR,
    "issue_ship": OPERATOR,
    "inventory": OPERATOR,
    "repack": OPERATOR,
    "stocktake_create": OPERATOR,
    "stocktake_save": OPERATOR,
    "stocktake_close": OPERATOR,
    "stock_import": OPERATOR,
    # tylko Administrator
    "hu_delivery": ADMIN,
    "user_list": ADMIN,
    "login_log": ADMIN,
    "user_create": ADMIN,
    "user_edit": ADMIN,
    "two_factor_setup": ADMIN,
    # drugi krok logowania (US-010) — każdy zalogowany; bez urządzenia przekierowuje
    "two_factor_verify": LOGGED_IN,
}

# Nieistniejące obiekty: kontrola roli działa przed pobraniem obiektu, a dla roli
# z dostępem widok zwraca 404 — nic się nie zmienia w bazie.
KWARGS = {"pk": 999_999, "line_id": 999_999, "fmt": "csv"}


def _named_routes():
    """(nazwa, wzorzec) wszystkich tras aplikacji; panel /admin/ osobno."""

    def walk(patterns, namespace=None):
        for p in patterns:
            if isinstance(p, URLResolver):
                yield from walk(p.url_patterns, p.namespace or namespace)
            elif isinstance(p, URLPattern) and namespace is None:
                yield p.name, p

    return list(walk(get_resolver().url_patterns))


def _url(name, pattern):
    kwargs = {k: v for k, v in KWARGS.items() if k in pattern.pattern.converters}
    return reverse(name, kwargs=kwargs)


class _MatrixBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.users = {}
        for role, username in (
            (Role.VIEWER, "m_viewer"),
            (Role.OPERATOR, "m_operator"),
            (Role.ADMIN, "m_admin"),
        ):
            user = User.objects.create_user(username, password="MatrixPass123!")
            Profile.objects.filter(user=user).update(role=role)
            cls.users[role] = user

    def setUp(self):
        cache.clear()  # limit prób logowania / wejść demo

    ROLES = (
        (None, 0),
        (Role.VIEWER, 1),
        (Role.OPERATOR, 2),
        (Role.ADMIN, 3),
    )

    def _client_for(self, role):
        self.client.logout()
        if role is not None:
            self.client.force_login(self.users[role])
        return self.client

    def _check_route(self, name, pattern, minimum):
        url = _url(name, pattern)
        for role, level in self.ROLES:
            for method in ("get", "post"):
                with self.subTest(route=name, role=role or "anonim", method=method):
                    resp = getattr(self._client_for(role), method)(url)
                    status = resp.status_code
                    self.assertLess(status, 500, f"{name}: 5xx")
                    if level >= LEVEL[minimum]:
                        self.assertNotEqual(status, 403, f"{name}: brak dostępu")
                    elif role is None:
                        self.assertIn(
                            status, (302, 405), f"{name}: anonim dostał {status}"
                        )
                        if status == 302:
                            self.assertTrue(
                                resp["Location"].startswith(reverse("login")),
                                f"{name}: przekierowanie poza logowanie",
                            )
                    else:
                        self.assertIn(
                            status, (403, 405), f"{name}: {role} dostał {status}"
                        )


class AccessMatrixTests(_MatrixBase):
    def test_every_route_has_matrix_entry(self):
        """Kryterium 3: nowa trasa bez wpisu w macierzy → czerwony test z nazwą."""
        names = {name for name, _ in _named_routes()}
        missing = sorted(n or "<bez nazwy>" for n in names - MATRIX.keys())
        self.assertEqual(missing, [], f"Trasy bez wpisu w MATRIX: {missing}")
        stale = sorted(MATRIX.keys() - names)
        self.assertEqual(stale, [], f"Wpisy MATRIX bez trasy: {stale}")

    def test_role_matrix(self):
        """Kryteria 1 i 2 (DEMO_MODE wyłączony — trasy demo dają 404)."""
        for name, pattern in _named_routes():
            self._check_route(name, pattern, MATRIX[name])


@override_settings(DEMO_MODE=True)
class DemoAccessMatrixTests(_MatrixBase):
    """Trasy demo przy DEMO_MODE: reset danych nie jest dostępny z UI (US-016, DEC-6)."""

    def test_demo_reset_route_removed(self):
        self.assertNotIn("demo_reset", dict(_named_routes()))
        for role, _ in self.ROLES:
            with self.subTest(role=role or "anonim"):
                resp = self._client_for(role).post("/demo/przywroc/")
                self.assertEqual(resp.status_code, 404)


class AdminSiteAccessTests(_MatrixBase):
    """Panel /admin/ (poza DEMO_MODE) — tylko konta `is_staff`, żadna rola aplikacji."""

    def test_app_roles_cannot_enter_admin(self):
        url = reverse("admin:index")
        for role, _ in self.ROLES:
            with self.subTest(role=role or "anonim"):
                resp = self._client_for(role).get(url)
                self.assertEqual(resp.status_code, 302)
                self.assertTrue(resp["Location"].startswith(reverse("admin:login")))

    def test_superuser_enters_admin(self):
        root = User.objects.create_superuser("m_root", password="RootPass123!")
        self.client.force_login(root)
        self.assertEqual(self.client.get(reverse("admin:index")).status_code, 200)
