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
- `DJANGO_SECRET_KEY`, `DJANGO_DEBUG`, `DJANGO_ALLOWED_HOSTS`, `DJANGO_TIME_ZONE`.


## Rozwój (lint, format, typy, testy)

Narzędzia deweloperskie w `requirements-dev.txt`, konfiguracja w `pyproject.toml`.

```bash
pip install -r requirements-dev.txt
python -m pytest -x -q  # testy (~10 s)
ruff check .            # lint
ruff format .           # formatowanie (jak black+isort)
python manage.py check --deploy   # audyt konfiguracji produkcyjnej
```

CI (GitHub Actions) uruchamia lint (Ruff), `check --deploy`, kontrolę migracji
i testy na każdym pushu/PR.

## Struktura

```
config/         # ustawienia (settings/base|dev|prod), URL-e, /healthz
warehouse/
  models.py     # Material, Location, HandlingUnit, IssueDocument, StockMovement, ...
  services.py   # logika: przyjęcie, alokacja, korekta, picking (FEFO→FIFO)
  views.py      # ekrany operatora
  forms.py      # formularze
  imports.py    # import lokalizacji CSV/XLSX
  exports.py    # eksport CSV/XLSX
  labels.py     # etykieta HU (PDF + QR)
  templates/ static/
```
