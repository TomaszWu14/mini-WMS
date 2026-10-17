# Jak pracujemy — CONTRIBUTING

Repozytorium prowadzimy jak trzyosobowy zespół: **[BA]** analityk biznesowy, **[DEV]** developer,
**[SEC]** specjalista ds. bezpieczeństwa. Decyzje biznesowe, priorytety, akceptację ryzyk i wydań
podejmuje **Product Owner (PO)** — właściciel repozytorium. Każda zmiana zostawia ślad w repozytorium
(dokument, issue, commit, PR), tak aby osoba z zewnątrz widziała, co, dlaczego i kto zaakceptował.

Mapa dokumentów: [README](README.md) → `docs/analiza/` ([BA]) → `docs/architektura/` ([DEV]) →
`docs/bezpieczenstwo/` ([SEC]) → `docs/testy/`, `docs/operacje/`. Stan wyjściowy i ryzyka:
[docs/AUDYT.md](docs/AUDYT.md). Założenia do potwierdzenia: [docs/analiza/ZALOZENIA.md](docs/analiza/ZALOZENIA.md).

## 1. Role

| Rola | Odpowiada za | Nie robi |
|---|---|---|
| [BA] | pytania do PO, historyjki z kryteriami Given/When/Then, wymagania FR/NFR, priorytety MoSCoW, macierz śledzenia, odbiór funkcji z perspektywy użytkownika | nie pisze kodu; gdy wymaganie niejasne — pyta, nie zgaduje |
| [DEV] | projekt (ADR), implementacja w małych krokach, testy, lint/typy, środowisko (Docker, CI, migracje), README/API/CHANGELOG | nie zmienia zakresu bez BA/PO; nie wyłącza testów ani kontroli bezpieczeństwa |
| [SEC] | klasyfikacja danych, threat model (STRIDE), wymagania bezpieczeństwa jako historyjki, przegląd PR (OWASP/ASVS), SECURITY.md, rejestr ryzyk i wyjątków | ma **prawo weta**: PR z ryzykiem wysokim/krytycznym nie wchodzi bez poprawki albo zapisanej akceptacji ryzyka przez PO |
| PO | odpowiada na pytania BA, akceptuje zakres, ryzyka, wydania; **jedyna osoba wykonująca merge do `main`** | — |

Gdy PO nie odpowiada, [BA] przyjmuje bezpieczne, minimalne założenie i zapisuje je w
`docs/analiza/ZALOZENIA.md` jako „do potwierdzenia”.

## 2. Proces dla każdej funkcji (nie przeskakujemy kroków)

1. **[BA] Analiza** — pytania do PO (maks. 5 naraz), historyjka US-xxx w `docs/analiza/HISTORYJKI.md`
   (issue z szablonu „Historyjka użytkownika”), kryteria G/W/T, NFR, priorytet. Sprawdzenie Definition of Ready.
2. **[SEC] Wymagania bezpieczeństwa** — jakie dane i jakiej klasy; mini threat model dla nowego przepływu
   (`docs/bezpieczenstwo/THREAT_MODEL.md`); zabezpieczenia jako dodatkowe kryteria akceptacji; wpis w
   `docs/bezpieczenstwo/RYZYKA.md`, jeśli coś zostaje otwarte.
3. **[DEV] Projekt** — krótki opis; decyzja istotna lub trudno odwracalna → ADR w `docs/architektura/adr/`;
   zmiany modelu danych i API najpierw w `MODEL_DANYCH.md` / `API.md`, potem w kodzie.
4. **[DEV] Implementacja** — gałąź `feature/<US-id>-<krótka-nazwa>` (albo `fix/`, `security/`, `docs/`, `chore/`);
   małe commity w konwencji Conventional Commits; testy na każde kryterium, także bezpieczeństwa
   („rola X bez dostępu dostaje 403”).
5. **[SEC] Przegląd** — checklista z szablonu PR; wynik ✅ / ⚠️ / ❌ z uzasadnieniem; wyniki skanów CI
   ocenione — fałszywe alarmy oznaczone z uzasadnieniem (np. `# nosec` z komentarzem), nie wyciszane hurtowo.
6. **[BA] Odbiór** — kryteria sprawdzone punkt po punkcie, komunikaty i UX, aktualizacja `docs/analiza/SLEDZENIE.md`.
7. **PR i podsumowanie** — opis wg szablonu, wpis w `CHANGELOG.md` (`[Unreleased]`), dokument operatora
   `docs/operator/<branch>.md` wg `docs/operator/TEMPLATE.md`. **Merge tylko po akceptacji PO.**

Małe zmiany (1–2 pliki, bez auth/danych/uploadu): kroki 1–3 mogą być jednym akapitem w PR, ale
przegląd SEC i odbiór BA zostają.

## 3. Definition of Ready

Historyjka wchodzi do realizacji, gdy:
- cel i korzyść są jasne, a PO potwierdził zakres (albo założenie jest zapisane w ZALOZENIA.md),
- kryteria akceptacji są testowalne (każde da się zamienić w test automatyczny),
- [SEC] dopisał kryteria bezpieczeństwa i klasę danych,
- dane, role i uprawnienia są określone,
- zależności są znane i nic nie blokuje.

## 4. Definition of Done

Funkcja jest skończona, gdy:
- wszystkie kryteria akceptacji (funkcjonalne i bezpieczeństwa) są spełnione i pokryte testami,
- CI jest zielone: lint, typy, testy z progiem pokrycia, skany bezpieczeństwa bez nowych ustaleń
  wysokich/krytycznych,
- dokumentacja zaktualizowana (WYMAGANIA, API, MODEL_DANYCH, ADR jeśli dotyczy, CHANGELOG, SLEDZENIE,
  dokument operatora),
- przegląd [SEC] i odbiór [BA] zapisane w PR,
- brak sekretów, danych osobowych i danych produkcyjnych w repozytorium, testach i logach,
- PO zaakceptował.

## 5. Konwencje

- **Język:** dokumentacja po polsku; kod, nazwy, komunikaty commitów po angielsku. Teksty UI po polsku,
  komunikaty z numerem dokumentu/HU (`docs/pitfalls/views.md`).
- **Commity:** [Conventional Commits](https://www.conventionalcommits.org/): `feat:`, `fix:`, `docs:`,
  `test:`, `refactor:`, `chore:`, `security:`, `ci:`; w treści odwołanie do historyjki (`US-003`) lub ryzyka (`R2`).
- **Gałęzie:** `feature/US-003-prod-secret-key`, `fix/…`, `security/…`, `docs/…`; PR jako *draft* do czasu
  zielonego CI i przeglądów. `main` = auto-deploy produkcji (Coolify) — nie pushujemy do `main`.
- **Zmiany stanu magazynu** tylko przez `warehouse/services.py` (transakcja + `StockMovement`);
  widoki zmieniają stan tylko na POST; każdy widok ma dekorator roli (`docs/pitfalls/`).
- **Migracje** odwracalne, `makemigrations --check` bez zmian; migracje niszczące w dwóch wdrożeniach.
- **Wersje:** SemVer w `pyproject.toml`; wydanie = wpis w CHANGELOG z datą + tag `vX.Y.Z` (robi PO).
- **Asystent AI:** `CLAUDE.md`, `.claude/` (hooki: `guard.py` blokuje groźne komendy, `check.py`
  uruchamia ruff/mypy/pytest przed zakończeniem), `docs/pitfalls/`. Te same reguły obowiązują ludzi.

## 6. Narzędzia — jak uruchomić lokalnie

Instalacja: `pip install -r requirements-dev.txt` (lock z hashami dla Pythona 3.11, sprawdzony też na 3.13).
**Zmiana zależności:** edytuj `requirements.in` / `requirements-dev.in`, potem przegeneruj lock poleceniem z
nagłówka pliku `.txt` (`pip-compile --generate-hashes --allow-unsafe --strip-extras …`, pip-tools 7.4.1 z
`click<8.2`, Python 3.11). Plików `requirements*.txt` nie edytuj ręcznie ([ADR-0007](docs/architektura/adr/0007-lock-zaleznosci-pip-compile.md)). Uzasadnienie doboru narzędzi i reguły
blokowania w CI: [ADR-0001](docs/architektura/adr/0001-narzedzia-jakosci-i-bezpieczenstwa.md).

| Narzędzie | Polecenie | Blokuje CI? |
|---|---|---|
| Lint + format | `ruff check .` · `ruff format --check .` (napraw: `ruff format .`) | tak |
| Typy | `mypy warehouse config` | tak |
| Testy + pokrycie | `coverage run -m pytest -q` · `coverage report` (próg 80 %; `services.py` ≥ 90 %) | tak |
| Kontrole Django | `python manage.py check` · `python manage.py makemigrations --check --dry-run` · `DJANGO_DEBUG=0 DJANGO_SECRET_KEY=<losowy-50+> DJANGO_ALLOWED_HOSTS=x python manage.py check --deploy` | tak |
| SAST | `bandit -c pyproject.toml -r warehouse config manage.py -ll -ii` · `semgrep scan --config p/django --config p/owasp-top-ten --metrics=off --severity ERROR .` | tak (bandit ≥ średnie; semgrep ERROR) |
| SCA | `pip-audit -r requirements.txt` (blokuje) · `pip-audit -r requirements-dev.txt` (doradczo) | tak / nie |
| Sekrety | `gitleaks git --no-banner .` (historia) · `gitleaks dir .` (drzewo); fałszywe alarmy: `.gitleaksignore` z komentarzem | tak |
| Obraz | `docker build -t miniwms:local .` · `trivy image --severity HIGH,CRITICAL --ignore-unfixed miniwms:local` · `trivy config .` | tak (HIGH/CRITICAL z poprawką) / doradczo |
| Testy mutacyjne | `scripts/mutate.sh warehouse/services.py` (wolne, Linux/WSL) | nie |
| Pełny skan lokalny | `scripts/security_scan.sh` → `reports/security-<data>.md` | nie |

Pre-commit (ruff, gitleaks, końce linii, duże pliki, klucze prywatne): `pip install pre-commit && pre-commit install`;
jednorazowo na wszystkim: `pre-commit run --all-files`.

Testy w CI działają przez `pytest` z `config.settings.test` (szybki hasher), raz na SQLite i raz na
PostgreSQL 16 (`test-postgres`, w tym test wyścigu). Lokalnie: `pytest -q` ≈ 10 s.

## 7. Czego nie robimy

- Nie obniżamy wymagań bezpieczeństwa, żeby „przeszło” — eskalujemy do PO (rejestr ryzyk).
- Nie wyłączamy, nie pomijamy i nie kwarantannujemy testów ani reguł skanerów bez uzasadnienia w PR.
- Nie wpisujemy sekretów, danych osobowych ani danych produkcyjnych do repo, testów, fixture'ów, logów.
- Nie testujemy bezpieczeństwa (DoS, masowe importy) na publicznym demo — to wspólna instancja ([SECURITY.md](SECURITY.md)).
- Nie wdrażamy ani nie uruchamiamy migracji na danych produkcyjnych bez zgody PO.
