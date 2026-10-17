# ADR-0008 — Dziennik audytowy: tabela `AuditEvent` zapisywana sygnałami modeli

| | |
|---|---|
| Status | zaakceptowany (PO, 2026-10-17: tabela + log JSON, retencja 365 dni — Z-42) |
| Data | 2026-10-17 |
| Właściciel | [DEV] z udziałem [SEC] |
| Powiązania | US-022, SEC-032, SEC-033, NFR-020; AUDYT R1, R7; TM-37, TM-40, RR-28; ASVS 7.1.3 |

## Kontekst

Zmiany kont (rola, hasło, status, 2FA) nie zostawiały śladu. Logi kontenera Coolify są rotowane, więc
nie nadają się na jedyny ślad. Konta zmieniają też ścieżki inne niż panel aplikacji: `/admin/`,
`manage.py changepassword` / `createsuperuser` / `reset_2fa`, `entrypoint.sh` oraz `seed_demo`.

## Rozważane opcje

| Opcja | Zalety | Wady |
|---|---|---|
| **tabela w bazie + linia logu JSON** | trwała, w backupie, przeglądana przez Administratora w UI | migracja, retencja do pilnowania |
| tylko log JSON | bez migracji | znika przy rotacji logów; brak podglądu w aplikacji |
| `django_admin_log` (LogEntry) | już jest | obejmuje tylko `/admin/`; brak odmów i ścieżek aplikacji |
| zapis w każdym widoku | proste | pomija `/admin/` i komendy (przegląd [SEC] US-022) |

## Decyzja

- Model `AuditEvent` (migracja `0011`): kto (FK i login tekstem), komu (FK i login tekstem), akcja, wynik
  (`OK` / `DENIED`), szczegóły. Loginy tekstem przetrwają usunięcie konta (`SET_NULL`).
- Zmiany kont zapisują **sygnały** `pre_save` i `post_save` na `User` i `Profile`, `post_save` i
  `post_delete` na `TOTPDevice` oraz `pre_delete` na `User`. Ślad zostawia każda ścieżka.
  - Kto zmienił, podaje `AuditActorMiddleware` (użytkownik żądania) albo nazwa komendy `manage.py`.
  - Przeliczenie hasha przy logowaniu (setter Django zeruje `_password`) i zapis `last_login` nie są zdarzeniami.
- Odmowy zapisują widoki wprost i tylko przy POST: GET da się wywołać z obcej strony.
- W widokach zmiana konta i jej wpisy idą w jednej transakcji. Linia logu powstaje w `on_commit`.
  - Komendy spoza aplikacji (`changepassword`) zapisują w trybie autocommit.
  - Wpis powstaje tam zaraz po zmianie, w osobnym zapytaniu.
- Retencja 365 dni: `purge_login_events` (ta sama komenda i Scheduled Task co dziennik logowań).
- Logi JSON maskują wartości pól wrażliwych (`config/log.py`). Obiekt żądania trafia do logu jako
  metoda i ścieżka, bez danych formularza.

## Konsekwencje

- Nowa ścieżka zmieniająca konto nie wymaga osobnego kodu audytu, jeśli zapisuje przez model.
  Wyjątek: `QuerySet.update()` i `bulk_update` omijają sygnały, więc dla kont są zabronione (pitfalls auth #14).
- `AuditEvent` nie jest w `/admin/`, więc nikt nie edytuje wpisów z UI. Superuser z dostępem do bazy
  nadal może je usunąć, co jest ryzykiem resztkowym (TM-37).
- Wycofanie migracji `0011` usuwa tabelę wraz z wpisami, więc najpierw trzeba zrobić backup.
