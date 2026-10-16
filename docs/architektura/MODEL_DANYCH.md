# Model danych — status, zasady zmian, plan

| | |
|---|---|
| Wersja | 0.1 |
| Data | 2026-10-16 |
| Status | szkic — do akceptacji Product Ownera |
| Właściciel | [DEV] |

**Źródło prawdy o modelu: [docs/04 — Model danych](../04-model-danych.md)** — diagram ERD, opis
13 encji (Django `User` + 12 modeli aplikacji), reguły integralności i 12 luk (pilnowanych
tylko w kodzie). Ten plik niczego z niego nie powtarza (Z-03); dopisuje to, czego tam nie ma:
plan zmian, zasady wprowadzania zmian i mapę tabel do klas danych.

Stan na dziś: 8 migracji (`0001_initial` … `0008_alter_location_capacity_and_more`),
`makemigrations --check` bez zmian ([AUDYT §2.2](../AUDYT.md)), `RunPython` tylko w
`0002_seed_defaults` (z funkcją wsteczną).

---

## 1. Zmiany planowane w modelu

**Dziś: brak zmian schematu w toku.** Kandydaci z audytu i backlogu — żaden nie jest jeszcze
zatwierdzony do realizacji.

| Kandydat | Źródło | Zmiana schematu? | Zakres zmiany | Status |
|---|---|---|---|---|
| Indeks funkcyjny `Upper("number")` na `HandlingUnit.number` | [docs/07 „Znane problemy” #3](../07-ograniczenia.md) | **tak** (nowa migracja `AddIndex`) | `number__iexact` (D-10) nie korzysta z indeksu unikalnego na PostgreSQL; przy setkach palet bez znaczenia, przy dziesiątkach tysięcy — tak | Could — US-039; do uruchomienia, gdy lista HU zwolni |
| Retencja `LoginEvent` (90 dni, Z-09) | R7, [AUDYT §3.3](../AUDYT.md), US-005 | **nie** | komenda `manage.py` usuwająca stare wpisy + Scheduled Task w Coolify; opcjonalnie skrócenie `user_agent` | planowane razem z R5 (US-005) |
| Limity ilości i liczby palet (`max_value` w formularzach i importach) | R3 (US-002), T16 | **nie** | walidacja w `forms.py`, `receipt_import.py`, `stock_import.py` i API skanera; kolumny `IntegerField` zostają | planowane (US-002, US-013) |
| Górny limit ilości jako `CheckConstraint` | T16 | tak (opcjonalnie) | obrona w głąb po stronie bazy; wymaga decyzji o wartości granicznej | nie planowane — do decyzji PO po US-002 |
| Domknięcie luk integralności z docs/04 (np. #1 status HU ↔ ilość/lokalizacja, #5 `picked_qty ≤ requested_qty`) | [docs/04](../04-model-danych.md) „obserwacje, nie zadania” | tak (constrainty, migracja danych) | tylko po analizie istniejących danych; D-09 świadomie dopuszcza HU z ilością 0 i statusem ZMAGAZYNOWANY | brak decyzji PO |
| Licznik nieudanych logowań konta `LoginFailureCounter` (klucz = skrót loginu, liczba, początek okna) | R6 | **tak** | wygasłe usuwa `purge_login_events` | US-009, migracja `0010` |
| Cache wspólny `miniwms_cache` (liczniki limitów per IP) | R6 | **tak** | `createcachetable` w entrypoint, wpisy wygasają same | US-009, ADR-0002 |
| Retencja / czyszczenie `django_session` | R5 | **tak** | `manage.py clearsessions` w harmonogramie i przy starcie | US-005, #23 |

Zmiana z tej tabeli, która wymaga migracji, przechodzi procedurę z sekcji 2 i trafia do
`docs/operator/<branch>.md` z planem wycofania (`docs/operator/TEMPLATE.md` §3–4).

---

## 2. Zasady zmian modelu

Pełna lista: [docs/pitfalls/db.md](../pitfalls/db.md) i [deploy.md](../pitfalls/deploy.md).
Tu tylko to, co obowiązuje przy **każdej** zmianie schematu.

| Zasada | Jak | Pułapka |
|---|---|---|
| Stan HU zmienia wyłącznie `services.py` | nowa operacja = nowa funkcja `@transaction.atomic` + `StockMovement` | db.md #1 |
| Reguła ilościowa = constraint w bazie, nie tylko `clean()` | `CheckConstraint(condition=…)` — **`condition=`, nie `check=`** (usunięte w Django 6.0) + migracja | db.md #5, #6 |
| Migracje odwracalne | każdy `RunPython` z funkcją wsteczną lub jawnie `RunPython.noop`; `apps.get_model`, nie import modeli | db.md #7 |
| Brak edycji zastosowanych migracji | poprawka = nowa migracja | db.md #8 |
| `makemigrations --check --dry-run` zielone | CI odrzuca brakujące migracje | db.md #8 |
| Usuwanie z historią zablokowane | `PROTECT` na materiale/lokalizacji — obsłuż `ProtectedError` w widoku, nie zmieniaj na `CASCADE` | db.md #10 |
| Migracje niszczące w dwóch wdrożeniach | najpierw kod przestaje używać kolumny, potem migracja ją usuwa | deploy.md #2 |
| Test na PostgreSQL | blokady i `FOR UPDATE` działają tylko tam; zmiana dotykająca blokad = test jak `tests_concurrency_pg.py` | db.md #2 |
| N+1 | nowa relacja w szablonie listy = dopisz `select_related` / `prefetch_related`; `assertNumQueries` | db.md #9 |

### Checklista zmiany modelu

1. Zmiana w `models.py` (+ constraint z `condition=`, jeśli to reguła ilościowa).
2. `python manage.py makemigrations` → przejrzyj plik: odwracalność, brak niszczących operacji na danych produkcyjnych.
3. `python manage.py makemigrations --check --dry-run` → „No changes detected”.
4. Test regresji w `warehouse/tests*.py`; jeśli dotyka blokad lub constraintów — uruchom też na PostgreSQL (`DATABASE_URL=postgres://… pytest`).
5. Zaktualizuj [docs/04](../04-model-danych.md) (ERD, tabela encji, luki) i tabelę z sekcji 1.
6. W `docs/operator/<branch>.md` wypełnij wiersze migracji dla dev / test / demo / prod oraz plan wycofania (`migrate warehouse <poprzednia>`; nieodwracalne → odtworzenie z kopii, [RUNBOOK.md](../operacje/RUNBOOK.md) §5).
7. Przed deployem z migracją: świeża kopia bazy prod ([RUNBOOK.md](../operacje/RUNBOOK.md) §3–4).

---

## 3. Retencja i wzrost tabel

| Tabela | Wzrost | Retencja dziś | Uwagi |
|---|---|---|---|
| `warehouse_stockmovement` | każda operacja magazynowa | brak (rejestr audytowy — celowo) | lista ruchów pokazuje 500 najnowszych, eksport buduje całość w pamięci (T9) |
| `warehouse_loginevent` | każde logowanie, wylogowanie i nieudana próba; w demo także każde wejście przez `/demo/` | **brak** | R7, R5; podgląd w UI: 100 wpisów na stronę |
| `django_session` | nowa sesja przy każdym kliencie bez ciasteczka (demo: każde `/demo/`) | brak `clearsessions` | R5 |
| pozostałe `warehouse_*` | proporcjonalnie do działalności magazynu | n/d | skala: ~200 palet, ~30 nowych tygodniowo ([docs/01](../01-problem-i-zakres.md)) |

---

## 4. Mapa tabel → klasa danych

Obowiązująca klasyfikacja i zasady postępowania z danymi: **[KLASYFIKACJA_DANYCH.md](../bezpieczenstwo/KLASYFIKACJA_DANYCH.md)**
(właściciel [SEC]) — klasy: Publiczne, Wewnętrzne, Poufne oraz znacznik **Dane osobowe**.
Poniższa mapa tylko wiąże fizyczne tabele z rejestrem zasobów DA-xx z tego dokumentu; **nie
definiuje klas** — w razie rozbieżności wygrywa `KLASYFIKACJA_DANYCH.md`.

| Tabela (PostgreSQL) | Encja | Rejestr | Klasa wg KLASYFIKACJA_DANYCH |
|---|---|---|---|
| `auth_user` | User | DA-08, DA-09 | Dane osobowe; kolumna `password` (hash) — Poufne |
| `warehouse_profile` | Profile | DA-08 | Dane osobowe (rola konta) |
| `warehouse_loginevent` | LoginEvent | DA-10, DA-12 | Dane osobowe (IP, przeglądarka, wpisany login; w demo także osoby anonimowe) |
| `warehouse_stockmovement` | StockMovement | DA-07, DA-11 | Wewnętrzne + Dane osobowe (`created_by`) |
| `warehouse_material`, `warehouse_unit`, `warehouse_location`, `warehouse_handlingunit`, `warehouse_hunumberingconfig` | Material, Unit, Location, HandlingUnit, HUNumberingConfig | DA-05, DA-11 | Wewnętrzne (`created_by` → Dane osobowe) |
| `warehouse_issuedocument`, `warehouse_issueline`, `warehouse_stocktakesheet`, `warehouse_stocktakeline` | IssueDocument, IssueLine, StocktakeSheet, StocktakeLine | DA-06, DA-11 | Wewnętrzne (+ osobowe, gdy odbiorca to osoba fizyczna; `created_by`) |
| `django_session` | sesje Django | DA-13 | Poufne (+ osobowe) |
| kopie `pg_dump` (wolumen `db_backups`) | całość bazy | DA-17 | Poufne (zawierają wszystkie powyższe tabele) |
| dane demo w bazie instancji demo | — | DA-03 | Publiczne (fikcyjne) |
| `django_admin_log`, `auth_permission`, `auth_group*`, `django_content_type` | tabele frameworka | — | poza rejestrem DA-xx — do klasyfikacji przez [SEC] |

Nazwy tabel to domyślne nazwy Django (`<app>_<model>`); żaden model nie ustawia `db_table`.
Nowe pole lub tabela z danymi osobowymi wymaga w tym samym PR wpisu DA-xx i oceny [SEC]
(KLASYFIKACJA_DANYCH §4 pkt 4).
