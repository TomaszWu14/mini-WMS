# mini-WMS — prosty system zarządzania magazynem

![Lista HU w trybie demo](docs/img/hu-list.png)

Lekki WMS w Django dla małego magazynu (jeden magazyn, kilku operatorów), który
nie ma jeszcze systemu WMS: przyjęcia z etykietami HU, lokalizacje, picking FEFO/FIFO
z terminalem skanera i pełna historia ruchów.

> **Projekt portfolio.** Nazwy firm są zamienione na fikcyjne, a dane demo i testowe są syntetyczne.
>
> Kod udostępniony do wglądu (portfolio), wszelkie prawa zastrzeżone — patrz [`LICENSE`](LICENSE).
> Historia commitów została zgnieciona przy publikacji wersji portfolio.

[![ci](https://github.com/TomaszWu14/mini-WMS/actions/workflows/ci.yml/badge.svg)](https://github.com/TomaszWu14/mini-WMS/actions/workflows/ci.yml)

## W skrócie

| | |
|---|---|
| **Problem** | Mały magazyn bez systemu WMS: palety (HU) bez etykiet, brak historii ruchów, picking „z pamięci”. |
| **Rozwiązanie** | Lekki WMS: przyjęcia z generowaniem HU, etykiety PDF z kodem QR, lokalizacje, picking FEFO → FIFO, pełny rejestr ruchów z audytem. |
| **Stack** | Python 3.11+, Django 5.1, PostgreSQL 16, ReportLab + qrcode (PDF/QR), openpyxl, Gunicorn + WhiteNoise, Docker Compose + Caddy (auto-HTTPS). |
| **Jakość** | 119 testów (`manage.py test`), ruff, CI w GitHub Actions: `check`, `check --deploy`, `makemigrations --check`. |
| **Wdrożenie** | Jedno polecenie `docker compose up -d --build` albo Coolify (`docker-compose.coolify.yml`). |

Lekki WMS w Django do zarządzania materiałem w magazynie: przyjęcia z generowaniem
HU (palet), alokacja w miejscach składowania, picking (wydania) oraz pełna historia
ruchów. Materiał bez master daty — opcjonalnie z partią i datą ważności oraz sztywnym
limitem ilości na palecie.

## Demo

Publiczne demo: **wkrótce: wms-demo.twapp.pl** (jeszcze niewdrożone).

| Login | Rola | Hasło |
|---|---|---|
| `demo_operator` | Operator (przyjęcia, alokacje, picking, skaner) | `demo1234` |
| `demo_podglad` | Podgląd (tylko odczyt) | `demo1234` |

Dane demo są **fikcyjne** (15 materiałów, ~30 HU z różnymi datami ważności,
3 dokumenty WZ w różnych stanach, otwarty spis z natury) i są **przywracane
codziennie** o 03:00 (`seed_demo --reset` jako *Scheduled Task* w Coolify — patrz
[COOLIFY.md](COOLIFY.md#11-instancja-demo-opcjonalnie)). Lokalnie:

```bash
export DEMO_MODE=1                 # Windows PowerShell: $env:DEMO_MODE=1
python manage.py migrate
python manage.py seed_demo         # --reset: wyczyść i zasiej od nowa (tylko przy DEMO_MODE)
python manage.py runserver
```

`DEMO_MODE=1` włącza baner „DEMO” na każdej stronie (także w skanerze), loginy demo
na stronie logowania, blokadę edycji kont demo (403), limit 10 prób logowania na
5 min na IP (429) i maile wyłącznie do konsoli. Bez tej zmiennej aplikacja działa
jak dotąd.

| Wydanie (WZ) po realizacji FEFO | Skaner — wybór zlecenia pickingu |
|---|---|
| ![Szczegóły wydania](docs/img/issue-detail.png) | ![Skaner — picking](docs/img/scanner-picking.png) |

## Przepływ danych

```
przyjęcie ──► HU (Do ułożenia) ──► alokacja w lokalizacji (Zmagazynowany)
                                        │
dokument WZ ──► picking: dobór HU FEFO → FIFO, najpierw PICKING, potem ZAPAS
                                        │
                     każda operacja ──► StockMovement (kto, kiedy, ile, skąd/dokąd)
```

Stan HU zmieniają wyłącznie funkcje z `warehouse/services.py`; każda zapisuje ruch
w `StockMovement` w tej samej transakcji, więc historia zawsze zgadza się ze stanem.

## Dlaczego ten stack

Django daje gotowe logowanie, panel admina i formularze, a logika magazynowa
mieści się w transakcjach (`transaction.atomic`) z blokadą wierszy
`select_for_update` — dwa równoległe pickingi nie zdejmą tej samej palety ponad
stan. PostgreSQL pilnuje reguł także na poziomie bazy (`CHECK` na ilości ≥ 0,
unikalne numery HU/WZ). Wdrożenie ma dwa warianty: samodzielny `docker compose`
z Caddy (automatyczny HTTPS bez panelu) albo Coolify, gdy serwer ma już
reverse-proxy i chcemy auto-deploy oraz harmonogram zadań z panelu.

## Ograniczenia i co dalej

- Jeden magazyn, bez wielu oddziałów i bez stref/ścieżek kompletacji.
- Brak integracji z ERP — materiały i zlecenia wydań wchodzą ręcznie albo z CSV/XLSX.
- Django 5.1 → migracja na 5.2 LTS do zrobienia.
- Limit logowań w demo używa cache w pamięci procesu (per worker gunicorna);
  przy większym ruchu — wspólny cache (np. Redis).
- Brak rezerwacji stanu pod otwarte WZ — dostępność liczona jest w chwili realizacji.

## Funkcje

- **Słownik materiałów** — indeks (≤40 zn.), nazwa, jednostka miary (domyślnie `PCS`),
  opcjonalny sztywny limit ilości na palecie.
- **Przyjęcie** — podajesz materiał i ilość (tryb: *ilość całkowita + liczba palet*
  albo *ilość na paletę + liczba palet*). System dzieli ilość równo (resztę dokłada do
  ostatniej palety) i generuje **HU** o numerach `prefiks + licznik` (konfigurowalny).
  HU może chwilowo czekać w strefie przyjęć (status *Do ułożenia*).
- **Etykiety HU** — wydruk PDF (A6) z **kodem QR** i danymi palety.
- **Lokalizacje** — kod tekstowy (np. `B0-81-301A`), typy **PICKING** / **ZAPAS**,
  pojemność informacyjna. Masowy **import z CSV/XLSX**.
- **Alokacja / przesunięcia** — ulokuj HU w miejscu; HU dostaje status *Zmagazynowany*.
- **Picking / wydania** — dokument wydania z pozycjami; wydanie **po materiale**
  (automatyczny dobór HU regułą **FEFO → FIFO**, z priorytetem lokalizacji PICKING)
  lub z **konkretnego HU**. Picking częściowy. Po zejściu do zera HU staje się *Pusty*
  i zwalnia lokalizację. Wydanie ponad stan jest blokowane.
- **Stany i ruchy** — bieżące stany wg materiału oraz pełny rejestr ruchów
  (przyjęcie / alokacja / przesunięcie / korekta / wydanie) z audytem *kto + kiedy*.
  **Eksport CSV i XLSX**.
- **Role i konta** — Administrator / Operator / Podgląd. Konta zakłada administrator
  w panelu Django. Logowanie wbudowane.
- **Dashboard** — kafelki: liczba HU, zajętość lokalizacji, dzisiejsze ruchy, stany.

## Wymagania

- Python 3.11+
- Zależności z `requirements.txt` (Django, reportlab, qrcode, openpyxl)

## Uruchomienie (development)

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt

python manage.py migrate           # tworzy bazę + jednostkę PCS i numerację HU
python manage.py createsuperuser   # konto administratora
python manage.py runserver
```

Aplikacja: <http://127.0.0.1:8000/> · Panel admina: <http://127.0.0.1:8000/admin/>

## Role użytkowników

| Rola          | Uprawnienia |
|---------------|-------------|
| Administrator | Wszystko + panel admina, zakładanie kont, edycja/usuwanie ruchów. |
| Operator      | Przyjęcia, alokacje, korekty, picking, import lokalizacji. |
| Podgląd       | Tylko odczyt list, stanów, ruchów i eksport. |

Superużytkownik Django jest automatycznie traktowany jak Administrator. Nowym kontom
nadaj rolę w panelu admina (sekcja *Profile użytkowników*).

## Pierwsze kroki

1. **Materiały** → dodaj indeksy (lub w panelu admina).
2. **Lokalizacje** → *Import CSV/XLSX* (kolumny: `kod`, `typ`, `pojemnosc`) lub dodaj
   ręcznie. Przykład:

   ```csv
   kod;typ;pojemnosc
   B0-81-301A;PICKING;1
   B0-81-302A;ZAPAS;2
   ```

3. **Przyjęcie** → wybierz materiał, podaj ilość i liczbę palet → powstają HU.
4. **HU** → *Etykieta PDF* do wydruku, *Ulokuj* w miejscu składowania.
5. **Wydania** → utwórz dokument, dodaj pozycje, *Realizuj wydanie*.

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
   git clone https://github.com/TomaszWu14/mini-WMS.git
   cd mini-WMS
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
> **Sieć lokalna (bez domeny/HTTPS):** ustaw `DOMAIN=:80` w `.env` oraz
> `DJANGO_SECURE_COOKIES=0` — Caddy będzie serwował po zwykłym HTTP.

## Wdrożenie na Coolify

Jeśli korzystasz z **Coolify** (self-hostowany panel deploy), użyj wariantu
`docker-compose.coolify.yml` (bez własnego Caddy — Coolify daje proxy + SSL).
Pełna instrukcja krok po kroku: **[COOLIFY.md](COOLIFY.md)**.

## Konfiguracja przez zmienne środowiskowe

Patrz `.env.example`. Najważniejsze:

- `DATABASE_URL` — np. `postgres://user:pass@host:5432/dbname` (domyślnie SQLite).
- `DJANGO_SECRET_KEY`, `DJANGO_DEBUG`, `DJANGO_ALLOWED_HOSTS`, `DJANGO_TIME_ZONE`.

Dla PostgreSQL doinstaluj sterownik: `pip install "psycopg[binary]"`.

## Testy

```bash
python manage.py test
```

Testy pokrywają m.in. podział ilości na palety, regułę FEFO/priorytet PICKING,
picking częściowy i blokadę stanu ujemnego, korekty oraz import lokalizacji.

## Rozwój (lint, format, typy)

Narzędzia deweloperskie w `requirements-dev.txt`, konfiguracja w `pyproject.toml`.

```bash
pip install -r requirements-dev.txt
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
