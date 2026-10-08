#!/usr/bin/env bash
set -e

# Czekaj na bazę danych (gdy używany jest PostgreSQL przez DATABASE_URL).
if [ -n "$DATABASE_URL" ]; then
  echo "Czekam na bazę danych..."
  python - <<'PY'
import os, time, sys
from urllib.parse import urlparse
url = urlparse(os.environ["DATABASE_URL"])
if url.scheme.startswith("postgres"):
    import socket
    host, port = url.hostname, url.port or 5432
    for _ in range(60):
        try:
            socket.create_connection((host, port), timeout=2).close()
            print("Baza dostępna.")
            break
        except OSError:
            time.sleep(1)
    else:
        print("Baza niedostępna — przerywam.", file=sys.stderr)
        sys.exit(1)
PY
fi

# Migracje bazy danych (idempotentne).
echo "Uruchamiam migracje..."
python manage.py migrate --noinput

# Automatyczne utworzenie konta administratora z zmiennych środowiskowych
# (idempotentne — nie nadpisuje istniejącego konta).
if [ -n "$DJANGO_SUPERUSER_USERNAME" ] && [ -n "$DJANGO_SUPERUSER_PASSWORD" ]; then
  echo "Sprawdzam konto administratora..."
  python manage.py shell <<'PY'
import os
from django.contrib.auth import get_user_model
User = get_user_model()
u = os.environ["DJANGO_SUPERUSER_USERNAME"]
if not User.objects.filter(username=u).exists():
    User.objects.create_superuser(
        u,
        os.environ.get("DJANGO_SUPERUSER_EMAIL", ""),
        os.environ["DJANGO_SUPERUSER_PASSWORD"],
    )
    print(f"Utworzono administratora: {u}")
else:
    print("Administrator już istnieje — pomijam.")
PY
fi

# Start serwera produkcyjnego (gunicorn).
echo "Startuję gunicorn na :8000..."
exec gunicorn config.wsgi:application \
  --bind 0.0.0.0:8000 \
  --workers "${GUNICORN_WORKERS:-3}" \
  --timeout 120 \
  --access-logfile - \
  --error-logfile -
