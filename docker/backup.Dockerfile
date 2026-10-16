# Kontener backupu (US-012): pg_dump z obrazu PostgreSQL + age (szyfrowanie),
# rclone (wysyłka poza serwer), curl (heartbeat). Bez kompilatorów, bez sekretów.
FROM postgres:16-alpine
# gosu (Go 1.24, kilkadziesiąt CVE wg trivy) służy tylko entrypointowi serwera PostgreSQL —
# ten kontener go nie używa (własny ENTRYPOINT), więc usuwamy go z obrazu.
RUN apk add --no-cache age rclone curl && rm -f /usr/local/bin/gosu
COPY scripts/pg_backup.sh /pg_backup.sh
ENTRYPOINT ["sh", "/pg_backup.sh"]
