#!/usr/bin/env python3
"""Stop hook: ruff + mypy na zmienionych plikach, potem pytest -x -q.

Zmienione = `git diff main...HEAD` + niezacommitowane + nowe nieśledzone.
Błąd → exit 2 i ostatnie ~60 linii wyniku na stderr (Claude kontynuuje i naprawia).
stop_hook_active=true → exit 0 (ochrona przed pętlą).
Pełne testy trwają ~11 s (MD5 hasher w config.settings.test), więc bez selekcji.
Tylko stdlib; narzędzia z .venv projektu.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(os.environ.get("CLAUDE_PROJECT_DIR") or Path(__file__).resolve().parents[2])
TAIL = 60
# mypy tylko na kodzie aplikacji (jak w pyproject: bez migracji i settings).
MYPY_DIRS = ("warehouse/", "config/")
MYPY_SKIP = ("warehouse/migrations/", "config/settings/")


def git(*args: str) -> list[str]:
    r = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True)
    return r.stdout.split() if r.returncode == 0 else []


def changed_files() -> list[str]:
    base = next(
        (b for b in ("main", "origin/main") if git("rev-parse", "--verify", "-q", b)),
        None,
    )
    files = set(git("diff", "--name-only", f"{base}...HEAD")) if base else set()
    files |= set(git("diff", "--name-only", "HEAD"))
    files |= set(git("ls-files", "--others", "--exclude-standard"))
    return sorted(f for f in files if (ROOT / f).exists())


def venv_python() -> str:
    for p in (ROOT / ".venv/Scripts/python.exe", ROOT / ".venv/bin/python"):
        if p.exists():
            return str(p)
    return sys.executable


def run(label: str, cmd: list[str]) -> str | None:
    r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    if r.returncode == 0:
        return None
    return f"=== {label} (exit {r.returncode}) ===\n{r.stdout}{r.stderr}"


def main() -> int:
    try:
        event = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        event = {}
    if event.get("stop_hook_active"):
        return 0

    files = changed_files()
    if not files or all(f.endswith(".md") for f in files):
        return 0

    py = venv_python()
    py_files = [f for f in files if f.endswith(".py")]
    typed = [
        f for f in py_files if f.startswith(MYPY_DIRS) and not f.startswith(MYPY_SKIP)
    ]

    failure = None
    if py_files:
        failure = run("ruff", [py, "-m", "ruff", "check", "--force-exclude", *py_files])
    if not failure and typed:
        failure = run("mypy", [py, "-m", "mypy", *typed])
    if not failure:
        failure = run("pytest", [py, "-m", "pytest", "-x", "-q", "-p", "no:warnings"])

    if failure:
        lines = failure.strip().splitlines()
        print(
            "[check] Sprawdzenia nie przeszły — popraw przed zakończeniem:\n"
            + "\n".join(lines[-TAIL:]),
            file=sys.stderr,
        )
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
