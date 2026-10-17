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
- **Skutki:** kamera wymaga HTTPS; przy wygaśnięciu sesji skaner pokazywał mylący komunikat
  (naprawione: przekierowanie na logowanie, patrz [07](07-ograniczenia.md))
  (patrz [07](07-ograniczenia.md)).

## D-09. Import stanów z ilością 0 zostaje — z ostrzeżeniem

- **Kontekst:** przy pierwszym imporcie ilości na paletach zwykle nie są znane; import
  tworzył palety z ilością 0 po cichu i nie sprawdzał pojemności lokalizacji.
- **Rozważane opcje:** (1) odrzucać wiersze bez ilości; (2) zostawić 0 i ostrzec.
- **Dlaczego ta:** (2) — odrzucenie blokuje start ewidencji; ilość uzupełnia się korektą.
- **Skutki:** podsumowanie importu podaje liczbę palet z ilością 0 i lokalizacje z
  przekroczoną pojemnością (informacyjnie, jak przy alokacji — W-08).

## D-10. Numery palet bez rozróżniania wielkości liter

- **Kontekst:** importy szukały palet bez rozróżniania wielkości liter, skaner i ekrany — z
  rozróżnianiem; „hu-001” wpisane ręcznie nie znajdowało „HU-001”.
- **Dlaczego ta:** jedna reguła wszędzie, taka jak w importach (które już pilnują, by nie
  powstały dwie palety różniące się tylko wielkością liter).
- **Skutki:** skaner, przepakowanie i inwentaryzacja szukają przez `number__iexact`.

## D-11. Zbiorczy wydruk etykiet: limit 200 z komunikatem

- **Kontekst:** wydruk obcinał listę do 200 palet bez informacji.
- **Dlaczego ta:** jeden PDF z setkami stron i tak trzeba drukować partiami; lepiej poprosić
  o zawężenie filtra niż wydrukować niepełną listę.
- **Skutki:** powyżej 200 palet — powrót do listy z komunikatem „Zawęź filtr”.

## D-12. Limit logowań zawsze; IP tylko od zaufanego proxy

- **Kontekst:** limit prób logowania działał tylko w trybie demo, a IP klienta brane było z
  pierwszego wpisu `X-Forwarded-For`, który klient może podrobić.
- **Dlaczego ta:** limit chroni każdą instalację, nie tylko demo. Za proxy ufamy wpisowi
  dopisanemu przez proxy (N-temu od końca), nie wpisowi klienta.
- **Skutki:** nowa zmienna `DJANGO_TRUSTED_PROXY_COUNT` (compose: 1 — Traefik/Caddy;
  domyślnie 0 = nagłówek ignorowany).

## D-13. Paleta tylko w jednym otwartym arkuszu spisu

- **Kontekst:** dwa otwarte arkusze mogły objąć tę samą paletę; zamknięcie drugiego
  nadpisałoby korektę z pierwszego.
- **Dlaczego ta:** nowy arkusz pomija palety, które są już w otwartym arkuszu, i mówi o tym
  komunikatem — bez blokowania tworzenia spisu.
- **Skutki:** po zamknięciu arkusza palety wracają do zakresu kolejnych spisów.
