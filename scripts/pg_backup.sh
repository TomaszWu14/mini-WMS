#!/bin/sh
# Cykliczny backup bazy PostgreSQL (pg_dump -> gzip) z retencją.
# Uruchamiany jako osobny kontener (patrz docker-compose).
set -eu

mkdir -p /backups
INTERVAL="${BACKUP_INTERVAL:-86400}"
KEEP="${BACKUP_KEEP_DAYS:-7}"
HOST="${DB_HOST:-db}"

echo "[backup] start — interwał ${INTERVAL}s, retencja ${KEEP} dni, host ${HOST}"

while true; do
  TS="$(date +%Y%m%d-%H%M%S)"
  FILE="/backups/wms-${TS}.sql.gz"
  if pg_dump -h "$HOST" -U "$POSTGRES_USER" "$POSTGRES_DB" | gzip > "$FILE"; then
    SIZE="$(du -h "$FILE" | cut -f1)"
    echo "[backup] $(date '+%Y-%m-%d %H:%M:%S') OK -> ${FILE} (${SIZE})"
  else
    echo "[backup] $(date '+%Y-%m-%d %H:%M:%S') BŁĄD pg_dump" >&2
    rm -f "$FILE"
  fi
  # Usuń kopie starsze niż KEEP dni.
  find /backups -name 'wms-*.sql.gz' -mtime +"${KEEP}" -delete 2>/dev/null || true
  sleep "$INTERVAL"
done
