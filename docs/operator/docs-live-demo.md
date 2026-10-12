# docs/live-demo — instrukcja dla operatora

| | |
|---|---|
| Branch | `docs/live-demo` |
| PR | utworzony razem z tym plikiem |
| Data | 2026-10-11 |
| Ryzyko | niskie — tylko dokumentacja (README, instrukcja Coolify); kod aplikacji bez zmian |

## 1. Co zmieniono

- README: link do działającego demo `https://miniwms.twapp.pl` z loginami demo i informacją
  o codziennym resecie danych (zamiast „Demo online nie jest utrzymywane”).
- Instrukcja Coolify: wymagana opcja **Preserve Repository During Deployment** (inaczej
  kontener `backup` restartuje się w kółko), domena bez portu, kilka domen po przecinku,
  adres działającego demo.

Zmiany techniczne bez wpływu na UI: brak.

## 2. Kroki do ręcznego sprawdzenia

| # | Konto (rola) | Gdzie | Co zrobić | Oczekiwany wynik |
|---|---|---|---|---|
| 1 | — | `https://miniwms.twapp.pl/login/` | otworzyć | baner DEMO, loginy demo na stronie, ważny certyfikat |
| 2 | `demo_operator` (Operator) | `https://miniwms.twapp.pl/` | zalogować się hasłem `demo1234` | pulpit z danymi demo (30 palet) |
| 3 | — | Coolify → `miniwms-demo` → Scheduled Tasks | sprawdzić zadanie | `reset-demo`, `0 3 * * *`, kontener `web` |

## 3. Checklista wdrożenia

### Migracje — na KAŻDEJ bazie
| Baza | Polecenie | Wykonano (kto, kiedy) |
|---|---|---|
| dev (lokalny SQLite) | `python manage.py migrate` | ☐ nie dotyczy — brak migracji |
| test (baza testów) | tworzona automatycznie przez `pytest` / `manage.py test` | ☐ nie dotyczy — brak zmian w kodzie |
| demo (jeśli wdrożone) | automatycznie w `entrypoint.sh` przy deployu | ☐ nie dotyczy — brak migracji |
| prod (PostgreSQL, Coolify) | automatycznie w `entrypoint.sh` przy deployu | ☐ nie dotyczy — brak migracji |

Nowe migracje w tym branchu: brak. Odwracalne: nie dotyczy.
Sprawdzenie: `python manage.py showmigrations warehouse` — wszystkie `[X]`.

### Zmienne środowiskowe
| Zmienna | Nowa / zmieniona / usunięta | Wartość prod | Ustawiona w Coolify |
|---|---|---|---|
| — | nie dotyczy (zmienne demo ustawione w panelu, nie w repo) | — | ☐ |

Zaktualizowano też: `.env.example` — nie dotyczy, `.env.docker.example` — nie dotyczy,
instrukcja Coolify — tak (kroki 4, 5, 11).

### Przed i po deployu
- ☐ CI zielone na PR (`ci.yml`, `security.yml`)
- ☐ backup bazy prod sprzed deployu — nie dotyczy (brak migracji)
- ☐ po deployu: `/healthz` zwraca `{"status": "ok"}`
- ☐ kroki z sekcji 2 wykonane

## 4. Plan wycofania
1. Kod: revert PR na `main`.
2. Migracje: nie dotyczy — branch nie zawiera migracji.
3. Zmienne środowiskowe: nie dotyczy.
4. Weryfikacja po wycofaniu: README bez linku do demo.
