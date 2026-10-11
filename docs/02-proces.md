# 02. Proces biznesowy

## Aktorzy

| Aktor | Rola w procesie |
|---|---|
| **Operator** | przyjmuje towar, rozmieszcza palety, kompletuje wydania, koryguje, przepakowuje, liczy spis |
| **Administrator** | to co operator + konta i role, dziennik logowań, termin dostawy palety |
| **Podgląd** | tylko odczyt: stany, palety, wydania, ruchy, raporty |
| **System** | nadaje numery palet i dokumentów, dobiera palety FEFO → FIFO, zapisuje każdy ruch |

## PRZED — ewidencja na papierze

```mermaid
flowchart TD
    A([Dostawa]) --> B[Operator zapisuje towar na kartce]
    B --> C[Paleta odstawiona — miejsce zapamiętane lub dopisane ręcznie]
    D([Zamówienie]) --> E[Operator szuka palety po pamięci lub kartce]
    E --> F{Znalazł?}
    F -->|nie| E
    F -->|tak| G[Zdejmuje towar — dowolna paleta, bez kontroli daty ważności]
    G --> H[Dopisuje wydanie na kartce — albo zapomina]
    I([Inwentaryzacja]) --> J[Liczenie całego magazynu i porównanie z kartką]
```

Słabe punkty: brak etykiet (C, E), pętla szukania (F), brak reguły wydania (G), brak
historii (H), inwentaryzacja bez punktu odniesienia (J).

## PO — z aplikacją

```mermaid
flowchart TD
    A([Dostawa]) --> B{Jak przyjąć?}
    B -->|formularz| C[Przyjęcie: materiał, ilość, liczba palet, partia, data ważności]
    B -->|plik CSV/XLSX| C2[Import przyjęć]
    C --> D{Ilość na paletę mieści się w limicie materiału?}
    C2 --> D
    D -->|nie| D1[Komunikat: zwiększ liczbę palet]
    D -->|tak| E[System tworzy palety: status Do ułożenia + ruch PRZYJĘCIE]
    E --> F[Wydruk etykiet z kodem QR]
    F --> G[Rozmieszczanie: skan palety i skan miejsca — albo wybór w panelu]
    G --> I[Paleta Zmagazynowana + ruch ALOKACJA lub PRZESUNIĘCIE]

    J([Zamówienie]) --> K[Dokument WZ: ręcznie lub z pliku]
    K --> L[Pozycje: po materiale albo konkretna paleta]
    L --> M{Gdzie kompletować?}
    M -->|panel| N{Wystarczy stanu?}
    N -->|tak| O[Realizuj: system dobiera palety — PICKING przed ZAPAS, FEFO, FIFO]
    N -->|nie| O2[Zamknij z brakami: wydaj tyle, ile jest]
    M -->|skaner| P[Operator skanuje paletę z materiałem z dokumentu]
    O --> Q[WZ Zrealizowany + ruchy WYDANIE]
    O2 --> Q
    P -->|wszystko pobrane| Q
    Q --> R[Spakuj] --> S[Wyślij: przewoźnik, numer przesyłki]
    Q -.->|pakowanie można pominąć| S

    T([Kontrola stanu]) --> U{Rodzaj}
    U -->|jedna paleta| V[Inwentaryzacja: ± ilość → ruch KOREKTA]
    U -->|łączenie palet| W{Ten sam materiał i partia?}
    W -->|tak| W1[Przepakowanie → dwa ruchy PRZEPAKOWANIE]
    W -->|nie| W2[Komunikat o błędzie]
    U -->|spis z natury| X[Arkusz = migawka stanu] --> Y[Wpisanie policzonych ilości] --> Z[Zamknięcie: różnice jako korekty z powodem SPIS]
```

## Punkty decyzyjne

| Punkt | Reguła | Gdzie |
|---|---|---|
| Limit na paletę | ilość na jednej palecie ≤ limit materiału (jeśli ustawiony) | `services.py:114` |
| Miejsce na regale | pojemność jest informacyjna — przekroczenie nie blokuje odłożenia, system pokazuje ostrzeżenie | `services.allocate_hu`, `location_over_capacity` |
| Dostępność stanu | wydanie po materiale wymaga pełnej dostępnej ilości; tryb „z brakami” wydaje, ile jest | `services.py:381`, `services.py:407` |
| Dobór palet | PICKING przed ZAPAS → najkrótsza data ważności → najstarsze przyjęcie | `services.py:305` |
| Wydanie z rampy | gdy na regałach brakuje, system bierze też palety „Do ułożenia” (bez lokalizacji) — na końcu kolejki | `services.py:315` |
| Łączenie palet | ten sam materiał, zgodna partia, cel niepusty | `services.py:251-269` |
| Spis | różnica policzone ≠ stan → korekta | `services.py:560` |
| Korekta pustej palety | korekta z 0 na więcej przywraca paletę do statusu „Do ułożenia” (bez lokalizacji) | `services.py:212` |

## Założenia procesu

- **Na czas spisu z natury magazyn jest zamrożony** — zamknięcie arkusza porównuje
  policzoną ilość z bieżącym stanem palety.
- **Wysyłka bez pakowania jest dozwolona** — pakowanie to opcjonalny krok.
- **Zwrotów nie ma** — proces kończy się na wysyłce.
