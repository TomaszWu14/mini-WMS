"""Demo dla rekrutera: „Wejdź jako demo”, panel powitalny, limit importu, uprawnienia."""

from unittest.mock import patch

from django.conf import settings
from django.contrib.auth.models import User
from django.test import TestCase, override_settings

from .imports import ImportError_, parse_locations_file
from .models import Profile, Role


def _demo_user(username="demo_operator", role=Role.OPERATOR):
    user = User.objects.create_user(username, password=settings.DEMO_PASSWORD)
    Profile.objects.filter(user=user).update(role=role)
    return user


@override_settings(DEMO_MODE=True)
class DemoLoginTests(TestCase):
    def test_button_logs_in_as_demo_user(self):
        _demo_user()
        resp = self.client.post("/login/demo/")
        self.assertRedirects(resp, "/")
        self.assertEqual(
            int(self.client.session["_auth_user_id"]), User.objects.get().pk
        )

    def test_next_is_kept_but_external_redirect_rejected(self):
        _demo_user()
        self.assertRedirects(self.client.post("/login/demo/", {"next": "/hu/"}), "/hu/")
        self.client.logout()
        resp = self.client.post("/login/demo/", {"next": "https://evil.example/"})
        self.assertRedirects(resp, "/")

    def test_get_not_allowed(self):
        self.assertEqual(self.client.get("/login/demo/").status_code, 405)

    def test_missing_demo_account_shows_message(self):
        resp = self.client.post("/login/demo/", follow=True)
        self.assertContains(resp, "Konto demo nie jest jeszcze utworzone")
        self.assertNotIn("_auth_user_id", self.client.session)

    @override_settings(DEMO_USER="admin")
    def test_only_demo_accounts_can_be_entered(self):
        User.objects.create_superuser("admin", password="x")
        self.client.post("/login/demo/")
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_login_page_shows_button(self):
        self.assertContains(self.client.get("/login/"), "Wejdź jako demo")


class DemoLoginOffTests(TestCase):
    def test_endpoint_and_button_absent_without_demo_mode(self):
        _demo_user()
        self.assertEqual(self.client.post("/login/demo/").status_code, 404)
        self.assertNotContains(self.client.get("/login/"), "Wejdź jako demo")


@override_settings(DEMO_MODE=True)
class WelcomePanelTests(TestCase):
    def test_shown_until_dismissed(self):
        _demo_user()
        self.client.post("/login/demo/")
        self.assertContains(self.client.get("/"), "Od czego zacząć")
        self.assertRedirects(self.client.post("/powitanie/ukryj/"), "/")
        self.assertNotContains(self.client.get("/"), "Od czego zacząć")

    def test_viewer_does_not_get_scanner_step(self):
        _demo_user("demo_podglad", Role.VIEWER)
        self.client.login(username="demo_podglad", password=settings.DEMO_PASSWORD)
        resp = self.client.get("/")
        self.assertContains(resp, "Wydanie według FEFO")
        self.assertNotContains(resp, "Skaner: rozmieść paletę")

    @override_settings(DEMO_MODE=False)
    def test_hidden_outside_demo(self):
        _demo_user()
        self.client.login(username="demo_operator", password=settings.DEMO_PASSWORD)
        self.assertNotContains(self.client.get("/"), "Od czego zacząć")


class DemoImportLimitTests(TestCase):
    data = b"kod;typ\nA-1;ZAPAS\nA-2;ZAPAS\nA-3;ZAPAS\n"

    @override_settings(DEMO_MODE=True, DEMO_IMPORT_MAX_ROWS=2)
    def test_demo_rejects_files_over_limit(self):
        with self.assertRaisesMessage(ImportError_, "najwyżej 2 wierszy"):
            parse_locations_file("lok.csv", self.data)

    @override_settings(DEMO_MODE=True, DEMO_IMPORT_MAX_ROWS=2)
    def test_demo_stops_reading_after_limit(self):
        # Generator, który wybuchnie, gdyby import czytał dalej niż limit+1.
        def rows():
            yield from ({"kod": f"A-{i}"} for i in range(3))
            raise AssertionError("czytano za daleko")

        with (
            patch("warehouse.imports._rows_from_csv", return_value=rows()),
            self.assertRaises(ImportError_),
        ):
            parse_locations_file("lok.csv", b"")

    @override_settings(DEMO_MODE=False, DEMO_IMPORT_MAX_ROWS=2)
    def test_no_limit_outside_demo(self):
        self.assertEqual(len(parse_locations_file("lok.csv", self.data)), 3)


@override_settings(DEMO_MODE=True)
class DemoAccountPermissionTests(TestCase):
    def test_demo_operator_gets_403_on_admin_pages(self):
        _demo_user()
        self.client.post("/login/demo/")
        for url in ("/uzytkownicy/", "/uzytkownicy/nowy/", "/uzytkownicy/dziennik/"):
            self.assertEqual(self.client.get(url).status_code, 403, url)
