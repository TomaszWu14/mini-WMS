# Audyt stanu repozytorium — miniWMS

| | |
|---|---|
| Data | 2026-10-15 |
| Stan kodu | `main` @ `f5be158` (25 commitów, 2026-10-08 → 2026-10-13, jeden autor) |
| Autorzy audytu | zespół [BA] / [DEV] / [SEC] (sesja asystenta AI), do akceptacji Product Ownera |
| Metoda | lektura całego kodu aplikacji, konfiguracji, CI i dokumentacji; uruchomienie narzędzi (sekcja 2.2); weryfikacja hipotez bezpieczeństwa testem w Django test client; niezależny drugi przegląd bezpieczeństwa |

Dokument opisuje **stan obecny** z trzech perspektyw. Nie zmienia kodu. Każde zgłoszenie
wskazuje plik i linię; to, czego nie sprawdzono, jest wypisane w sekcji 6.

---

## 0. Streszczenie

- **[BA]** Aplikacja ma spójny, dobrze opisany zakres (docs/01–07): przyjęcia z etykietą QR,
  rozmieszczanie skanerem, wydania FEFO→FIFO, korekty, spis z natury, raporty, 3 role.
  26 wymagań funkcjonalnych ma kryteria akceptacji i wskazanie testu. Brakuje: wymagań
  niefunkcjonalnych, backlogu z priorytetami, macierzy śledzenia do PR, mierników sukcesu
  i wymagań dotyczących danych osobowych.
- **[DEV]** Kod jest czysty: ruff, ruff format, mypy (cały kod), bandit, pip-audit,
  `check --deploy`, `makemigrations --check` — wszystko zielone. 224 testy przechodzą w 8 s,
  pokrycie 81 % (serwisy 91 %, widoki 70 %). Dług: `views.py` 1405 linii, uszkodzony
  plik XLSX wywraca import błędem 500, CI mierzy mypy tylko w 3 plikach i nie pilnuje
  pokrycia, skany bezpieczeństwa są doradcze i miesięczne.
- **[SEC]** Fundamenty są solidne (role na serwerze, CSRF, ORM, transakcje z blokadami,
  limit uploadu, neutralizacja formuł CSV, HSTS/nosniff/Referrer-Policy, obraz non-root).
  Cztery ryzyka **wysokie** (dwa z nich głównie przez publiczne demo): (1) konto z rolą
  Administrator może przejąć konto superusera (zmiana hasła i dezaktywacja — potwierdzone
  testem), (2) słabe domyślne sekrety w `docker-compose.yml` i konta demo zakładane przez
  `seed_demo` także bez `DEMO_MODE`, (3) nieograniczona liczba palet w przyjęciu — jeden
  formularz lub jeden wiersz importu może utworzyć miliony palet i zablokować numerację HU
  dla wszystkich, (4) import XLSX wczytuje cały `sharedStrings.xml` do pamięci mimo limitu
  5 MB (bomba zip), a uszkodzony plik daje 500. Sześć ryzyk średnich/niskich w sekcji 3.3.
- **Publiczne demo** (`miniwms.twapp.pl`, rola Operator dla każdego) jest świadomą decyzją,
  ale zwiększa wagę każdego błędu w ścieżkach operatora — to powierzchnia dostępna anonimowo.
- **Proces:** repozytorium nie ma CONTRIBUTING, SECURITY, CHANGELOG, szablonów issue/PR,
  CODEOWNERS, Dependabota ani pre-commit. Jest za to harness asystenta AI (`.claude/`,
  `docs/pitfalls/`, dokumenty operatora per branch) — do utrzymania.
- **Pilne do backlogu (pierwsze historyjki):** R1–R4 z sekcji 3.3 (lista w 3.4), retencja
  dziennika logowań i limiter na `/demo/`.

---

## 1. [BA] Perspektywa analityka biznesowego

### 1.1 Co aplikacja robi (AS-IS)

**Cel** (docs/01): jedno źródło prawdy o tym, *co* jest w magazynie, *gdzie* stoi i *co się
z tym działo*, na poziomie pojedynczej palety (HU). Kontekst: mały magazyn (~200 palet,
~30 nowych tygodniowo, 2 operatorów), bez ERP, dotąd ewidencja na papierze.

**Użytkownicy i role** (`warehouse/roles.py`): Podgląd (odczyt), Operator (operacje
magazynowe + skaner), Administrator (konta, dziennik logowań, termin dostawy).
Superuser Django = Administrator + panel `/admin/` (edycja/usuwanie ruchów).

**Procesy** (docs/02): przyjęcie (formularz lub import) → etykiety QR → rozmieszczanie
(panel lub skaner) → wydanie WZ (ręcznie, z pliku; dobór palet PICKING→ZAPAS, FEFO, FIFO;
realizacja pełna lub z brakami; pakowanie opcjonalne; wysyłka) → kontrola stanu (korekta
z powodem, przepakowanie, spis z natury przy zamrożonym magazynie).

**Interfejsy:** panel web (35 ekranów), skaner w przeglądarce telefonu (8 ekranów, 8
endpointów JSON), 4 importy CSV/XLSX, 2 eksporty CSV/XLSX, 3 rodzaje PDF (etykieta HU,
etykiety lokalizacji, WZ). Interfejs po polsku. Razem ok. 70 tras URL.

**Status:** „zaawansowany prototyp”, nie wdrożony u klienta; wymagania pochodzą z
obserwacji autora, nie z wdrożenia. Działa publiczne demo z danymi fikcyjnymi.

### 1.2 Dokumentacja istniejąca a struktura docelowa (sekcja 2 promptu)

| Dokument docelowy | Co już jest | Luka |
|---|---|---|
| `analiza/WIZJA.md` | docs/01 (problem, cel, zakres, poza zakresem) | brak mierników sukcesu („liczb nie zbierano”), brak horyzontu/roadmapy |
| `analiza/INTERESARIUSZE.md` | docs/01 — tabela 3 ról | brak Product Ownera, administratora infrastruktury, odbiorcy WZ (klient/przewoźnik), osoby odpowiedzialnej za dane osobowe |
| `analiza/PROCESY.md` | docs/02 — AS-IS/TO-BE w Mermaid, punkty decyzyjne | brak procesów administracyjnych: zakładanie kont, backup/odtworzenie, zamrożenie magazynu na spis |
| `analiza/WYMAGANIA.md` | docs/05 — 26 FR (W-01…W-26) z kryteriami i wskazaniem testu | **brak NFR** (wydajność, dostępność, RODO, użyteczność, bezpieczeństwo); kryteria opisowe, nie Given/When/Then |
| `analiza/HISTORYJKI.md` | brak | brak backlogu i priorytetów MoSCoW |
| `analiza/SLOWNIK.md` | docs/01 — 7 pojęć | wystarczający; dopisać: Operator/Administrator/Podgląd, LOT, korekta, powód korekty |
| `analiza/ZALOZENIA.md` | docs/02 — 3 założenia procesu | brak rejestru „do potwierdzenia” → **utworzony w tej sesji** |
| `analiza/SLEDZENIE.md` | docs/05 — kolumna „Gdzie zrealizowane” (kod + test) | brak powiązania wymaganie → historyjka → PR |
| `architektura/ARCHITEKTURA.md` | README „Stack i dlaczego”, docs/wdrozenie „Struktura” | brak diagramu kontekstu/kontenerów (C4) |
| `architektura/MODEL_DANYCH.md` | docs/04 — ERD, 13 encji, 12 luk integralności | kompletny |
| `architektura/API.md` | brak | 8 endpointów JSON skanera nieudokumentowanych |
| `architektura/adr/` | docs/06 — D-01…D-13 (kontekst, opcje, decyzja, skutki) | format bliski ADR; brak decyzji o narzędziach (CI, skany), o publicznym demo, o harnessie AI |
| `bezpieczenstwo/*` | fragmenty: docs/pitfalls/auth.md, D-12, pyproject `[tool.bandit]` | **brak** klasyfikacji danych, threat modelu, rejestru ryzyk, RODO, ASVS |
| `testy/STRATEGIA_TESTOW.md` | fragmenty w docs/pitfalls/db.md i deploy.md | brak |
| `operacje/RUNBOOK.md` | COOLIFY.md (deploy, backup, odtworzenie §10), docs/wdrozenie.md, docs/operator/*.md | brak: incydenty, monitoring, rotacja sekretów, test odtworzenia |
| `README.md` | jest, portfolio-ready | brak linków do nowych dokumentów i statusu skanów bezpieczeństwa |
| `CONTRIBUTING.md`, `SECURITY.md`, `CHANGELOG.md` | brak | brak Definition of Ready/Done, polityki zgłaszania podatności, historii wersji (wersja `0.1.0` od początku) |
| `.github/ISSUE_TEMPLATE`, `pull_request_template.md`, `CODEOWNERS`, `dependabot.yml` | brak | brak |

### 1.3 Czego brakuje w wymaganiach

1. **Wymagania niefunkcjonalne nie istnieją jako dokument.** W kodzie są decyzje, które
   je implikują: sesja 30 min bezczynności (`base.py:185`), limit uploadu 5 MB
   (`forms.py:23`), limit 200 etykiet na wydruk (`views.py:502`), 500 ruchów na liście
   (`views.py:1162`), limit logowań 10/5 min (`demo.py:32`). Trzeba je spisać jako NFR
   z identyfikatorami i uzasadnieniem.
2. **Dane osobowe nie są przedmiotem żadnego wymagania.** Dziennik logowań zbiera IP,
   przeglądarkę i wpisany login (także przy nieudanej próbie), bez retencji (sekcja 3.3, R7).
3. **Mierniki sukcesu** — brak. Propozycja do uzgodnienia: czas znalezienia palety, odsetek
   wydań zgodnych z FEFO, liczba korekt po spisie, czas przyjęcia dostawy.
4. **Backlog i priorytety** — wszystkie 26 wymagań ma status „spełnione”, docs/07 „Co dalej”
   zawiera jeden punkt (Redis). Nie ma listy kandydatów na kolejne funkcje ani ich wartości
   biznesowej.
5. **Decyzje zakresowe wymagają potwierdzenia przez PO:** blokada palet po terminie ważności,
   zwroty/anulowanie WZ, rezerwacja stanu pod otwarte WZ, wiele magazynów, atrybuty
   logistyczne materiału — dziś „poza zakresem” decyzją autora (docs/01, 07).
6. **Znane ślepe ścieżki UX** (docs/03): skaner — błąd wczytania zlecenia bez komunikatu;
   endpointy tylko-POST wywołane GET-em przekierowują bez informacji. Oba drobne, do backlogu.
7. **Walidacja z użytkownikami nie nastąpiła** — wymagania „potwierdzone z interesariuszami”
   pochodzą z obserwacji autora; przed realnym wdrożeniem warto zaplanować test
   użyteczności skanera (telefon, rękawice, hala).

### 1.4 Ocena

Dokumentacja analityczna jest ponadprzeciętna jak na projekt jednoosobowy: proces, model
danych, wymagania z kryteriami, dziennik decyzji. Główna luka to **brak warstwy
„dlaczego i ile”** (mierniki, NFR, priorytety) i **brak śladu procesu** (historyjki → PR).

---

## 2. [DEV] Perspektywa developera

### 2.1 Architektura i stack

- Django 5.2 LTS (zainstalowane 5.2.18), jedna aplikacja `warehouse`, ustawienia
  `config/settings/{base,dev,prod,test}.py` wybierane przez `DJANGO_DEBUG`.
- Warstwa usług `warehouse/services.py` (693 linie): każda zmiana stanu w `@transaction.atomic`
  z `select_for_update` i wpisem `StockMovement` (D-05). Widoki i skaner wołają te same funkcje.
- Dane: SQLite lokalnie, PostgreSQL 16 produkcyjnie; 8 migracji; `CheckConstraint` na ilości
  i limicie, `UniqueConstraint` na pozycjach spisu; `RunPython` z funkcją wsteczną.
- Frontend: szablony Django + własny CSS (988 linii) + 448 linii własnego JS (skaner,
  kamera, prezentacja demo) + vendor jsQR (10 101 linii). Bez bundlera, bez frameworka.
- Wdrożenie: Dockerfile dwuetapowy (python:3.11-slim, venv, non-root `app`, HEALTHCHECK),
  gunicorn 3 workery, WhiteNoise, dwa warianty compose (Caddy auto-HTTPS / Coolify+Traefik),
  kontener `backup` (pg_dump co 24 h, retencja 7 dni), `/healthz`.
- Rozmiar: ok. 5,5 tys. linii Pythona aplikacji, 3 tys. linii testów, 2,4 tys. linii
  szablonów, 2,4 tys. linii dokumentacji Markdown.

### 2.2 Wyniki narzędzi (uruchomione w tej sesji, Python 3.13, czysty venv)

| Narzędzie | Zakres | Wynik |
|---|---|---|
| `ruff check .` | cały projekt | ✅ bez uwag |
| `ruff format --check .` | 51 plików | ✅ sformatowane |
| `mypy warehouse config` | 41 plików (pełny zakres, nie tylko CI) | ✅ bez błędów |
| `pytest -q` | 226 testów w 12 plikach | ✅ 224 passed, 2 skipped (PostgreSQL), **8,2 s** |
| `coverage` | warehouse + config bez migracji i testów | **81 %** ogółem; services 91 %, models 93 %, forms 91 %, scanner_views 74 %, **views 70 %**, imports 77 %, receipt_import 68 %, **exports 53 %**, config/log 29 % |
| `bandit -ll -ii` (konfiguracja z pyproject) | warehouse, config, manage.py | ✅ 0 zgłoszeń średnich+; niskie to hasła w testach (B106/B105), `random` w seed_demo (B311), `try/except/pass` w labels.py:62 |
| `pip-audit` | `requirements.txt` + `requirements-dev.txt` (bez Playwright) | ✅ brak znanych podatności |
| `manage.py check --deploy` | ustawienia prod | ✅ tylko W009 od klucza-zaślepki użytego w audycie |
| `manage.py makemigrations --check` | modele vs migracje | ✅ bez zmian |

Nie uruchomiono: trivy (obraz), gitleaks (historia; zrobiono lekki skan wzorców — sekcja 6),
semgrep, testów na PostgreSQL, testów mutacyjnych.

### 2.3 Testy

- 226 funkcji testowych: `tests.py` (113, 1432 linie) + 11 plików `tests_<obszar>.py`
  (po poprawkach i decyzjach). Styl: Django `TestCase`, test client, bez fixtures/factory.
- Pokrywają reguły biznesowe (FEFO, limity, blokady), role (35 asercji o 403/przekierowaniu),
  importy, eksporty (w tym formuły CSV), PDF, demo, tour, hardening. Jest test wyścigu
  dwóch WZ o jedną paletę na PostgreSQL (`tests_concurrency_pg.py`, CI `test-postgres`).
- Najsłabiej pokryte: `exports.py` 53 % (XLSX bez testu), `receipt_import.py` 68 %,
  `views.py` 70 % (głównie ścieżki błędów i eksport ruchów), `config/log.py` 29 %.
- CI uruchamia testy przez `manage.py test` (PBKDF2, ~5 min) zamiast `pytest`
  (MD5 w `config.settings.test`, 8 s). Pokrycie nie jest mierzone ani pilnowane progiem.
- `scripts/mutate.sh` (mutmut na `services.py`) — brak zapisanych wyników w repo.
- Testy leżą w pakiecie aplikacji, nie w `tests/`; `pyproject` wskazuje `python_files`
  ręcznie — działa, ale utrudnia podział na jednostkowe/integracyjne/e2e.

### 2.4 Dług techniczny i problemy (uporządkowane wg wpływu)

| # | Problem | Gdzie | Wpływ | Propozycja |
|---|---|---|---|---|
| T1 | **Uszkodzony plik XLSX (lub CSV z rozszerzeniem .xlsx) kończy import błędem 500** — `zipfile.BadZipFile` nie jest łapany; widoki łapią tylko `ImportError_`. Potwierdzone testem na `/stany/import/` i `/lokalizacje/import/`. | `imports.py:92` (`load_workbook`), `views.py:344,429,808,886` | operator widzi stronę błędu zamiast komunikatu; na demo każdy anonimowy może generować 500 | w `_rows_from_xlsx` łapać `BadZipFile`/`InvalidFileException`/`KeyError` → `ImportError_("Plik nie jest poprawnym XLSX")`; test |
| T2 | **`views.py` ma 1405 linii** (pitfall mówi o 1177 — nieaktualne); 47 widoków, pulpit z 4 funkcjami pomocniczymi, eksporty, użytkownicy | `warehouse/views.py` | koszt zmian, konflikty, trudniejszy review | podział na moduły: `views/dashboard.py`, `views/issues.py`, `views/users.py`, `views/exports.py`; bez zmiany URL-i |
| T3 | **Zamknięcie WZ przez skaner poza warstwą usług** — `api_pick` sam ustawia `ZREALIZOWANY` po ostatnim pobraniu, bez blokady dokumentu | `scanner_views.py:357-363` | łamie D-05 (zmiana stanu tylko w `services.py`); logika domknięcia dokumentu istnieje w dwóch miejscach | przenieść do `services.pick_from_hu`/nowej `complete_if_picked(document)` pod `select_for_update` |
| T4 | **mypy w CI tylko dla 3 plików**, choć cały kod przechodzi | `.github/workflows/ci.yml:54` | regresje typów w widokach/importach niewykryte | `mypy warehouse config` w CI (dziś zielone, koszt 0) |
| T5 | **Brak progu pokrycia i raportu coverage w CI** | `ci.yml` | pokrycie może spaść niezauważenie | `coverage run -m pytest` + `coverage report --fail-under=80` (+ artefakt HTML) |
| T6 | **CI testuje przez `manage.py test` (~5 min)** zamiast `pytest` (8 s) | `ci.yml:68,103` | wolny feedback, więcej minut Actions | `pytest -q` z `config.settings.test` (ten sam zestaw testów; różnica to tylko hasher) |
| T7 | **Zależności w dwóch miejscach** (`pyproject [project.dependencies]` i `requirements.txt`) synchronizowane ręcznie; brak lockfile | `pyproject.toml`, `requirements*.txt` | rozjazd, niereprodukowalny build (`Django>=5.2,<5.3`, `pip install --upgrade pip` bez wersji) | `pip-compile` → `requirements.txt` z hashami albo `uv lock`; Dockerfile instaluje z locka |
| T8 | **Cache LocMem per proces** dla limitu logowań i blokady resetu demo | `demo.py:56,129`, `base.py` (brak `CACHES`) | limit realnie ×3 (workery); znany problem (docs/07) | DB-backed cache (`DatabaseCache`, bez nowej usługi) albo Redis, gdy pojawi się więcej workerów |
| T9 | **Eksport ruchów buduje wszystkie wiersze w pamięci** (pitfall views #9), lista ruchów ucina do 500 bez filtra dat | `views.py:1169-1208, 1162` | przy dziesiątkach tysięcy ruchów długi request | `StreamingHttpResponse` dla CSV, filtr zakresu dat w UI i eksporcie |
| T10 | **Martwy/duplikujący się kod:** `HUNumberingConfig.get_solo` nieużywane (`generate_hu_number` tworzy konfigurację samo); `_norm`/`_get` zdublowane w `stock_import.py` i `issue_import.py` | `models.py:155`, `issue_import.py:20-28` | drobne | usunąć `get_solo`, wspólny moduł `imports_common` |
| T11 | **`stocktake_save` zapisuje pozycje bez transakcji** — błąd w środku pętli zostawia częściowy zapis | `views.py:1051-1079` | rzadkie; spis zapisywany ręcznie | `with transaction.atomic()` |
| T12 | **`demo.js` ładowane na każdej stronie** także poza trybem demo | `base.html` (ostatnia linia), `scanner/base.html` | 258 linii JS na produkcji bez potrzeby | ładować tylko przy `demo_mode` |
| T13 | **Brak wersjonowania i CHANGELOG** — `version = "0.1.0"`, brak tagów/releasów, historia tylko w `docs/operator/*.md` | `pyproject.toml` | audytor/rekruter nie widzi wydań | Keep a Changelog + SemVer, tag przy merge do `main` |
| T14 | **Nieaktualne drobiazgi w docs:** pitfall views #8 (1177 linii), `wdrozenie.md` „Struktura” bez `scanner_views.py`, `stock_import.py`, `demo.py`; docs/07 „Co dalej” jeden punkt | `docs/pitfalls/views.md`, `docs/wdrozenie.md` | mylące dla nowej osoby | poprawić przy reorganizacji docs |
| T15 | **Brak `ADMINS`/alertów o błędach 500** — logi JSON na stdout są, ale nikt nie dostaje powiadomienia | `base.py:195` | awaria niezauważona do zgłoszenia użytkownika | Sentry/GlitchTip lub `ADMINS` + `mail_admins`, albo alert w Coolify na restarty |
| T16 | **Walidacja zakresów i długości:** `IntegerField` bez `max_value`; `int(raw)` w zapisie spisu i `delta` w API inwentaryzacji bez górnej granicy; `int(float(...))` w importach rzuca `OverflowError` (np. `1e999`), którego nie ma w `except (TypeError, ValueError)`; brak walidacji długości kodów (40) i numerów HU (30) w importach; `Content-Disposition` budowany z kodu lokalizacji/numeru HU (znak nowej linii lub `"` z importu → `BadHeaderError`) | `forms.py:111,132,207-213,276,332`, `views.py:370,498,1066`, `scanner_views.py:421`, `imports.py:32,59` | na PostgreSQL wartości > 2^31−1 lub za długie kody kończą się `DataError` → 500 i wycofaniem całego importu; na SQLite przechodzą | `max_value` wszędzie, `except (…, OverflowError)`, `max_length` w importach, `django.utils.http.content_disposition_header()`; testy |

### 2.5 Ocena

Kod jest **gotowy do rozwoju zespołowego**: spójna warstwa usług, constrainty w bazie,
blokady wierszy sprawdzone na PostgreSQL, zielone narzędzia, szybkie testy. Dług dotyczy
głównie **procesu** (CI, lock zależności, wersjonowanie, podział widoków), nie logiki domenowej.
Harness asystenta AI (`.claude/hooks/guard.py` blokuje push na `main`, `rm -r`, SQL
niszczący, zapis `.env`; `check.py` uruchamia ruff/mypy/pytest przed zakończeniem) to
realna, przetestowana (`test_hooks.py`) wartość, którą zespół powinien utrzymać.

---

## 3. [SEC] Perspektywa bezpieczeństwa

### 3.1 Co już jest dobrze (żeby nie wyważać otwartych drzwi)

- Autoryzacja po stronie serwera dla **każdego** z 47 widoków i 16 endpointów skanera
  (`login_required` 22, `operator_required` 36, `admin_required` 5); zmiany stanu tylko na POST;
  rola z `Profile`, superuser = Administrator; nowe konto = Podgląd.
- CSRF: middleware, `{% csrf_token %}` w każdym formularzu POST, skaner wysyła `X-CSRFToken`;
  brak `csrf_exempt`. Brak `|safe`/`mark_safe`/`autoescape off`; brak surowego SQL poza
  `LOCK TABLE` z nazwami tabel z modeli (`seed_demo.py:116`).
- Sesje: 30 min bezczynności, `HttpOnly`, `SameSite=Lax`, `Secure` w prod; HSTS 30 dni,
  `nosniff`, `Referrer-Policy: same-origin`, `X-Frame-Options: DENY`, przekierowanie na HTTPS
  z wyjątkiem `/healthz`; `prod.py` odmawia startu z kluczem `django-insecure-*`.
- Walidatory haseł Django; limit prób logowania (10/5 min/IP) zawsze, IP tylko od zaufanego
  proxy (`DJANGO_TRUSTED_PROXY_COUNT`, D-12); dziennik logowań (udane/nieudane/wylogowania).
- Upload: limit 5 MB (`_MaxSizeFileMixin` + `DATA_UPLOAD_MAX_MEMORY_SIZE`), `openpyxl`
  w `read_only`, limit 500 wierszy w demo; eksport neutralizuje formuły CSV/XLSX
  (`exports.py:9-13`); nazwy plików w `Content-Disposition` pochodzą z numerów systemowych.
- Demo: konta demo chronione przed edycją (`user_edit`), `/admin/` wyłączony przy `DEMO_MODE`,
  „Wejdź jako demo” tylko kontem z listy, `seed_demo --reset` odmawia bez `DEMO_MODE`.
- Obraz: dwuetapowy, slim, non-root, bez kompilatorów, `.dockerignore` wyklucza `.env` i `.git`;
  tylko Caddy/Traefik wystawione na świat; sekrety wyłącznie w env; `.env*` ignorowane;
  `guard.py` blokuje zapis plików z sekretami.
- CI: lint, `check --deploy`, kontrola migracji, testy na SQLite i PostgreSQL, build i smoke
  obrazu; `security.yml`: bandit (blokujący ≥ średnie), gitleaks (pełna historia), trivy,
  pip-audit.

### 3.2 Wstępna klasyfikacja danych (do potwierdzenia w `KLASYFIKACJA_DANYCH.md`)

| Klasa | Dane | Gdzie |
|---|---|---|
| Publiczne | kod, dokumentacja, dane demo, konta demo (login i hasło jawne z założenia) | repo, `miniwms.twapp.pl` |
| Wewnętrzne (tajemnica przedsiębiorstwa klienta) | materiały, lokalizacje, stany, palety, dokumenty WZ (referencja, przewoźnik, nr przesyłki), ruchy, spisy | tabele `warehouse_*`, eksporty CSV/XLSX, PDF, backupy |
| Poufne | `DJANGO_SECRET_KEY`, hasła bazy i superusera, backupy `pg_dump` | env Coolify/compose, wolumen `db_backups` |
| **Dane osobowe** (RODO) | login, e-mail, hash hasła (`auth_user`); **IP, przeglądarka, wpisany login** (`LoginEvent`, także nieudane próby); „kto” w ruchach, dokumentach, materiałach (`created_by`); kolumna „Kto” w eksporcie ruchów; referencja WZ może zawierać nazwę klienta | `auth_user`, `warehouse_loginevent`, `created_by`, eksporty, logi gunicorna (IP) |

### 3.3 Top 10 ryzyk

Waga = wpływ × prawdopodobieństwo w kontekście *realnego wdrożenia u klienta*; tam, gdzie
*publiczne demo* (anonimowy Operator) zmienia obraz, podano dwie oceny. Oznaczenia:
**W** wysokie, **Ś** średnie, **N** niskie.

| # | Ryzyko | Waga | Gdzie | Scenariusz | Rekomendacja |
|---|---|---|---|---|---|
| **R1** | **Eskalacja: konto z rolą Administrator (nie superuser) może zmienić hasło i dezaktywować konto superusera.** Potwierdzone testem: POST na `/uzytkownicy/<pk superusera>/` z nowym hasłem → 302, nowe hasło działa; z `is_active` pustym → konto wyłączone. Poza `get_role` nigdzie nie ma sprawdzenia `is_superuser`. | **W** | `views.py:1296-1335` (`user_edit`) | nielojalny/przejęty Administrator ustawia hasło superuserowi → loguje się do `/admin/` → edytuje lub usuwa ruchy (`StockMovementAdmin` pozwala superuserowi) i dziennik logowań → niszczy ślad audytowy; albo wyłącza jedyne konto serwisowe (w demo `/admin/` to 404, więc skutek to lockout) | w `user_edit`: konto z `is_superuser` edytuje tylko superuser (403 dla roli); test „Administrator nie zmieni superusera”; rozważyć potwierdzenie własnym hasłem przy zmianie cudzego |
| **R2** | **Niebezpieczne wartości domyślne przy wdrożeniu prywatnym.** (a) `docker-compose.yml`: `DJANGO_SECRET_KEY` domyślnie `zmien-mnie-w-produkcji`, `DJANGO_SUPERUSER_PASSWORD` domyślnie `admin`, `POSTGRES_PASSWORD` domyślnie `wms`; `prod.py` odrzuca tylko prefiks `django-insecure-`, więc wartość domyślna i zaślepka `YOUR_DJANGO_SECRET_KEY_HERE` z `.env.docker.example` **przechodzą**. (b) `seed_demo` bez `DEMO_MODE` zakłada konta `demo_operator` (Operator) i `demo_podglad` z hasłem `demo1234` — strażnik `DEMO_MODE` działa tylko przy `--reset`, a `is_demo_account` bez `DEMO_MODE` tych kont nie wyróżnia; README i COOLIFY.md zachęcają do uruchomienia `seed_demo`. | **W** | `docker-compose.yml:18,53,65`, `config/settings/prod.py:12`, `seed_demo.py:79,134-141` | operator kopiuje `.env.docker.example`, pomija klucz → aplikacja startuje z publicznie znanym kluczem (podpis sesji/CSRF do podrobienia) i kontem `admin/admin`; albo „na próbę” uruchamia `seed_demo` na instancji prywatnej → każdy z internetu loguje się `demo_operator/demo1234` i zmienia stany | w compose `${VAR:?…}` jak w wariancie dla Coolify; w `prod.py` odrzucać klucze < 50 znaków i znane zaślepki; `seed_demo` bez `DEMO_MODE` odmawia albo tworzy konta demo z `set_unusable_password()` i ostrzeżeniem; testy ustawień i komendy |
| **R3** | **Nieograniczona liczba palet w przyjęciu → DoS i globalna blokada numeracji HU.** `ReceiveForm.pallets`/`total_quantity` mają `min_value` bez `max_value`; import przyjęć bierze `palety` z pliku bez limitu (limit 500 wierszy w demo nie pomaga — wystarczy jeden wiersz); `split_quantity` buduje listę długości `pallets`, `receive_material` tworzy HU + ruch na każdą; `generate_hu_number` trzyma `select_for_update` na `HUNumberingConfig` wewnątrz zewnętrznej transakcji do końca żądania. | **W** (demo) / **Ś** | `forms.py:207-213`, `receipt_import.py:54-59`, `services.py:75-85,91-108,119-162` | anonim po `/demo/` wysyła `POST /przyjecie/` z `total_quantity=5000000&pallets=5000000` (albo plik z jednym wierszem `palety=5000000`); worker mieli miliony INSERT-ów do `--timeout 120` i SIGKILL; 3 równoległe żądania = wszystkie workery zajęte; przez ten czas każde inne przyjęcie, import i `seed_demo --reset` czekają na blokadę licznika | `max_value` na `pallets` (np. 500) i ilościach; twardy limit palet na wiersz i HU na plik w imporcie; walidacja przed pierwszym zapisem; test |
| **R4** | **Import XLSX bez utwardzenia.** Typ pliku po rozszerzeniu; uszkodzony plik → 500 (T1, potwierdzone); **bomba `sharedStrings.xml`**: `load_workbook(read_only=True)` i tak wczytuje cały `xl/sharedStrings.xml` do pamięci (`openpyxl/reader/excel.py:139,291`) zanim `islice` obetnie wiersze, a limit 5 MB dotyczy rozmiaru po kompresji (deflate ~1000:1 → gigabajty XML); `openpyxl` w obrazie produkcyjnym **bez `defusedxml`** (w czystym venv jest tylko jako zależność pip-audit); brak limitu wierszy poza demo. | **W** (demo) / **Ś** | `imports.py:89-127`, `forms.py:20-31`, `requirements.txt` | anonim na demo (albo operator u klienta) wgrywa spreparowany `.xlsx` (1 wiersz, ogromny `sharedStrings.xml`) w pętli → MemoryError/OOM-kill workera, presja na pamięć hosta; 5 MB XLSX z milionami wierszy → transakcja na minuty | przed `load_workbook` otworzyć `zipfile.ZipFile` i odrzucić, gdy suma `file_size` członków > np. 50 MB; `defusedxml` w `requirements.txt`; limit wierszy zawsze (np. 10 000); magic bytes `PK\x03\x04`; `BadZipFile`/`InvalidFileException`/`KeyError` → `ImportError_`; testy |
| **R5** | **Publiczne demo = anonimowy Operator bez limitów poza logowaniem.** `/demo/` (GET) i `/login/demo/` wołają `login()` z pominięciem limitera `LoginView.post` — każde trafienie klienta bez ciasteczek to nowy wiersz `django_session` i `LoginEvent`, a nigdzie nie ma `clearsessions`; `location_labels` renderuje QR dla wszystkich lokalizacji bez limitu (`hu_labels` ma 200); `hu_list`, `location_list`, `stock_by_location`, `report_locations` bez paginacji; limit 500 wierszy importu jest per plik, bez limitu łącznej liczby obiektów; `demo_reset` uruchamia `seed_demo` z `LOCK TABLE` na 9 tabel w żądaniu HTTP (cooldown 60 s per worker). Świadome wyjątki demo (logowanie na GET = login CSRF, jawne hasło, współdzielone konta bez rozliczalności) — do rejestru jako zaakceptowane. | **Ś** | `demo.py:86-100,104-121,126-143`, `views.py:310-317,375-383,453-474,858-876,1347-1372`, `imports.py:119-127`, `seed_demo.py:116` | bot `GET /demo/` 100 żądań/s → miliony wierszy sesji i dziennika dziennie, dziennik bezużyteczny, backup puchnie (link jest w README i na YouTube); skrypt: 200 importów × 500 lokalizacji → `GET /lokalizacje/etykiety/` zajmuje workera 120 s (wystarczy rola Podgląd); nie zagraża danym (fikcyjne), zagraża dostępności i wizerunkowi | limiter per IP na `/demo/`, `/login/demo/` i ścieżkach operatora w demo; `clearsessions` w harmonogramie; limit etykiet lokalizacji jak `HU_LABELS_LIMIT`; paginacja list; limit łącznej liczby HU/lokalizacji w demo; reset tylko z Scheduled Task; wyjątki w `RYZYKA.md` z datą przeglądu |
| **R6** | **Uwierzytelnianie poniżej minimum z sekcji 6 promptu:** limit logowań per IP i per proces (3 workery → 30 prób/5 min), brak blokady per konto, brak 2FA dla Administratora i `/admin/`, hasher PBKDF2 (domyślny Django) zamiast argon2/bcrypt; `/admin/` na produkcji (poza demo) dostępny z internetu. | **Ś** | `demo.py:53-75`, `base.py:145` (brak `PASSWORD_HASHERS`), `config/urls.py:50` | atak słownikowy z puli IP na konto `admin` (login znany z `.env.docker.example`): 30 prób/5 min/IP × N adresów; przejęte hasło = pełny dostęp | argon2 (`argon2-cffi`, `PASSWORD_HASHERS`), licznik prób per login w bazie/cache współdzielonym, 2FA (`django-otp`) dla ADMIN i `/admin/`, opcjonalnie allowlista IP dla `/admin/` w Caddy/Traefik |
| **R7** | **RODO — dziennik logowań bez retencji i podstawy:** `LoginEvent` przechowuje IP, user-agent i **dowolny wpisany tekst** w polu login (przy nieudanej próbie może to być hasło wpisane w złe pole) bezterminowo; demo loguje IP każdego odwiedzającego `/demo/`; eksport ruchów zawiera loginy pracowników; brak `clearsessions`; brak polityki prywatności, rejestru czynności, procedury usunięcia/eksportu danych osoby. | **Ś** | `signals.py:57-89`, `models.py:510-538`, `views.py:1169-1208`, `demo.py:120` | pracownik żąda informacji/usunięcia — brak procedury; wyciek bazy ujawnia IP i nawyki logowania; organ nadzorczy pyta o podstawę i retencję | retencja (np. 90 dni) komendą `manage.py purge_login_events` + Scheduled Task; nie zapisywać UA albo skracać; w demo nie logować IP; `RODO.md` z podstawą (art. 6 ust. 1 lit. f — bezpieczeństwo) i rejestrem; procedura praw osób |
| **R8** | **Brak Content-Security-Policy i Permissions-Policy.** 7 inline handlerów `onclick` i inline `window.CSRF` w szablonach utrudniają ścisłe CSP. HSTS 30 dni z `preload=True` (preload wymaga ≥ 1 roku — flaga bez efektu). | **Ś** | `base.py:71-82` (middleware), `prod.py:38-40`, `scanner/base.html` | XSS dziś nie znaleziono (autoescape, `textContent` w skanerze), ale bez CSP każdy przyszły błąd szablonu/JS ma pełny zasięg: kradzież sesji operatora | `django-csp` z nonce, usunąć inline handlery; `Permissions-Policy: camera=(self), geolocation=()`; HSTS 1 rok albo bez `preload` |
| **R9** | **Backup na tym samym serwerze, nieszyfrowany, bez testu odtworzenia:** `pg_dump` → gzip w wolumenie Dockera na hoście bazy, retencja 7 dni, brak kopii off-site, brak alertu gdy backup zawodzi (tylko log), odtworzenie opisane, ale nieprzećwiczone. | **Ś** | `scripts/pg_backup.sh`, oba pliki compose (usługa `backup`), `COOLIFY.md §10` | awaria dysku/ransomware/błąd operatora `docker volume rm` = utrata bazy i kopii naraz | kopia off-site (rclone → S3/B2/inny host) szyfrowana (`age`/`gpg`), retencja 30 dni, miesięczny test odtworzenia w RUNBOOK, alert przy braku świeżej kopii |
| **R10** | **Łańcuch dostaw i CI doradcze:** `security.yml` raz w miesiącu, trivy `--exit-code 0`, pip-audit `\|\| true`, `bandit[toml]`/`pip-audit` bez wersji, trivy instalowany przez `curl … install.sh \| sh` z gałęzi `main`; `ci.yml` bez top-level `permissions:` (token z domyślnymi uprawnieniami); brak Dependabota; brak pre-commit (gitleaks lokalnie); Dockerfile bazuje na tagu `python:3.11-slim` (nie digest); akcje GitHub przypięte do wersji głównych (`@v4`, `@v7`), nie SHA; `pip install --upgrade pip` bez wersji; `Django>=5.2,<5.3` bez locka. | **N/Ś** | `security.yml:48`, `ci.yml` (brak `permissions`), `Dockerfile:4,18` | nowe CVE w zależności niezauważone do 4 tygodni; podmieniony skrypt instalacyjny lub tag akcji wykonuje się na runnerze z tokenem repo | `dependabot.yml` (pip, docker, github-actions), pip-audit blokujący na PR dla `requirements.txt`, trivy blokujący dla CRITICAL (`aquasecurity/trivy-action@<sha>`), `permissions: contents: read`, akcje po SHA, lock z hashami (T7), `SECURITY.md` |

**Poza listą (niskie, do rejestru ryzyk):**

- `Content-Disposition` budowany z `loc.code` / `hu.number` (`views.py:370,498`): kod lokalizacji
  z importu CSV może zawierać `"` lub znak nowej linii (pole w cudzysłowie; `update_or_create`
  nie waliduje) → `BadHeaderError` → 500 przy pobraniu etykiety. Fix:
  `django.utils.http.content_disposition_header()` albo `FileResponse(filename=…)`.
- Walidacja zakresów i długości (T16): wartości > 2^31−1 i za długie kody dają `DataError`
  na PostgreSQL (500), `OverflowError` z `int(float("1e999"))` nie jest łapany.
- `_client_ip` (`signals.py:38-48`) nie waliduje wyniku: przy `TRUSTED_PROXY_COUNT` większym
  niż realna liczba proxy wartość z `X-Forwarded-For` trafia do pola `inet` → `DataError`
  w sygnale logowania (500) i spoofowany klucz limitera. Fix: `ipaddress.ip_address()`
  z fallbackiem na `REMOTE_ADDR`.
- Kod aplikacji w kontenerze jest zapisywalny przez użytkownika runtime (`Dockerfile:32-40`:
  `chown -R app:app /app` przed `USER app`) — RCE przez przyszły błąd parsera XLSX/PDF
  zyskałoby trwałość między restartami. Fix: `/app` root-owned, `chown` tylko `staticfiles`.
- `ADMINS` puste → brak alertów o 500 (T15); access log gunicorna zapisuje parametry
  zapytań (`?q=`, `?material=`) — bez danych osobowych; `healthz` zdradza stan bazy
  (status 503) — standard; Django 5.2 bez przypiętej wersji łatki (dobre dla łatek
  bezpieczeństwa, złe dla reprodukowalności).

### 3.4 Pilne poprawki z audytu (kandydaci na pierwsze historyjki backlogu)

1. **R1** — blokada edycji superusera przez rolę Administrator (jeden warunek + test). Mała zmiana, wysoka waga.
2. **R3** — `max_value` dla palet i ilości w formularzach, limit palet na wiersz i HU na plik w imporcie (kilka linii + test).
3. **R2** — compose z `${VAR:?}`; `prod.py` odrzuca słabe/zaślepkowe klucze; `seed_demo` bez `DEMO_MODE` nie tworzy kont demo z działającym hasłem; testy.
4. **T1/R4** — obsługa uszkodzonego XLSX, limit rozmiaru po rozpakowaniu, `defusedxml` w `requirements.txt`, limit wierszy zawsze; testy.
5. **R7 + R5** — retencja dziennika logowań (komenda + harmonogram), `clearsessions` w harmonogramie, limiter na `/demo/` i `/login/demo/`; `RODO.md` v0.1.
6. **R10** — `dependabot.yml`, pip-audit blokujący na PR, `permissions: contents: read` w `ci.yml`, `SECURITY.md`.

Pozostałe (reszta R5, R6, R8, R9, T16) wymagają decyzji PO o zakresie i koszcie (sekcja 5).

### 3.5 Kandydaci do listy wyjątków (wymagają świadomej akceptacji PO w `RYZYKA.md`)

- Publiczne demo z rolą Operator dla anonimowych, logowanie na GET `/demo/`, jawne hasło demo (R5).
- Brak 2FA i `/admin/` z internetu do czasu realnego wdrożenia (R6).
- Backup tylko lokalny do czasu wdrożenia u klienta (R9).

---

## 4. [BA] Pytania do Product Ownera — seria 1

Maksymalnie 5 naraz, zgodnie z procesem. Odpowiedzi trafią do `docs/analiza/ZALOZENIA.md`
(potwierdzone) lub `WIZJA.md`.

1. **Cel repozytorium na najbliższe miesiące:** portfolio/rekrutacja, realne wdrożenie
   u klienta, czy jedno i drugie? Od tego zależy, czy inwestujemy najpierw w RODO, 2FA,
   backup off-site i runbook (wdrożenie), czy w widoczny proces i dokumenty (portfolio).
2. **Zakres:** czy „poza zakresem” z docs/01 (ERP, zwroty/anulowanie WZ, blokada palet po
   terminie, rezerwacje, wiele magazynów, atrybuty logistyczne) pozostaje poza zakresem?
   Czy jest lista funkcji, które chcesz dodać w pierwszej kolejności?
3. **Priorytet bezpieczeństwa:** zgadzasz się, żeby poprawki z sekcji 3.4 (R1–R4, R7, R10)
   były pierwszymi historyjkami, przed nowymi funkcjami? Czy coś z 3.5 akceptujesz jako
   wyjątek (publiczny Operator w demo, brak 2FA do wdrożenia, backup lokalny)?
4. **Publiczne demo:** zostaje w obecnej formie (anonimowy Operator, reset przyciskiem)?
   Akceptujesz ryzyko niedostępności demo (R3–R5), czy chcesz limitów (rate limit, mniejsze
   importy, reset tylko z harmonogramu)?
5. **Konwencje i porządek:** (a) commity po angielsku w Conventional Commits, dokumentacja
   po polsku — potwierdzasz? (b) istniejące docs/01–07 przenieść do `docs/analiza/` pod
   nowymi nazwami (z przekierowaniem linków w README), czy zostawić i tylko linkować?
   (c) próg pokrycia testami w CI: 80 % ogółem i 90 % dla `services.py` (dziś 81 % / 91 %)?

---

## 5. Decyzje potrzebne od PO (poza pytaniami)

| ID | Decyzja | Domyślne założenie, jeśli brak odpowiedzi (zapisane w ZALOZENIA.md) |
|---|---|---|
| DEC-1 | Reorganizacja `docs/` do struktury z sekcji 2 promptu | przenieść z przekierowaniami; nic nie usuwać |
| DEC-2 | Skany bezpieczeństwa blokujące na PR (koszt minut Actions) | bandit + pip-audit + gitleaks blokujące na PR; trivy i semgrep tygodniowo doradczo |
| DEC-3 | Próg pokrycia | 80 % ogółem, 90 % `services.py` |
| DEC-4 | Hasher argon2 i 2FA | argon2 tak (bez wpływu na UX); 2FA po decyzji o wdrożeniu |
| DEC-5 | Retencja dziennika logowań | 90 dni |
| DEC-6 | Publiczne demo: limity | rate limit per IP na ścieżkach operatora, reset tylko z harmonogramu |

---

## 6. Metoda i zakres audytu

**Przeczytano w całości:** `README.md`, `CLAUDE.md`, `COOLIFY.md`, `LICENSE`, `docs/01–07`,
`docs/wdrozenie.md`, `docs/pitfalls/*`, `docs/operator/TEMPLATE.md` (+1 przykład),
`config/**`, `warehouse/{models,services,views,scanner_views,demo,forms,imports,
stock_import,receipt_import,issue_import,exports,labels,documents,admin,roles,signals,
urls,context_processors,apps,pdf_fonts}.py`, `management/commands/seed_demo.py`,
migracja `0002`, szablony `base.html`, `login.html`, `scanner/base.html`, `403.html`,
`Dockerfile`, `entrypoint.sh`, oba `docker-compose*.yml`, `Caddyfile`, `.env*.example`,
`.github/workflows/*`, `scripts/*`, `.claude/**`, `pyproject.toml`, `requirements*.txt`,
`.gitignore`, `.dockerignore`, `.gitleaksignore`, `.gitattributes`.
Pozostałe szablony i JS: grep pod kątem `|safe`, `mark_safe`, `autoescape`, `csrf`, inline
handlerów, zewnętrznych URL-i.

**Uruchomiono:** ruff (check, format), mypy (pełny zakres), pytest + coverage, bandit
(wszystkie poziomy), pip-audit (prod), `check`, `check --deploy`, `makemigrations --check`;
skrypt weryfikujący R1 i T1 w Django test client (SQLite); lekki skan całej historii
gita pod kątem wzorców sekretów (klucze AWS/GitHub/Slack/OpenAI-podobne, klucze prywatne,
`DJANGO_SECRET_KEY=`, `POSTGRES_PASSWORD=`) — jedyne trafienie to klucz testowy CI w `ci.yml`;
w historii nigdy nie było plików `.env`, `.pem`, `.key`.

**Niezależny drugi przegląd bezpieczeństwa** (osobny agent z własnym kontekstem, tylko odczyt,
bez znajomości wstępnych wniosków poza listą ośmiu ustaleń do pominięcia): dostarczył 11
dodatkowych ustaleń (R3, część R2, R4, R5, R10 i punkty „poza listą”); każde sprawdzono w kodzie
(numery linii) przed wpisaniem; jego mapę tras zweryfikowano z `urls.py` i dekoratorami
(załącznik A).

**Nie sprawdzono:** trivy na obrazie, gitleaks na historii (tylko lekki skan wzorców), semgrep,
pip-audit dla Playwright (narzędzie do nagrywania filmu), testy na PostgreSQL, testy mutacyjne, dynamiczny test publicznego
demo (nie atakujemy cudzej instancji bez zgody), jakość UX na urządzeniu mobilnym,
zawartość filmów/zrzutów, konfiguracja samego Coolify/serwera (poza repo).

---

## Załącznik A — mapa tras i ról (pokrycie kontroli dostępu)

Legenda: **P** publiczne, **L** `@login_required` (każda rola), **O** `@operator_required`
(Operator i Administrator), **A** `@admin_required`. GET = odczyt, POST = zmiana stanu.

| Rola | Trasy |
|---|---|
| P | `healthz`; `login/` (POST limitowany 10/5 min/IP); `login/demo/` (POST, tylko `DEMO_MODE`, **bez limitu**); `demo/` (**GET loguje**, tylko `DEMO_MODE`, bez limitu); `logout/` (POST) |
| L | `/` pulpit; `materialy/`; `lokalizacje/`, `lokalizacje/etykiety/` (**PDF bez limitu**), `lokalizacje/<pk>/etykieta/`; `raporty/`, `raporty/lokalizacje/`, `raporty/material/` (limit 500); `hu/` (bez paginacji), `hu/etykiety/` (limit 200), `hu/<pk>/`, `hu/<pk>/etykieta/`; `wydania/`, `wydania/<pk>/`, `wydania/<pk>/pdf/`; `spis/`, `spis/<pk>/`; `stany/`, `stany/lokalizacje/`, `stany/eksport/<fmt>/`; `ruchy/` (limit 500), `ruchy/eksport/<fmt>/` (bez limitu); `powitanie/ukryj/` (POST) |
| O | skaner: 8 ekranów i 8 endpointów JSON (`require_GET`/`require_POST`); `materialy/nowy/`; `lokalizacje/nowa/`, `lokalizacje/import/`; `przyjecie/` (**bez limitu palet**), `przyjecie/import/`; `hu/<pk>/alokacja/`, `hu/<pk>/korekta/`; `wydania/nowy/`, `wydania/import/`, `wydania/<pk>/pozycja/`, `…/pozycja/<id>/usun/` (pozycja zawężona do dokumentu), `…/realizuj/`, `…/spakuj/`, `…/wyslij/`; `inwentaryzacja/`; `przepakowanie/`; `spis/nowy/`, `spis/<pk>/zapisz/`, `spis/<pk>/zamknij/`; `stany/import/`; `demo/przywroc/` (POST, tylko `DEMO_MODE`) |
| A | `uzytkownicy/`, `uzytkownicy/dziennik/` (paginacja 100), `uzytkownicy/nowy/` (może nadać rolę Administrator), `uzytkownicy/<pk>/` (konta demo → 403; **brak strażnika `is_superuser`** — R1); `hu/<pk>/dostawa/` |
| superuser | `admin/` (tylko gdy nie `DEMO_MODE`; edycja i usuwanie ruchów oraz dziennika logowań) |

Wniosek: wszystkie 47 widoków i 16 endpointów skanera mają dekorator; zmiany stanu tylko na
POST (GET → render albo redirect); jedyna mutacja na GET to `/demo/`. Brak kontroli
obiektowej jest zgodny z założeniem jednego magazynu (Z-06). Endpointy do testu „brak
dostępu dla każdej roli” (wymóg sekcji 6 promptu) — dziś 35 asercji w testach; brakuje
systematycznej macierzy rola × trasa.
