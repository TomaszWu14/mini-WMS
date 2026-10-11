"""Testy hooków: JSON na stdin → kod wyjścia. Uruchom: pytest .claude/hooks -q"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

GUARD = Path(__file__).with_name("guard.py")


def run_guard(event: dict) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(GUARD)],
        input=json.dumps(event),
        capture_output=True,
        text=True,
    )


def bash(cmd: str) -> dict:
    return {"tool_name": "Bash", "tool_input": {"command": cmd}, "cwd": "."}


BLOCKED = [
    # 1. rm -r poza tmp
    ("rm", bash("rm -rf warehouse")),
    ("rm", bash("rm -r ./config")),
    ("rm", bash("cd x && rm -fr /")),
    (
        "rm",
        {
            "tool_name": "PowerShell",
            "tool_input": {"command": "Remove-Item -Recurse -Force warehouse"},
        },
    ),
    # 2. git
    ("git", bash("git push --force origin feat")),
    ("git", bash("git push -f")),
    ("git", bash("git push --force-with-lease origin x")),
    # 3. SQL
    ("sql", bash('psql -c "DROP TABLE warehouse_material"')),
    ("sql", bash("sqlite3 db.sqlite3 'TRUNCATE warehouse_stockmovement'")),
    ("sql", bash("sqlite3 db.sqlite3 'DELETE FROM warehouse_handlingunit'")),
    ("sql", bash('sqlite3 db.sqlite3 "UPDATE warehouse_handlingunit SET quantity=0"')),
    (
        "sql",
        {
            "tool_name": "Write",
            "tool_input": {"file_path": "x.sql", "content": "delete from t;"},
        },
    ),
    # 4. sekrety
    (
        "env",
        {
            "tool_name": "Write",
            "tool_input": {"file_path": "C:\\repo\\.env", "content": "X=1"},
        },
    ),
    (
        "env",
        {
            "tool_name": "Edit",
            "tool_input": {
                "file_path": "/repo/.env.production",
                "old_string": "a",
                "new_string": "b",
            },
        },
    ),
    (
        "env",
        {
            "tool_name": "Write",
            "tool_input": {"file_path": "/repo/deploy/server.pem", "content": "x"},
        },
    ),
    ("env", bash("echo SECRET=1 >> .env")),
    ("env", bash("sed -i 's/a/b/' .env.docker")),
    # 5. produkcja
    (
        "prod",
        bash(
            "curl -X GET 'https://coolify.example.com/api/v1/deploy?uuid=abc&force=false'"
        ),
    ),
    ("prod", bash("curl -s https://coolify.twapp.pl/api/v1/applications")),
    ("prod", bash("coolify deploy --uuid abc")),
    ("prod", bash("ssh root@204.0.0.1 docker ps")),
    ("prod", bash("docker compose -f docker-compose.coolify.yml up -d")),
    ("prod", bash("git push origin main")),
    ("prod", bash("git push origin HEAD:main")),
    ("prod", bash("gh pr merge 5 --squash")),
    ("prod", bash("psql -h db.prod.example.com -U wms")),
    (
        "prod",
        bash(
            "DATABASE_URL=postgres://wms:pw@10.0.0.5:5432/wms python manage.py migrate"
        ),
    ),
]

ALLOWED = [
    bash("rm -rf /tmp/build"),
    bash("rm -rf $TMPDIR/x"),
    bash("rm -rf warehouse/__pycache__"),
    bash("rm -r C:/Users/t/AppData/Local/Temp/claude/x"),
    bash("rm warehouse/old.py"),
    bash("git push -u origin chore/claude-harness"),
    bash("git reset --soft HEAD~1"),
    bash("git commit -m 'drop unused import'"),
    bash("sqlite3 db.sqlite3 'DELETE FROM t WHERE id=1'"),
    bash("sqlite3 db.sqlite3 'UPDATE t SET a=1 WHERE id=2'"),
    bash("psql -h localhost -U wms"),
    bash("DATABASE_URL=postgres://wms:pw@localhost:5432/wms python manage.py test"),
    bash("python manage.py runserver 8001"),
    bash("grep -n '^## ' COOLIFY.md"),
    bash("git add COOLIFY.md README.md"),
    bash('gh pr create --body "see https://example.com — Coolify notes"'),
    {
        "tool_name": "Write",
        "tool_input": {"file_path": "/repo/.env.example", "content": "X="},
    },
    {
        "tool_name": "Edit",
        "tool_input": {
            "file_path": "/repo/warehouse/views.py",
            "old_string": "a",
            "new_string": "b",
        },
    },
    {"tool_name": "Read", "tool_input": {"file_path": "/repo/.env"}},
]


@pytest.mark.parametrize(
    "rule,event", BLOCKED, ids=lambda v: v if isinstance(v, str) else ""
)
def test_blocked(rule, event):
    r = run_guard(event)
    assert r.returncode == 2, (rule, event)
    assert "ZABLOKOWANO" in r.stderr


@pytest.mark.parametrize("event", ALLOWED)
def test_allowed(event):
    r = run_guard(event)
    assert r.returncode == 0, (event, r.stderr)


def test_bad_json_fails_open():
    r = subprocess.run(
        [sys.executable, str(GUARD)], input="nie-json", capture_output=True, text=True
    )
    assert r.returncode == 0


@pytest.mark.parametrize("branch,code", [("main", 2), ("feat/x", 0)])
def test_reset_hard_only_blocked_on_main(tmp_path, branch, code):
    subprocess.run(["git", "init", "-q", "-b", branch, str(tmp_path)], check=True)
    r = run_guard(
        {
            "tool_name": "Bash",
            "tool_input": {"command": "git reset --hard HEAD~1"},
            "cwd": str(tmp_path),
        }
    )
    assert r.returncode == code, r.stderr
