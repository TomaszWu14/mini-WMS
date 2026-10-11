# 06. Dziennik decyzji

Format: decyzja → kontekst → rozważane opcje → dlaczego ta → skutki.
Kontekst i skutki odczytane z kodu; rozważane opcje i powody wyboru potwierdzone przez autora.

## D-01. Stan prowadzony na poziomie palety (HU), nie sumy w lokalizacji

- **Kontekst:** towar ma partie i daty ważności; dwie palety tego samego materiału mogą mieć
  różne daty. Na papierze nie dało się wskazać, którą paletę wydać.
- **Rozważane opcje:** (1) stan jako ilość materiału w lokalizacji, bez numerów palet;
  (2) stan na poziomie palety.
- **Dlaczego ta:** reguła FEFO wymaga daty ważności przypisanej do konkretnej palety; etykieta
  z QR identyfikuje jeden fizyczny obiekt, który operator skanuje.
- **Skutki:** każda operacja dotyczy palety (`HandlingUnit`); stan materiału to suma palet.
  Potrzebne są operacje na paletach: przepakowanie, korekta, status „Pusty”.

## D-02. Brak zewnętrznej master daty — słownik materiałów prowadzony w aplikacji

- **Kontekst:** firma nie ma ERP ani innego źródła kartotek materiałowych.
- **Rozważane opcje:** (1) kartoteka importowana z pliku jako jedyne źródło materiałów;
  (2) słownik prowadzony w aplikacji.
- **Dlaczego ta:** nie ma systemu, który dostarczałby kartotekę; materiał to tylko indeks, nazwa, jednostka i opcjonalny limit na paletę —
  tyle, ile potrzebuje magazyn; import stanów sam zakłada brakujące materiały.
- **Skutki:** brak atrybutów logistycznych (wymiary, waga, EAN); ryzyko literówek w indeksach
  przy ręcznym zakładaniu.

## D-03. Numer WZ liczony od nowa każdego dnia (`WZ<data>-NNN`)

- **Kontekst:** numer dokumentu wydania nadaje system przy jego utworzeniu.
- **Rozważane opcje:** (1) jeden licznik ciągły (np. `WZ-000123`); (2) data + licznik dzienny.
- **Dlaczego ta:** łatwiej szukać — z numeru od razu widać dzień wystawienia dokumentu.
- **Skutki:** licznik nie jest blokowany w bazie — przy kolizji zapis jest ponawiany
  (`services.py:37`); numer jest odporny na usunięcie dokumentu (`services.py:501`).

## D-04. Wymiana danych plikami CSV/XLSX zamiast integracji

- **Kontekst:** firma nie ma systemu ERP.
- **Rozważane opcje:** (1) wszystkie dane wpisywane ręcznie w aplikacji; (2) importy i eksporty
  plików CSV/XLSX.
- **Dlaczego ta:** nie ma systemu, z którym można się zintegrować; plik CSV/XLSX da się
  przygotować w dowolnym arkuszu kalkulacyjnym.
- **Skutki:** cztery importy (lokalizacje, stany początkowe, przyjęcia, zlecenia wydań) z
  raportem błędnych wierszy; eksport stanów i ruchów. Brak automatycznej synchronizacji.

## D-05. Każda zmiana stanu przez jedną warstwę usług, razem z zapisem ruchu

- **Kontekst:** jednym z problemów pracy na papierze był brak historii operacji.
- **Rozważane opcje:** (1) każdy ekran sam zmienia stan i zapisuje ruch; (2) jedna warstwa
  usług wywoływana przez wszystkie ekrany i skaner.
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

- **Kontekst:** dwóch operatorów, mała skala, liczy się szybkość wdrożenia.
- **Rozważane opcje:** (1) dedykowane terminale Android z własną aplikacją; (2) strona w
  przeglądarce telefonu.
- **Dlaczego ta:** szybkość wdrożenia — telefon jest pod ręką, nie trzeba niczego kupować ani
  instalować; ten sam serwer i te same reguły co panel; kamera telefonu czyta kod QR.
- **Skutki:** kamera wymaga HTTPS; przy wygaśnięciu sesji skaner pokazuje mylący komunikat
  (patrz [07](07-ograniczenia.md)).
