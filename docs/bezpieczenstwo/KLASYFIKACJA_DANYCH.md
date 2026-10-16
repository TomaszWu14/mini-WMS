# Klasyfikacja danych

| | |
|---|---|
| Wersja | 0.1 |
| Data | 2026-10-16 |
| Status | szkic — do akceptacji Product Ownera |
| Właściciel | [SEC] |

Rozwija wstępną klasyfikację z [`docs/AUDYT.md`](../AUDYT.md) §3.2. Służy jako wejście do
[`THREAT_MODEL.md`](THREAT_MODEL.md) (identyfikatory DA-xx), [`RODO.md`](RODO.md) (retencja,
prawa osób) i [`RYZYKA.md`](RYZYKA.md). Założenia: wdrożenie jak produkcyjne (Z-04), jeden
magazyn i jedna firma (Z-06), publiczne demo jako powierzchnia dostępna anonimowo (Z-05).

## 1. Klasy danych

Cztery klasy. **Dane osobowe** to znacznik dodatkowy: zasób może należeć do klasy podstawowej
(np. Wewnętrzne) i jednocześnie zawierać dane osobowe — wtedy stosuje się **bardziej
restrykcyjne** z wymagań obu klas.

| Klasa | Definicja | Przykłady w mini-WMS | Kto ma dostęp |
|---|---|---|---|
| **Publiczne** | Ujawnienie nie szkodzi; z założenia dostępne każdemu. | kod i dokumentacja w publicznym repo (licencja „all rights reserved” ogranicza użycie, nie dostęp), fikcyjne dane demo, jawne konta demo | wszyscy (internet) |
| **Wewnętrzne** | Tajemnica przedsiębiorstwa klienta; ujawnienie szkodzi konkurencyjności, ale nie jest naruszeniem praw osób. | materiały, lokalizacje, stany palet, dokumenty WZ, ruchy, spisy, eksporty i PDF | zalogowani wg roli: Podgląd (odczyt), Operator (operacje + skaner), Administrator (+ konta) |
| **Poufne** | Ujawnienie daje przejęcie systemu albo hurtowy dostęp do danych. | `DJANGO_SECRET_KEY`, hasła bazy i superusera, hash hasła, identyfikator sesji, backupy `pg_dump`, sekrety CI/CD | wąski krąg: właściciel instancji i administrator infrastruktury; nigdy przez UI |
| **Dane osobowe** | Informacje o zidentyfikowanej lub możliwej do zidentyfikowania osobie (RODO art. 4 pkt 1), w tym adres IP i identyfikator konta. | login, e-mail, `LoginEvent` (IP, przeglądarka, wpisany login), znaczniki „kto” (`created_by`), kolumna „Kto” w eksporcie | Administrator (dziennik, konta), sama osoba (dostęp do swoich danych), superuser, administrator infrastruktury |

## 2. Wymagania ochrony per klasa

Kolumna „Stan dziś” wskazuje, czy wymaganie jest spełnione; luki mają odnośniki do ryzyk
(R1–R10 z audytu, RR-xx z rejestru).

| Wymaganie | Publiczne | Wewnętrzne | Poufne | Dane osobowe |
|---|---|---|---|---|
| **Tranzyt** | HTTPS zalecany | HTTPS wymagany (przekierowanie + HSTS, `prod.py`) | HTTPS/SSH; nigdy w URL, e-mailu, czacie | HTTPS wymagany; ciasteczko sesji `Secure` |
| **Spoczynek** | bez wymagań; integralność gałęzi `main` | szyfrowanie dysku hosta (poza aplikacją) | tylko w env/menedżerze sekretów; backup szyfrowany | jak Wewnętrzne; hasła wyłącznie jako hash PBKDF2 |
| **Retencja** | bez limitu (historia git) | okres ewidencji ustala administrator danych; brak auto-usuwania | rotacja po podejrzeniu naruszenia i zmianie osób; backup 7 dni | zdefiniowana w [`RODO.md`](RODO.md) §6 (LoginEvent 90 dni — Z-09, do potwierdzenia) |
| **Logi aplikacji** | tak | tylko identyfikatory (numer HU/WZ), bez wartości pól | nigdy | tylko minimum (identyfikator konta); nie logować haseł ani treści pól wolnego tekstu |
| **Eksporty / PDF** | tak | tak, dla zalogowanych; po pobraniu odpowiada użytkownik | nigdy | tylko z uzasadnieniem (kolumna „Kto” w eksporcie ruchów) |
| **Demo / fixtures / testy / repo** | tak — to jest klasa dla demo i repo | wyłącznie dane syntetyczne | nigdy (wyjątek: jawne hasło demo, bo z definicji Publiczne) | nigdy prawdziwe dane osobowe; w demo wyjątek techniczny: IP odwiedzających zapisuje sam serwer |

**Stan dziś — luki:** backup nieszyfrowany i na tym samym hoście (R9, RR-13); dziennik logowań
bez retencji (R7, RR-11); sekrety w `docker-compose.yml` z wartościami domyślnymi (R2, RR-02);
szyfrowanie dysku hosta niezweryfikowane (poza repo).

## 3. Rejestr zasobów danych (DA-xx)

DF-xx — przepływy z [`THREAT_MODEL.md`](THREAT_MODEL.md) §3.

| ID | Zasób | Klasa | Gdzie | Kto ma dostęp (role) | Przepływy | Uwagi |
|---|---|---|---|---|---|---|
| DA-01 | Kod źródłowy i obraz Docker | Publiczne | repo GitHub, obraz z `Dockerfile` | wszyscy | DF-08 | licencja „all rights reserved” (`LICENSE`): kod do wglądu, bez prawa użycia; w historii nie wykryto sekretów (AUDYT §6) |
| DA-02 | Dokumentacja (`docs/`, README, `COOLIFY.md`, audyt, model zagrożeń) | Publiczne | repo GitHub | wszyscy | DF-08 | zawiera opisy niezałatanych luk — patrz RR-20; nie wpisywać do niej sekretów, adresów e-mail ani danych instancji klienta |
| DA-03 | Dane magazynowe demo (15 materiałów, ~30 palet, 3 WZ, spis) | Publiczne | baza instancji demo, `seed_demo` | każdy odwiedzający (rola Operator) | DF-07, DF-02 | fikcyjne i deterministyczne (`SEED`); resetowane co 24 h (Scheduled Task) |
| DA-04 | Konta demo i jawne hasło (`demo_operator`, `demo_podglad`, `demo1234`) | Publiczne | README, `login.html`, env `DEMO_PASSWORD` | wszyscy | DF-01, DF-07 | jawne z założenia (Z-05, wyjątek W-1); na instancji prywatnej muszą nie istnieć (R2b, RR-03) |
| DA-05 | Dane magazynowe: materiały, jednostki, lokalizacje, palety (HU), stany, partie, daty ważności | Wewnętrzne | tabele `warehouse_material`, `_unit`, `_location`, `_handlingunit`, `_hunumberingconfig` | Podgląd — odczyt; Operator i Administrator — zapis | DF-02, DF-03, DF-04, DF-05 | `Material.created_by` i `HandlingUnit.created_by` → DA-11 |
| DA-06 | Dokumenty WZ i pozycje, arkusze spisu z natury | Wewnętrzne (+ DO, gdy odbiorca to osoba fizyczna) | tabele `warehouse_issuedocument`, `_issueline`, `_stocktake*` | Podgląd — odczyt; Operator i Administrator — zapis | DF-02, DF-03, DF-05 | `reference` (wolny tekst) może zawierać nazwę klienta; także `carrier`, `tracking_number` |
| DA-07 | Ruchy magazynowe `StockMovement` (rejestr audytowy: typ, ilość, powód, notatka) | Wewnętrzne + DO (`created_by`) | tabela `warehouse_stockmovement` | Podgląd — odczyt; superuser — zmiana i usuwanie w `/admin/` | DF-02, DF-03, DF-05, DF-06 | `note` to wolny tekst; „tylko dopisywanie” jest konwencją aplikacji, nie ograniczeniem bazy (TM-37) |
| DA-08 | Konta pracowników: login, e-mail (opcjonalny), flagi, rola (`Profile`) | Dane osobowe | tabele `auth_user`, `warehouse_profile` | Administrator (lista, edycja roli/statusu/hasła), superuser | DF-01, DF-06 | rola pochodzi z `Profile`, nie z grup Django; e-mail edytowalny tylko w `/admin/` |
| DA-09 | Hash hasła | Poufne (+ DO) | `auth_user.password` (PBKDF2) | nikt przez UI; administrator bazy | DF-01, DF-06 | brak argon2 (R6); hasło nigdy nie jest logowane |
| DA-10 | Dziennik logowań `LoginEvent`: login, rodzaj, IP, user-agent, czas | Dane osobowe | tabela `warehouse_loginevent` | Administrator (`/uzytkownicy/dziennik/`), superuser (`/admin/`) | DF-01, DF-06, DF-07 | `username` = dowolny tekst z formularza (także hasło wpisane w złe pole); brak retencji (R7) |
| DA-11 | Znaczniki „kto” (`created_by`) w materiałach, HU, WZ, ruchach, spisach | Dane osobowe (pseudonim: login) | kolumny FK do `auth_user` | jak dane, których dotyczą | DF-02, DF-03, DF-05 | `on_delete=SET_NULL` — usunięcie konta anonimizuje znacznik |
| DA-12 | Ślad odwiedzających demo: IP i user-agent w `LoginEvent`, sesje, logi proxy | Dane osobowe (osoby anonimowe) | `warehouse_loginevent`, `django_session`, logi Traefik/Caddy | Administrator infrastruktury; Administrator aplikacji | DF-07 | IP prawdziwe mimo fikcyjnych danych; `seed_demo --reset` **nie** czyści `LoginEvent`; brak klauzuli informacyjnej |
| DA-13 | Sesje użytkowników | Poufne (+ DO) | tabela `django_session` (silnik bazodanowy) | nikt przez UI | DF-01, DF-07 | wiersz powstaje także dla anonimowego trafienia w `/demo/`; brak `clearsessions` (R5); komunikaty flash też trafiają do sesji |
| DA-14 | Eksporty CSV/XLSX (stany, ruchy) | Wewnętrzne + DO (kolumna „Kto”) | generowane na żądanie, pobierane do przeglądarki | każdy zalogowany (`login_required`) | DF-05 | po pobraniu poza kontrolą aplikacji; formuły neutralizowane (`exports.py:9-15`) |
| DA-15 | PDF: etykiety HU i lokalizacji (QR), dokument WZ | Wewnętrzne | generowane na żądanie, nie przechowywane | zalogowani wg widoku | DF-05 | nazwy plików z numerów systemowych; kody z importu są wyjątkiem (T16) |
| DA-16 | Pliki importu CSV/XLSX | Wewnętrzne | przetwarzane z `upload.read()` w pamięci; pliki > 2,5 MB Django zapisuje tymczasowo i usuwa po żądaniu | Operator, Administrator | DF-04 | limit 5 MB (`forms.py:20-31`); nie zapisujemy trwale; zawartość może zawierać dane klienta |
| DA-17 | Backupy `pg_dump` (gzip) | Poufne (zawiera DA-05…DA-13) | wolumen `db_backups` na tym samym hoście, retencja 7 dni | administrator infrastruktury | DF-08 | nieszyfrowane, bez kopii off-site, bez testu odtworzenia (R9, W-3) |
| DA-18 | Logi: access log gunicorna, logi JSON aplikacji, logi proxy | Wewnętrzne (mogą zawierać DO) | stdout kontenerów, Docker/Coolify | administrator infrastruktury | DF-01…DF-08 | access log zawiera ścieżkę i `?q=`; za proxy adres peera to zwykle adres proxy — IP klienta jest w logach proxy, o ile access log jest włączony (do zweryfikowania na instancji); retencja zależna od Docker/Coolify |
| DA-19 | Sekrety uruchomieniowe: `DJANGO_SECRET_KEY`, `POSTGRES_PASSWORD`, `DJANGO_SUPERUSER_PASSWORD`, `PGPASSWORD` | Poufne | zmienne środowiskowe Coolify lub `.env` (ignorowany przez git i Docker) | administrator infrastruktury | DF-08 | widoczne w panelu Coolify i `docker inspect`; domyślne wartości w `docker-compose.yml` (R2) |
| DA-20 | Sekrety CI/CD i wdrożenia: `GITHUB_TOKEN`, GitHub App / webhook Coolify | Poufne | ustawienia GitHub i Coolify | właściciel repo | DF-08 | `main` = auto-deploy (Z-02); ochrona konta właściciela jest poza repo (TM-53) |

## 4. Zasady postępowania

1. **Dane osobowe nigdy nie trafiają do demo, fixtures, testów, zrzutów ekranu ani nagrań.**
   Dane testowe i demo są syntetyczne (`seed_demo`, `SEED`); nazwy firm fikcyjne (README).
2. **Sekrety wyłącznie w zmiennych środowiskowych** (Coolify lub `.env`, który nie jest w repo
   ani w obrazie). Nie w kodzie, `docker-compose.yml`, dokumentacji, logach ani w
   zgłoszeniach. Jedyny wyjątek: jawne hasło kont demo (DA-04).
3. **Wolny tekst z formularzy** (login w nieudanej próbie, `reference`, `note`, nazwy) traktuj
   jako potencjalnie osobowy lub poufny: nie kopiuj go do logów aplikacji, nie wstawiaj do
   komunikatów bez kodowania.
4. **Nowe pole lub tabela z danymi osobowymi** wymaga w tym samym PR: wpisu w §3 (DA-xx),
   wpisu w [`RODO.md`](RODO.md) (retencja, rejestr czynności) i oceny przez [SEC].
5. **Backup = baza produkcyjna.** Chroń go jak klasę Poufne; nigdy nie odtwarzaj backupu
   produkcji na instancji dev, demo ani testowej.
6. **Demo ma osobną bazę i osobne sekrety** (`COOLIFY.md` §11: „nigdy na danych
   produkcyjnych”). `DEMO_MODE=1` tylko na instancji publicznej.
7. **Eksporty i PDF** pobieraj tylko do pracy; nie wysyłaj ich poza organizację bez
   potrzeby. Eksport ruchów (kolumna „Kto”) traktuj jak dane osobowe.
8. **Dokumentacja bezpieczeństwa jest publiczna** (DA-02): bez adresów e-mail, nazwisk,
   adresów instancji klienta i sekretów. Opis niezałatanej luki publikujemy dopiero po
   decyzji PO (RR-20).
9. **Incydent** (podejrzenie wycieku, przejęcia konta, kradzieży backupu): procedura w
   [`RUNBOOK.md`](../operacje/RUNBOOK.md) (dokument powstaje równolegle); dla danych osobowych
   termin zgłoszenia to 72 h — [`RODO.md`](RODO.md) §9.

## 5. Utrzymanie dokumentu

Przegląd razem z rejestrem ryzyk ([`RYZYKA.md`](RYZYKA.md) — proces w §4) oraz przy każdej
zmianie `models.py`, `signals.py`, `exports.py` lub konfiguracji wdrożenia. Zmiana klasy
zasobu wymaga akceptacji PO.
