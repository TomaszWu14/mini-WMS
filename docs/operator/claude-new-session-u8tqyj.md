# docs+ci: proces BA/DEV/SEC — audyt, dokumentacja, pipeline CI — instrukcja dla operatora

| | |
|---|---|
| Branch | `claude/new-session-u8tqyj` (nazwa techniczna sesji Claude) |
| PR | #23 (draft) |
| Data | 2026-10-16 |
| Ryzyko | średnie — pięć poprawek bezpieczeństwa zmienia zachowanie (US-001…US-005; US-003 — wdrożenie bez sekretów nie wstaje); obraz Dockera bez pip/setuptools/wheel; nowe joby blokujące w CI |

## 1. Co zmieniono
- **Zmiany widoczne dla użytkowników:**
  - (US-001) Administrator, który nie jest superuserem, nie może już edytować konta superusera ani
    konta z dostępem do panelu `/admin/` — dostaje stronę „Brak uprawnień”, a na liście użytkowników
    zamiast „Edytuj” widzi kreskę. Hasło superusera zmienia superuser (`/admin/` albo
    `python manage.py changepassword <login>` w kontenerze).
  - (US-002) Przyjęcie: najwyżej 500 palet i 1 000 000 sztuk na raz — powyżej formularz pokazuje błąd.
    Import przyjęć: najwyżej 2 000 palet w pliku; import stanów: najwyżej 2 000 wierszy. Plik ponad
    limit jest odrzucany w całości z komunikatem „Podziel plik; nic nie zapisano”. Liczby spoza
    zakresu w pliku dają komunikat przy wierszu zamiast błędu serwera.
  - (US-004) Import XLSX: plik, który nie jest prawdziwym XLSX (np. CSV z rozszerzeniem `.xlsx`)
    albo jest uszkodzony, daje komunikat „Plik nie jest poprawnym XLSX…” zamiast błędu serwera.
    XLSX, który po rozpakowaniu przekracza 50 MB, jest odrzucany. Każdy import (lokalizacje,
    stany, przyjęcia, wydania) obejmuje najwyżej 10 000 wierszy także poza demo; w demo — 500
    jak dotąd. W XLSX puste wiersze wliczają się do limitu, a kolumny od 51. są pomijane
    (importy używają kilku pierwszych). Zaszyfrowany XLSX jest odrzucany.
  - (US-005) Demo: więcej niż 10 wejść (osoby niezalogowanej) przez `/demo/` lub „Wejdź jako demo” w 5 minut z jednego
    adresu daje stronę „Zbyt wiele wejść do demo…” (HTTP 429). W trybie demo dziennik logowań nie
    pokazuje IP ani przeglądarki. Na produkcji dziennik działa jak dotąd, ale wpisy starsze niż
    90 dni są usuwane.
- **Zmiany dla administratora infrastruktury (US-005):** nowa komenda `python manage.py
  purge_login_events`; przy każdym starcie kontenera w logach pojawiają się linie
  „Usunięto N wpisów dziennika logowań…” i (cicho) `clearsessions`. Do dodania w Coolify dwa
  Scheduled Tasks — COOLIFY.md §10a.
- **Zmiany dla administratora infrastruktury (US-003):**
  - Produkcja (`DJANGO_DEBUG=0`) nie startuje, gdy `DJANGO_SECRET_KEY` ma mniej niż 50 znaków, jest
    zaślepką (`zmien-mnie-w-produkcji`, `YOUR_DJANGO_SECRET_KEY_HERE`) albo zaczyna się od
    `django-insecure-`. W logach kontenera: `ImproperlyConfigured: Ustaw DJANGO_SECRET_KEY…`.
    PO potwierdził, że klucze w Coolify (demo i produkcja) spełniają próg (Z-36).
  - Wariant prywatny `docker-compose.yml` (LAN/Caddy) nie ma już wartości domyślnych
    `admin` / `wms` / `zmien-mnie-w-produkcji`: bez `DJANGO_SECRET_KEY`, `DJANGO_SUPERUSER_PASSWORD`
    i `POSTGRES_PASSWORD` w `.env` polecenie `docker compose up` kończy się błędem
    „required variable … is missing”. Istniejąca baza: `POSTGRES_PASSWORD` w `.env` musi być
    równe dotychczasowemu hasłu (domyślnie było `wms`), inaczej `web` nie połączy się z bazą.
  - `entrypoint.sh` przy **pierwszym** zakładaniu superusera odrzuca hasło `admin`, zaślepkę
    `YOUR_…` i hasła niespełniające walidatorów Django — kontener kończy pracę z komunikatem
    `DJANGO_SUPERUSER_PASSWORD odrzucone: …`.
  - **Instalacje LAN sprzed tej zmiany:** jeśli istniejący superuser nadal ma hasło `admin`
    (dawna wartość domyślna), kontener **nie wystartuje** i wypisze polecenie naprawy:
    `docker compose run --rm --entrypoint python web manage.py changepassword <login>`, potem
    `docker compose up -d`. Hasło bazy równe zaślepce `YOUR_POSTGRES_PASSWORD_HERE` też blokuje start.
  - `python manage.py seed_demo` bez `DEMO_MODE=1` kończy się błędem i nie zakłada kont demo.
    Instancja demo (`DEMO_MODE=1`, zadanie `reset-demo`) działa bez zmian.
- **Dokumentacja procesu i produktu** (wszystko w statusie „szkic 0.1 — do akceptacji PO”):
  `docs/AUDYT.md` (stan wyjściowy, ryzyka R1–R10, pytania), `CONTRIBUTING.md` (role, 7 kroków,
  Definition of Ready/Done, konwencje, narzędzia), `SECURITY.md`, `CHANGELOG.md`, szablony issue
  i PR, `CODEOWNERS`, `docs/analiza/*` (wizja, interesariusze, procesy, wymagania FR/NFR/SEC,
  backlog US-001…US-049, słownik, założenia Z-01…Z-34, śledzenie), `docs/architektura/*` (C4,
  model danych, API skanera, ADR), `docs/bezpieczenstwo/*` (klasyfikacja danych, threat model
  STRIDE, rejestr ryzyk i wyjątków, RODO, checklista ASVS), `docs/testy/STRATEGIA_TESTOW.md`,
  `docs/operacje/RUNBOOK.md`. README ma nową sekcję z mapą dokumentów.
- **CI (`ci.yml`, ADR-0001):** lint → mypy na całym kodzie → pytest z progiem pokrycia (80 %
  ogółem, 90 % `services.py`; SQLite i PostgreSQL) → bandit + semgrep → pip-audit → gitleaks
  (pełna historia) → build obrazu, smoke test i skan trivy (HIGH/CRITICAL z poprawką blokuje).
  Raporty jako artefakty. Akcje przypięte do SHA, token tylko do odczytu. `security.yml`
  co tydzień, doradczo. Dependabot (pip, akcje, docker) i `.pre-commit-config.yaml`.
- **Obraz Dockera:** oba etapy usuwają pip, setuptools i wheel po instalacji zależności —
  gunicorn i `manage.py` ich nie używają, a skan trivy wykazał podatności tylko w tych
  narzędziach. Skutek operacyjny: w kontenerze nie zadziała `pip install`; pakiety wchodzą
  wyłącznie przez rebuild.
- **Hasła (US-008):** nowe i zmieniane hasła są zapisywane algorytmem argon2. Istniejące konta
  logują się jak dotąd; przy pierwszym udanym logowaniu hasło przechodzi na argon2 (bez działania
  użytkownika). Logowanie trwa ułamek sekundy dłużej. Nowa zależność `argon2-cffi` w obrazie.
- **Testy (US-007):** macierz dostępu rola × trasa — tylko testy, bez zmian w działaniu aplikacji.
- **Kod:** dwa komentarze `# nosemgrep` z uzasadnieniem (`seed_demo.py` — `LOCK TABLE` z nazwami
  tabel z modeli; test wyścigu — celowe `sleep`); komentarz w `scanner.js` (numer pułapki).
  `pyproject.toml`: `coverage` pomija też `tests_*.py` i ma `fail_under = 80`.

## 2. Kroki do ręcznego sprawdzenia

| # | Konto (rola) | Gdzie | Co zrobić | Oczekiwany wynik |
|---|---|---|---|---|
| 1 | — | GitHub → PR #23 → Checks | otworzyć ostatni przebieg `CI` | 8 jobów zielonych; artefakty `reports-coverage`, `reports-sast`, `reports-sca`, `reports-image` do pobrania |
| 2 | — | GitHub → Actions → `security` → Run workflow | uruchomić ręcznie | 4 joby kończą się sukcesem (doradcze), artefakty `weekly-*` |
| 3 | — | GitHub → podgląd `README.md` | kliknąć kilka linków z sekcji „Proces zespołowy” | dokumenty otwierają się, diagramy Mermaid renderują się (C4 w ARCHITEKTURA, DFD w THREAT_MODEL) |
| 4 | `demo_operator` (Operator) | demo po deployu: `/skaner/` → Rozmieszczanie | zeskanować paletę i lokalizację | działa jak przed zmianą (obraz bez pip nie wpływa na aplikację) |
| 6 | konto z rolą Administrator (nie superuser) | `/uzytkownicy/` | spojrzeć na wiersz superusera; wejść ręcznie na `/uzytkownicy/<id superusera>/` | brak przycisku „Edytuj”; strona „Brak uprawnień” |
| 7 | `demo_operator` (Operator) | `/przyjecie/` | wpisać 501 palet | błąd przy polu „Liczba palet”; żadna paleta nie powstaje |
| 8 | `demo_operator` (Operator) | `/przyjecie/` | 10 szt. na 2 palety | przyjęcie przechodzi jak dotąd |
| 5 | admin infrastruktury | Coolify → kontener `web` → Logs | po deployu sprawdzić start | migracje bez zmian, `Startuję gunicorn`, brak błędów o `pip` ani `ImproperlyConfigured` |
| 9 | admin infrastruktury | Coolify (demo) → kontener `web` → Terminal | `python manage.py seed_demo --reset` | dane demo przywrócone jak dotąd |
| 10 | admin infrastruktury | dowolna maszyna z Dockerem, katalog repo, bez `.env` | `docker compose config` | błąd „required variable DJANGO_SECRET_KEY is missing…” |
| 12 | Operator | `/lokalizacje/import/` | wgrać plik CSV przemianowany na `.xlsx` | komunikat „Plik nie jest poprawnym XLSX…”, brak zmian |
| 13 | Operator | `/stany/import/` | wgrać zwykły XLSX z kilkoma wierszami | import jak dotąd |
| 14 | admin infrastruktury | Coolify (prod i demo) → Scheduled Tasks | dodać `purge-login-events` i `clearsessions` wg COOLIFY.md §10a, uruchomić ręcznie „Execute now” | log „Usunięto N wpisów…”, brak błędów |
| 15 | anonim (przeglądarka prywatna) | demo: `/demo/` | odświeżyć 11 razy w ciągu minuty (wylogowując się) | 11. raz: „Zbyt wiele wejść do demo…” |
| 16 | Administrator | demo: `/uzytkownicy/dziennik/` | spojrzeć na nowe wpisy | kolumny IP i przeglądarka puste |
| 17 | dowolne konto | `/login/` po deployu | zalogować się dotychczasowym hasłem | logowanie działa; w `/admin/` → Users hash zaczyna się od `argon2` |
| 11 | admin infrastruktury | instalacja LAN | przed aktualizacją zalogować się jako superuser hasłem `admin` | jeśli się da — zmienić hasło przed deployem (inaczej kontener nie wstanie, patrz §1) |

## 3. Checklista wdrożenia

### Migracje — na KAŻDEJ bazie
| Baza | Polecenie | Wykonano (kto, kiedy) |
|---|---|---|
| dev (lokalny SQLite) | `python manage.py migrate` | ☐ nie dotyczy — brak migracji |
| test (baza testów) | tworzona automatycznie przez `pytest` / `manage.py test` | ☐ testy zielone (305 passed, 2 skipped lokalnie; CI na PR) |
| demo (jeśli wdrożone) | automatycznie w `entrypoint.sh` przy deployu | ☐ nie dotyczy — brak migracji |
| prod (PostgreSQL, Coolify) | automatycznie w `entrypoint.sh` przy deployu | ☐ nie dotyczy — brak migracji |

Nowe migracje w tym branchu: brak. Odwracalne: nie dotyczy.
Sprawdzenie: `python manage.py showmigrations warehouse` — wszystkie `[X]`.

### Zmienne środowiskowe
| Zmienna | Nowa / zmieniona / usunięta | Wartość prod | Ustawiona w Coolify |
|---|---|---|---|
| `DJANGO_SECRET_KEY` | zmieniona (wymóg: ≥ 50 losowych znaków) | bez zmian — już spełnia (Z-36) | ☐ sprawdzić na demo i prod przed deployem |
| `DJANGO_SUPERUSER_PASSWORD` | zmieniona (wariant prywatny: wymagana; nowe konto: walidatory Django) | bez zmian | ☐ nie dotyczy (Coolify już wymaga) |
| — (zależność) | nowe: `defusedxml==0.7.1`, `argon2-cffi==25.1.0` w `requirements.txt` | instalowane w obrazie | ☐ nie dotyczy (rebuild obrazu) |
| `POSTGRES_PASSWORD` | zmieniona (wariant prywatny: wymagana, bez domyślnego `wms`) | bez zmian | ☐ nie dotyczy (Coolify już wymaga); LAN: wpisać do `.env` dotychczasowe hasło |

Zaktualizowano też: `.env.example` — nie dotyczy, `.env.docker.example` — nie dotyczy (już ma
wszystkie trzy zmienne), `COOLIFY.md` — nie dotyczy (wariant Coolify już wymagał sekretów).

### Przed i po deployu
- ☐ CI zielone na PR (`ci.yml`; `security.yml` uruchomiony ręcznie raz)
- ☐ backup bazy prod sprzed deployu — nie dotyczy (brak migracji); zalecany mimo to, bo zmienia się obraz
- ☐ po deployu: `/healthz` zwraca `{"status": "ok"}`; logowanie; lista HU; jeden skan na `/skaner/`
- ☐ w ustawieniach repo: włączyć *Private vulnerability reporting* (SECURITY.md) i ochronę gałęzi `main` (RYZYKA RR-21)

## 4. Plan wycofania
1. Kod: Coolify → zasób → **Deployments** → poprzedni deployment → **Redeploy**
   (albo revert PR na `main`). Poprzedni obraz zawiera pip — bez wpływu na działanie.
2. Migracje: nie dotyczy.
3. Zmienne środowiskowe: nic do cofania. Jeśli po deployu kontener nie wstaje z
   `ImproperlyConfigured: Ustaw DJANGO_SECRET_KEY…`, ustawić nowy klucz
   (`python -c "import secrets; print(secrets.token_urlsafe(64))"`) i zrobić redeploy — zmiana klucza
   wyloguje użytkowników, dane zostają.
4. Weryfikacja po wycofaniu: `/healthz`, logowanie, lista HU.
