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

| ID | Wymaganie | Stan w kodzie |
|---|---|---|
| [W-08](05-wymagania.md) | Pojemność lokalizacji ma być **informacyjna** | alokacja blokuje przepełnienie (`warehouse/services.py:160-170`) |
| [W-11](05-wymagania.md) | FEFO także przy kompletacji **skanerem** | skaner przyjmuje dowolną paletę z materiałem z dokumentu (`warehouse/scanner_views.py` `api_pick`) |

## Znane problemy

**Reguły i dane**
1. Formularz przyjęcia liczy najcięższą paletę jako zaokrąglenie w górę (`forms.py:248`), a
   podział kładzie całą resztę na ostatnią paletę (`services.py:84`). Przykład: 10 szt. na
   4 palety przy limicie 3 — formularz przepuszcza, zapis kończy się błędem.
2. Lokalizacja z pojemnością 0 („bez limitu”) w raporcie zajętości jest pokazana jako „pełna”
   (`templates/warehouse/report_locations.html:24`).
3. Import stanów tworzy palety z ilością 0 o statusie „Zmagazynowany” i zakłada lokalizacje bez
   sprawdzania pojemności (`stock_import.py:125-137`).
4. Numery palet: importy porównują bez rozróżniania wielkości liter, skaner i ekrany — z
   rozróżnianiem.

**Współbieżność** (przy dwóch operatorach ryzyko niskie, ale realne)
5. Realizacja WZ nie blokuje dokumentu — dwa równoczesne kliknięcia „Realizuj” mogą wydać
   podwójnie (`services.py:407`). Do potwierdzenia testem na PostgreSQL.
6. Korekty ilości liczą nowy stan z wartości odczytanej wcześniej, bez blokady palety
   (`views.py:1048`, `services.py:198`).

**Ekrany**
7. Strona „brak uprawnień” (403) nie ma menu — użytkownik wraca przyciskiem przeglądarki.
8. Kafel „Import wydań” na pulpicie jest widoczny dla roli Podgląd i prowadzi do 403.
9. W trybie demo „Administracja” w menu prowadzi do 404.
10. Skaner: po wygaśnięciu sesji (30 min) pokazuje „Błąd serwera (200).” zamiast ekranu
    logowania; pusty skan nie daje żadnej reakcji.
11. Szczegóły palety, WZ i spisu nie mają linku powrotu do listy; przyjęcie nie ma „Anuluj”.

Pełna lista ścieżek ślepych: [03-user-flow.md](03-user-flow.md#ścieżki-ślepe-znane-problemy).

## Co dalej (priorytet)

1. W-11 — FEFO na skanerze (podpowiedź palety, ostrzeżenie przy innej).
2. W-08 — pojemność jako ostrzeżenie zamiast blokady.
3. Problem 1 — jedna reguła podziału w formularzu i w zapisie.
4. Problem 5 — blokada dokumentu przy realizacji.
5. Aktualizacja Django 5.1 → 5.2 LTS (seria 5.1 nie dostaje już poprawek bezpieczeństwa).
