"""US-003 / R2: produkcja nie startuje ze słabym kluczem; seed_demo tylko w trybie demo.

Ustawienia produkcyjne wybiera `DJANGO_DEBUG=0` przy imporcie `config.settings`, więc
każdy wariant sprawdzamy w osobnym procesie z podstawionym środowiskiem.
"""

import os
import secrets
import subprocess
import sys
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.management import CommandError, call_command
from django.test import SimpleTestCase, TestCase, override_settings

ROOT = Path(__file__).resolve().parents[1]
GOOD_KEY = secrets.token_urlsafe(48)[:50]  # losowy, dokładnie 50 znaków


def _load_prod(secret_key):
    env = {
        k: v
        for k, v in os.environ.items()
        if not k.startswith("DJANGO_") and k != "DATABASE_URL"
    }
    env.update(
        DJANGO_DEBUG="0",
        DJANGO_ALLOWED_HOSTS="miniwms.example.com",
        DJANGO_SETTINGS_MODULE="config.settings",
    )
    if secret_key is not None:
        env["DJANGO_SECRET_KEY"] = secret_key
    code = "import django; django.setup(); from django.conf import settings; print('DEBUG', settings.DEBUG)"
    return subprocess.run(
        [sys.executable, "-c", code],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )


class ProdSecretKeyTests(SimpleTestCase):
    def assert_refused(self, key):
        r = _load_prod(key)
        self.assertNotEqual(r.returncode, 0, f"klucz przyjęty: {key!r}")
        self.assertIn("ImproperlyConfigured", r.stderr)
        self.assertIn("DJANGO_SECRET_KEY", r.stderr)

    def test_missing_key_refused(self):
        self.assert_refused(None)

    def test_compose_default_refused(self):
        self.assert_refused("zmien-mnie-w-produkcji")

    def test_env_example_placeholder_refused(self):
        self.assert_refused("YOUR_DJANGO_SECRET_KEY_HERE")

    def test_django_insecure_prefix_refused(self):
        self.assert_refused("django-insecure-" + GOOD_KEY)

    def test_short_key_refused(self):
        self.assert_refused(GOOD_KEY[:49])

    def test_low_entropy_key_refused(self):
        self.assert_refused("ab" * 30)

    def test_strong_key_accepted(self):
        r = _load_prod(GOOD_KEY)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("DEBUG False", r.stdout)


class SeedDemoModeTests(TestCase):
    @override_settings(DEMO_MODE=False)
    def test_seed_refused_without_demo_mode(self):
        with self.assertRaisesMessage(CommandError, "DEMO_MODE=1"):
            call_command("seed_demo", stdout=StringIO())
        self.assertFalse(
            User.objects.filter(username__in=["demo_operator", "demo_podglad"]).exists()
        )

    @override_settings(DEMO_MODE=True)
    def test_seed_works_in_demo_mode(self):
        call_command("seed_demo", stdout=StringIO())
        self.assertTrue(User.objects.filter(username="demo_operator").exists())


class ComposeSecretsTests(SimpleTestCase):
    """Wariant prywatny compose wymaga sekretów (`${VAR:?…}`), bez wartości domyślnych."""

    def test_private_compose_requires_secrets(self):
        text = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
        for var in (
            "DJANGO_SECRET_KEY",
            "DJANGO_SUPERUSER_PASSWORD",
            "POSTGRES_PASSWORD",
        ):
            self.assertIn("${" + var + ":?", text, var)
            self.assertNotIn("${" + var + ":-", text, var)


def _entrypoint_superuser_snippet():
    """Drugi blok `<<'PY'` z entrypoint.sh — tworzenie superusera z env."""
    text = (ROOT / "entrypoint.sh").read_text(encoding="utf-8")
    blocks = text.split("<<'PY'\n")
    return blocks[2].split("\nPY\n")[0]


class EntrypointSuperuserPasswordTests(TestCase):
    """US-003 / RR-02: entrypoint nie zakłada superusera ze słabym hasłem."""

    def _run(self, password):
        # exec wyłącznie kodu z entrypoint.sh w repo (nie danych z zewnątrz).
        env = {
            "DJANGO_SUPERUSER_USERNAME": "boot_admin",
            "DJANGO_SUPERUSER_PASSWORD": password,
        }
        with patch.dict(os.environ, env):
            exec(_entrypoint_superuser_snippet(), {})  # noqa: S102  # nosec B102  # nosemgrep

    def test_weak_or_placeholder_password_stops_start(self):
        for pw in ("admin", "YOUR_DJANGO_SUPERUSER_PASSWORD_HERE", "12345678"):
            with self.subTest(pw=pw), self.assertRaises(SystemExit) as cm:
                self._run(pw)
            self.assertIn("DJANGO_SUPERUSER_PASSWORD", str(cm.exception))
        self.assertFalse(User.objects.filter(username="boot_admin").exists())

    def test_strong_password_creates_superuser(self):
        with redirect_stdout(StringIO()):
            self._run("Mocne-Haslo-Startowe-2026")
        self.assertTrue(User.objects.get(username="boot_admin").is_superuser)
