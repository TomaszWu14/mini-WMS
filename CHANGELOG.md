# Changelog

Wszystkie istotne zmiany w projekcie są opisane w tym pliku. Format: [Keep a Changelog](https://keepachangelog.com/pl/1.1.0/),
wersjonowanie: [SemVer](https://semver.org/lang/pl/). Numer wersji: `pyproject.toml`.
Wpisy dodaje autor PR w sekcji `[Unreleased]`; przy wydaniu PO nadaje numer i datę oraz tag w git.

## [Unreleased]

### Added
- Audyt stanu repozytorium z trzech perspektyw ([BA] / [DEV] / [SEC]) z top 10 ryzyk i mapą tras — `docs/AUDYT.md` (#23).
- Rejestr założeń „do potwierdzenia” — `docs/analiza/ZALOZENIA.md` (#23).
- Dokumentacja procesu zespołowego: `CONTRIBUTING.md` (Definition of Ready/Done, konwencje), `SECURITY.md`,
  szablony issue (historyjka, błąd, zagadnienie bezpieczeństwa) i PR, `CODEOWNERS`.
- Dokumentacja analityczna: `docs/analiza/` (WIZJA, INTERESARIUSZE, PROCESY, WYMAGANIA 0.1, HISTORYJKI, SLOWNIK, SLEDZENIE).
- Dokumentacja architektury: `docs/architektura/` (ARCHITEKTURA C4, MODEL_DANYCH, API skanera, ADR).
- Dokumentacja bezpieczeństwa: `docs/bezpieczenstwo/` (KLASYFIKACJA_DANYCH, THREAT_MODEL 0.1, RYZYKA, RODO 0.1, CHECKLISTA_ASVS).
- Strategia testów (`docs/testy/`) i runbook operacyjny (`docs/operacje/`).
- CI: pipeline lint → typy → testy z progiem pokrycia → SAST (bandit, semgrep) → SCA (pip-audit) → skan sekretów (gitleaks)
  → build obrazu → skan obrazu (trivy); wyniki jako artefakty; Dependabot; konfiguracja pre-commit
  (ADR-0001).

### Changed
- **US-007:** macierz dostępu rola × trasa w testach (`warehouse/tests_access_matrix.py`) — każda trasa ma test
  odmowy dla ról poniżej minimum i test dostępu; nowa trasa bez wpisu w macierzy zatrzymuje CI.
- CI uruchamia testy przez `pytest` z pomiarem pokrycia (próg 80 % ogółem, 90 % `warehouse/services.py`)
  i sprawdza typy w całym kodzie aplikacji (`mypy warehouse config`), nie tylko w trzech plikach.
- Cotygodniowe skany bezpieczeństwa (`security.yml`) zamiast miesięcznych; akcje GitHub przypięte do SHA.

### Security
- **US-001 / R1:** rola Administrator nie może już zmienić hasła, roli ani statusu konta superusera ani konta `is_staff` (403); lista
  użytkowników nie pokazuje dla takich kont przycisku „Edytuj”. Testy: `warehouse/tests_security.py`.
- **US-002 / R3:** przyjęcie i import przyjęć mają limity — najwyżej 500 palet i 1 000 000 sztuk na przyjęcie,
  2 000 palet na plik importu; plik ponad limit jest odrzucany przed jakimkolwiek zapisem, a liczby spoza zakresu
  dają komunikat zamiast błędu 500. Testy: `warehouse/tests_input_limits.py`.
- **US-003 / R2:** wdrożenie produkcyjne nie startuje z kluczem `DJANGO_SECRET_KEY` krótszym niż 50 znaków, z niską różnorodnością
  znaków ani ze znaną zaślepką; prywatny `docker-compose.yml` wymaga `DJANGO_SECRET_KEY`, `DJANGO_SUPERUSER_PASSWORD` i `POSTGRES_PASSWORD`
  (bez wartości domyślnych); `entrypoint.sh` nie zakłada superusera z hasłem `admin`, zaślepką ani hasłem
  odrzucanym przez walidatory Django, nie startuje, gdy istniejący superuser ma hasło `admin` albo hasło bazy jest zaślepką; `seed_demo` odmawia bez `DEMO_MODE=1`. Testy: `warehouse/tests_deploy_settings.py`, krok CI dla compose.
- **US-004 / R4:** import XLSX sprawdza sygnaturę ZIP i sumę rozmiarów po rozpakowaniu (najwyżej 50 MB) przed
  otwarciem pliku; uszkodzony plik daje komunikat zamiast błędu 500; limit 10 000 wierszy obowiązuje także poza demo (puste wiersze XLSX się wliczają, czytane jest najwyżej 50 kolumn,
  zaszyfrowane archiwa są odrzucane);
  `defusedxml` w zależnościach produkcyjnych. Testy: `warehouse/tests_imports_hardening.py`.
- **US-005 / R7, R5:** `manage.py purge_login_events` usuwa dziennik logowań starszy niż 90 dni (`--days N`); obie komendy
  sprzątające (`purge_login_events`, `clearsessions`) uruchamia start kontenera i Scheduled Task (COOLIFY.md §10a);
  `/demo/` i `/login/demo/` mają limit 10 wejść na 5 min z jednego IP (429); w trybie demo dziennik logowań nie zapisuje
  IP ani user-agenta. Testy: `warehouse/tests_retention.py`, `DemoEntryRateLimitTests`.
- **US-008 / R6:** hasła zapisywane algorytmem argon2 (`argon2-cffi`); istniejące hashe PBKDF2 są podnoszone do argon2
  przy następnym udanym logowaniu. Testy: `warehouse/tests_passwords.py`.
- Obraz runtime bez pip/setuptools/wheel (skan trivy wykazał podatności tylko w narzędziach instalacyjnych; ADR-0001).
- Zidentyfikowano i opisano ryzyka R1–R10 (`docs/AUDYT.md` §3.3); poprawki zaplanowane jako US-001…US-006
  w `docs/analiza/HISTORYJKI.md` (US-001…US-005, US-008 zrobione).

## [0.1.0] — 2026-10-13

Stan aplikacji przed wprowadzeniem procesu zespołowego (BA / DEV / SEC). Historia zmian z tego okresu:
`docs/operator/*.md` (jeden dokument na gałąź) i opisy PR #8–#22.

### Added
- Przyjęcia z podziałem na palety (HU) i etykietami QR (PDF), rozmieszczanie w panelu i skanerem w telefonie.
- Wydania WZ z doborem palet PICKING → ZAPAS, FEFO → FIFO; realizacja pełna lub z brakami; pakowanie; wysyłka; WZ w PDF.
- Korekty ilości z powodem, przepakowanie (łączenie palet), spis z natury (migawka → liczenie → zatwierdzenie).
- Stany, rejestr ruchów, raporty, eksport CSV/XLSX; importy CSV/XLSX (lokalizacje, stany, przyjęcia, zlecenia).
- Trzy role (Administrator, Operator, Podgląd), dziennik logowań, limit prób logowania.
- Tryb demo (`DEMO_MODE`): publiczne konta demo, wejście bez logowania `/demo/`, prezentacja z napisami, przywracanie danych.
- Wdrożenie: Dockerfile (non-root, healthcheck), Docker Compose z Caddy (auto-HTTPS) lub Coolify, kontener backupu.
- CI: ruff, `check --deploy`, kontrola migracji, testy na SQLite i PostgreSQL 16 (z testem wyścigu), build i smoke obrazu.
- Dokumentacja analityczna `docs/01–07` i harness asystenta AI (`.claude/`, `docs/pitfalls/`, `docs/operator/`).

[Unreleased]: https://github.com/TomaszWu14/miniWMS-public/compare/f5be158...HEAD
[0.1.0]: https://github.com/TomaszWu14/miniWMS-public/tree/f5be158
