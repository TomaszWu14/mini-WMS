"""US-019: konfiguracja narzędzi CI pozostaje spójna z repozytorium."""

import pathlib
import tomllib

from django.test import SimpleTestCase

ROOT = pathlib.Path(__file__).resolve().parent.parent


class MypyConfigTests(SimpleTestCase):
    def setUp(self):
        self.config = tomllib.loads(
            (ROOT / "pyproject.toml").read_text(encoding="utf-8")
        )

    def test_untyped_bodies_checked_for_app_code(self):
        self.assertTrue(self.config["tool"]["mypy"]["check_untyped_defs"])

    def test_every_test_module_listed_in_override(self):
        """mypy nie zna wzorca `tests_*` — nowy plik testów musi trafić na listę."""
        listed = {
            m
            for o in self.config["tool"]["mypy"]["overrides"]
            if o.get("check_untyped_defs") is False
            for m in o["module"]
        }
        on_disk = {
            f"warehouse.{p.stem}" for p in (ROOT / "warehouse").glob("tests*.py")
        }
        self.assertEqual(on_disk - listed, set())

    def test_coverage_threshold(self):
        self.assertGreaterEqual(
            self.config["tool"]["coverage"]["report"]["fail_under"], 80
        )
