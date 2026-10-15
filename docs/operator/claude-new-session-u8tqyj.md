# docs: audyt BA/DEV/SEC i rejestr założeń — instrukcja dla operatora

| | |
|---|---|
| Branch | `claude/new-session-u8tqyj` (nazwa techniczna sesji Claude) |
| PR | jeszcze nie utworzony (draft po pushu) |
| Data | 2026-10-15 |
| Ryzyko | niskie — tylko dokumentacja; kod, migracje, konfiguracja i CI bez zmian |

## 1. Co zmieniono
- Zmiany widoczne dla użytkowników magazynu: nie dotyczy.
- Nowy dokument `docs/AUDYT.md`: stan repozytorium z trzech perspektyw ([BA] wymagania i
  dokumentacja, [DEV] jakość kodu i dług, [SEC] top 10 ryzyk z wagą), pytania do Product
  Ownera (seria 1) i lista decyzji. Wyniki narzędzi uruchomionych w sesji (ruff, mypy, pytest
  + coverage, bandit, pip-audit, `check --deploy`).
- Nowy rejestr `docs/analiza/ZALOZENIA.md`: 10 założeń „do potwierdzenia” przyjętych do czasu
  odpowiedzi PO.
- Ten dokument operatora.

## 2. Kroki do ręcznego sprawdzenia

| # | Konto (rola) | Gdzie | Co zrobić | Oczekiwany wynik |
|---|---|---|---|---|
| 1 | — | GitHub, PR | otworzyć `docs/AUDYT.md` w podglądzie | tabele i sekcje renderują się; linki do plików prowadzą do istniejących ścieżek |
| 2 | — | GitHub, PR | przeczytać §4 (pytania) i §5 (decyzje) | PO odpowiada w PR lub w sesji; odpowiedzi trafią do `docs/analiza/ZALOZENIA.md` |

## 3. Checklista wdrożenia

### Migracje — na KAŻDEJ bazie
| Baza | Polecenie | Wykonano (kto, kiedy) |
|---|---|---|
| dev (lokalny SQLite) | `python manage.py migrate` | ☐ nie dotyczy — brak migracji |
| test (baza testów) | tworzona automatycznie przez `pytest` / `manage.py test` | ☐ testy zielone (224 passed, 2 skipped w sesji) |
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
- ☐ CI zielone na PR (`ci.yml`; `security.yml` tylko z harmonogramu)
- ☐ backup bazy prod sprzed deployu — nie dotyczy (brak migracji)
- ☐ po deployu: `/healthz` zwraca `{"status": "ok"}` (merge dokumentacji uruchomi redeploy — bez zmian w działaniu)

## 4. Plan wycofania
1. Kod: Coolify → zasób → **Deployments** → poprzedni deployment → **Redeploy**
   (albo revert PR na `main`). Zmiana nie dotyka działania aplikacji.
2. Migracje: nie dotyczy.
3. Zmienne środowiskowe: nie dotyczy.
4. Weryfikacja po wycofaniu: `/healthz`, logowanie, lista HU.
