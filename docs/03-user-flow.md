# 03. User flow — mapa ekranów i przejść

Numeracja ekranów: 1–35 panel w przeglądarce, 40–47 skaner (telefon lub kolektor).
Diagramy pokazują rdzeń przejść; pełna lista jest w tabelach.

## Panel web

```mermaid
flowchart LR
    subgraph S1["1 Logowanie"]
        s1a[Użytkownik, Hasło]:::el
        s1b[Zaloguj]:::el
        s1c[Konta demo — tylko DEMO]:::el
    end
    subgraph S2["2 Pulpit"]
        s2a[6 KPI, mapa obłożenia, ruchy 14 dni]:::el
        s2b[Plan na dziś, kafle skrótów]:::el
    end
    subgraph S5["5 HU (palety)"]
        s5a[Filtr numer/status, tabela HU]:::el
        s5b[Drukuj etykiety, + Przyjęcie, Ulokuj]:::el
    end
    subgraph S6["6 Szczegóły HU"]
        s6a[Dane HU, historia ruchów]:::el
        s6b[Ulokuj, Korekta, Przepakuj, Termin dostawy]:::el
    end
    subgraph S9["9 Przyjęcie"]
        s9a[Materiał, tryb, ilość, palety, LOT, data]:::el
        s9b[Przyjmij i wygeneruj HU]:::el
    end
    subgraph S11["11 Alokacja HU"]
        s11a[Lokalizacja — lista]:::el
        s11b[Ulokuj / Anuluj]:::el
    end
    subgraph S16["16 Lista WZ"]
        s16a[Tabela dokumentów]:::el
        s16b[+ Nowe wydanie, Import]:::el
    end
    subgraph S18["18 Szczegóły WZ"]
        s18a[Pozycje + podpowiedź FEFO]:::el
        s18b[Dodaj pozycję, Realizuj, Zamknij z brakami]:::el
        s18c[Spakuj, Wyślij, Drukuj WZ]:::el
    end
    subgraph S22["22 Spis — szczegóły"]
        s22a[Tabela: stan ewid., Policzono, Różnica]:::el
        s22b[Zapisz policzone, Zamknij i zatwierdź]:::el
    end
    S1 -->|Zaloguj OK| S2
    S1 -->|złe hasło| S1
    S2 -->|kafel / menu HU| S5
    S2 -->|menu Przyjęcie| S9
    S9 -->|OK: komunikat z numerami HU| S5
    S9 -->|błąd walidacji| S9
    S5 -->|numer HU| S6
    S5 -->|Ulokuj| S11
    S6 -->|Ulokuj/Przesuń| S11
    S11 -->|OK| S6
    S11 -->|lokalizacja pełna| S11
    S2 -->|menu Wydania| S16
    S16 -->|+ Nowe wydanie → Utwórz| S18
    S18 -->|Dodaj / Realizuj / Spakuj / Wyślij| S18
    S2 -->|menu Spis z natury| S22
    S22 -->|Zapisz / Zamknij| S22
    S2 -->|Wyloguj| S1
    classDef el fill:#f6f6f6,stroke:#bbb,color:#222
```

| Nr | Ekran (URL) | Rola | Elementy | Akcja użytkownika | Prowadzi do |
|---|---|---|---|---|---|
| 1 | Logowanie `/login/` | gość | Użytkownik, Hasło, Zaloguj; w DEMO: konta demo | Zaloguj | OK → 2 (lub `next`); błąd → 1 „Niepoprawny login lub hasło.”; DEMO >10 prób/5 min → 429 tekst |
| 2 | Pulpit `/` | wszyscy | 6 KPI, obłożenie lokalizacji, ruchy 14 dni, realizacja wydań, plan na dziś, kafle, top 10 materiałów, ostatnie ruchy | kafel / menu / pozycja planu | odpowiedni ekran |
| 3 | Materiały `/materialy/` | wszyscy | szukaj, tabela, „+ Nowy materiał” (operator) | Szukaj / + Nowy | 3 / 4 |
| 4 | Nowy materiał | operator | indeks, nazwa, jednostka, maks./paletę | Zapisz / Anuluj | 3 „Dodano materiał” / poprzednia strona |
| 5 | HU `/hu/` | wszyscy | filtr numer/status, tabela, Drukuj etykiety, + Przyjęcie, Ulokuj | numer HU / Ulokuj / Drukuj | 6 / 11 / PDF |
| 6 | HU — szczegóły | wszyscy | dane HU, historia (50); operator: Ulokuj, Korekta, Przepakuj; admin: Termin dostawy | przyciski | 11 / 12 / 15 / 13 / PDF |
| 7 | Lokalizacje | wszyscy | tabela, etykiety; operator: Import, + Nowa | | 8 / 10 / PDF |
| 8 | Nowa lokalizacja | operator | kod, typ, pojemność | Zapisz | 7 |
| 9 | Przyjęcie `/przyjecie/` | operator | materiał, tryb (całkowita / na paletę), ilości, palety, LOT, data ważności, nr dostawy; brak „Anuluj” | Przyjmij | OK → 5 z numerami HU; walidacja/limit → 9 |
| 10 | Import lokalizacji / przyjęć / zleceń / stanów | operator | plik CSV/XLSX (≤5 MB) | Importuj | lista (7 / 5 / 16 / 26) z podsumowaniem i ostrzeżeniami — także przy błędzie |
| 11 | Alokacja HU | operator | lokalizacja (lista) | Ulokuj / Anuluj | 6; pełna → 11 z błędem; pusty HU → 6 z błędem |
| 12 | Korekta ilości HU | operator | nowa ilość ≥0, uwaga | Zapisz korektę | 6 |
| 13 | Termin dostawy HU | admin | data, nr dostawy | Zapisz | 6 |
| 14 | Inwentaryzacja `/inwentaryzacja/` | operator | nr HU, Dodaj/Odejmij, ilość, powód, uwaga, ostatnie korekty | Zapisz zmianę | 14 z komunikatem; nieznany HU / stan <0 → błąd pola |
| 15 | Przepakowanie | operator | HU źródłowy, docelowy, ilość, ostatnie przepakowania | Przepakuj | 15 |
| 16 | Wydania `/wydania/` | wszyscy | tabela WZ; operator: Import, + Nowe | | 18 / 17 / 10 |
| 17 | Nowe wydanie | operator | referencja | Utwórz | 18 |
| 18 | WZ — szczegóły | wszyscy | pozycje z podpowiedzią FEFO, ruchy, Drukuj WZ; operator: Dodaj pozycję, Usuń, Realizuj, Zamknij z brakami, Spakuj, Wyślij | każda akcja | 18 z komunikatem (dane formularza przepadają przy błędzie) |
| 19 | Spis z natury `/spis/` | wszyscy | lista arkuszy; operator: nowy arkusz (zakres) | Utwórz arkusz | 22 |
| 22 | Spis — szczegóły | wszyscy | tabela z polem „Policzono” (operator, otwarty) | Zapisz / Zamknij | 22 |
| 26 | Stany `/stany/` | wszyscy | tabela wg materiału, CSV, Excel; operator: Import | Wg lokalizacji / eksport | 27 / plik |
| 27 | Stan wg lokalizacji | wszyscy | szukaj, tabela | HU | 6 |
| 28 | Ruchy `/ruchy/` | wszyscy | filtr typu, CSV, Excel, ostatnie 500 | | plik |
| 29 | Raporty | wszyscy | 4 karty | | 30 / 31 / 27 / 28 |
| 30 | Zajętość lokalizacji | wszyscy | KPI, tabela z zapełnieniem | kod | 27 |
| 31 | Kartoteka materiału | wszyscy | wybór materiału, stan, historia (500) | | 31 |
| 32 | Użytkownicy | admin | tabela, mapa uprawnień, Dziennik, + Nowy | | 33 / 34 / 35 |
| 33 | Nowy użytkownik | admin | login, e-mail, hasło, rola | Utwórz | 32 |
| 34 | Edycja użytkownika | admin | rola, aktywne, nowe hasło | Zapisz | 32; własne konto → błąd; konto demo → 403 tekst |
| 35 | Dziennik logowań | admin | tabela, stronicowanie 100 | | 32 |

## Skaner

```mermaid
flowchart LR
    subgraph K1["40 Menu skanera"]
        k1[6 kafli]:::el
    end
    subgraph K2["41 Rozmieszczanie"]
        k2a[Skan HU → karta HU]:::el
        k2b[Skan lokalizacji → Potwierdź / Reset]:::el
    end
    subgraph K3["42 Picking — lista"]
        k3[Skan numeru lub kafel zlecenia]:::el
    end
    subgraph K4["43 Picking — zlecenie"]
        k4a[Pozycje picked/requested]:::el
        k4b[Skan HU → ilość klawiaturą → Potwierdź]:::el
    end
    subgraph K5["44 Inwentaryzacja"]
        k5[Skan HU → ± ilość → Potwierdź]:::el
    end
    subgraph K6["45 Przepakowanie"]
        k6[Skan źródła → skan celu → ilość → Potwierdź]:::el
    end
    subgraph K7["46 Podgląd HU"]
        k7[Skan HU → karta]:::el
    end
    subgraph K8["47 Co w lokalizacji"]
        k8[Skan lokalizacji → lista palet]:::el
    end
    P2["2 Pulpit (web)"] -->|Otwórz skaner| K1
    K1 -->|‹| P2
    K1 --> K2 & K3 & K5 & K6 & K7 & K8
    K2 -->|Potwierdź OK → po 0,8 s| K2
    K3 -->|skan / kafel| K4
    K4 -->|pozycja OK| K4
    K4 -->|wszystko pobrane → Wróć do listy| K3
    K5 -->|OK| K5
    K6 -->|OK| K6
    classDef el fill:#f6f6f6,stroke:#bbb,color:#222
```

| Nr | Ekran | Elementy | Akcja | Prowadzi do / wynik |
|---|---|---|---|---|
| 40 | Menu skanera `/skaner/` | 6 kafli, „‹” | kafel / ‹ | 41–47 / Pulpit web |
| 41 | Rozmieszczanie | pole skanu, karta HU, karta lokalizacji, Potwierdź, Reset | skan HU → skan lokalizacji → Potwierdź | baner „✓ HU → LOC”, reset; błędy: nieznany HU/lokalizacja, pusty HU, pełna lokalizacja |
| 42 | Picking — lista | pole numeru, kafle otwartych WZ | skan / kafel | 43; nieznany numer → błąd |
| 43 | Picking — zlecenie | pozycje, skan HU, klawiatura, Potwierdź, „Wróć do listy” | skan HU → ilość → Potwierdź | pozycja odhaczona; komplet → WZ Zrealizowany → „Wróć do listy”; błędy: materiał spoza WZ, za dużo, brak stanu |
| 44 | Inwentaryzacja | skan HU, ±, ilość, „stan po zmianie”, Potwierdź | | ruch KOREKTA; błąd przy wyniku <0 |
| 45 | Przepakowanie | skan źródła, celu, ilość, „Cała paleta” | | 2 ruchy; błędy: ten sam HU, inny materiał, pusty cel, inny LOT (dopiero po Potwierdź) |
| 46 | Podgląd HU | skan HU, karta | | tylko odczyt |
| 47 | Co w lokalizacji | skan lokalizacji, lista palet | | tylko odczyt |

## Ścieżki alternatywne
- **Gość** → każdy adres przekierowuje na 1 i po zalogowaniu wraca (`next`).
- **Rola Podgląd** → menu bez operacji; wejście na adres operatora = domyślna strona 403 Django
  bez menu (`roles.py:37`).
- **Modal vs strona** — brak modali; potwierdzenia przez `confirm()` przeglądarki (usuń pozycję,
  realizuj, zamknij z brakami, zamknij spis).
- **Błąd walidacji** — formularze na osobnych stronach: ta sama strona z błędami pól; formularze
  wbudowane w szczegóły WZ i spisu: komunikat nad stroną, wpisane wartości przepadają.
- **Przerwanie procesu** — skaner: „Reset” lub „‹” bez potwierdzenia; web: „Anuluj” (brak na
  ekranie 9).

## Ścieżki ślepe (znane problemy)
1. Strona 403 bez nawigacji (każdy ekran operatora/admina dla złej roli).
2. Kafel „Import wydań” (D02) widoczny dla roli Podgląd → 403 (`dashboard.html:134`).
3. „Administracja” w menu i kafel A03 w trybie DEMO → 404 (`config/urls.py:41`).
4. Ekrany 6, 18, 22 bez linku powrotu do listy; ekran 9 bez „Anuluj”.
5. Skaner — wygasła sesja pokazuje „Błąd serwera (200).” zamiast logowania (`scanner.js:47-51`).
6. Skaner — pusty skan: brak reakcji; błąd wczytania zlecenia: pusta lista bez komunikatu
   (`picking_doc.html:93-95`).
7. Endpointy tylko-POST wywołane GET-em — ciche przekierowanie bez komunikatu.
8. Spis: wartości nie-liczbowe w „Policzono” pomijane bez informacji (`views.py:1009`).
9. „Administracja” dla roli Administrator bez konta superusera → logowanie panelu Django
   odrzuca konto (brak `is_staff`, `views.py:1220`).
10. Skaner — kompletacja: przy pozycji z „konkretnym HU” skaner przyjmuje dowolną paletę tego
    materiału, bez ostrzeżenia (`scanner_views.py:284-291`).
