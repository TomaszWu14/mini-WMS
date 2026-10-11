# 06. Dziennik decyzji

Format: decyzja → kontekst → rozważane opcje → dlaczego ta → skutki.
Decyzje D-01…D-04 potwierdzone jako przemyślane; D-05…D-08 wynikają z kodu i odpowiedzi
interesariuszy.

## D-01. Stan prowadzony na poziomie palety (HU), nie sumy w lokalizacji

- **Kontekst:** towar ma partie i daty ważności; dwie palety tego samego materiału mogą mieć
  różne daty. Na papierze nie dało się wskazać, którą paletę wydać.
- **Rozważane opcje:** `<DO UZUPEŁNIENIA: co rozważałeś — np. stan jako ilość materiału w
  lokalizacji?>`
- **Dlaczego ta:** reguła FEFO wymaga daty ważności przypisanej do konkretnej palety; etykieta
  z QR identyfikuje jeden fizyczny obiekt, który operator skanuje.
- **Skutki:** każda operacja dotyczy palety (`HandlingUnit`); stan materiału to suma palet.
  Potrzebne są operacje na paletach: przepakowanie, korekta, status „Pusty”.

## D-02. Brak zewnętrznej master daty — słownik materiałów prowadzony w aplikacji

- **Kontekst:** firma nie ma ERP ani innego źródła kartotek materiałowych.
- **Rozważane opcje:** `<DO UZUPEŁNIENIA>`
- **Dlaczego ta:** materiał to tylko indeks, nazwa, jednostka i opcjonalny limit na paletę —
  tyle, ile potrzebuje magazyn; import stanów sam zakłada brakujące materiały.
- **Skutki:** brak atrybutów logistycznych (wymiary, waga, EAN); ryzyko literówek w indeksach
  przy ręcznym zakładaniu.

## D-03. Numer WZ liczony od nowa każdego dnia (`WZ<data>-NNN`)

- **Kontekst:** numer dokumentu wydania nadaje system przy jego utworzeniu.
- **Rozważane opcje:** `<DO UZUPEŁNIENIA — np. jeden licznik ciągły?>`
- **Dlaczego ta:** `<DO UZUPEŁNIENIA — np. czy data w numerze miała ułatwiać szukanie dokumentu?>`
- **Skutki:** licznik nie jest blokowany w bazie — przy kolizji zapis jest ponawiany
  (`services.py:37`); numer jest odporny na usunięcie dokumentu (`services.py:501`).

## D-04. Wymiana danych plikami CSV/XLSX zamiast integracji

- **Kontekst:** firma nie ma systemu ERP.
- **Rozważane opcje:** `<DO UZUPEŁNIENIA>`
- **Dlaczego ta:** nie ma systemu, z którym można się zintegrować; plik CSV/XLSX da się
  przygotować w dowolnym arkuszu kalkulacyjnym.
- **Skutki:** cztery importy (lokalizacje, stany początkowe, przyjęcia, zlecenia wydań) z
  raportem błędnych wierszy; eksport stanów i ruchów. Brak automatycznej synchronizacji.

## D-05. Każda zmiana stanu przez jedną warstwę usług, razem z zapisem ruchu

- **Kontekst:** jednym z problemów pracy na papierze był brak historii operacji.
- **Rozważane opcje:** `<DO UZUPEŁNIENIA>`
- **Dlaczego ta:** zmiana stanu i wpis w rejestrze ruchów są w jednej transakcji bazy danych —
  nie da się zmienić stanu bez śladu.
- **Skutki:** historia zawsze zgadza się ze stanem; ekrany i skaner korzystają z tych samych
  funkcji (`warehouse/services.py`).

## D-06. Wysyłka bez pakowania jest dozwolona

- **Kontekst:** nie każde wydanie wymaga osobnego pakowania.
- **Dlaczego ta:** potwierdzone z interesariuszami — pakowanie jest krokiem opcjonalnym.
- **Skutki:** WZ może przejść z „Zrealizowany” od razu do „Wysłany”.

## D-07. Spis z natury przy zamrożonym magazynie

- **Kontekst:** spis porównuje policzoną ilość z bieżącym stanem palety w chwili zamknięcia
  arkusza.
- **Dlaczego ta:** na czas spisu magazyn nie wykonuje ruchów, więc stan bieżący = migawka.
- **Skutki:** ruch wykonany w trakcie spisu zostałby nadpisany korektą — procedura musi
  wykluczać ruchy w trakcie spisu.

## D-08. Skaner jako strona w przeglądarce telefonu lub kolektora

- **Kontekst:** dwóch operatorów, mała skala, brak budżetu na dedykowane terminale
  `<DO UZUPEŁNIENIA: potwierdź>`.
- **Rozważane opcje:** `<DO UZUPEŁNIENIA>`
- **Dlaczego ta:** ten sam serwer i te same reguły co panel; kamera telefonu czyta kod QR.
- **Skutki:** kamera wymaga HTTPS; przy wygaśnięciu sesji skaner pokazuje mylący komunikat
  (patrz [07](07-ograniczenia.md)).
