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


class TraceabilityMatrixTests(SimpleTestCase):
    """US-025: macierz SLEDZENIE.md kompletna i z istniejącymi nazwami testów."""

    DOCS = ROOT / "docs" / "analiza"

    def _matrix(self) -> str:
        text = (self.DOCS / "SLEDZENIE.md").read_text(encoding="utf-8")
        return text.split("\n## 6.", 1)[0]  # §6–§7 to opis i luki, nie macierz

    def _tests_index(self) -> tuple[dict[str, dict[str, set[str]]], set[str]]:
        """{moduł: {klasa: {metody}}} oraz wszystkie nazwy funkcji testowych."""
        import ast

        modules: dict[str, dict[str, set[str]]] = {}
        functions: set[str] = set()
        for path in sorted((ROOT / "warehouse").glob("tests*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            classes: dict[str, set[str]] = {}
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    classes[node.name] = {
                        n.name for n in node.body if isinstance(n, ast.FunctionDef)
                    }
                elif isinstance(node, ast.FunctionDef) and node.name.startswith(
                    "test_"
                ):
                    functions.add(node.name)
            modules[path.stem] = classes
        return modules, functions

    def test_every_requirement_has_a_row(self):
        import re

        wanted = set(
            re.findall(
                r"^\| \*\*((?:FR|NFR|SEC)-\d{3})\*\*|^\| ((?:FR|NFR|SEC)-\d{3}) \|",
                (self.DOCS / "WYMAGANIA.md").read_text(encoding="utf-8"),
                re.M,
            )
        )
        ids = {a or b for a, b in wanted}
        rows = set(re.findall(r"^\| ((?:FR|NFR|SEC)-\d{3}) \|", self._matrix(), re.M))
        self.assertGreater(len(ids), 50)
        self.assertEqual(sorted(ids - rows), [], "wymagania bez wiersza w SLEDZENIE.md")
        self.assertEqual(sorted(rows - ids), [], "wiersze bez wymagania w WYMAGANIA.md")

    def test_test_names_in_matrix_exist(self):
        import re

        modules, functions = self._tests_index()
        all_classes = {c: m for mod in modules.values() for c, m in mod.items()}
        missing = []
        for name in sorted(set(re.findall(r"`([A-Za-z_][\w.]*)`", self._matrix()))):
            parts = name.split(".")
            if name.endswith(".py"):
                ok = (ROOT / "warehouse" / name).exists()
            elif parts[0].startswith("tests"):
                mod = modules.get(parts[0], {})
                ok = (len(parts) == 1) or (
                    parts[1] in mod and (len(parts) == 2 or parts[2] in mod[parts[1]])
                )
            elif parts[0].endswith("Tests"):
                ok = parts[0] in all_classes and (
                    len(parts) == 1 or parts[1] in all_classes[parts[0]]
                )
            elif name.startswith("test_") and len(parts) == 1:
                ok = name in functions
            else:
                continue  # kod, ustawienie albo komenda — nie nazwa testu
            if not ok:
                missing.append(name)
        self.assertEqual(
            missing, [], "nazwy testów w SLEDZENIE.md, których nie ma w kodzie"
        )

    def test_done_stories_are_in_reverse_index(self):
        """Kryterium 2: odbiór historyjki (status „zrobione”) = wiersz §5 z numerem PR."""
        import re

        stories = (self.DOCS / "HISTORYJKI.md").read_text(encoding="utf-8")
        done = {
            us
            for us, body in re.findall(
                r"^### (US-\d{3})(.*?)(?=^### |\Z)", stories, re.M | re.S
            )
            if re.search(r"^\| Status \| zrobione", body, re.M)
        }
        index = self._matrix().split("## 5.", 1)[1]
        recorded = set(
            re.findall(r"^\| (US-\d{3}) \|[^\n]*zrobione, #\d+", index, re.M)
        )
        self.assertGreater(len(done), 10)
        self.assertEqual(
            sorted(done - recorded), [], "zrobione historyjki bez wpisu w §5"
        )
