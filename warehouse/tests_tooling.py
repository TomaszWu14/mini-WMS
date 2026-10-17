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


class SupplyChainTests(SimpleTestCase):
    """US-020: locki z hashami z jednego źródła, obrazy przypięte digestem."""

    LOCKS = (
        "requirements.txt",
        "requirements-dev.txt",
        "requirements-mutation.txt",
        "requirements-semgrep.txt",
    )

    @staticmethod
    def _pins(path):
        pins = {}
        for line in (ROOT / path).read_text(encoding="utf-8").splitlines():
            line = line.split("#", 1)[0].strip()
            if "==" in line and not line.startswith("-"):
                name, version = line.rstrip(" \\").split("==", 1)
                pins[name.split("[")[0].strip().lower().replace("_", "-")] = (
                    version.strip()
                )
        return pins

    def test_every_locked_package_has_hashes(self):
        for lock in self.LOCKS:
            with self.subTest(lock=lock):
                text = (ROOT / lock).read_text(encoding="utf-8")
                self.assertIn(
                    "pip-compile", text.splitlines()[1] + text.splitlines()[4]
                )
                entries = [
                    ln
                    for ln in text.splitlines()
                    if "==" in ln and not ln.startswith("#")
                ]
                self.assertTrue(entries)
                for entry in entries:
                    self.assertTrue(
                        entry.rstrip().endswith("\\"), entry
                    )  # po nim linie --hash

    def test_direct_pins_match_lock(self):
        """Ręczna zmiana w .in bez przegenerowania locka → czerwony test."""
        for source, lock in (
            ("requirements.in", "requirements.txt"),
            ("requirements-dev.in", "requirements-dev.txt"),
            ("requirements-mutation.in", "requirements-mutation.txt"),
            ("requirements-semgrep.in", "requirements-semgrep.txt"),
        ):
            locked = self._pins(lock)
            for name, version in self._pins(source).items():
                with self.subTest(source=source, package=name):
                    self.assertEqual(locked.get(name), version)

    def test_pyproject_reads_single_source(self):
        config = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
        self.assertEqual(config["project"]["dynamic"], ["dependencies"])
        self.assertNotIn("dependencies", config["project"])
        self.assertEqual(
            config["tool"]["setuptools"]["dynamic"]["dependencies"]["file"],
            ["requirements.in"],
        )

    def test_images_pinned_by_digest(self):
        files = [
            "Dockerfile",
            "docker/backup.Dockerfile",
            *(p.name for p in ROOT.glob("docker-compose*.yml")),
        ]
        for name in files:
            text = (ROOT / name).read_text(encoding="utf-8")
            refs = [
                ln.split()[1]
                if ln.startswith("FROM")
                else ln.split("image:", 1)[1].strip()
                for ln in (raw.strip() for raw in text.splitlines())
                if ln.startswith("FROM ") or ln.startswith("image:")
            ]
            for ref in refs:
                if "${" in ref:  # obraz budowany lokalnie (np. miniwms-web:${TAG})
                    continue
                with self.subTest(file=name, image=ref):
                    self.assertRegex(ref, r"@sha256:[0-9a-f]{64}$")

    def test_ci_and_scripts_use_digests_and_locks(self):
        """Przegląd [SEC] US-020: obrazy i instalacje w CI oraz skryptach też przypięte."""
        import re

        paths = [*ROOT.glob(".github/workflows/*.yml"), *ROOT.glob("scripts/*.sh")]
        image = re.compile(
            r"\b(?:python|postgres|caddy):[\w.-]+(?:@sha256:[0-9a-f]{64})?"
        )
        for path in paths:
            text = path.read_text(encoding="utf-8")
            for ref in image.findall(text):
                with self.subTest(file=path.name, image=ref):
                    self.assertIn("@sha256:", ref)
            for line in text.splitlines():
                if re.search(r"\bpip\"? install\b", line) and "-r requirements" in line:
                    with self.subTest(file=path.name, line=line.strip()):
                        self.assertIn("--require-" + "hashes", line)

    def test_dockerfile_installs_only_from_lock(self):
        text = (ROOT / "Dockerfile").read_text(encoding="utf-8")
        self.assertIn("--require-hashes", text)
        self.assertNotIn("--upgrade pip", text)
