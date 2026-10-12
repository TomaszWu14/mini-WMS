# chore/harness-after-demo — instrukcja dla operatora

| | |
|---|---|
| Branch | `chore/harness-after-demo` |
| PR | utworzony razem z tym plikiem |
| Data | 2026-10-11 |
| Ryzyko | niskie — tylko konfiguracja pracy z asystentem AI i dokumentacja; aplikacja bez zmian |

## 1. Co zmieniono

Dla użytkownika magazynu: nic — aplikacja bez zmian.

Techniczne bez wpływu na UI:
- `guard.py`: reguła „wywołanie Coolify” blokuje już tylko faktyczne wywołania (HTTP do
  panelu/API, CLI `coolify`), a nie każde wystąpienie słowa (np. `grep` w instrukcji wdrożenia).
  Webhook deployu, `docker compose … coolify`, `gh pr merge` i push do `main` nadal blokowane.
- `worker.md`: zakaz `git stash/checkout/restore/reset/switch` — równolegli workerzy dzielą
  jedno drzewo robocze.
- `docs/pitfalls/deploy.md` pkt 8: „Preserve Repository During Deployment” dla kontenera
  `backup` i domena bez `:8000`.

## 2. Kroki do ręcznego sprawdzenia

| # | Konto (rola) | Gdzie | Co zrobić | Oczekiwany wynik |
|---|---|---|---|---|
| 1 | — | terminal | `.venv/Scripts/python -m pytest .claude/hooks -q` | 49 passed |

## 3. Checklista wdrożenia

### Migracje — na KAŻDEJ bazie
| Baza | Polecenie | Wykonano (kto, kiedy) |
|---|---|---|
| dev (lokalny SQLite) | `python manage.py migrate` | ☐ nie dotyczy — brak migracji |
| test (baza testów) | tworzona automatycznie przez `pytest` / `manage.py test` | ☐ testy zielone (173) |
| demo (jeśli wdrożone) | automatycznie w `entrypoint.sh` przy deployu | ☐ nie dotyczy — brak migracji |
| prod (PostgreSQL, Coolify) | automatycznie w `entrypoint.sh` przy deployu | ☐ nie dotyczy — brak migracji |

Nowe migracje w tym branchu: brak. Odwracalne: nie dotyczy.
Sprawdzenie: `python manage.py showmigrations warehouse` — wszystkie `[X]`.

### Zmienne środowiskowe
| Zmienna | Nowa / zmieniona / usunięta | Wartość prod | Ustawiona w Coolify |
|---|---|---|---|
| — | nie dotyczy | — | ☐ |

Zaktualizowano też: `.env.example` — nie dotyczy, `.env.docker.example` — nie dotyczy,
instrukcja Coolify — nie dotyczy.

### Przed i po deployu
- ☐ CI zielone na PR (`ci.yml`, `security.yml`)
- ☐ backup bazy prod sprzed deployu — nie dotyczy (brak migracji)
- ☐ po deployu: `/healthz` zwraca `{"status": "ok"}`
- ☐ kroki z sekcji 2 wykonane

## 4. Plan wycofania
1. Kod: revert PR na `main`.
2. Migracje: nie dotyczy — branch nie zawiera migracji.
3. Zmienne środowiskowe: nie dotyczy.
4. Weryfikacja po wycofaniu: `pytest .claude/hooks -q`.
