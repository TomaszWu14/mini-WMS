# 01. Problem i zakres

## Problem

Mały magazyn prowadził ewidencję na kartce papieru. Około 200 palet (liczba rośnie),
około 30 nowych palet tygodniowo, dwóch operatorów pracujących na zmiany. Firma nie ma
systemu ERP.

Skutki pracy na papierze:

- **palety nie mają etykiet** — nie da się ich jednoznacznie wskazać ani zeskanować,
- **miejsce palety zna tylko osoba, która ją odstawiła** — szukanie towaru zależy od pamięci,
- **brak historii** — nie wiadomo, kto, kiedy i ile przyjął lub wydał,
- **wydanie bez reguły** — operator bierze dowolną paletę, a nie tę z najkrótszą datą
  ważności,
- **inwentaryzacja** to liczenie całego magazynu i porównanie z kartką.

Liczb strat lub błędów nie zbierano — problem opisany jest jakościowo.

## Interesariusze

| Kto | Potrzeba |
|---|---|
| Magazynierzy (operatorzy) | szybko przyjąć, odłożyć i znaleźć paletę; skanować zamiast pisać |
| Kierownicy | aktualny stan i miejsce towaru; historia operacji; spis z natury bez chaosu |
| Administrator systemu | konta i role; kto się logował |

Wymagania zgłaszali magazynierzy i kierownicy.

## Cel

Jedno źródło prawdy o tym, **co** jest w magazynie, **gdzie** stoi i **co się z tym działo** —
na poziomie pojedynczej palety.

## Słownik

| Pojęcie | Znaczenie |
|---|---|
| **HU** (Handling Unit) | paleta z unikalnym numerem i etykietą; podstawowa jednostka stanu |
| **Lokalizacja** | miejsce na regale; typ **PICKING** (miejsce kompletacji, bliżej) albo **ZAPAS** |
| **WZ** | dokument wydania zewnętrznego — lista materiałów do wydania |
| **FEFO** | *First Expired, First Out* — najpierw wydawany towar z najkrótszą datą ważności |
| **FIFO** | *First In, First Out* — przy równych datach najpierw najstarsze przyjęcie |
| **Ruch** | zapis każdej zmiany stanu: kto, kiedy, ile, skąd, dokąd |
| **Spis z natury** | inwentaryzacja: migawka stanu → liczenie → zatwierdzenie różnic |

## Zakres — co jest

- Słownik materiałów i lokalizacji (ręcznie i z plików CSV/XLSX).
- Przyjęcie towaru z podziałem na palety i wydrukiem etykiet z kodem QR.
- Rozmieszczanie i przesuwanie palet (panel i skaner w telefonie).
- Wydania: dokument WZ, automatyczny dobór palet FEFO → FIFO, realizacja pełna albo z
  brakami, pakowanie, wysyłka.
- Korekty ilości, łączenie palet (przepakowanie), spis z natury.
- Stany, rejestr ruchów, raporty, eksport CSV/XLSX.
- Trzy role: Administrator, Operator, Podgląd; dziennik logowań.

## Poza zakresem — i dlaczego

| Czego nie ma | Dlaczego |
|---|---|
| Integracja z ERP | firma nie ma ERP; dane wchodzą z plików |
| Zwroty od klientów, anulowanie WZ | w tym magazynie zwrotów nie ma |
| Blokada palet po terminie ważności | decyzja zakresu — reguła FEFO wydaje je jako pierwsze |
| Wiele magazynów, strefy, ścieżki kompletacji | jeden mały magazyn |
| Rezerwacja stanu pod otwarte WZ | przy tej skali dostępność liczona w chwili realizacji wystarcza |

Szczegóły ograniczeń i znanych problemów: [07-ograniczenia.md](07-ograniczenia.md).

## Status

Zaawansowany prototyp.
