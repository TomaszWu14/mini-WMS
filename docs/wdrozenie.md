# Wdrożenie i rozwój

Instrukcja uruchomienia lokalnego jest w [README](../README.md#jak-uruchomić). Tu: serwer,
zmienne środowiskowe, narzędzia deweloperskie i struktura kodu.

## Uruchomienie na serwerze (Docker + automatyczny HTTPS)

Aplikacja startuje **jednym poleceniem** i działa dalej sama: wykonuje migracje,
tworzy konto administratora, serwuje pliki statyczne (WhiteNoise), a **Caddy
automatycznie pobiera i odnawia certyfikat HTTPS** (Let's Encrypt). Wszystko
restartuje się po awarii i po restarcie serwera (`restart: unless-stopped`).

### Wymagania wstępne

- Docker + Docker Compose na serwerze.
- **Domena** skierowana na publiczne IP serwera (rekord `A` w DNS),
  np. `miniwms.example.com`.
- Otwarte porty **80** i **443**.

### Kroki

1. Pobierz projekt i skonfiguruj zmienne:

   ```bash
   git clone https://github.com/TomaszWu14/miniWMS-public.git
   cd miniWMS-public
   cp .env.docker.example .env      # ustaw DOMAIN, hasła, klucz
   ```

2. Uruchom (build + start w tle):

   ```bash
   docker compose up -d --build
   ```

To wszystko. Po chwili (Caddy musi pobrać certyfikat) aplikacja działa pod
**`https://TWOJA_DOMENA/`**, panel admina pod `/admin/`. Konto administratora
zakłada się automatycznie z danych w `.env`
(`DJANGO_SUPERUSER_USERNAME` / `DJANGO_SUPERUSER_PASSWORD`). Ruch z `http://`
jest automatycznie przekierowany na `https://`.

Przydatne komendy (opcjonalnie):

```bash
docker compose logs -f web     # logi aplikacji
docker compose logs -f caddy   # logi HTTPS/certyfikatu
docker compose down            # zatrzymanie
docker compose up -d --build   # aktualizacja po zmianach w kodzie
```

> **Uwagi:** certyfikat wystawiany jest tylko dla prawdziwej domeny (nie dla
> samego IP). Dane bazy są w wolumenie `db_data`, a certyfikaty w `caddy_data`
> (trwałe między restartami). Tylko Caddy jest wystawiony na świat — aplikacja
> `web` jest dostępna wyłącznie przez niego.
>
> **Sieć lokalna (bez domeny/HTTPS):** ustaw w `.env` `DOMAIN=:80`,
> `DJANGO_SECURE_COOKIES=0`, `DJANGO_SSL_REDIRECT=0` oraz
> `DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1` (albo IP serwera) — Caddy będzie serwował po
> zwykłym HTTP pod `http://localhost/`.

## Wdrożenie na Coolify

Jeśli korzystasz z **Coolify** (self-hostowany panel deploy), użyj wariantu
`docker-compose.coolify.yml` (bez własnego Caddy — Coolify daje proxy + SSL).
Pełna instrukcja krok po kroku: **[COOLIFY.md](../COOLIFY.md)**.

## Konfiguracja przez zmienne środowiskowe

Patrz `.env.example`. Najważniejsze:

- `DATABASE_URL` — np. `postgres://user:pass@host:5432/dbname` (domyślnie SQLite).
- `DJANGO_SECRET_KEY`, `DJANGO_DEBUG`, `DJANGO_ALLOWED_HOSTS`, `DJANGO_CSRF_TRUSTED_ORIGINS`,
  `DJANGO_TIME_ZONE`, `DJANGO_SESSION_AGE` (sekundy bezczynności, domyślnie 1800).
- `DJANGO_TRUSTED_PROXY_COUNT` — liczba proxy przed aplikacją (Caddy/Traefik: 1); od tego zależy
  IP w limicie i dzienniku logowań.
- `DEMO_MODE`, `DEMO_USER`, `DEMO_PASSWORD` — publiczna instancja demo (COOLIFY.md §11).
- `DJANGO_SECURE_COOKIES`, `DJANGO_SSL_REDIRECT`, `DJANGO_HSTS_SECONDS`, `DJANGO_CONN_MAX_AGE`,
  `DJANGO_MAX_UPLOAD_BYTES`, `GUNICORN_WORKERS` (domyślnie 3).
Pełna lista z opisem wrażliwości: [docs/operacje/RUNBOOK.md](operacje/RUNBOOK.md).


## Rozwój (lint, format, typy, testy)

Narzędzia deweloperskie w `requirements-dev.txt`, konfiguracja w `pyproject.toml`.

```bash
pip install -r requirements-dev.txt
python -m pytest -x -q  # testy (~10 s)
ruff check .            # lint
ruff format .           # formatowanie (jak black+isort)
python manage.py check --deploy   # audyt konfiguracji produkcyjnej
```

CI (GitHub Actions) uruchamia przy każdym pushu/PR: lint (Ruff), mypy, `check --deploy`,
kontrolę migracji, testy z progiem pokrycia (SQLite i PostgreSQL), SAST (bandit, semgrep),
SCA (pip-audit), skan sekretów (gitleaks), build i skan obrazu (trivy). Szczegóły i polecenia
lokalne: [CONTRIBUTING.md](../CONTRIBUTING.md) §6, [ADR-0001](architektura/adr/0001-narzedzia-jakosci-i-bezpieczenstwa.md).

## Struktura

```
config/         # ustawienia (settings/base|dev|prod), URL-e, /healthz
warehouse/
  models.py     # Material, Location, HandlingUnit, IssueDocument, StockMovement, ...
  services.py   # logika: przyjęcie, alokacja, korekta, picking (FEFO→FIFO)
  views/        # ekrany operatora — moduł na obszar (ADR-0006)
  forms.py      # formularze
  imports.py    # import lokalizacji CSV/XLSX
  exports.py    # eksport CSV/XLSX
  labels.py     # etykiety HU i lokalizacji (PDF + QR); documents.py — WZ w PDF
  scanner_views.py  # ekrany i JSON API skanera (docs/architektura/API.md)
  stock_import.py, receipt_import.py, issue_import.py  # importy stanów, przyjęć, zleceń
  demo.py       # tryb demo: „Wejdź jako demo”, /demo/, reset danych, limit prób logowania
  roles.py, signals.py  # role i dekoratory; profil użytkownika, dziennik logowań
  management/commands/seed_demo.py  # dane demo
  templates/ static/
```
