# Kontener backupu (US-012): pg_dump z obrazu PostgreSQL + age (szyfrowanie),
# rclone (wysyłka poza serwer), curl (heartbeat). Bez kompilatorów, bez sekretów.
FROM postgres:16-alpine
RUN apk add --no-cache age rclone curl
COPY scripts/pg_backup.sh /pg_backup.sh
ENTRYPOINT ["sh", "/pg_backup.sh"]
