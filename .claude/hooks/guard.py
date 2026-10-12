#!/usr/bin/env python3
"""PreToolUse guard: blokuje groźne komendy i zapisy (exit 2 + powód na stderr).

Wejście: JSON hooka na stdin ({tool_name, tool_input, cwd, ...}).
Tylko stdlib. Błędny JSON → przepuszczamy (fail-open), żeby nie zablokować sesji.
Testy: .claude/hooks/test_hooks.py (pytest .claude/hooks).
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import PurePath

SHELL_TOOLS = {"Bash", "PowerShell"}
WRITE_TOOLS = {"Write", "Edit", "MultiEdit", "NotebookEdit"}

# --- 1. rm -r poza katalogami tymczasowymi -----------------------------------
RM_RE = re.compile(r"(?:^|[\s;&|(])rm\s+((?:-[A-Za-z]+\s+|--[a-z-]+\s+)*)([^;&|]*)")
PS_RM_RE = re.compile(
    r"(?:Remove-Item|\brm\b|\bri\b|\bdel\b|\brmdir\b)[^;|]*-Recurse([^;|]*)", re.I
)
TEMP_MARKERS = (
    "/tmp/",
    "\\temp\\",
    "/temp/",
    "$tmpdir",
    "$env:temp",
    "%temp%",
    "scratchpad",
)
# Katalogi cache/artefaktów narzędzi — bezpieczne do usuwania.
CACHE_NAMES = {
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "mutants",
    ".mutmut-cache",
    "htmlcov",
    "staticfiles",
}

# --- 2. git -------------------------------------------------------------------
FORCE_PUSH_RE = re.compile(r"\bgit\s+push\b[^;&|]*\s(?:--force\S*|-f\b|\+\S+)")
RESET_HARD_RE = re.compile(r"\bgit\s+reset\b[^;&|]*--hard")
PROTECTED = {"main", "master"}

# --- 3. SQL -------------------------------------------------------------------
DROP_RE = re.compile(
    r"\bDROP\s+(?:TABLE|DATABASE|SCHEMA|INDEX|VIEW|SEQUENCE|COLUMN|CONSTRAINT|"
    r"TRIGGER|FUNCTION|ROLE|USER|OWNED|EXTENSION|TYPE)\b",
    re.I,
)
TRUNCATE_RE = re.compile(r"\bTRUNCATE\s+(?:TABLE\s+)?\w", re.I)
DELETE_RE = re.compile(r"\bDELETE\s+FROM\s+[\w.\"`]+", re.I)
UPDATE_RE = re.compile(r"\bUPDATE\s+[\w.\"`]+\s+SET\b", re.I)

# --- 4. sekrety -----------------------------------------------------------------
SECRET_NAME_RE = re.compile(
    r"^(?:\.env(?:\..+)?|.*\.(?:pem|key|p12|pfx|jks|keystore)|id_(?:rsa|ed25519|ecdsa)"
    r"(?:\.pub)?|\.netrc|\.pgpass|credentials(?:\..+)?|secrets?\.(?:json|ya?ml|toml|txt))$",
    re.I,
)
SECRET_ALLOWED_RE = re.compile(r"\.(?:example|sample|template)$", re.I)
SHELL_WRITE_ENV_RE = re.compile(
    r"(?:>>?|\btee\s+(?:-a\s+)?|\bsed\s+-i\S*\s+.*?|\b(?:cp|mv)\s+\S+\s+|"
    r"Set-Content\s+(?:-Path\s+)?|Add-Content\s+(?:-Path\s+)?|Out-File\s+(?:-FilePath\s+)?)"
    r"\s*[\"']?([^\s\"';&|]*\.env(?:\.[\w.-]+)?)\b",
    re.I,
)

# --- 5. produkcja ---------------------------------------------------------------
LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1", "db", ""}
DEPLOY_RES = [
    # Tylko faktyczne wywołania (HTTP do panelu/API albo CLI `coolify`) — samo słowo
    # w nazwie pliku (COOLIFY.md) czy w grepie dokumentacji nie jest deployem.
    (
        re.compile(
            r"https?://[^\s'\"/]*coolify[^\s'\"/]*"  # URL z hostem panelu Coolify
            r"|(?:^|[;&|(])\s*coolify\s",  # CLI `coolify …` na pozycji polecenia
            re.I,
        ),
        "wywołanie Coolify (deploy produkcyjny)",
    ),
    (re.compile(r"/api/v1/deploy|[?&]uuid=.*force=", re.I), "webhook deployu Coolify"),
    (
        re.compile(r"(?:^|[\s;&|(])(?:ssh|scp|rsync)\s"),
        "połączenie z serwerem (ssh/scp/rsync)",
    ),
    (
        re.compile(r"docker[\s-]compose\b[^;&|]*coolify", re.I),
        "docker compose wariantu produkcyjnego",
    ),
    (
        re.compile(r"DOCKER_HOST\s*=\s*\S*ssh://|docker\s+(?:-H|--host)\s", re.I),
        "zdalny Docker (produkcja)",
    ),
    (re.compile(r"\bgh\s+pr\s+merge\b"), "merge do main = auto-deploy na produkcję"),
]
PUSH_RE = re.compile(r"\bgit\s+push\b([^;&|]*)")
PG_URL_RE = re.compile(r"postgres(?:ql)?://[^@\s]*@([^:/\s]+)", re.I)
PG_HOST_RE = re.compile(
    r"\b(?:psql|pg_dump|pg_dumpall|pg_restore)\b[^;&|]*?(?:-h\s*|--host[=\s])([^\s;&|]+)"
)


def _current_branch(cwd: str | None) -> str:
    try:
        out = subprocess.run(
            ["git", "symbolic-ref", "--short", "HEAD"],
            cwd=cwd or None,
            capture_output=True,
            text=True,
            timeout=5,
        )
        return out.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return ""


def _is_temp_or_cache(target: str) -> bool:
    t = target.strip("\"'").replace("\\", "/").lower()
    if any(m.replace("\\", "/") in t + "/" for m in TEMP_MARKERS):
        return True
    if "/appdata/local/temp/" in t + "/" or t.startswith(
        ("/tmp", "$tmpdir", "${tmpdir")
    ):
        return True
    return PurePath(t.rstrip("/")).name in CACHE_NAMES


def check_rm(cmd: str) -> str | None:
    for m in RM_RE.finditer(cmd):
        flags, rest = m.group(1), m.group(2)
        if not re.search(r"(?:^|\s)-[A-Za-z]*[rR]|--recursive", flags):
            continue
        targets = [t for t in rest.split() if not t.startswith("-")]
        bad = [t for t in targets if not _is_temp_or_cache(t)]
        if not targets or bad:
            return f"rm -r poza katalogiem tymczasowym: {' '.join(bad) or '?'}"
    for m in PS_RM_RE.finditer(cmd):
        if not _is_temp_or_cache(m.group(0)):
            return "Remove-Item -Recurse poza katalogiem tymczasowym"
    return None


def check_git(cmd: str, cwd: str | None) -> str | None:
    if FORCE_PUSH_RE.search(cmd):
        return "git push --force/-f jest zablokowany"
    if RESET_HARD_RE.search(cmd) and _current_branch(cwd) in PROTECTED:
        return "git reset --hard na gałęzi main jest zablokowany"
    return None


def check_sql(text: str) -> str | None:
    if DROP_RE.search(text):
        return "SQL DROP jest zablokowany"
    if TRUNCATE_RE.search(text):
        return "SQL TRUNCATE jest zablokowany"
    for stmt in re.split(r";", text):
        if (DELETE_RE.search(stmt) or UPDATE_RE.search(stmt)) and not re.search(
            r"\bWHERE\b", stmt, re.I
        ):
            return "SQL DELETE/UPDATE bez WHERE jest zablokowany"
    return None


def check_secret_path(path: str) -> str | None:
    name = PurePath(path.replace("\\", "/")).name
    if SECRET_NAME_RE.match(name) and not SECRET_ALLOWED_RE.search(name):
        return f"zapis do pliku z sekretami ({name}) jest zablokowany — edytuj ręcznie"
    return None


def check_prod(cmd: str, cwd: str | None) -> str | None:
    for rx, why in DEPLOY_RES:
        if rx.search(cmd):
            return f"{why} — wykonaj ręcznie"
    for m in PUSH_RE.finditer(cmd):
        args = m.group(1).split()
        refs = [a.split(":")[-1] for a in args if not a.startswith("-")][1:]
        if any(r in PROTECTED for r in refs) or (
            not refs and _current_branch(cwd) in PROTECTED
        ):
            return "git push na main = auto-deploy na produkcję — wykonaj ręcznie"
    for rx in (PG_URL_RE, PG_HOST_RE):
        for m in rx.finditer(cmd):
            if m.group(1).lower() not in LOCAL_HOSTS:
                return f"połączenie z bazą na hoście {m.group(1)} (produkcja?) — wykonaj ręcznie"
    return None


def evaluate(event: dict) -> str | None:
    tool = event.get("tool_name", "")
    inp = event.get("tool_input") or {}
    cwd = event.get("cwd")
    if tool in SHELL_TOOLS:
        cmd = inp.get("command", "")
        m = SHELL_WRITE_ENV_RE.search(cmd)
        env_hit = check_secret_path(m.group(1)) if m else None
        return (
            check_rm(cmd)
            or check_git(cmd, cwd)
            or check_sql(cmd)
            or env_hit
            or check_prod(cmd, cwd)
        )
    if tool in WRITE_TOOLS:
        path = inp.get("file_path") or inp.get("notebook_path") or ""
        reason = check_secret_path(path)
        if reason:
            return reason
        if path.lower().endswith(".sql"):
            return check_sql(inp.get("content") or inp.get("new_string") or "")
    return None


def main() -> int:
    try:
        event = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0
    reason = evaluate(event)
    if reason:
        print(f"[guard] ZABLOKOWANO: {reason}.", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
