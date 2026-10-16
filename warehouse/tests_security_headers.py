"""US-011 / SEC-022, SEC-024, SEC-025: CSP z nonce, Permissions-Policy, HSTS."""

import os
import re
import secrets
import subprocess
import sys
from pathlib import Path

from django.contrib.auth.models import User
from django.test import SimpleTestCase, TestCase, override_settings

from .models import Profile, Role

ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = ROOT / "warehouse" / "templates"

SCRIPT_TAG = re.compile(r"<script\b([^>]*)>", re.IGNORECASE)
EVENT_ATTR = re.compile(r"""\son[a-z]+\s*=\s*["']""", re.IGNORECASE)


def _csp(resp):
    return resp.get("Content-Security-Policy", "")


def _script_src(policy):
    return next(d for d in policy.split(";") if d.strip().startswith("script-src"))


class TemplateScanTests(SimpleTestCase):
    """Kryterium 2: w szablonach brak `on*=`, `javascript:` i skryptów inline bez nonce."""

    def _templates(self):
        return sorted(TEMPLATES.rglob("*.html"))

    def test_no_inline_event_handlers(self):
        offenders = [
            f"{p.relative_to(ROOT)}:{n}"
            for p in self._templates()
            for n, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1)
            if EVENT_ATTR.search(line) or "javascript:" in line
        ]
        self.assertEqual(offenders, [])

    def test_inline_scripts_have_nonce(self):
        offenders = []
        for p in self._templates():
            for attrs in SCRIPT_TAG.findall(p.read_text(encoding="utf-8")):
                if "src=" not in attrs and 'nonce="{{ csp_nonce }}"' not in attrs:
                    offenders.append(str(p.relative_to(ROOT)))
        self.assertEqual(offenders, [])


class SecurityHeadersTests(TestCase):
    """Kryteria 1 i 4 na odpowiedziach aplikacji (ten sam middleware w dev i prod)."""

    PAGES = (
        "/",
        "/stany/",
        "/ruchy/",
        "/przyjecie/",
        "/spis/",
        "/skaner/",
        "/skaner/rozmieszczanie/",
        "/skaner/inwentaryzacja/",
        "/uzytkownicy/",
    )

    def setUp(self):
        user = User.objects.create_user("adm", password="AdmPass123!")
        Profile.objects.filter(user=user).update(role=Role.ADMIN)
        self.client.force_login(user)

    def test_csp_with_nonce_and_no_unsafe_inline_scripts(self):
        for url in self.PAGES:
            with self.subTest(url=url):
                resp = self.client.get(url)
                self.assertEqual(resp.status_code, 200)
                script_src = _script_src(_csp(resp))
                self.assertIn("'nonce-", script_src)
                self.assertNotIn("unsafe-inline", script_src)
                self.assertNotIn("unsafe-eval", script_src)

    def test_every_inline_script_carries_response_nonce(self):
        for url in self.PAGES:
            with self.subTest(url=url):
                resp = self.client.get(url)
                nonce = re.search(r"'nonce-([^']+)'", _csp(resp)).group(1)
                html = resp.content.decode()
                for attrs in SCRIPT_TAG.findall(html):
                    if "src=" not in attrs:
                        self.assertIn(f'nonce="{nonce}"', attrs, url)
                self.assertIsNone(EVENT_ATTR.search(html), url)

    def test_nonce_differs_per_request(self):
        first = _csp(self.client.get("/"))
        second = _csp(self.client.get("/"))
        self.assertNotEqual(first, second)

    def test_policy_restricts_framing_and_objects(self):
        policy = _csp(self.client.get("/"))
        for directive in (
            "frame-ancestors 'none'",
            "object-src 'none'",
            "base-uri 'self'",
        ):
            self.assertIn(directive, policy)

    def test_permissions_policy(self):
        """Kryterium 4: kamera tylko dla własnej domeny (skaner), bez geolokalizacji."""
        resp = self.client.get("/skaner/")
        policy = resp["Permissions-Policy"]
        self.assertIn("camera=(self)", policy)
        self.assertIn("geolocation=()", policy)

    def test_json_api_without_csp(self):
        resp = self.client.get("/skaner/api/hu/", {"code": "X"})
        self.assertNotIn("Content-Security-Policy", resp)

    @override_settings(CSP_REPORT_ONLY=True)
    def test_report_only_switch(self):
        resp = self.client.get("/")
        self.assertNotIn("Content-Security-Policy", resp)
        self.assertIn("'nonce-", resp["Content-Security-Policy-Report-Only"])

    def test_admin_site_pages_have_no_unnonced_inline_scripts(self):
        root = User.objects.create_superuser("root", password="RootPass123!")
        self.client.force_login(root)
        for url in (
            "/admin/",
            "/admin/warehouse/material/",
            "/admin/warehouse/material/add/",
        ):
            with self.subTest(url=url):
                html = self.client.get(url).content.decode()
                inline = [a for a in SCRIPT_TAG.findall(html) if "src=" not in a]
                # Django admin trzyma dane w <script type="application/json"> — nie wykonuje się.
                executable = [a for a in inline if "application/json" not in a]
                self.assertEqual(executable, [], url)
                self.assertIsNone(EVENT_ATTR.search(html), url)


class HstsSettingsTests(SimpleTestCase):
    """Kryterium 5: HSTS ≥ 1 rok albo bez `preload` (ustawienia produkcyjne)."""

    def test_prod_hsts(self):
        env = {k: v for k, v in os.environ.items() if not k.startswith("DJANGO_")}
        env.update(
            DJANGO_DEBUG="0",
            DJANGO_SECRET_KEY=secrets.token_urlsafe(48),
            DJANGO_ALLOWED_HOSTS="miniwms.example.com",
            DJANGO_SETTINGS_MODULE="config.settings",
        )
        env.pop("DATABASE_URL", None)
        code = (
            "import django; django.setup(); from django.conf import settings as s; "
            "print(s.SECURE_HSTS_SECONDS, s.SECURE_HSTS_PRELOAD, s.CSP_REPORT_ONLY)"
        )
        out = subprocess.run(
            [sys.executable, "-c", code],
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
            timeout=60,
        )
        self.assertEqual(out.returncode, 0, out.stderr)
        seconds, preload, report_only = out.stdout.split()
        self.assertTrue(int(seconds) >= 31_536_000 or preload == "False")
        self.assertEqual(report_only, "False")
