# chore/env-examples — instrukcja dla operatora

| | |
|---|---|
| Branch | `chore/env-examples` |
| PR | jeszcze nie utworzony |
| Data | 2026-10-13 |
| Ryzyko | niskie — tylko pliki przykładowe zmiennych i dokumentacja; aplikacja ich nie czyta |

## 1. Co zmieniono
- `.env.example` (uruchomienie lokalne): opisane `DEMO_MODE`, `DEMO_USER`, `DEMO_PASSWORD` i
  `DJANGO_TRUSTED_PROXY_COUNT` (zakomentowane, z wartościami domyślnymi).
- `.env.docker.example` (`docker-compose.yml` z Caddy): usunięte `ACME_EMAIL` (już nieużywane),
  dodane `DJANGO_SSL_REDIRECT=1`, `DJANGO_TRUSTED_PROXY_COUNT=1` i opis trybu sieci lokalnej.
- Dokumenty operatora `feat-recruiter-ready` i `fix-compose-from-zero`: punkty o plikach
  przykładowych oznaczone jako zrobione.

## 2. Kroki do ręcznego sprawdzenia

| # | Konto (rola) | Gdzie | Co zrobić | Oczekiwany wynik |
|---|---|---|---|---|
| 1 | — | repo | `cp .env.docker.example .env`, uzupełnić wartości, `docker compose up -d --build` | 4 kontenery działają (jak w `fix-compose-from-zero.md`) |

## 3. Checklista wdrożenia

### Migracje — na KAŻDEJ bazie
| Baza | Polecenie | Wykonano (kto, kiedy) |
|---|---|---|
| dev (lokalny SQLite) | `python manage.py migrate` | ☐ nie dotyczy — brak migracji |
| test (baza testów) | tworzona automatycznie przez `pytest` / `manage.py test` | ☐ testy zielone |
| demo (jeśli wdrożone) | automatycznie w `entrypoint.sh` przy deployu | ☐ nie dotyczy — brak migracji |
| prod (PostgreSQL, Coolify) | automatycznie w `entrypoint.sh` przy deployu | ☐ nie dotyczy — brak migracji |

Nowe migracje w tym branchu: brak. Odwracalne: nie dotyczy.
Sprawdzenie: `python manage.py showmigrations warehouse` — wszystkie `[X]`.

### Zmienne środowiskowe
| Zmienna | Nowa / zmieniona / usunięta | Wartość prod | Ustawiona w Coolify |
|---|---|---|---|
| — | tylko opis w plikach przykładowych, bez zmian w kodzie | — | ☐ nie dotyczy |

Zaktualizowano też: `.env.example` ☑, `.env.docker.example` ☑, `COOLIFY.md` §6 — nie dotyczy.

### Przed i po deployu
- ☐ CI zielone na PR (`ci.yml`, `security.yml`)
- ☐ backup bazy prod sprzed deployu — nie dotyczy
- ☐ Redeploy — nie dotyczy (pliki przykładowe nie trafiają do działającej aplikacji)

## 4. Plan wycofania
1. Kod: revert PR na `main`.
2. Migracje: nie dotyczy.
3. Zmienne środowiskowe: nie dotyczy.
4. Weryfikacja po wycofaniu: nie dotyczy.
