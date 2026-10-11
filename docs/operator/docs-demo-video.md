# docs/demo-video — instrukcja dla operatora

| | |
|---|---|
| Branch | `docs/demo-video` |
| PR | utworzony razem z tym plikiem |
| Data | 2026-10-11 |
| Ryzyko | niskie — tylko plik wideo i link w README, kod aplikacji bez zmian |

## 1. Co zmieniono

- README: link „Prezentacja działania — 2 min, z napisami” do wideo w repozytorium.
- Nowy plik `docs/video/miniwms-demo.mp4` (1:56, 4,3 MB, bez dźwięku, z napisami) —
  nagranie ekranu na danych demo: proces PRZED, przyjęcie, rozmieszczenie skanerem, wydanie
  FEFO, model danych, ograniczenia.

Zmiany techniczne bez wpływu na UI: brak.

## 2. Kroki do ręcznego sprawdzenia

| # | Konto (rola) | Gdzie | Co zrobić | Oczekiwany wynik |
|---|---|---|---|---|
| 1 | — | GitHub, README na stronie repo | kliknąć „Prezentacja działania” | otwiera się plik wideo, odtwarza się z napisami |

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
`COOLIFY.md` — nie dotyczy.

### Przed i po deployu
- ☐ CI zielone na PR (`ci.yml`, `security.yml`)
- ☐ backup bazy prod sprzed deployu — nie dotyczy (brak migracji)
- ☐ po deployu: `/healthz` zwraca `{"status": "ok"}`
- ☐ kroki z sekcji 2 wykonane

## 4. Plan wycofania
1. Kod: revert PR na `main` (albo Coolify → **Deployments** → poprzedni → **Redeploy**).
2. Migracje: nie dotyczy — branch nie zawiera migracji.
3. Zmienne środowiskowe: nie dotyczy.
4. Weryfikacja po wycofaniu: README bez linku do wideo, `/healthz`.
