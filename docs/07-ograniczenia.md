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

## Znane problemy (otwarte — wymagają decyzji)

1. Import stanów tworzy palety z ilością 0 o statusie „Zmagazynowany” (ilość „do uzupełnienia”)
   i zakłada lokalizacje bez sprawdzania pojemności (`stock_import.py:125-137`).
2. Numery palet: importy porównują bez rozróżniania wielkości liter, skaner i ekrany — z
   rozróżnianiem.
3. Zbiorczy wydruk etykiet palet obcina listę do 200 bez komunikatu (`views.py:514`).
4. Limit prób logowania działa tylko w trybie demo (`demo.py:50`). Adres IP w dzienniku i w
   limicie pochodzi z nagłówka `X-Forwarded-For` bez weryfikacji (`signals.py:30-35`) —
   poprawka zależy od konfiguracji proxy na serwerze.
5. Dwa otwarte arkusze spisu mogą obejmować tę samą paletę (`services.py:600`).
6. Blokady wierszy działają tylko na PostgreSQL; testy na SQLite nie dowodzą braku wyścigów.

**Reguła celowa (nie błąd):** wydanie automatyczne bierze też palety „Do ułożenia” (bez
lokalizacji), na końcu kolejki — towar można wydać prosto z rampy, gdy na regałach go brakuje
([02](02-proces.md#punkty-decyzyjne), `services.py:367`).

Ścieżki ekranów: [03-user-flow.md](03-user-flow.md#ścieżki-ślepe-znane-problemy).

## Co dalej (priorytet)

1. Decyzje do problemów 1–5 powyżej.
2. Test współbieżności realizacji WZ na PostgreSQL (CI z usługą Postgres).
3. Aktualizacja Django 5.1 → 5.2 LTS (seria 5.1 nie dostaje już poprawek bezpieczeństwa).
