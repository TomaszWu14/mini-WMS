# Wizja produktu — miniWMS

| | |
|---|---|
| Wersja | 0.1 |
| Data | 2026-10-16 |
| Status | szkic — do akceptacji Product Ownera |
| Właściciel | [BA] |

Dokument uzupełnia [docs/01](../01-problem-i-zakres.md), nie zastępuje go (Z-03). Dopisuje to, czego
brakowało wg [audytu §1.2–1.3](../AUDYT.md): mierniki sukcesu i horyzont. Co nieznane — oznaczone
„do potwierdzenia (Z-xx)” albo zebrane w sekcji „Otwarte pytania”.

## 1. Problem

Mały magazyn (ok. 200 palet, ok. 30 nowych tygodniowo, dwóch operatorów na zmiany, bez ERP) prowadził
ewidencję na kartce: palety bez etykiet, miejsce towaru znane tylko temu, kto je odstawił, brak historii
ruchów, wydania bez względu na datę ważności i inwentaryzacja bez punktu odniesienia. Liczb strat nie
zbierano — problem jest opisany jakościowo. Pełny opis: [docs/01 — Problem](../01-problem-i-zakres.md#problem).

## 2. Cel produktu

Jedno źródło prawdy o tym, **co** jest w magazynie, **gdzie** stoi i **co się z tym działo** — na poziomie
pojedynczej palety ([docs/01 — Cel](../01-problem-i-zakres.md#cel)). Rozpisany na efekty, które mają być
mierzalne:

| Efekt biznesowy | Mechanizm w produkcie | Miernik |
|---|---|---|
| Szybciej znaleźć paletę | etykieta QR, lokalizacja zapisana skanem | M-01 |
| Wydawać zgodnie z datą ważności | dobór FEFO → FIFO, podpowiedź w WZ i na skanerze | M-02 |
| Wiedzieć, ile naprawdę jest | korekty z powodem, spis z natury | M-03 |
| Szybciej obsłużyć dostawę | przyjęcie z podziałem na palety i wydruk etykiet | M-04 |
| Móc polegać na narzędziu | stabilność i dostępność | M-05, M-06 |

## 3. Dla kogo

Magazynierzy (Operator), kierownicy (stan, historia, spis), administrator kont oraz — w publicznym demo —
odwiedzający oceniający projekt. Pełna lista z wpływem i rolami: [INTERESARIUSZE.md](INTERESARIUSZE.md)
(ST-01…ST-10). Uwaga: wymagania pochodzą z obserwacji autora, nie z wdrożenia ([README](../../README.md),
[audyt §1.3 pkt 7](../AUDYT.md)).

## 4. Co NIE jest celem

Integracja z ERP, zwroty i anulowanie WZ, blokada palet po terminie ważności, wiele magazynów i strefy,
rezerwacja stanu pod otwarte WZ, atrybuty logistyczne materiału — decyzje zakresowe wraz z uzasadnieniem:
[docs/01 — Poza zakresem](../01-problem-i-zakres.md#poza-zakresem--i-dlaczego) i
[docs/07](../07-ograniczenia.md). Zmiana któregokolwiek punktu wymaga decyzji PO (pytanie 5 poniżej).

## 5. Mierniki sukcesu (propozycja do uzgodnienia)

Wartość bazowa dla wszystkich: **brak danych** — liczb nie zbierano, aplikacja nie była wdrożona. Pierwszy
pomiar po wdrożeniu (lub pilotażu) staje się punktem odniesienia; cele ustala PO **po** tym pomiarze, nie przed.

| ID | Miernik | Jak mierzyć (źródło) | Baza | Cel |
|---|---|---|---|---|
| M-01 | Czas znalezienia palety | poza aplikacją: stoper na próbie losowo wskazanych palet. W aplikacji tylko pośrednio: udział palet z ilością > 0 w statusie „Do ułożenia” (bez lokalizacji) — lista HU z filtrem statusu | brak danych | do potwierdzenia |
| M-02 | Odsetek wydań zgodnych z FEFO | `StockMovement` typu WYDANIE + data ważności palet (odtworzenie, czy w chwili wydania była paleta z krótszą datą w tej samej klasie PICKING/ZAPAS). Ostrzeżenie skanera trafia do odpowiedzi API (`scanner_views.py:329`); zapisu odstępstwa w ruchu nie stwierdzono — do oceny [DEV] | brak danych | do potwierdzenia (kierunek: wzrost) |
| M-03 | Korekty po spisie | `StockMovement` typu KOREKTA z powodem SPIS: liczba i suma \|Δ\| na arkusz (`StocktakeSheet.closed_at`); odsetek pozycji arkusza z różnicą | brak danych | do potwierdzenia (kierunek: spadek z kolejnymi spisami) |
| M-04 | Czas przyjęcia dostawy | czas od ruchu PRZYJĘCIE do ALOKACJA tej samej palety (`StockMovement.created_at`); rozładunek i etykietowanie — poza aplikacją (stoper) | brak danych | do potwierdzenia |
| M-05 | Liczba błędów 500 | logi JSON na stdout (`config/log.py`, kontener `web`); alertów brak (T15), więc liczenie ręczne z logów | brak danych | do potwierdzenia (kierunek: 0 w ścieżkach operatora) |
| M-06 | Dostępność i użycie demo | `GET /healthz` sondowany z zewnątrz (monitoring poza repo — dziś brak); użycie: liczba `LoginEvent` (LOGIN) kont demo na dobę — zawyżana przez boty (R5), retencja wg Z-09 | brak danych | do potwierdzenia (Z-05) |

## 6. Horyzont — dwa scenariusze celu repozytorium

Cel repozytorium nie jest rozstrzygnięty ([audyt §4 pyt. 1](../AUDYT.md)); roboczo obowiązuje Z-04 (**B**).

| Aspekt | A. Portfolio / rekrutacja | B. Wdrożenie u klienta |
|---|---|---|
| Odbiorca | rekruterzy, oceniający kod i proces (ST-09) | magazynierzy i kierownik realnej firmy (ST-01…03) |
| Sukces to | demo działa, dokumenty i proces są widoczne, CI zielone | M-01…M-05 poprawione względem pomiaru bazowego w realnym magazynie |
| Priorytet backlogu | stabilność demo (R3–R5), czytelność dokumentów | R1–R4, R7, RODO, 2FA (R6), backup off-site i test odtworzenia (R9), runbook |
| Dane | fikcyjne; osobowe tylko odwiedzających demo | dane firmy i pracowników → RODO obowiązkowe |
| Walidacja z użytkownikami | niepotrzebna | wymagana (test skanera: telefon, rękawice, hala) |
| Mierzalne mierniki | tylko M-05, M-06 | M-01…M-06 |

Wynika z tego: (1) bez wdrożenia M-01…M-04 nie mają źródła danych, więc w scenariuszu A pozostają
„do potwierdzenia”; (2) Z-04 przyjmuje wyższy reżim (B), bo łatwiej go obniżyć niż nadrobić — stąd
pierwszeństwo poprawek bezpieczeństwa przed nowymi funkcjami (Z-07); (3) rozstrzygnięcie A/B/oba zmienia
kolejność backlogu, nie zakres już zbudowanych funkcji.

## 7. Status produktu

Zaawansowany prototyp, niewdrożony u klienta ([docs/01](../01-problem-i-zakres.md#status),
[docs/07](../07-ograniczenia.md)). 26 wymagań W-01…W-26 spełnionych ([docs/05](../05-wymagania.md)), wersja
`0.1.0` bez tagów (T13), działa publiczne demo (`miniwms.twapp.pl`). Stan jakości i pilne luki:
[AUDYT §2.2 i §3.4](../AUDYT.md).

## Otwarte pytania (do PO)

1. Cel repozytorium: portfolio (A), wdrożenie (B) czy oba? — rozstrzyga Z-04 i kolejność backlogu.
2. Czy zestaw M-01…M-06 jest właściwy; którego nie mierzymy?
3. Kto i jak zmierzy wartości bazowe M-01 i M-04, skoro nie ma magazynu pilotażowego (pilotaż, symulacja)?
4. Czy wolno zmienić aplikację (zapis odstępstwa od FEFO w ruchu) wyłącznie na potrzeby M-02? To nowe wymaganie.
5. Czy „poza zakresem” z docs/01 zostaje bez zmian i czy jest lista kandydatów na kolejne funkcje
   (docs/07 „Co dalej” ma jeden punkt)? ([audyt §1.3 pkt 4–5](../AUDYT.md))
