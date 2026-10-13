# docs: logo miniWMS — instrukcja dla operatora

| | |
|---|---|
| Branch | `ccr-93422d57-atfl7j` (nazwa techniczna sesji Claude) |
| PR | jeszcze nie utworzony |
| Data | 2026-10-13 |
| Ryzyko | niskie — tylko pliki graficzne i dokumentacja, aplikacja bez zmian |

## 1. Co zmieniono
- Logo jako osobne pliki w `docs/brand/`: znak w SVG, znak z napisem w PNG (wersja na
  jasne i na ciemne tło) i kwadratowy awatar 800×800, np. na kanał YouTube. Opis plików:
  `docs/brand/README.md`.
- README zaczyna się od logo.
- Dokument operatora z #21 ma teraz nazwę `feat-prezentacja-bez-lektora.md`.
- Zmiany techniczne bez wpływu na UI: nie dotyczy.

## 2. Kroki do ręcznego sprawdzenia

| # | Konto (rola) | Gdzie | Co zrobić | Oczekiwany wynik |
|---|---|---|---|---|
| 1 | — | GitHub, strona repo | otworzyć README | logo nad tytułem |
| 2 | — | `docs/brand/` | otworzyć pliki | znak SVG, dwa PNG z napisem, awatar |

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
1. Kod: revert PR na `main`.
2. Migracje: nie dotyczy.
3. Zmienne środowiskowe: nie dotyczy.
4. Weryfikacja po wycofaniu: README bez logo.
