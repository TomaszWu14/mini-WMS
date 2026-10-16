# ADR-0002 — Cache wspólny dla workerów: DatabaseCache w PostgreSQL

| | |
|---|---|
| Status | zaakceptowany (decyzja PO 2026-10-16) |
| Data | 2026-10-16 |
| Właściciel | [DEV] z udziałem [SEC] |
| Powiązania | US-009; AUDYT R6, T8; pitfalls/auth #6; `config/settings/base.py` (`CACHES`), `entrypoint.sh` (`createcachetable`) |

## Kontekst

Limit prób logowania, limit wejść do demo i blokada resetu demo trzymały liczniki w domyślnym cache
Django (LocMem), czyli osobno w każdym procesie gunicorna. Przy 3 workerach realny limit był
~3× wyższy, a licznik nie przeżywał restartu. US-009 wymaga limitu nieudanych logowań **na konto**
i **wspólnego dla wszystkich workerów** (atak słownikowy z puli IP).

## Rozważane opcje

| Opcja | Zalety | Wady |
|---|---|---|
| LocMem (stan) | zero konfiguracji | liczniki per proces — nie spełnia US-009 |
| **DatabaseCache w istniejącym PostgreSQL** | brak nowej usługi i zmiennych; ta sama kopia zapasowa i ten sam dostęp | wolniejszy od Redisa; `incr` nie jest atomowy (odczyt + zapis), przy równoległych próbach licznik może być niższy o kilka; tabela wymaga `createcachetable` |
| Redis | szybki, atomowy `INCR`, standard dla limiterów | nowa usługa w obu compose i w Coolify, nowa zmienna `REDIS_URL`, więcej do utrzymania i zabezpieczenia |

## Decyzja

**DatabaseCache**, tabela `miniwms_cache`, zakładana idempotentnie przez `manage.py createcachetable`
w `entrypoint.sh` (po `migrate`). Development (`dev.py`, `runserver` = jeden proces) zostaje na LocMem;
testy (`test.py`) używają DatabaseCache jak produkcja. Limit konta: 10 nieudanych prób / 15 min
(`LOGIN_ACCOUNT_LIMIT`, `LOGIN_ACCOUNT_WINDOW`; decyzja PO).

## Zmiana po przeglądach [SEC]/[DB] (2026-10-16)

Licznik **konta** przeniesiono z cache do tabeli `LoginFailureCounter` (migracja `0010`): `incr` w DatabaseCache
nie jest atomowy i zapisywał wpis z domyślnym `TIMEOUT` 300 s (okno 5 zamiast 15 min), a culling przy
`MAX_ENTRIES` = 300 pozwalał zalać tabelę i wyrzucić licznik. Teraz: atomowy `UPDATE count = count + 1`,
pełne okno, wygasłe wiersze usuwa `purge_login_events`. W cache zostają liczniki per IP (skrót IP w kluczu)
i blokada resetu demo; `MAX_ENTRIES` = 100 000.

## Konsekwencje

- Wszystkie liczniki w cache (logowanie per IP, per konto, wejścia demo, blokada resetu) są wspólne
  dla workerów i przeżywają restart kontenera.
- Nieatomowy `incr` dotyczy już tylko limitów per IP (okno 300 s = domyślny `TIMEOUT`, więc wygasanie się zgadza;
  każda próba przedłuża okno — limit jest trochę ostrzejszy). Licznik konta jest atomowy (tabela).
- Blokada konta daje przeciwnikowi możliwość czasowego zablokowania znanego loginu (np. `admin`) —
  cecha każdej blokady per konto; okno 15 min ogranicza skutek, a zablokowany użytkownik może
  poczekać. Odblokowanie ręczne: RUNBOOK §8.3a.
- Tabela cache nie jest migracją Django — nowa instalacja i każdy start kontenera ją tworzą, jeśli
  jej nie ma.
