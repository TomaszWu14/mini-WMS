#!/usr/bin/env bash
set -e

# Czekaj na bazę danych (gdy używany jest PostgreSQL przez DATABASE_URL).
if [ -n "$DATABASE_URL" ]; then
  echo "Czekam na bazę danych..."
  python - <<'PY'
import os, time, sys
from urllib.parse import urlparse
url = urlparse(os.environ["DATABASE_URL"])
# US-003: zaślepka hasła bazy z .env.docker.example nie może trafić do produkcji.
if (url.password or "").startswith("YOUR_"):
    sys.exit("POSTGRES_PASSWORD to zaślepka z .env.docker.example — ustaw losowe hasło.")
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
# US-009: tabela cache wspólnego dla workerów (idempotentne).
python manage.py createcachetable

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
    # US-003: hasło musi przejść walidatory Django (odrzucają `admin`) i nie może
    # być zaślepką z .env.docker.example.
    from django.contrib.auth.password_validation import validate_password
    from django.core.exceptions import ValidationError
    pw = os.environ["DJANGO_SUPERUSER_PASSWORD"]
    try:
        if pw.startswith("YOUR_"):
            raise ValidationError("to zaślepka z .env.docker.example")
        validate_password(pw, User(username=u))
    except ValidationError as e:
        raise SystemExit("DJANGO_SUPERUSER_PASSWORD odrzucone: " + "; ".join(e.messages))
    User.objects.create_superuser(
        u,
        os.environ.get("DJANGO_SUPERUSER_EMAIL", ""),
        os.environ["DJANGO_SUPERUSER_PASSWORD"],
    )
    print(f"Utworzono administratora: {u}")
else:
    # US-003: konto z dawnym domyślnym hasłem (compose sprzed US-003) blokuje start.
    existing = User.objects.get(username=u)
    if any(existing.check_password(w) for w in ("admin", "YOUR_DJANGO_SUPERUSER_PASSWORD_HERE")):
        raise SystemExit(
            f"Konto {u} ma domyślne hasło — zmień je przed startem: "
            f"docker compose run --rm --entrypoint python web manage.py changepassword {u}"
        )
    print("Administrator już istnieje — pomijam.")
PY
fi

# US-005: retencja dziennika logowań i wygasłe sesje — przy każdym starcie; codziennie
# robi to Scheduled Task (COOLIFY.md §10a). Błąd sprzątania nie blokuje startu.
python manage.py purge_login_events || echo "Ostrzeżenie: purge_login_events nie powiodło się."
python manage.py clearsessions || echo "Ostrzeżenie: clearsessions nie powiodło się."

# Start serwera produkcyjnego (gunicorn).
echo "Startuję gunicorn na :8000..."
exec gunicorn config.wsgi:application \
  --bind 0.0.0.0:8000 \
  --workers "${GUNICORN_WORKERS:-3}" \
  --timeout 120 \
  --access-logfile - \
  --error-logfile -
