#!/usr/bin/env bash
# Testy mutacyjne (mutmut 3) jednego modułu + raport z przeżytymi mutantami.
#
#   scripts/mutate.sh warehouse/services.py                 # cały moduł
#   scripts/mutate.sh warehouse/services.py 'split_quantity' # tylko funkcje pasujące do wzorca
#
# Wynik: reports/mutation-<moduł>-<data>.md. Wolne (minuty–godziny) — NIE podpinać pod hooki.
# mutmut nie działa natywnie na Windowsie → poza Linuksem uruchamia się w kontenerze
# python:3.11-slim (wymaga Dockera). Zawsze na kopii repo — drzewo robocze zostaje nietknięte.
set -euo pipefail

MOD_PATH="${1:?Użycie: scripts/mutate.sh <ścieżka/modułu.py> [wzorzec-funkcji]}"
FILTER="${2:-}"
MOD_PATH="${MOD_PATH//\\//}"
MOD_NAME="${MOD_PATH%.py}"
MOD_NAME="${MOD_NAME//\//.}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
STAMP="${MUTATE_STAMP:-$(date +%Y-%m-%d_%H%M)}"
REPORT_NAME="mutation-${MOD_NAME}-${STAMP}.md"

[[ -f "$ROOT/$MOD_PATH" ]] || { echo "Brak pliku: $MOD_PATH" >&2; exit 1; }
mkdir -p "$ROOT/reports"

if [[ "$(uname -s)" != "Linux" && -z "${MUTATE_INNER:-}" ]]; then
  command -v docker >/dev/null || { echo "mutmut wymaga Linuksa/WSL albo Dockera." >&2; exit 1; }
  echo "[mutate] $(uname -s) → uruchamiam w kontenerze python:3.11-slim"
  MSYS_NO_PATHCONV=1 docker run --rm -v "$ROOT":/src:ro -v "$ROOT/reports":/out \
    -e MUTATE_INNER=1 -e REPORT_DIR=/out -e MUTATE_STAMP="$STAMP" python:3.11-slim bash -c "
      set -e
      mkdir /work && tar -C /src --exclude=.venv --exclude=.git --exclude=mutants \
        --exclude=reports --exclude='*.sqlite3' -cf - . | tar -C /work -xf -
      cd /work && pip install -q --root-user-action=ignore --require-hashes -r requirements-mutation.txt
      bash scripts/mutate.sh '$MOD_PATH' '$FILTER'"
  exit $?
fi

REPORT_DIR="${REPORT_DIR:-$ROOT/reports}"
PY="${PYTHON:-python}"

# Kopia robocza (mutmut tworzy mutants/ i nadpisujemy w niej [tool.mutmut]).
WORK="$ROOT"
if [[ -z "${MUTATE_INNER:-}" ]]; then
  WORK="$(mktemp -d)"
  tar -C "$ROOT" --exclude=.venv --exclude=.git --exclude=mutants --exclude=reports \
    -cf - . | tar -C "$WORK" -xf -
fi
cd "$WORK"

"$PY" - "$MOD_PATH" <<'PY'
import re, sys
p = "pyproject.toml"
s = open(p, encoding="utf-8").read()
s = re.sub(r'source_paths = \[[^\]]*\]', f'source_paths = ["{sys.argv[1]}"]', s)
open(p, "w", encoding="utf-8").write(s)
PY

SELECT=()
[[ -n "$FILTER" ]] && SELECT=("${MOD_NAME}.*${FILTER}*")
START=$(date +%s)
"$PY" -m mutmut run "${SELECT[@]}" >mutmut-run.log 2>&1 || true
SECS=$(( $(date +%s) - START ))

"$PY" -m mutmut results --all true >results.txt 2>&1 || true
# Z filtrem liczymy tylko pasujące funkcje (reszta modułu ma status "not checked").
grep -E "${MOD_NAME//./\.}\.x_[^:]*${FILTER}" results.txt >mod-results.txt || true
total=$(wc -l <mod-results.txt | tr -d ' ')
killed=$(grep -c ': killed' mod-results.txt || true)
survived=$(grep -c ': survived' mod-results.txt || true)
other=$(( total - killed - survived ))

{
  echo "# Testy mutacyjne: \`$MOD_PATH\`"
  echo
  echo "Data: ${STAMP/_/ } · filtr: \`${FILTER:-brak}\` · czas: ${SECS} s"
  echo
  echo "| Mutanty | Zabite | Przeżyły | Inne (timeout/bez testów/…) |"
  echo "|---|---|---|---|"
  echo "| $total | $killed | $survived | $other |"
  echo
  if [[ "$total" -eq 0 ]]; then
    echo "Brak wyników — ostatnie linie logu mutmut:"
    echo '```'; tail -40 mutmut-run.log; echo '```'
  fi
  if [[ "$other" -gt 0 ]]; then
    echo "## Inne statusy"; echo '```'; grep -v -e ': killed' -e ': survived' mod-results.txt; echo '```'
  fi
  echo "## Przeżyte mutanty (do 30) — brakujące asercje w testach"
  grep ': survived' mod-results.txt | head -30 | cut -d: -f1 | while read -r m; do
    echo; echo "### \`$m\`"; echo '```diff'; "$PY" -m mutmut show "$m" 2>/dev/null | head -25; echo '```'
  done
} >"$REPORT_DIR/$REPORT_NAME"

echo "[mutate] $total mutantów: zabite $killed, przeżyły $survived, inne $other (${SECS} s)"
echo "[mutate] raport: reports/$REPORT_NAME"
