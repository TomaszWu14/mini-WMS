#!/usr/bin/env bash
# Skan bezpieczeństwa: pip-audit (CVE w zależnościach), bandit (SAST, medium+),
# trivy na obrazie Dockera (jeśli trivy jest zainstalowane). Raport: reports/security-<data>.md
#
#   scripts/security_scan.sh
#
# Kod wyjścia: 1 gdy pip-audit lub bandit coś znalazł, inaczej 0.
set -uo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT" || exit 1
PY="$ROOT/.venv/Scripts/python.exe"
[[ -x "$PY" ]] || PY="$ROOT/.venv/bin/python"
[[ -x "$PY" ]] || PY="python"
STAMP="$(date +%Y-%m-%d_%H%M)"
mkdir -p reports
OUT="reports/security-${STAMP}.md"
status=0

section() { printf '\n## %s\n\n' "$1" >>"$OUT"; }
block() { { echo '```'; cat; echo '```'; } >>"$OUT"; }

echo "# Skan bezpieczeństwa — $(date '+%Y-%m-%d %H:%M')" >"$OUT"
echo >>"$OUT"
echo "Commit: \`$(git rev-parse --short HEAD 2>/dev/null)\` · branch: \`$(git branch --show-current 2>/dev/null)\`" >>"$OUT"

# --- pip-audit: zależności produkcyjne (requirements.txt) i deweloperskie ---
section "pip-audit (requirements.txt + requirements-dev.txt)"
"$PY" -m pip_audit -r requirements.txt -r requirements-dev.txt --progress-spinner off 2>&1 | grep -v "^WARNING:cachecontrol" | block
pa=${PIPESTATUS[0]}
echo "Wynik: exit $pa ($([[ $pa -eq 0 ]] && echo 'brak znanych podatności' || echo 'ZNALEZIONO PROBLEMY'))" >>"$OUT"
[[ $pa -ne 0 ]] && status=1

# --- bandit: poziom i pewność medium+ (konfiguracja w pyproject [tool.bandit]) ---
section "bandit (severity ≥ medium, confidence ≥ medium)"
"$PY" -m bandit -c pyproject.toml -r warehouse config manage.py -ll -ii -q 2>&1 | block
bd=${PIPESTATUS[0]}
echo "Wynik: exit $bd ($([[ $bd -eq 0 ]] && echo 'brak zgłoszeń' || echo 'ZNALEZIONO PROBLEMY'))" >>"$OUT"
[[ $bd -ne 0 ]] && status=1

# --- trivy: obraz Dockera (opcjonalnie) ---
section "trivy (obraz Dockera, HIGH/CRITICAL)"
if command -v trivy >/dev/null 2>&1 && command -v docker >/dev/null 2>&1; then
  IMAGE="mini-wms:security-scan"
  if docker build -q -t "$IMAGE" . >/dev/null 2>&1; then
    trivy image --severity HIGH,CRITICAL --no-progress "$IMAGE" 2>&1 | block
    echo "Wynik: exit ${PIPESTATUS[0]} (doradczo — nie zmienia kodu wyjścia)" >>"$OUT"
  else
    echo "Pominięto: \`docker build\` nie powiódł się." >>"$OUT"
  fi
else
  echo "Pominięto: brak \`trivy\` (lub \`docker\`) w PATH. W CI skan trivy działa w \`security.yml\`." >>"$OUT"
fi

echo "[security] raport: $OUT (exit $status)"
exit $status
