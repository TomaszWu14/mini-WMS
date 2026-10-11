# portfolio-cleanup — instrukcja dla operatora

| | |
|---|---|
| Branch | `portfolio-cleanup` |
| PR | `#8` |
| Data | 2026-10-11 |
| Ryzyko | niskie — logika magazynu bez zmian; zmiana nazwy marki w nagłówkach, etykietach i PDF WZ oraz dokumentacja |

## 1. Co zmieniono

- Nazwa w nagłówku panelu, na stronie logowania, na etykietach HU i lokalizacji oraz w
  stopce dokumentu WZ (PDF): **miniWMS** zamiast dawnej nazwy marki.
- Przykłady w podpowiedziach formularzy i w instrukcji importu lokalizacji: neutralne kody
  (`A-01-01A`, `HU00000001`) zamiast kodów z systemu firmowego.
- Nowa dokumentacja analityczna `docs/01–07` i README jako strona tytułowa; szczegóły
  wdrożenia przeniesione do `docs/wdrozenie.md`.
- Usunięte dwa nieużywane zrzuty ekranu z dawną nazwą marki (`docs/screenshots/`).

Zmiany techniczne bez wpływu na UI: wartości testowe w `warehouse/tests.py`, nowy test
`BrandingTests`, nazwa zmiennej w nagłówku PDF WZ (`documents.py`), `mypy
--follow-imports=silent` w hooku Stop (`.claude/hooks/check.py`), opis w `pyproject.toml`.

## 2. Kroki do ręcznego sprawdzenia

| # | Konto (rola) | Gdzie | Co zrobić | Oczekiwany wynik |
|---|---|---|---|---|
| 1 | — (gość) | `/login/` | otworzyć stronę | nagłówek „miniWMS”, brak dawnej nazwy |
| 2 | `demo_operator` (Operator) | `/hu/` → paleta → „Etykieta” | otworzyć PDF | etykieta z napisem miniWMS |
| 3 | `demo_operator` (Operator) | `/wydania/` → dokument → „Drukuj WZ” | otworzyć PDF | nagłówek „miniWMS”, stopka „miniWMS”, dane dokumentu w nagłówku poprawne |
| 4 | `demo_operator` (Operator) | `/lokalizacje/import/` | odczytać instrukcję | przykład `A-01-01A` |
| 5 | — | GitHub, gałąź `portfolio-cleanup` | otworzyć `docs/02`, `03`, `04` | diagramy Mermaid się renderują |

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
| — | nie dotyczy | — | ☐ |

Zaktualizowano też: `.env.example` — nie dotyczy, `.env.docker.example` — nie dotyczy,
`COOLIFY.md` — tylko adres repozytorium (`miniWMS-public`).

### Przed i po deployu
- ☐ CI zielone na PR (`ci.yml`, `security.yml`)
- ☐ backup bazy prod sprzed deployu — nie dotyczy (brak migracji)
- ☐ po deployu: `/healthz` zwraca `{"status": "ok"}`
- ☐ kroki z sekcji 2 wykonane na prod

## 4. Plan wycofania
1. Kod: Coolify → zasób → **Deployments** → poprzedni deployment → **Redeploy**
   (albo revert PR #8 na `main`).
2. Migracje: nie dotyczy — branch nie zawiera migracji.
3. Zmienne środowiskowe: nie dotyczy.
4. Weryfikacja po wycofaniu: `/healthz`, logowanie, lista HU.
