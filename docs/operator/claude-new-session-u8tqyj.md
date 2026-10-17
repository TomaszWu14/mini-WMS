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
- **Indeks dziennika logowań (US-051):** migracja `0012` przy deployu (automatycznie w `entrypoint.sh`) — **wymaga
  zgody PO przed wdrożeniem na produkcję**. Bez zmiennych i zmian w interfejsie.
- **Numeracja palet (US-050):** import przyjęć/stanów zapisuje się hurtem — inne przyjęcia nie czekają na koniec pliku.
  Numery HU bez zmian w formacie, nadal kolejne. Bez migracji i zmiennych.
- **Blokady palet (US-053):** zmiana wewnętrzna — równoległe realizacje WZ nie kończą się błędem 500; bez migracji,
  zmiennych i zmian w interfejsie.
- **Pozycje WZ (US-052):** przy pozycji, z której już coś pobrano, nie ma przycisku „Usuń” (pobrany towar jest w
  historii ruchów); usunięcie ostatniej niepobranej pozycji zamyka dokument. Bez migracji i zmiennych.
- **Dziennik audytowy (US-022):** Użytkownicy → „🗂 Dziennik audytowy” pokazuje, kto komu zmienił rolę, hasło,
  status lub 2FA i kiedy odmówiono zmiany (także zmiany przez `/admin/` i `manage.py`). Wpisy starsze niż rok usuwa
  istniejący Scheduled Task `purge-login-events`. Logi kontenera nie zawierają haseł ani tokenów. Migracja `0011`.
- **Zależności i obrazy (US-020):** obraz `web` instaluje pakiety wyłącznie z locka z hashami; obrazy `postgres`
  i `caddy` w compose są przypięte digestem (te same wersje co dotąd: `16-alpine`, `2-alpine`). Coolify zbuduje
  obraz jak zwykle. Aktualizacje obrazów i pakietów przychodzą wyłącznie przez PR Dependabota. Bez migracji i zmiennych.
- **Kontrola typów w CI (US-019):** dotyczy tylko procesu wytwórczego — nic do zrobienia przy wdrożeniu.
- **Wydania skanerem (US-018):** dokument WZ zamyka się po ostatnim pobraniu jak dotąd; równoczesne „Realizuj” w panelu
  i skaner na tym samym WZ nie kończą się już błędem serwera. Bez migracji i zmiennych.
- **Kod widoków (US-017):** `warehouse/views.py` rozbity na pakiet `warehouse/views/` — bez zmian w działaniu, adresach
  i uprawnieniach; nic do zrobienia przy wdrożeniu.
- **Demo (US-016):** znika przycisk „Przywróć dane demo” (i `POST /demo/przywroc/`). Przyjęcia i importy w demo
  odmawiają powyżej 2000 palet / 500 lokalizacji („Limit demo…”), zapisy powyżej 60 na 5 min z jednego IP → 429.
  **Akcja w Coolify (demo):** Scheduled Task `reset-demo` — Command zmienić na
  `python manage.py seed_demo --reset --keep-users` (dotąd `--reset` wylogowywał wszystkich). Bez migracji i zmiennych.
- **Listy i etykiety lokalizacji (US-015):** listy HU, lokalizacji, „Stan wg lokalizacji” i raport zajętości pokazują
  po 100 wierszy z przyciskami stron (filtry zostają). Lista lokalizacji ma pole kodu i wybór typu. „Drukuj etykiety”
  na liście lokalizacji drukuje lokalizacje z bieżącego filtra, najwyżej 200 — przy większej liczbie komunikat „Zawęź filtr”.
  Bez migracji i nowych zmiennych.
- **Adres IP za proxy (US-014):** jeśli proxy przekaże w `X-Forwarded-For` coś, co nie jest adresem IP, aplikacja
  użyje adresu połączenia (proxy) zamiast błędu przy logowaniu. Bez zmian dla poprawnej konfiguracji.
- **Walidacja danych (US-013):** każda ilość (korekta, pozycja WZ, przepakowanie, spis, skaner) najwyżej
  1 000 000, pojemność lokalizacji najwyżej 10 000 — powyżej komunikat przy polu. Importy: liczba typu `1e999`
  → „Wiersz N: nieprawidłowa liczba…”, za długi kod lokalizacji / numer HU / partia / referencja → wiersz
  pominięty z komunikatem. Stan jednej palety najwyżej 1 000 000. Etykiety z cudzysłowem lub polskimi znakami w kodzie pobierają się poprawnie.
- **Backup (US-012):** kontener `backup` ma teraz własny obraz (`docker/backup.Dockerfile`: PostgreSQL 16 +
  `age`, `rclone`, `curl`) — Coolify go zbuduje przy deployu. Bez nowych zmiennych działa jak dotąd (kopia
  lokalna, 7 dni), ale błąd `pg_dump` nie daje już fałszywego „OK”. Kopia poza serwerem włącza się po
  ustawieniu zmiennych z RUNBOOK §5.0 (klucz publiczny age, cel rclone, URL heartbeat).
- **Nagłówki bezpieczeństwa (US-011):** przeglądarka dostaje `Content-Security-Policy` i `Permissions-Policy`.
  Wygląd i działanie bez zmian. Gdyby po deployu coś na stronie przestało działać (np. przycisk nic nie
  robi), w konsoli przeglądarki będzie „Refused to execute… Content Security Policy” — wtedy ustawić
  w Coolify `DJANGO_CSP_REPORT_ONLY=1` i redeploy (tryb tylko raportowania), zgłosić stronę. HSTS bez `preload`.
- **2FA dla Administratora (US-010):** na **Użytkownicy → Moja weryfikacja dwuetapowa** (`/2fa/`)
  Administrator skanuje kod QR aplikacją (Google Authenticator, Aegis…) i wpisuje pierwszy kod. Od
  tej pory po haśle aplikacja pyta o 6-cyfrowy kod (także przed `/admin/`). Włączenie jest dobrowolne;
  Operator i Podgląd logują się jak dotąd. Utrata telefonu: RUNBOOK §8.3b (`manage.py reset_2fa`).
- **Blokada konta (US-009):** po 10 nieudanych logowaniach w 15 minut na to samo konto (z dowolnych
  adresów) kolejne próby — także z poprawnym hasłem — kończą się komunikatem „Zbyt wiele nieudanych prób
  logowania na to konto. Spróbuj ponownie za 15 minut.” Inne konta działają. W dzienniku logowań
  pojawia się rodzaj „Zablokowana próba”. Blokada działa też na `/admin/login/`. Konta demo (przy
  `DEMO_MODE`) nie są blokowane. Limity są teraz wspólne dla wszystkich procesów serwera (wcześniej ~3× luźniejsze). Odblokowanie ręczne: RUNBOOK §8.3a.
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
| 18 | Administrator | `/2fa/` | zeskanować QR, wpisać kod; wylogować się i zalogować | po haśle ekran „Weryfikacja dwuetapowa”; po kodzie pełny dostęp |
| 19 | superuser | kontener `web` → Terminal | `python manage.py reset_2fa <login>` | „Usunięto 1 urządzeń 2FA…”; logowanie samym hasłem |
| 20 | `demo_operator` na telefonie | demo przez HTTPS: `/skaner/rozmieszczanie/` | „Skanuj aparatem”, zeskanować etykietę palety | kamera startuje, kod odczytany (US-011 kryt. 3) |
| 21 | dowolne | dowolna strona → narzędzia deweloperskie → Konsola | przejść kilka ekranów | brak komunikatów „Content Security Policy” |
| 22 | admin infrastruktury | Coolify → `backup` → Logs (po ustawieniu §5.0) | Restart kontenera `backup` | `OK -> /backups/wms-…`, `off-site OK -> offsite:…`; zielony ping w Healthchecks |
| 23 | PO | komputer z kluczem prywatnym | pobrać plik `.age` z bucketu, `age -d -i miniwms-backup.key … > kopia.sql.gz`, `gunzip -t kopia.sql.gz` | odszyfrowanie i test OK; wpis w RUNBOOK §5.4 |
| 24 | Operator | `/hu/<id>/korekta/` | wpisać nową ilość 2000000 | błąd przy polu „Nowa ilość”, stan bez zmian |
| 25 | Podgląd | `/lokalizacje/` (ponad 200 lokalizacji) | „🏷 Drukuj etykiety” bez filtra; potem wybrać typ / wpisać początek kodu i powtórzyć | najpierw komunikat „Wybrano N lokalizacji — limit… Zawęź filtr”; po zawężeniu PDF |
| 26 | Podgląd | `/hu/` (ponad 100 palet) | ustawić filtr statusu, przejść „Następna →” | strona 2 z tym samym filtrem; licznik „Strona 2 z N” |
| 27 | admin infrastruktury | Coolify (demo) → Scheduled Tasks → `reset-demo` | zmienić Command na `python manage.py seed_demo --reset --keep-users`, uruchomić ręcznie (Execute) przy zalogowanym demo w drugiej karcie | log „Dane demo zasiane.”; w drugiej karcie po odświeżeniu sesja trwa, dane w stanie początkowym |
| 28 | `demo_operator` | demo: baner | spojrzeć na żółty baner | brak przycisku „Przywróć dane demo” |
| 29 | `demo_operator` / Operator | skaner → Kompletacja zlecenia | pobrać całą ilość ostatniej pozycji | komunikat o wydaniu, zlecenie oznaczone jako zrealizowane; w panelu WZ „Zrealizowany” |
| 30 | Administrator | `/uzytkownicy/` → edycja konta Operatora | zmienić rolę i hasło, zapisać; otworzyć „Dziennik audytowy” | dwa wpisy (zmiana roli, zmiana hasła) z Twoim loginem; hasła nigdzie nie widać |
| 31 | admin infrastruktury | kontener `web` → Terminal | `python manage.py changepassword <login>` | w „Dzienniku audytowym” wpis „Zmiana hasła”, kto: `manage.py changepassword` |
| 32 | Operator | WZ z dwiema pozycjami | skanerem pobrać część pierwszej pozycji; w panelu spróbować usunąć obie | pierwsza bez przycisku „Usuń”; drugą da się usunąć |
| 17 | dowolne konto | `/login/` po deployu | zalogować się dotychczasowym hasłem | logowanie działa; w `/admin/` → Users hash zaczyna się od `argon2` |
| 11 | admin infrastruktury | instalacja LAN | przed aktualizacją zalogować się jako superuser hasłem `admin` | jeśli się da — zmienić hasło przed deployem (inaczej kontener nie wstanie, patrz §1) |

## 3. Checklista wdrożenia

### Migracje — na KAŻDEJ bazie
| Baza | Polecenie | Wykonano (kto, kiedy) |
|---|---|---|
| dev (lokalny SQLite) | `python manage.py migrate` | ☐ migracje `0009`, `0010`, `0011`, `0012` |
| test (baza testów) | tworzona automatycznie przez `pytest` / `manage.py test` | ☐ testy zielone (465 passed, 9 skipped lokalnie; CI na PR) |
| demo (jeśli wdrożone) | automatycznie w `entrypoint.sh` przy deployu (+ `createcachetable`) | ☐ `0009`–`0012` zastosowane; tabela `miniwms_cache` istnieje |
| prod (PostgreSQL, Coolify) | automatycznie w `entrypoint.sh` przy deployu (+ `createcachetable`) | ☐ `0009`–`0012` zastosowane; tabela `miniwms_cache` istnieje |

Nowe migracje w tym branchu: biblioteki `otp_totp` 0001–0003 (US-010, nowa tabela urządzeń 2FA) oraz
`warehouse/migrations/0009_loginevent_blocked_kind.py` i `0010_loginfailurecounter.py` (US-009; `0010` dodaje tabelę liczników) — tylko lista wyborów
`LoginEvent.kind`, bez zmian w danych. Odwracalna: tak (`python manage.py migrate warehouse 0008`).
`warehouse/migrations/0011_auditevent.py` (US-022) — nowa tabela dziennika audytowego, bez zmian w istniejących danych;
odwracalna (`python manage.py migrate warehouse 0010` — **usuwa wpisy audytu**, przed cofnięciem backup).
`warehouse/migrations/0012_loginevent_created_idx.py` (US-051) — tylko indeks na `warehouse_loginevent`, bez zmian
w danych; na czas budowy (przy tysiącach wierszy — ułamek sekundy) logowania czekają na zapis do dziennika.
Odwracalna: `python manage.py migrate warehouse 0011` (usuwa sam indeks).
Poza migracjami: tabela cache `miniwms_cache` (`createcachetable`, idempotentne, w `entrypoint.sh`).
Sprawdzenie: `python manage.py showmigrations warehouse` — wszystkie `[X]`.

### Zmienne środowiskowe
| Zmienna | Nowa / zmieniona / usunięta | Wartość prod | Ustawiona w Coolify |
|---|---|---|---|
| `DJANGO_SECRET_KEY` | zmieniona (wymóg: ≥ 50 losowych znaków) | bez zmian — już spełnia (Z-36) | ☐ sprawdzić na demo i prod przed deployem |
| `DJANGO_SUPERUSER_PASSWORD` | zmieniona (wariant prywatny: wymagana; nowe konto: walidatory Django) | bez zmian | ☐ nie dotyczy (Coolify już wymaga) |
| — (zależność) | nowe: `defusedxml==0.7.1`, `argon2-cffi==25.1.0`, `django-otp==1.7.4` w `requirements.txt` | instalowane w obrazie | ☐ nie dotyczy (rebuild obrazu) |
| `BACKUP_AGE_RECIPIENT`, `BACKUP_RCLONE_REMOTE`, `BACKUP_HEARTBEAT_URL`, `BACKUP_OFFSITE_KEEP_DAYS`, `BACKUP_OFFSITE_PRUNE`, `RCLONE_CONFIG_OFFSITE_*` | nowe, opcjonalne (US-012) | wg RUNBOOK §5.0 (klucz publiczny, cel off-site w katalogu, URL Healthchecks; S3: klucz bez prawa usuwania + lifecycle 30 dni) | ☐ ustawić w zasobie prod i demo; klucz prywatny — tylko offline u PO |
| `DJANGO_CSP_REPORT_ONLY` | nowa, opcjonalna (domyślnie `0` = CSP egzekwowana) | nie ustawiać | ☐ nie dotyczy (tylko awaryjnie `1`) |
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
2. Migracje: przed redeployem poprzedniej wersji `python manage.py migrate otp_totp zero` (usuwa urządzenia 2FA)
   i `python manage.py migrate warehouse 0008` (cofa `0012`, `0011`, `0010` i `0009`; `0011` usuwa dziennik audytowy —
   wcześniej backup) w kontenerze `web`
   (wpisy „Zablokowana próba” zostaną w tabeli z kodem `BLOCKED` — stara wersja pokaże sam kod). Tabelę
   `miniwms_cache` można zostawić.
3. Zmienne środowiskowe: nic do cofania. Jeśli po deployu kontener nie wstaje z
   `ImproperlyConfigured: Ustaw DJANGO_SECRET_KEY…`, ustawić nowy klucz
   (`python -c "import secrets; print(secrets.token_urlsafe(64))"`) i zrobić redeploy — zmiana klucza
   wyloguje użytkowników, dane zostają.
4. Weryfikacja po wycofaniu: `/healthz`, logowanie, lista HU.
