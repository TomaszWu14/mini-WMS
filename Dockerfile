# syntax=docker/dockerfile:1

# --- Etap 1: builder — instalacja zależności do izolowanego venv ------------
FROM python:3.11-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt


# --- Etap 2: runtime — chudy obraz produkcyjny, bez narzędzi budowania ------
FROM python:3.11-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH" \
    DJANGO_DEBUG=0

# Venv z etapu builder (bez kompilatorów i cache pip w finalnym obrazie).
COPY --from=builder /opt/venv /opt/venv

# Użytkownik nie-root.
RUN useradd --create-home --uid 1000 app
WORKDIR /app

COPY --chown=app:app . .
# `WORKDIR` tworzy /app jako root, a `COPY --chown` zmienia właściciela tylko
# skopiowanych plików — nie samego katalogu. Bez tego `app` nie mógłby utworzyć
# /app/staticfiles i `collectstatic` padał w kontenerze (choć lokalnie działa).
RUN chmod +x /app/entrypoint.sh \
    && mkdir -p /app/staticfiles \
    && chown -R app:app /app

USER app

# Pliki statyczne do obrazu (serwuje je WhiteNoise) — jako użytkownik app.
# Build-time SECRET_KEY tylko na czas collectstatic; w runtime nadpisze go
# realny klucz z Coolify/compose (prod.py wymaga własnego klucza).
RUN DJANGO_SECRET_KEY="build-only-key-overridden-at-runtime" \
    python manage.py collectstatic --noinput

EXPOSE 8000

# Healthcheck bez curl — czysto Pythonem (503/odmowa połączenia = unhealthy).
HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
    CMD python -c "import urllib.request as u; import sys; \
sys.exit(0 if u.urlopen('http://127.0.0.1:8000/healthz', timeout=3).getcode()==200 else 1)"

ENTRYPOINT ["/app/entrypoint.sh"]
