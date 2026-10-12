# 07. Ograniczenia, znane problemy, co dalej

Status: **zaawansowany prototyp**.

## Czego aplikacja nie robi (świadomie)

| Brak | Powód |
|---|---|
| Integracja z ERP | firma nie ma ERP — dane wchodzą z plików CSV/XLSX ([D-04](06-decyzje.md)) |
| Zwroty od klientów, anulowanie WZ | w tym magazynie zwrotów nie ma |
| Blokada palet po terminie ważności | poza zakresem; reguła FEFO wydaje je jako pierwsze |
| Wiele magazynów, strefy, ścieżki kompletacji | jeden mały magazyn |
| Rezerwacja stanu pod otwarte WZ | dostępność liczona w chwili realizacji |
| Atrybuty logistyczne materiału (wymiary, waga, EAN) | brak master daty ([D-02](06-decyzje.md)) |

## Wymagania niespełnione

Brak. W-08, W-11, W-25 i W-26 domknięto poprawkami z gałęzi `fix/code-gaps` (szczegóły w
[05](05-wymagania.md)).

## Naprawione po przeglądzie kodu (gałąź `fix/code-gaps`)

| Było | Teraz | Gdzie |
|---|---|---|
| Pojemność blokowała alokację (W-08) | alokacja przechodzi, panel i skaner pokazują ostrzeżenie | `services.allocate_hu`, `location_over_capacity` |
| Skaner przyjmował dowolną paletę materiału (W-11, W-25) | pilnuje palety wskazanej w WZ; ostrzega, gdy paleta nie jest pierwsza wg FEFO | `scanner_views.api_pick` |
| Korekta bez powodu (W-26) | powód z listy wymagany w serwisie, formularzach i skanerze | `services.correct_hu_quantity` |
| Formularz przyjęcia i zapis liczyły podział palet inaczej | reszta rozkładana po 1 szt. na ostatnie palety — zgodnie z kontrolą limitu w formularzu | `services.split_quantity` |
| Realizacja WZ, pakowanie, wysyłka, alokacja i korekty bez blokady wiersza | blokada `select_for_update` i ponowne sprawdzenie stanu; korekta liczona od zablokowanej wartości | `services._lock_and_sync`, `adjust_hu_quantity` |
| Kilka pozycji WZ mogło wskazywać więcej, niż jest na palecie | dodanie pozycji jest odrzucane z komunikatem | `views.issue_add_line` |
| Pojemność 0 („bez limitu”) w raporcie jako „pełna”; import wymuszał ≥ 1; import lokalizacji bez transakcji | „bez limitu” w raporcie, 0 dozwolone w imporcie, import w jednej transakcji | `report_locations.html`, `imports.py` |
| API skanera przyjmowało wydanie bez WZ | dokument wymagany | `scanner_views.api_pick` |
| 403 bez menu; kafel importu dla roli Podgląd; „Administracja” prowadziła do 404 (demo) lub do odmowy (Administrator bez superusera) | 403 w układzie aplikacji; kafel tylko dla operatora; link do panelu Django tylko dla superusera poza demo | `templates/403.html`, `base.html`, `dashboard.html` |
| Skaner po wygaśnięciu sesji: „Błąd serwera (200)”; pusty skan bez reakcji | przekierowanie na logowanie; komunikat „Pusty skan” | `scanner.js`, ekrany skanera |
| Skaner i „Realizuj” na tym samym WZ mogły pobrać ponad żądaną ilość | pozycja i dokument blokowane przed paletą; pobranie ponad pozostałą ilość albo do zamkniętego WZ odrzucane | `services.pick_from_hu` |
| Zamknięcie spisu na PostgreSQL: błąd `FOR UPDATE` na złączeniu z pustą paletą | blokada tylko pozycji arkusza (`of=("self",)`) | `services.close_stocktake` |
| Dwa równoległe przepakowania A→B i B→A mogły się zakleszczyć | blokady palet zawsze w kolejności `pk` | `services.repack_hu` |
| Brak powrotu z detali palety, WZ i spisu; brak „Anuluj” w przyjęciu; spis po cichu pomijał nieliczby | linki powrotu, „Anuluj”, ostrzeżenie o pominiętych wartościach | szablony, `views.stocktake_save` |

## Rozstrzygnięte decyzje (gałąź `fix/open-decisions`)

| Było | Teraz | Decyzja |
|---|---|---|
| Import stanów po cichu tworzył palety z ilością 0 i nie sprawdzał pojemności | podsumowanie podaje liczbę palet z ilością 0 i lokalizacje z przekroczoną pojemnością | [D-09](06-decyzje.md#d-09-import-stanów-z-ilością-0-zostaje--z-ostrzeżeniem) |
| Importy szukały palet bez rozróżniania wielkości liter, skaner i ekrany — z rozróżnianiem | wszędzie bez rozróżniania | [D-10](06-decyzje.md#d-10-numery-palet-bez-rozróżniania-wielkości-liter) |
| Zbiorczy wydruk etykiet obcinał listę do 200 bez komunikatu | powyżej 200 — komunikat „Zawęź filtr” | [D-11](06-decyzje.md#d-11-zbiorczy-wydruk-etykiet-limit-200-z-komunikatem) |
| Limit logowań tylko w demo; IP z podrabialnego `X-Forwarded-For` | limit zawsze; IP od zaufanego proxy (`DJANGO_TRUSTED_PROXY_COUNT`) | [D-12](06-decyzje.md#d-12-limit-logowań-zawsze-ip-tylko-od-zaufanego-proxy) |
| Dwa otwarte arkusze spisu mogły objąć tę samą paletę | nowy arkusz pomija palety z otwartego arkusza i mówi o tym | [D-13](06-decyzje.md#d-13-paleta-tylko-w-jednym-otwartym-arkuszu-spisu) |
| Blokady wierszy sprawdzane tylko na SQLite (gdzie nic nie blokują) | job CI `test-postgres`: cały zestaw na PostgreSQL 16 + test wyścigu dwóch WZ o jedną paletę | `tests_concurrency_pg.py` |
| Django 5.1 (bez poprawek bezpieczeństwa) | Django 5.2 LTS | — |

## Znane problemy

1. Limit logowań liczy próby w pamięci procesu (LocMem) — przy N workerach gunicorna realny
   limit to N×10 prób / 5 min. Wspólny cache (Redis), gdy to za mało.
2. Dwa arkusze spisu założone w tej samej chwili mogą jeszcze objąć tę samą paletę (brak
   blokady przy tworzeniu — przy ręcznym zakładaniu spisów wystarcza).
3. Wyszukiwanie palety bez rozróżniania wielkości liter (`number__iexact`) nie korzysta z
   indeksu na PostgreSQL — przy setkach palet bez znaczenia; przy dziesiątkach tysięcy indeks
   funkcyjny `Upper("number")` (migracja).

**Reguła celowa (nie błąd):** wydanie automatyczne bierze też palety „Do ułożenia” (bez
lokalizacji), na końcu kolejki — towar można wydać prosto z rampy, gdy na regałach go brakuje
([02](02-proces.md#punkty-decyzyjne), `services.py:367`).

Ścieżki ekranów: [03-user-flow.md](03-user-flow.md#ścieżki-ślepe-znane-problemy).

## Co dalej (priorytet)

1. Wspólny cache (Redis) dla limitu logowań, gdy aplikacja dostanie więcej workerów.
