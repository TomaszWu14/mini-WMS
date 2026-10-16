#!/bin/sh
# Cykliczny backup bazy PostgreSQL (US-012, RUNBOOK §5):
#   pg_dump -Z 6    -> kopia lokalna (.sql.gz) w $BACKUP_DIR (retencja BACKUP_KEEP_DAYS, domyślnie 7 dni)
#   age             -> kopia szyfrowana kluczem PUBLICZNYM (BACKUP_AGE_RECIPIENT); klucz
#                      prywatny jest offline u PO — serwer nie umie odszyfrować kopii
#   rclone          -> wysyłka poza serwer (BACKUP_RCLONE_REMOTE, np. "offsite:bucket/miniwms").
#                      Retencja off-site (30 dni) najlepiej regułą lifecycle bucketu, a klucz
#                      serwera bez prawa usuwania (przejęty serwer nie skasuje kopii). Usuwanie
#                      przez skrypt tylko z BACKUP_OFFSITE_PRUNE=1 (np. SFTP bez lifecycle).
#   curl            -> ping BACKUP_HEARTBEAT_URL po pełnym sukcesie ("dead man's switch":
#                      brak pingu = alert z usługi monitorującej, np. Healthchecks.io)
# Konfiguracja rclone wyłącznie ze zmiennych RCLONE_CONFIG_<NAZWA>_* (bez pliku na dysku).
# BACKUP_ONCE=1 — jeden przebieg i kod wyjścia (test, ręczne uruchomienie).
set -eu

DIR="${BACKUP_DIR:-/backups}"
INTERVAL="${BACKUP_INTERVAL:-86400}"
KEEP="${BACKUP_KEEP_DAYS:-7}"
OFFSITE_KEEP="${BACKUP_OFFSITE_KEEP_DAYS:-30}"
HOST="${DB_HOST:-db}"
RECIPIENT="${BACKUP_AGE_RECIPIENT:-}"
REMOTE="${BACKUP_RCLONE_REMOTE:-}"
HEARTBEAT="${BACKUP_HEARTBEAT_URL:-}"
MIN_BYTES="${BACKUP_MIN_BYTES:-1024}"
PRUNE="${BACKUP_OFFSITE_PRUNE:-0}"

log() { echo "[backup] $(date '+%Y-%m-%d %H:%M:%S') $*"; }
fail() { echo "[backup] $(date '+%Y-%m-%d %H:%M:%S') BŁĄD: $*" >&2; return 1; }

if [ -n "$REMOTE" ] && [ -z "$RECIPIENT" ]; then
  fail "BACKUP_RCLONE_REMOTE ustawione bez BACKUP_AGE_RECIPIENT — nie wysyłam kopii bez szyfrowania." || exit 2
fi

case "$OFFSITE_KEEP" in
  ''|*[!0-9]*|0) fail "BACKUP_OFFSITE_KEEP_DAYS musi być liczbą dni ≥ 1 (jest: '$OFFSITE_KEEP')." || exit 2 ;;
esac
if [ -n "$REMOTE" ] && [ -z "${REMOTE#*:}" ]; then
  fail "BACKUP_RCLONE_REMOTE musi wskazywać katalog (np. offsite:bucket/miniwms), nie cały zdalny dysk." || exit 2
fi

mkdir -p "$DIR"
log "start — interwał ${INTERVAL}s, lokalnie ${KEEP} dni, off-site: ${REMOTE:-wyłączony} (usuwanie przez skrypt: $([ "$PRUNE" = 1 ] && echo "${OFFSITE_KEEP} dni" || echo "nie — lifecycle bucketu")), heartbeat: $([ -n "$HEARTBEAT" ] && echo tak || echo nie)"

backup_once() {
  TS="$(date +%Y%m%d-%H%M%S)"
  FILE="$DIR/wms-${TS}.sql.gz"
  TMP="$FILE.part"

  # Bez potoku `pg_dump | gzip`: tam błąd pg_dump przykrywał sukces gzip i log mówił „OK”
  # przy pustym pliku. pg_dump -Z kompresuje sam (format plain = plik .sql.gz), kod wyjścia jest jego.
  if ! pg_dump -h "$HOST" -U "$POSTGRES_USER" -Z 6 -f "$TMP" "$POSTGRES_DB"; then
    rm -f "$TMP"
    fail "pg_dump przerwany"
    return 1
  fi
  SIZE="$(wc -c < "$TMP" | tr -d ' ')"
  if [ "$SIZE" -lt "$MIN_BYTES" ] || ! gzip -t "$TMP"; then
    rm -f "$TMP"
    fail "kopia podejrzanie mała (${SIZE} B) albo uszkodzona"
    return 1
  fi
  mv "$TMP" "$FILE"
  log "OK -> ${FILE} (${SIZE} B)"

  if [ -n "$RECIPIENT" ]; then
    if ! age -r "$RECIPIENT" -o "$FILE.age" "$FILE"; then
      rm -f "$FILE.age"
      fail "szyfrowanie age"
      return 1
    fi
    if [ -n "$REMOTE" ]; then
      if ! rclone copyto "$FILE.age" "$REMOTE/$(basename "$FILE").age"; then
        rm -f "$FILE.age"
        fail "wysyłka rclone do $REMOTE"
        return 1
      fi
      log "off-site OK -> $REMOTE/$(basename "$FILE").age"
      if [ "$PRUNE" = "1" ]; then
        # Tylko ten katalog (bez podkatalogów innych instalacji) i tylko nasze pliki.
        rclone delete "$REMOTE" --max-depth 1 --min-age "${OFFSITE_KEEP}d" \
          --include '/wms-*.sql.gz.age' || fail "retencja off-site (kopia wysłana, stare zostają)"
      fi
    fi
    rm -f "$FILE.age"  # zaszyfrowana kopia lokalnie niepotrzebna
  fi

  if [ -n "$HEARTBEAT" ]; then
    curl -fsS -m 10 --retry 3 -o /dev/null "$HEARTBEAT" || fail "heartbeat (kopia zrobiona)"
  fi
  return 0
}

while true; do
  STATUS=0
  backup_once || STATUS=1
  find "$DIR" \( -name 'wms-*.sql.gz' -o -name 'wms-*.part' -o -name 'wms-*.age' \) \
    -mtime +"${KEEP}" -delete 2>/dev/null || true
  if [ "${BACKUP_ONCE:-0}" = "1" ]; then
    exit "$STATUS"
  fi
  sleep "$INTERVAL"
done
