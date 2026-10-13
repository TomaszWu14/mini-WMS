# chore: porządki w repozytorium — instrukcja dla operatora

| | |
|---|---|
| Branch | `ccr-93422d57-atfl7j` (nazwa techniczna sesji Claude) |
| PR | jeszcze nie utworzony |
| Data | 2026-10-13 |
| Ryzyko | niskie — bez zmian w działaniu aplikacji; jedna adnotacja typu i pliki pomocnicze |

## 1. Co zmieniono
- Zmiany widoczne dla użytkowników: nie dotyczy.
- `mypy` znów przechodzi bez błędów. Poprawiony typ grup w imporcie wydań
  (`warehouse/issue_import.py`). Logika bez zmian.
- `.gitignore` bez zdublowanego bloku. Doszły cache narzędzi (`.mypy_cache`, `.ruff_cache`,
  `.pytest_cache`) i raporty pokrycia.
- Dokument operatora z PR #19 dostał czytelną nazwę:
  `docs/operator/feat-demo-bez-logowania-youtube.md`.

## 2. Kroki do ręcznego sprawdzenia

| # | Konto (rola) | Gdzie | Co zrobić | Oczekiwany wynik |
|---|---|---|---|---|
| 1 | `demo_operator` (Operator) | `/wydania/` → import zleceń z pliku | zaimportować plik z dwoma referencjami | dwa dokumenty WZ, jak przed zmianą |

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
| — | nie dotyczy | — | ☐ nie dotyczy |

Zaktualizowano też: `.env.example` — nie dotyczy, `.env.docker.example` — nie dotyczy,
`COOLIFY.md` — nie dotyczy.

### Przed i po deployu
- ☐ CI zielone na PR (`ci.yml`, `security.yml`)
- ☐ backup bazy prod sprzed deployu — nie dotyczy (brak migracji)
- ☐ po deployu: `/healthz` zwraca `{"status": "ok"}`

## 4. Plan wycofania
1. Kod: Coolify → zasób → **Deployments** → poprzedni deployment → **Redeploy**
   (albo revert PR na `main`).
2. Migracje: nie dotyczy.
3. Zmienne środowiskowe: nie dotyczy.
4. Weryfikacja po wycofaniu: `/healthz`, logowanie, lista HU.
