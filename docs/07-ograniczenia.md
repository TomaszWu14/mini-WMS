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
| [W-25](05-wymagania.md) | Skaner respektuje paletę wskazaną w pozycji WZ | pozycja dobierana tylko po materiale (`warehouse/scanner_views.py:284-291`) |
| [W-26](05-wymagania.md) | Każda korekta ilości ma powód | powód tylko w „Inwentaryzacji”; „Korekta ilości” i skaner zapisują bez powodu (`warehouse/views.py:586`, `warehouse/scanner_views.py:404`) |

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
12. Zbiorczy wydruk etykiet palet obcina listę do 200 bez komunikatu (`views.py:514`).

**Reguły — obserwacje z przeglądu kodu**

13. Skaner ignoruje paletę wskazaną w pozycji WZ — wymaganie [W-25](05-wymagania.md).
14. Korekta bez powodu — wymaganie [W-26](05-wymagania.md).
15. Wydanie automatyczne bierze też palety „Do ułożenia” (bez lokalizacji), na końcu kolejki —
    **reguła celowa**: towar można wydać prosto z rampy, gdy na regałach go brakuje
    ([02](02-proces.md#punkty-decyzyjne), `services.py:315`).
16. Kilka pozycji WZ może wskazywać tę samą paletę; formularz sprawdza ilość tylko dla jednej
    pozycji, więc realizacja kończy się błędem braku stanu (`forms.py:340`).
17. Import lokalizacji nie pozwala ustawić pojemności 0 („bez limitu”) — wymusza ≥ 1
    (`imports.py:56`); formularz pozwala (`forms.py:59`). Import lokalizacji, w odróżnieniu od
    pozostałych trzech, nie działa w jednej transakcji (`imports.py:112`).
18. API skanera przyjmuje wydanie bez dokumentu WZ (ruch WYDANIE bez dokumentu); ekrany skanera
    z tego nie korzystają (`scanner_views.py:273`).

**Dostęp**
19. Rola Administrator bez konta superusera widzi „Administracja”, ale panel Django jej nie
    wpuści (konto nie ma `is_staff`, `views.py:1220`). Mapa uprawnień przypisuje
    Administratorowi „Edycję / usuwanie ruchów” (`views.py:1182`), a panel pozwala na to tylko
    superuserowi (`admin.py:106-111`).
20. Limit prób logowania działa tylko w trybie demo (`demo.py:50`). Adres IP w dzienniku i w
    limicie pochodzi z nagłówka `X-Forwarded-For` bez weryfikacji (`signals.py:30-35`).

**Współbieżność — uzupełnienie**
21. Alokacja nie blokuje lokalizacji — dwie równoczesne mogą przekroczyć pojemność
    (`services.py:160-174`).
22. Dwa otwarte arkusze spisu mogą obejmować tę samą paletę (`services.py:534`).

Pełna lista ścieżek ślepych: [03-user-flow.md](03-user-flow.md#ścieżki-ślepe-znane-problemy).

## Co dalej (priorytet)

1. W-11 — FEFO na skanerze (podpowiedź palety, ostrzeżenie przy innej).
2. W-25 — skaner pilnuje palety wskazanej w pozycji WZ.
3. W-26 — powód przy każdej korekcie.
4. W-08 — pojemność jako ostrzeżenie zamiast blokady.
5. Problem 1 — jedna reguła podziału w formularzu i w zapisie.
6. Problem 5 — blokada dokumentu przy realizacji.
7. Aktualizacja Django 5.1 → 5.2 LTS (seria 5.1 nie dostaje już poprawek bezpieczeństwa).
