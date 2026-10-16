"""US-012 / R9: logika `scripts/pg_backup.sh` (jeden przebieg, BACKUP_ONCE=1).

`pg_dump`, `rclone` i `curl` są atrapami w PATH (zapisują wywołania); `age` jest prawdziwy,
jeśli jest w systemie (wtedy test odszyfrowuje kopię kluczem prywatnym), inaczej atrapa.
"""

import gzip
import os
import shutil
import subprocess
import tempfile
from io import StringIO
from pathlib import Path
from unittest import skipUnless

from django.core.management import call_command
from django.test import SimpleTestCase, TestCase

from .models import HandlingUnit, Material, Unit

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "pg_backup.sh"
HAS_AGE = shutil.which("age") is not None and shutil.which("age-keygen") is not None

PG_DUMP = """#!/bin/sh
# Atrapa: pg_dump -Z N -f PLIK BAZA — jak prawdziwy zapisuje plik gzip.
out=""; while [ $# -gt 0 ]; do [ "$1" = "-f" ] && out="$2"; shift; done
[ "${FAKE_PG_FAIL:-0}" = "1" ] && { echo "connection refused" >&2; : > "$out"; exit 1; }
[ "${FAKE_PG_EMPTY:-0}" = "1" ] && { printf '' | gzip > "$out"; exit 0; }
i=0; while [ $i -lt 400 ]; do echo "INSERT INTO warehouse_handlingunit VALUES ($i);"; i=$((i+1)); done | gzip > "$out"
"""
LOGGER = """#!/bin/sh
echo "$(basename "$0") $*" >> "$CALLS"
[ "$(basename "$0")" = "rclone" ] && [ "${FAKE_RCLONE_FAIL:-0}" = "1" ] && [ "$1" = "copyto" ] && exit 1
exit 0
"""
FAKE_AGE = """#!/bin/sh
echo "age $*" >> "$CALLS"
out=""; while [ $# -gt 1 ]; do [ "$1" = "-o" ] && out="$2"; shift; done
cp "$1" "$out"
"""


class BackupScriptTests(SimpleTestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.bin = self.tmp / "bin"
        self.bin.mkdir()
        self.backups = self.tmp / "backups"
        self.calls = self.tmp / "calls.log"
        self.calls.touch()
        self._stub("pg_dump", PG_DUMP)
        for name in ("rclone", "curl"):
            self._stub(name, LOGGER)
        if not HAS_AGE:
            self._stub("age", FAKE_AGE)
        self.recipient, self.identity = self._age_key()

    def _stub(self, name, body):
        path = self.bin / name
        path.write_text(body)
        path.chmod(0o755)

    def _age_key(self):
        if not HAS_AGE:
            return "age1fakerecipient", None
        identity = self.tmp / "key.txt"
        subprocess.run(
            ["age-keygen", "-o", str(identity)], check=True, capture_output=True
        )
        public = next(
            line.split(": ")[1]
            for line in identity.read_text().splitlines()
            if line.startswith("# public key:")
        )
        return public.strip(), identity

    def _run(self, **env):
        full = {
            "PATH": f"{self.bin}:{os.environ['PATH']}",
            "CALLS": str(self.calls),
            "BACKUP_ONCE": "1",
            "BACKUP_DIR": str(self.backups),
            "POSTGRES_USER": "wms",
            "POSTGRES_DB": "wms",
        }
        full.update(env)
        return subprocess.run(
            ["sh", str(SCRIPT)], env=full, capture_output=True, text=True, timeout=60
        )

    def _calls(self):
        return self.calls.read_text()

    def _offsite_env(self, **extra):
        env = {
            "BACKUP_AGE_RECIPIENT": self.recipient,
            "BACKUP_RCLONE_REMOTE": "offsite:miniwms",
            "BACKUP_HEARTBEAT_URL": "https://hc.example/ping/abc",
        }
        env.update(extra)
        return env

    def test_full_success_encrypts_uploads_prunes_and_pings(self):
        """Kryteria 1–3: kopia szyfrowana poza serwerem, retencja 30 dni, heartbeat."""
        r = self._run(**self._offsite_env())
        self.assertEqual(r.returncode, 0, r.stderr)
        calls = self._calls()
        self.assertRegex(
            calls,
            r"rclone copyto \S+/wms-\d{8}-\d{6}\.sql\.gz\.age offsite:miniwms/wms-",
        )
        self.assertIn(
            "rclone delete offsite:miniwms --min-age 30d --include wms-*.sql.gz.age",
            calls,
        )
        self.assertIn(
            "curl -fsS -m 10 --retry 3 -o /dev/null https://hc.example/ping/abc", calls
        )
        local = list(self.backups.glob("wms-*.sql.gz"))
        self.assertEqual(len(local), 1)
        self.assertEqual(
            list(self.backups.glob("*.age")),
            [],
            "zaszyfrowana kopia nie zostaje lokalnie",
        )
        self.assertIn(
            b"INSERT INTO warehouse_handlingunit",
            gzip.decompress(local[0].read_bytes()),
        )

    @skipUnless(HAS_AGE, "brak age w systemie")
    def test_encrypted_copy_decrypts_only_with_private_key(self):
        """Kryterium 1: na serwerze jest tylko klucz publiczny; odszyfrowanie wymaga prywatnego."""
        keep = self.tmp / "keep"
        self._stub(
            "rclone",
            f'#!/bin/sh\necho "rclone $*" >> "$CALLS"\n[ "$1" = copyto ] && cp "$2" {keep}\nexit 0\n',
        )
        r = self._run(**self._offsite_env())
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertNotIn(b"INSERT", keep.read_bytes())
        plain = subprocess.run(
            ["age", "-d", "-i", str(self.identity), str(keep)],
            capture_output=True,
            check=True,
        ).stdout
        self.assertIn(b"INSERT INTO warehouse_handlingunit", gzip.decompress(plain))

    def test_pg_dump_failure_is_not_reported_as_ok(self):
        """Uwaga [DEV]: pipefail — błąd pg_dump nie daje „OK”, nie wysyła i nie pinguje."""
        r = self._run(FAKE_PG_FAIL="1", **self._offsite_env())
        self.assertEqual(r.returncode, 1)
        self.assertNotIn(" OK ", r.stdout)
        self.assertIn("pg_dump przerwany", r.stderr)
        self.assertNotIn("rclone", self._calls())
        self.assertNotIn("curl", self._calls())
        self.assertEqual(list(self.backups.iterdir()), [])

    def test_empty_dump_rejected(self):
        r = self._run(FAKE_PG_EMPTY="1", **self._offsite_env())
        self.assertEqual(r.returncode, 1)
        self.assertIn("podejrzanie mała", r.stderr)
        self.assertNotIn("curl", self._calls())

    def test_upload_failure_skips_heartbeat(self):
        """Kryterium 3: brak wysyłki = brak pingu → alert z usługi monitorującej."""
        r = self._run(FAKE_RCLONE_FAIL="1", **self._offsite_env())
        self.assertEqual(r.returncode, 1)
        self.assertNotIn("curl", self._calls())

    def test_refuses_unencrypted_offsite(self):
        r = self._run(BACKUP_RCLONE_REMOTE="offsite:miniwms")
        self.assertEqual(r.returncode, 2)
        self.assertIn("bez szyfrowania", r.stderr)
        self.assertEqual(self._calls(), "")

    def test_local_only_mode_still_works(self):
        """Bez konfiguracji off-site — jak dotąd: tylko kopia lokalna."""
        r = self._run()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(len(list(self.backups.glob("wms-*.sql.gz"))), 1)
        self.assertEqual(self._calls(), "")

    def test_custom_offsite_retention(self):
        self._run(**self._offsite_env(BACKUP_OFFSITE_KEEP_DAYS="14"))
        self.assertIn("--min-age 14d", self._calls())


class BackupFingerprintTests(TestCase):
    """Kryterium 4: odcisk danych do porównania produkcji z kopią odtworzoną."""

    def test_fingerprint_lists_counts(self):
        unit = Unit.objects.get_or_create(code="PCS")[0]
        material = Material.objects.create(index="FP-1", name="Odcisk", unit=unit)
        HandlingUnit.objects.create(number="HU-FP-1", material=material, quantity=7)
        out = StringIO()
        call_command("backup_fingerprint", stdout=out)
        text = out.getvalue()
        self.assertIn("palety (HU): 1", text)
        self.assertIn("suma ilości na paletach: 7", text)
        self.assertIn("materiały: 1", text)
