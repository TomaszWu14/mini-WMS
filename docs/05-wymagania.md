# 05. Wymagania

Wymagania odtworzone z działającego kodu i potwierdzone z interesariuszami. Kolumna
„Gdzie zrealizowane” wskazuje kod i test, który sprawdza kryterium (`warehouse/tests.py`,
chyba że podano inaczej). **Cztery wymagania nie są spełnione** — oznaczone ⚠ i opisane w
[07-ograniczenia.md](07-ograniczenia.md).

## Przyjęcie i etykiety

| ID | Wymaganie | Kryterium akceptacji | Gdzie zrealizowane |
|---|---|---|---|
| W-01 | Operator przyjmuje towar, podając materiał, ilość i liczbę palet | Przyjęcie 100 szt. na 3 palety tworzy 3 palety po 33, 33 i 34 szt., każda ze statusem „Do ułożenia” i ruchem PRZYJĘCIE | `services.py:75` `split_quantity`, `receive_material`; `ReceiveTests`, `SplitQuantityTests` |
| W-02 | Ilość na palecie nie przekracza limitu materiału | Przy limicie 50 przyjęcie 120 szt. na 2 palety jest odrzucane z komunikatem o limicie | `services.py:114`, `forms.py:244`; `test_receive_respects_max_per_pallet` |
| W-03 | Każda paleta ma unikalny numer nadawany automatycznie | Dwa kolejne przyjęcia dają kolejne numery bez duplikatów | `services.py:59` `generate_hu_number`; `test_sequential_unique_numbers` |
| W-04 | Etykieta palety z kodem QR do druku | Etykieta PDF zawiera numer palety, materiał, ilość i kod QR; komplet pól mieści się na jednej stronie A4 | `labels.py`; `test_hu_label_with_all_fields_single_page` |
| W-05 | Przyjęcia i stany początkowe można wczytać z pliku CSV/XLSX | Plik z nieznanym materiałem: poprawne wiersze wczytane, błędny pominięty z komunikatem „Wiersz N…” | `receipt_import.py`, `stock_import.py`; `ReceiptImportTests`, `StockImportTests` |

## Rozmieszczanie

| ID | Wymaganie | Kryterium akceptacji | Gdzie zrealizowane |
|---|---|---|---|
| W-06 | Operator odkłada paletę w lokalizacji — w panelu lub skanerem | Po skanie palety i miejsca paleta ma status „Zmagazynowany”, lokalizację i ruch ALOKACJA | `services.py` `allocate_hu`, `scanner_views.py` `api_allocate`; `test_allocate_sets_location_and_status`, `test_api_allocate` |
| W-07 | Zmiana miejsca palety jest zapisywana jako przesunięcie | Przeniesienie z A do B tworzy ruch PRZESUNIĘCIE z polami „z” i „do” | `services.py:182` |
| W-08 ⚠ | Pojemność lokalizacji jest **informacyjna** | Odłożenie palety do lokalizacji „pełnej” jest możliwe; system tylko informuje o przekroczeniu | **Niespełnione:** `services.py:160-170` blokuje alokację (`test_allocate_enforces_capacity` sprawdza blokadę) |
| W-09 | Pustej palety nie da się odłożyć | Próba alokacji palety o statusie „Pusty” kończy się komunikatem | `services.py:153`, `views.py` `hu_allocate` |

## Wydania

| ID | Wymaganie | Kryterium akceptacji | Gdzie zrealizowane |
|---|---|---|---|
| W-10 | Wydanie po materiale dobiera palety automatycznie: PICKING przed ZAPAS, potem najkrótsza data ważności, potem najstarsze przyjęcie | Dwie palety tego materiału z datami 2026-01 i 2026-03 → wydanie bierze najpierw paletę z 2026-01; paleta w PICKING ma pierwszeństwo przed ZAPAS | `services.py:305` `_pickable_hus`; `test_fefo_prefers_earliest_expiry`, `test_picking_location_priority` |
| W-11 ⚠ | Kolejność FEFO obowiązuje także przy kompletacji **skanerem** | Skan palety z późniejszą datą, gdy jest paleta z wcześniejszą, kończy się ostrzeżeniem lub odmową | **Niespełnione:** `scanner_views.py` `api_pick` przyjmuje dowolną paletę z materiałem z dokumentu |
| W-12 | Stan palety nie może spaść poniżej zera | Wydanie 60 szt. z palety z 50 szt. jest odrzucane; baza odrzuca ilość < 0 | `services.py:341-347`, `models.py:216`; `test_overpick_blocked`, `test_hu_quantity_check_constraint` |
| W-13 | Dokument WZ realizowany w całości albo z brakami | Brak stanu: „Realizuj” zgłasza błąd; „Zamknij z brakami” wydaje dostępną ilość i pokazuje brak | `services.py:407` `execute_issue_document`; `test_full_execution_raises_on_shortage`, `test_partial_execution_closes_with_shortage` |
| W-14 | Pozycję WZ można wskazać jako konkretną paletę | Pozycja z paletą innego materiału niż pozycja jest odrzucana przy realizacji | `forms.py:327`, `services.py:421`; `test_execute_rejects_specific_hu_wrong_material` |
| W-15 | Po pobraniu całej palety jest ona „Pusta” i zwalnia miejsce | Wydanie całej ilości → status „Pusty”, brak lokalizacji | `services.py:231`; `test_pick_to_zero_marks_empty_and_frees_location` |
| W-16 | WZ przechodzi przez stany: Otwarty → Zrealizowany → (Spakowany) → Wysłany | Spakować można tylko zrealizowany; wysłać — zrealizowany lub spakowany; pozycji nie da się zmienić poza stanem „Otwarty” | `services.py:477, 489`, `views.py` `issue_add_line`; `test_pack_and_ship_flow`, `test_pack_requires_realized`, `test_cannot_add_line_to_packed_document` |
| W-17 | Skaner prowadzi kompletację dokumentu i zamyka go po pobraniu wszystkiego | Ostatnia pozycja pobrana → WZ „Zrealizowany”; materiał spoza dokumentu odrzucony | `scanner_views.py` `api_pick`; `test_document_pick_completes_order`, `test_document_pick_rejects_wrong_material` |
| W-25 ⚠ | Skaner respektuje paletę wskazaną w pozycji WZ | Pozycja z „konkretnym HU”: skan innej palety tego samego materiału kończy się odmową | **Niespełnione:** `scanner_views.py:284-291` dobiera pozycję tylko po materiale |

## Kontrola stanu

| ID | Wymaganie | Kryterium akceptacji | Gdzie zrealizowane |
|---|---|---|---|
| W-18 | Korekta ilości palety z powodem i historią | Korekta +5 tworzy ruch KOREKTA +5 z powodem; korekta o 0 jest odrzucana | `services.py:198` `correct_hu_quantity`; `test_correction_logs_movement`, `test_web_inventory_add` |
| W-19 | Łączenie palet tylko tego samego materiału i partii | Przepakowanie między różnymi materiałami jest odrzucane; opróżnione źródło staje się „Puste” | `services.py:242` `repack_hu`; `RepackTests` |
| W-20 | Spis z natury: migawka → liczenie → zatwierdzenie różnic | Zamknięcie arkusza z różnicą tworzy korektę z powodem „Spis z natury”; pozycje niepoliczone nie zmieniają stanu | `services.py:534, 560`; `StocktakeTests` |
| W-26 ⚠ | Każda korekta ilości ma powód | Zapis korekty bez powodu jest odrzucany — na ekranie palety, w inwentaryzacji i na skanerze | **Niespełnione:** powód wybierany tylko w „Inwentaryzacji” (`forms.py:112`); „Korekta ilości” i skaner zapisują bez powodu (`views.py:586`, `scanner_views.py:404`) |

## Raporty i dostęp

| ID | Wymaganie | Kryterium akceptacji | Gdzie zrealizowane |
|---|---|---|---|
| W-21 | Każda zmiana stanu zostawia ślad: kto, kiedy, ile, skąd, dokąd | Każda operacja z W-01…W-20 tworzy wpis w rejestrze ruchów | `models.py` `StockMovement`, `services.py`; `test_receive_creates_hus_and_movements` |
| W-22 | Stany i ruchy można wyeksportować do CSV i Excel | Eksport respektuje filtr typu; komórki zaczynające się od `=` są neutralizowane | `exports.py`; `test_movement_export_respects_type_filter`, `test_csv_export_neutralizes_formula_injection` |
| W-23 | Trzy role: Podgląd (odczyt), Operator (operacje), Administrator (konta) | Podgląd nie otworzy przyjęcia (403); nowe konto ma domyślnie rolę Podgląd | `roles.py`; `test_viewer_role_forbidden_on_receive`, `test_new_user_default_viewer` |
| W-24 | Dziennik logowań i ochrona kont | Udane i nieudane logowania są zapisywane; administrator nie odbierze sobie roli; słabe hasło jest odrzucane | `signals.py`, `views.py` `user_edit`; `SecurityTests` |
