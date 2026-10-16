# Backlog — historyjki użytkownika

| | |
|---|---|
| Wersja | 0.1 |
| Data | 2026-10-16 |
| Status | szkic — do akceptacji Product Ownera |
| Właściciel | [BA] |

Backlog wynika z [AUDYT.md](../AUDYT.md) (§2.4 dług T1–T16, §3.3–3.5 ryzyka R1–R10), z luk
wskazanych w [WYMAGANIA.md](WYMAGANIA.md) i [PROCESY.md](PROCESY.md) oraz z „poza zakresem”
w [docs/01](../01-problem-i-zakres.md). Macierz do wymagań i testów: [SLEDZENIE.md](SLEDZENIE.md).
Kolejność: najpierw pilne poprawki bezpieczeństwa (Z-07), potem reszta.

## 1. Zasady

| Element | Zasada |
|---|---|
| Format | „Jako <rola> chcę <cel>, aby <korzyść>”. Role: Operator, Administrator, Podgląd, Kierownik; PO; [SEC]; ST-05 administrator infrastruktury; ST-07 administrator danych ([INTERESARIUSZE.md](INTERESARIUSZE.md)). |
| Kryteria | Given / When / Then, testowalne; kryteria bezpieczeństwa są częścią historyjki, nie osobną pozycją. Każde kryterium da się zamienić w test lub krok CI. |
| Powiązania | `Wymagania` wskazuje FR / NFR / SEC z [WYMAGANIA.md](WYMAGANIA.md); `Źródło` — R/T/§ z audytu lub dokument. |
| MoSCoW | **Must** — pilne poprawki wysokich ryzyk (US-001…006); **Should** — ważne, po Must; **Could** — jeśli starczy czasu lub po decyzji PO; **Won't (na teraz)** — świadomie poza zakresem, do potwierdzenia przez PO. |
| Rozmiar | **S** — zmiana lokalna (1–2 pliki kodu) + test. **M** — kilka plików lub modułów albo konfiguracja + testy. **L** — przekrojowa zmiana (wiele plików lub szablonów), nowa zależność albo ADR. Bez godzin: brak historii prędkości. |
| Status | `do zrobienia`; `w toku` z podaniem, kto; `odroczone` (Won't). Po wdrożeniu: `gotowe` + numer PR w [SLEDZENIE.md](SLEDZENIE.md). |
| Definition of Ready / Done | [CONTRIBUTING.md](../../CONTRIBUTING.md) §3–4. Gałąź: `feature/US-nnn-krótka-nazwa` (albo `security/`, `fix/`). |
| Testy | „Test do napisania” podaje **propozycję** nazwy pliku i klasy (pliki oznaczone „nowy” jeszcze nie istnieją). Konwencja: `warehouse/tests_<obszar>.py`. |
| „w toku: ADR-0001/CI” | Pozycja realizowana równolegle w tej samej gałęzi przez wycinek CI (ADR-0001, `docs/architektura/adr/`); BA nie duplikuje pracy, tylko odbiera kryteria. |

### Parametry do potwierdzenia (symbole użyte w kryteriach)

Wartości liczbowe bez źródła w kodzie lub audycie nie są wymaganiami — kryteria używają symboli.

| Symbol | Znaczenie | Propozycja / źródło | PYT |
|---|---|---|---|
| L_PAL | maks. palet w jednym przyjęciu (formularz i wiersz importu) | 500 (AUDYT R3: „np. 500”) | PYT-02 |
| L_QTY | maks. ilość w przyjęciu, korekcie, spisie, API skanera | do ustalenia (≤ 2^31−1 = granica bazy) | PYT-02 |
| L_HU_PLIK | maks. palet (HU) utworzonych jednym plikiem importu | do ustalenia | PYT-02 |
| L_WIERSZE | maks. wierszy w pliku importu poza demo | 10 000 (AUDYT R4) | PYT-02 |
| L_ROZP | maks. suma rozmiarów członków ZIP po rozpakowaniu XLSX | 50 MB (AUDYT R4) | PYT-02 |
| K / W | limiter wejść demo: K żądań na W sekund z jednego IP | do ustalenia (punkt wyjścia: jak logowanie, 10 / 300 s) | PYT-22 |
| N_KONTO / W_KONTO | limit nieudanych prób na konto w oknie | do ustalenia | PYT-07 |
| RETENCJA | wiek, po którym kasujemy `LoginEvent` | 90 dni (Z-09, DEC-5) | PYT-09 |
| ROZMIAR_STRONY | liczba wierszy na stronę list | 100 (precedens: dziennik logowań) | — |
| L_ETYKIET_LOK | maks. etykiet lokalizacji na wydruk | 200 (jak `HU_LABELS_LIMIT`, D-11) | — |
| L_DEMO | maks. łączna liczba palet / lokalizacji w demo | do ustalenia | PYT-22 |

---

## 2. Must — pilne poprawki bezpieczeństwa (AUDYT §3.4)

Kolejność zgodna z AUDYT §3.4. Wszystkie wymagają potwierdzenia parametrów w PYT przed startem
(Definition of Ready), poza US-001.

### US-001 — Administrator nie edytuje konta superusera

| | |
|---|---|
| Historyjka | Jako **PO** chcę, aby konto z rolą Administrator nie mogło zmienić hasła ani dezaktywować konta superusera, aby nikt poza superuserem nie przejął `/admin/` i nie zniszczył śladu audytowego. |
| MoSCoW · rozmiar | Must · S |
| Status | zrobione — do akceptacji PO (PR #23, gałąź sesji) |
| Źródło | AUDYT §3.3 **R1** (waga W, potwierdzone testem), §3.4 pkt 1; `views.py:1296-1335` (`user_edit`); pitfalls/auth #8 |
| Wymagania | SEC-009 (odmowa jest źródłem zdarzenia dla US-022); także: FR-023, FR-024 |
| Zależności | — (PYT-06 dotyczy tylko zakresu GET) |

**Kryteria akceptacji**

1. **Given** Administrator A (rola ADMIN, bez `is_superuser`) i konto superusera S; **When** A wysyła POST `/uzytkownicy/<S.pk>/` z nowym hasłem; **Then** odpowiedź 403 (strona „Brak uprawnień” w układzie aplikacji), a `S.check_password(stare_hasło)` jest nadal prawdziwe.
2. **Given** j.w.; **When** POST z pustym `is_active`; **Then** 403 i `S.is_active` pozostaje `True`.
3. **Given** j.w.; **When** POST zmieniający rolę S albo GET `/uzytkownicy/<S.pk>/`; **Then** 403 (zakres GET — PYT-06; domyślnie 403).
4. **Given** superuser; **When** POST edycji dowolnego konta, także innego superusera; **Then** 302 i zmiana zapisana (brak regresji).
5. **Given** Administrator A; **When** POST edycji konta Operatora; **Then** 302 (brak regresji względem `UserManagementTests.test_edit_user_role_and_password`).

**Testy:** `warehouse/tests_security.py` `SuperuserProtectionTests` (9 testów: hasło, dezaktywacja, rola, GET, lista bez linku, konto staff, próba nadania is_superuser, superuser edytuje superusera, Administrator edytuje Operatora; ochrona obejmuje też konta `is_staff` — uwaga z przeglądu [SEC]). Odbiór [BA] 2026-10-16: kryteria 1–5 spełnione.

### US-002 — Limity liczby palet i ilości w przyjęciu i imporcie

| | |
|---|---|
| Historyjka | Jako **Operator** chcę, aby przyjęcie i import odrzucały nierealnie duże liczby palet i ilości, aby jedna pomyłka lub złośliwy plik nie zablokowały numeracji HU i pracy wszystkich. |
| MoSCoW · rozmiar | Must · S |
| Status | zrobione — do akceptacji PO (PR #23, gałąź sesji) |
| Źródło | AUDYT §3.3 **R3** (W na demo / Ś), §3.4 pkt 2; T16 (część); `forms.py:207-213`, `receipt_import.py:54-59`, `services.py:75-162` |
| Wymagania | SEC-015, SEC-021; NFR-009, NFR-003; także: FR-001, FR-005 |
| Zależności | wartości L_PAL, L_QTY, L_HU_PLIK (PYT-02); stałe wspólne z US-013 |

**Kryteria akceptacji**

1. **Given** Operator; **When** POST `/przyjecie/` z liczbą palet = L_PAL+1; **Then** formularz wraca z błędem pola, nie powstaje żadna paleta ani ruch, a `HUNumberingConfig.next_number` nie zmienia się.
2. **Given** Operator; **When** liczba palet = L_PAL (wartość graniczna); **Then** przyjęcie przechodzi: L_PAL palet i L_PAL ruchów PRZYJĘCIE.
3. **Given** Operator; **When** ilość łączna > L_QTY albo liczba palet < 1; **Then** błąd pola, bez zapisu.
4. **Given** plik importu przyjęć z wierszem o liczbie palet > L_PAL; **When** import; **Then** wiersz pominięty z komunikatem „Wiersz N: …”, poprawne wiersze wczytane (jak FR-005), brak palet z błędnego wiersza.
5. **Given** plik, którego suma palet po wszystkich wierszach > L_HU_PLIK; **When** import; **Then** cały plik odrzucony **przed** pierwszym zapisem z komunikatem o limicie, baza bez zmian.
6. **Given** użytkownik z rolą Podgląd; **When** POST `/przyjecie/`; **Then** nadal 403 (brak regresji SEC-007).

**Testy:** `warehouse/tests_input_limits.py` — `ReceiveFormLimitTests` (5), `ServiceLimitTests` (2), `ReceiptImportLimitTests` (3). Wartości: L_PAL = 500, L_QTY = 1 000 000, L_HU_PLIK = 2 000 (`services.MAX_*`, Z-23/Z-35). Odbiór [BA] 2026-10-16: kryteria 1–6 spełnione. Po przeglądach [SEC]/[DB]: limit objął też import stanów (`StockImportLimitTests`, 2 testy), import przyjęć blokuje i odświeża materiały przed zapisem; komunikaty mówią, co zrobić („podziel dostawę / plik”).

### US-003 — Wdrożenie nie startuje ze słabymi sekretami; konta demo tylko w trybie demo

| | |
|---|---|
| Historyjka | Jako **administrator infrastruktury (ST-05)** chcę, aby wdrożenie bez ustawionych sekretów kończyło się błędem, a konta demo nie powstawały poza trybem demo, aby nie uruchomić instancji z publicznie znanym kluczem i hasłami. |
| MoSCoW · rozmiar | Must · M |
| Status | zrobione — do akceptacji PO (PR #23, gałąź sesji) |
| Źródło | AUDYT §3.3 **R2** (W), §3.4 pkt 3; `docker-compose.yml:18,53,65`, `config/settings/prod.py:12`, `seed_demo.py:79,134-141` |
| Wymagania | SEC-026, SEC-027 |
| Zależności | PYT-05 (wariant `seed_demo`); koordynacja z CI: krok smoke-testu w `ci.yml` używa klucza 42-znakowego (< progu 50) — wymaga wydłużenia |

**Kryteria akceptacji**

1. **Given** plik compose wariantu prywatnego bez `DJANGO_SECRET_KEY`, `DJANGO_SUPERUSER_PASSWORD` i `POSTGRES_PASSWORD` w środowisku; **When** walidacja konfiguracji compose (`config`); **Then** błąd „required variable … is missing” dla każdej z trzech (składnia `${VAR:?…}`, jak w wariancie Coolify).
2. **Given** `DJANGO_DEBUG=0` i `DJANGO_SECRET_KEY` równy `zmien-mnie-w-produkcji`, `YOUR_DJANGO_SECRET_KEY_HERE`, zaczynający się od `django-insecure-` albo krótszy niż 50 znaków; **When** import `config.settings.prod`; **Then** `ImproperlyConfigured` z komunikatem o wymogu losowego klucza.
3. **Given** losowy klucz ≥ 50 znaków; **When** import `config.settings.prod` i `manage.py check --deploy`; **Then** ustawienia ładują się bez błędu (klucze w CI i w smoke-teście także ≥ 50 znaków).
4. **Given** brak `DEMO_MODE`; **When** `manage.py seed_demo` (bez `--reset`); **Then** `CommandError` „wymaga DEMO_MODE=1” i brak kont `demo_operator` / `demo_podglad` (wariant domyślny; alternatywa: konta z `set_unusable_password()` — PYT-05).
5. **Given** `DEMO_MODE=1`; **When** `seed_demo`; **Then** zachowanie bez zmian (`SeedDemoTests` zielone).
6. **Given** README.md i COOLIFY.md; **Then** nie zalecają uruchamiania `seed_demo` na instancji bez `DEMO_MODE` (przegląd dokumentów).

**Testy:** `warehouse/tests_deploy_settings.py` — `ProdSecretKeyTests` (7: brak klucza, `zmien-mnie-w-produkcji`, `YOUR_DJANGO_SECRET_KEY_HERE`, prefiks `django-insecure-`, 49 znaków, niska różnorodność znaków → odmowa; losowy 50 znaków → start), `SeedDemoModeTests` (2), `ComposeSecretsTests` (1), `EntrypointSuperuserPasswordTests` (4: `entrypoint.sh` odmawia założenia superusera z hasłem `admin`, zaślepką lub hasłem niespełniającym walidatorów Django, a istniejący superuser z hasłem `admin` blokuje start), `EntrypointDatabasePasswordTests` (2: zaślepka hasła bazy blokuje start); `tests_demo.SeedDemoTests` działa z `DEMO_MODE=True`. Krok CI „Compose (wariant prywatny) odmawia startu bez sekretów” — kryterium 1 dla każdej z trzech zmiennych. Odbiór [BA] 2026-10-16: kryteria 1–6 spełnione (6: README każe ustawić `DEMO_MODE=1` przed `seed_demo`, COOLIFY.md §11 opisuje instancję demo). PO potwierdził 2026-10-16, że klucze w Coolify (demo i produkcja) mają ≥ 50 losowych znaków (Z-36), więc nowy próg nie zatrzyma istniejących wdrożeń. Po przeglądzie [SEC]: objęto też instalacje zrobione przed US-003 (istniejące konto z `admin`/`admin`) i zaślepkę hasła bazy. Dodatkowo: klucz tylko do `collectstatic` w `Dockerfile` wydłużony do ≥ 50 znaków.

### US-004 — Bezpieczny import XLSX

| | |
|---|---|
| Historyjka | Jako **Operator** chcę, aby uszkodzony lub złośliwy plik XLSX kończył się czytelnym komunikatem, a nie błędem 500 ani wyczerpaniem pamięci, aby import był bezpieczny także na publicznym demo. |
| MoSCoW · rozmiar | Must · M |
| Status | zrobione — do akceptacji PO (PR #23, gałąź sesji) |
| Źródło | AUDYT §2.4 **T1**, §3.3 **R4** (W na demo / Ś), §3.4 pkt 4; `imports.py:89-127`, `views.py:344,429,808,886`, `forms.py:20-31` |
| Wymagania | SEC-019, SEC-021; NFR-007, NFR-008; także: FR-005, NFR-003 |
| Zależności | wartości L_ROZP i L_WIERSZE (PYT-02); `defusedxml` w `requirements.txt` (lock — US-020) |

**Kryteria akceptacji** (dla wszystkich czterech importów: `/stany/import/`, `/lokalizacje/import/`, `/przyjecie/import/`, `/wydania/import/`)

1. **Given** plik `.xlsx`, który nie jest ZIP-em (np. CSV z rozszerzeniem `.xlsx`); **When** import; **Then** odpowiedź 200 z komunikatem „Plik nie jest poprawnym XLSX”, bez 500 i bez zmian w bazie.
2. **Given** poprawny ZIP, którego suma `file_size` członków > L_ROZP, a rozmiar po kompresji < 5 MB (mały po kompresji, duży po rozpakowaniu); **When** import; **Then** odrzucony **przed** `load_workbook` z komunikatem o limicie.
3. **Given** plik `.xlsx` bez sygnatury `PK\x03\x04`; **When** import; **Then** odrzucony jak w kryterium 1.
4. **Given** plik z liczbą wierszy > L_WIERSZE, `DEMO_MODE` wyłączony; **When** import; **Then** odrzucony z komunikatem „najwyżej N wierszy” (jak dziś w demo); limit demo (500) bez zmian.
5. **Given** środowisko produkcyjne (`requirements.txt`); **Then** `defusedxml` jest zainstalowany w przypiętej wersji, a openpyxl go wykrywa (np. `openpyxl.xml.DEFUSEDXML is True` — do potwierdzenia przez [DEV]).
6. **Given** błędy `BadZipFile`, `InvalidFileException`, `KeyError` z biblioteki; **When** import; **Then** każdy zamieniony na `ImportError_` z komunikatem, nigdy 500.

**Testy:** `warehouse/tests_imports_hardening.py` — `BrokenXlsxViewTests` (4: plik bez sygnatury ZIP i ucięty ZIP na wszystkich czterech importach, bomba dekompresyjna odrzucona bez wywołania `load_workbook`, poprawny XLSX nadal działa), `LibraryErrorTests` (3), `RowLimitTests` (4: XLSX i CSV poza demo, wartość graniczna, limit demo bez zmian), `DefusedXmlTests` (2), `ReviewRegressionTests` (6, z przeglądu [SEC]: arkusz 16 384 kolumn czyta najwyżej 50 kolumn, „dziura” do wiersza 1 048 576 liczy się do limitu, zaszyfrowany członek ZIP i nieobsługiwana kompresja odrzucone przed `load_workbook`). Przed poprawką 20 sprawdzeń (z podtestami) czerwonych. Wartości: L_WIERSZE = 10 000 (`IMPORT_MAX_ROWS`), L_ROZP = 50 MB (`IMPORT_MAX_UNCOMPRESSED_BYTES`) — Z-23, do potwierdzenia przez PO. Kryterium 5: `openpyxl.xml.DEFUSEDXML is True`, `defusedxml==0.7.1` w `requirements.txt` i `pyproject.toml`. Odbiór [BA] 2026-10-16: kryteria 1–6 spełnione. Wartości w zapisie wykładniczym — US-013.

### US-005 — Retencja dziennika logowań, czyszczenie sesji, limiter wejść demo

| | |
|---|---|
| Historyjka | Jako **administrator danych (ST-07)** chcę, aby dziennik logowań i sesje miały ograniczony czas życia, a anonimowe wejścia demo — limit żądań, aby nie gromadzić danych osobowych bezterminowo i nie dopuścić do zalania bazy przez boty. |
| MoSCoW · rozmiar | Must · M |
| Status | zrobione — do akceptacji PO (PR #23, gałąź sesji) |
| Źródło | AUDYT §3.3 **R7** (Ś) i **R5** (Ś, część), §3.4 pkt 5; Z-09, DEC-5, DEC-6; `signals.py:57-89`, `demo.py:86-143` |
| Wymagania | SEC-005, SEC-035, SEC-036, SEC-040; także: FR-024, NFR-012 |
| Zależności | parametry RETENCJA, K / W (PYT-09, PYT-22); harmonogram w Coolify (ST-05); opis retencji w `RODO.md` (US-023) |

**Kryteria akceptacji**

1. **Given** trzy `LoginEvent`: sprzed 100, 91 i 10 dni; **When** `manage.py purge_login_events`; **Then** zostaje tylko wpis 10-dniowy, komenda wypisuje liczbę usuniętych (2), a drugie uruchomienie usuwa 0.
2. **Given** wpisy sprzed 40 i 10 dni; **When** `purge_login_events --days 30`; **Then** zostaje wpis 10-dniowy (parametr nadpisuje domyślne RETENCJA).
3. **Given** wygasłe i aktywne sesje w `django_session`; **When** `manage.py clearsessions`; **Then** zostają tylko aktywne.
4. **Given** COOLIFY.md; **Then** opisuje harmonogram (Scheduled Task) dla `purge_login_events` i `clearsessions` (dziennie) — weryfikacja ręczna na środowisku.
5. **Given** `DEMO_MODE`; **When** więcej niż K żądań GET `/demo/` albo POST `/login/demo/` w oknie W z jednego IP (wg `_client_ip`, D-12); **Then** (K+1)-sze dostaje 429 i nie powstaje nowa sesja ani `LoginEvent`.
6. **Given** `DEMO_MODE`; **When** udane wejście `/demo/`; **Then** `LoginEvent.ip` jest pusty (pole nullable — bez migracji); user-agent — wg PYT-09.
7. **Given** brak `DEMO_MODE`; **When** GET `/demo/` i POST `/login/demo/`; **Then** nadal 404 (`DemoEntryOffTests` zielone).

**Testy:** `warehouse/tests_retention.py` — `PurgeLoginEventsTests` (5: domyślne 90 dni, `--days`, granica 89 dni, `--days 0` odrzucone, stała 90), `ClearSessionsTests` (1), `LoginEventPrivacyTests` (2: w demo brak IP i UA, poza demo bez zmian); `tests_demo_entry.DemoEntryRateLimitTests` (5: `/demo/` i `/login/demo/` — (K+1)-sze żądanie 429 bez sesji i `LoginEvent`, limit per IP, udane wejście bez IP, odświeżanie przez zalogowanego nie liczy się do limitu). Przed poprawką 9 testów czerwonych. Parametry: RETENCJA = 90 dni (**decyzja PO 2026-10-16**, Z-09), K / W = 10 / 300 s (Z-37, potwierdzone przez PO), w demo `LoginEvent` bez IP i user-agenta (Z-38, potwierdzone przez PO; poza demo bez zmian). Kryterium 4: COOLIFY.md §10a (dwa Scheduled Tasks); dodatkowo `entrypoint.sh` uruchamia obie komendy przy starcie. Limiter jest per proces gunicorna (LocMem, jak limit logowań — pułapka auth #6) i liczy tylko wejścia anonimowe (po przeglądzie [SEC]: zalogowany, odświeżając `/demo/`, nie zużywa limitu innym za tym samym NAT; `--days` ograniczone do 1…36 500). Przegląd [DB]: brak indeksu na `LoginEvent.created_at` — przy obecnej skali pełny skan jest tani, indeks wymaga migracji → US-051. Odbiór [BA] 2026-10-16: kryteria 1–3 i 5–7 spełnione; 4 — do sprawdzenia ręcznie na środowisku po deployu.

### US-006 — Łańcuch dostaw i CI: blokujące skany, Dependabot, SECURITY.md

| | |
|---|---|
| Historyjka | Jako **PO** chcę, aby podatne zależności i słaba konfiguracja CI blokowały merge, a zgłaszający podatność miał kanał kontaktu, aby łańcuch dostaw nie był najsłabszym ogniwem. |
| MoSCoW · rozmiar | Must · M |
| Status | do zrobienia; **w toku: ADR-0001/CI** (Dependabot, pip-audit blokujący, `permissions`, przypięte narzędzia) i **[SEC]** (SECURITY.md) |
| Źródło | AUDYT §3.3 **R10** (N/Ś), §3.4 pkt 6; `security.yml:48`, `ci.yml`, Z-10, DEC-2 |
| Wymagania | SEC-028, SEC-029, SEC-031 |
| Zależności | ADR-0001; PYT-13 (trivy: Z-10 vs R10); US-020 (reszta łańcucha dostaw) |

**Kryteria akceptacji**

1. **Given** repozytorium; **Then** istnieje `.github/dependabot.yml` z ekosystemami pip, docker i github-actions (okresowo) i otwiera PR-y aktualizacji.
2. **Given** PR dodający do `requirements.txt` zależność ze znaną podatnością; **When** CI; **Then** job pip-audit jest czerwony i blokuje merge (bez `|| true`).
3. **Given** PR z wzorcem sekretu lub problemem bandit ≥ średni; **When** CI; **Then** jobs gitleaks / bandit czerwone (Z-10).
4. **Given** `ci.yml`; **Then** ma top-level `permissions: contents: read`; narzędzia bezpieczeństwa są instalowane w przypiętych wersjach, bez `curl … | sh`.
5. **Given** trivy; **Then** tryb (blokujący / doradczy) zgodny z decyzją PO (PYT-13).
6. **Given** `SECURITY.md`; **Then** zawiera wspierane wersje, kanał zgłoszeń poza publicznym issue, oczekiwany czas odpowiedzi (ustala PO) i zakres (publiczne demo = wspólna instancja, bez testów obciążeniowych).

**Test do napisania:** brak testu jednostkowego — weryfikacja przebiegiem CI na PR kontrolnym z podatną zależnością (zamykanym po teście) oraz przeglądem [SEC] / [BA] dla SECURITY.md.

---

## 3. Should

### US-007 — Macierz dostępu rola × trasa

| | |
|---|---|
| Historyjka | Jako **[SEC]** chcę zautomatyzowanej macierzy rola × trasa, aby każda trasa miała test „brak dostępu”, a nowy widok bez dekoratora nie mógł trafić na produkcję. |
| MoSCoW · rozmiar | Should · M |
| Status | zrobione — do akceptacji PO (PR #23, gałąź sesji) |
| Źródło | prompt PO sekcja 6; AUDYT Zał. A i §3.1 („≈ 35 asercji, brak macierzy”); pitfalls/auth #1 |
| Wymagania | SEC-007, SEC-008; także: FR-023 |
| Zależności | — (zalecane **przed** US-017) |

**Kryteria akceptacji**

1. **Given** wszystkie trasy z `get_resolver()` z przypisaną rolą minimalną (P / L / O / A wg Załącznika A AUDYT); **When** test iteruje po rolach anonim, Podgląd, Operator, Administrator i metodach GET / POST; **Then** rola poniżej minimum dostaje 302 (anonim → `/login/`) albo 403, nigdy 200 ani 5xx.
2. **Given** ta sama macierz; **When** rola spełnia minimum; **Then** odpowiedź nie jest 403 (dostęp pozytywny).
3. **Given** nowa trasa dodana bez wpisu w macierzy; **When** uruchomienie testu; **Then** test jest czerwony i podaje nazwę trasy.

**Testy:** `warehouse/tests_access_matrix.py` — `AccessMatrixTests` (2: kompletność macierzy dla 70 nazwanych tras i macierz 70 tras × 4 role × GET/POST = 560 sprawdzeń w podtestach), `DemoAccessMatrixTests` (1: `demo/przywroc/` przy `DEMO_MODE`), `AdminSiteAccessTests` (2: `/admin/` tylko dla `is_staff`, role aplikacji → logowanie panelu). Odmowa: anonim → 302 na `/login/` albo 405, rola poniżej minimum → 403 albo 405 (zła metoda odrzucana przed rolą); nigdy 200 ani 5xx. Dostęp: rola minimalna nie dostaje 403 ani 5xx (nieistniejący `pk` → 404, bez zmian w bazie). Sprawdzenie mutacyjne [DEV]: usunięcie `@admin_required` z `hu_delivery` i dodanie trasy bez wpisu dają czerwony test z nazwą trasy. Odbiór [BA] 2026-10-16: kryteria 1–3 spełnione. Zmiana wyłącznie w testach — bez zmian w działaniu aplikacji.

### US-008 — Hasła w argon2

| | |
|---|---|
| Historyjka | Jako **Administrator** chcę, aby hasła były przechowywane algorytmem argon2, aby wyciek bazy nie pozwalał szybko łamać haseł. |
| MoSCoW · rozmiar | Should · S |
| Status | zrobione — do akceptacji PO (PR #23, gałąź sesji) |
| Źródło | AUDYT §3.3 **R6** (Ś); DEC-4 (argon2: tak) |
| Wymagania | SEC-001 |
| Zależności | `argon2-cffi` w `requirements.txt` (koła binarne — obraz bez kompilatorów); miękko US-020 |

**Kryteria akceptacji**

1. **Given** produkcyjne / dev `PASSWORD_HASHERS`; **When** zakładam konto lub zmieniam hasło; **Then** hash zaczyna się od `argon2$`.
2. **Given** konto z hashem PBKDF2; **When** poprawne logowanie; **Then** hash zostaje podniesiony do argon2, a hasło działa.
3. **Given** `config.settings.test`; **Then** szybki hasher (MD5) zostaje wyłącznie tam (pitfalls/auth #11), a `prod.py` / `dev.py` go nie zawierają.
4. **Given** obraz budowany w CI; **When** smoke test; **Then** kontener jest healthy (instalacja `argon2-cffi` bez kompilatora).

**Testy:** `warehouse/tests_passwords.py` — `PasswordHasherTests` (3: nowe i zmienione hasło → `argon2$`, hash PBKDF2 podniesiony do argon2 przy poprawnym logowaniu, błędne hasło nie zmienia hasha), `HasherConfigTests` (3: argon2 pierwszy w `base.py`, MD5 tylko w `test.py`, `argon2-cffi` przypięty). Przed zmianą testy czerwone (brak `PASSWORD_HASHERS` w `base.py`). Sprawdzenie [DEV]: ustawienia produkcyjne (`DJANGO_DEBUG=0`) tworzą hash `argon2$`. Kryterium 4 — smoke test obrazu w CI (`argon2-cffi-bindings` ma koła `abi3` dla Linuksa, bez kompilatora). Odbiór [BA] 2026-10-16: kryteria 1–3 spełnione; 4 — CI na PR.

### US-009 — Limit prób logowania per konto i wspólny dla workerów

| | |
|---|---|
| Historyjka | Jako **Administrator** chcę limitu prób logowania liczonego per konto i wspólnie dla wszystkich workerów, aby atak słownikowy z puli adresów IP nie zgadywał hasła. |
| MoSCoW · rozmiar | Should · M |
| Status | zrobione — do akceptacji PO (PR #23, gałąź sesji) |
| Źródło | AUDYT §3.3 **R6**, §2.4 **T8**; docs/07 „Znane problemy” #1 i „Co dalej” (Redis); D-12 |
| Wymagania | SEC-003, SEC-004; NFR-013 |
| Zależności | wybór cache (`DatabaseCache` bez nowej usługi albo Redis) → ADR; PYT-07 (blokada czasowa vs opóźnienie) |

**Kryteria akceptacji**

1. **Given** N_KONTO nieudanych prób na login `admin` z różnych IP w oknie W_KONTO; **When** kolejna próba z nowego IP, także z poprawnym hasłem; **Then** 429 do końca okna; po upływie okna logowanie działa.
2. **Given** konto `admin` zablokowane; **When** inny użytkownik B loguje się poprawnie; **Then** sukces (brak globalnej blokady).
3. **Given** licznik w cache współdzielonym; **When** 10 nieudanych prób przechodzi przez różne procesy; **Then** 11. dostaje 429 (limit globalny, nie ×3).
4. **Given** zablokowana próba; **Then** zapis w dzienniku zdarzeń (rodzaj „zablokowane”) bez wpisanego hasła.

**Testy:** `warehouse/tests_login_limits.py` — `AccountLockoutTests` (8: blokada po 10 próbach z różnych IP także dla poprawnego hasła, logowanie po oknie, login bez wielkości liter, inne konto działa, udane logowanie zeruje licznik, nieistniejące konto — ta sama odpowiedź, wpis „Zablokowana próba” bez hasła, zablokowana próba nie sprawdza hasła), `SharedCacheTests` (3: backend DatabaseCache, licznik w tabeli `miniwms_cache`, nowy klient cache widzi ten sam licznik). Przed poprawką 11 czerwonych; `test_login_rate_limit` i `test_rate_limit_also_without_demo_mode` bez regresji. Decyzje PO 2026-10-16: DatabaseCache (ADR-0002), N_KONTO / W_KONTO = 10 / 15 min, nowy rodzaj zdarzenia BLOCKED (migracja `0009_loginevent_blocked_kind` — tylko lista wyborów, bez zmian w wierszach, odwracalna). PYT-07: blokada czasowa (429), nie opóźnienie. Odbiór [BA] 2026-10-16: kryteria 1–4 spełnione. **Po przeglądach [SEC]/[DB]** (poprawki w osobnym commicie): login normalizowany jak w formularzu (NFKC + casefold) — warianty unicode nie omijają blokady; `/admin/login/` ma ten sam limit per IP i blokadę konta; licznik konta w tabeli `LoginFailureCounter` (migracja `0010`, atomowy `UPDATE count = count + 1`, pełne okno 15 min, odporny na culling cache); `MAX_ENTRIES` cache 100 000; IP w kluczach cache jako skrót; publiczne konta demo wyłączone z blokady w `DEMO_MODE`. Testy dodatkowe: unicode (2), pełne okno, `AdminLoginGuardTests` (3), `DemoAccountsExemptTests`, `SharedCounterTests` (6).

### US-010 — 2FA dla Administratora

| | |
|---|---|
| Historyjka | Jako **Administrator** chcę logować się z drugim składnikiem (TOTP), aby przejęte hasło nie dawało dostępu do kont i `/admin/`. |
| MoSCoW · rozmiar | Should (warunkowo: DEC-4) · L |
| Status | zrobione — do akceptacji PO (PR #23, gałąź sesji) |
| Źródło | AUDYT §3.3 **R6**; prompt PO sekcja 6 („2FA dla adminów opcjonalnie”); DEC-4 |
| Wymagania | SEC-006 |
| Zależności | US-008, US-022; ADR (np. `django-otp`); procedura resetu w RUNBOOK |

**Kryteria akceptacji**

1. **Given** Administrator z włączonym TOTP; **When** logowanie samym hasłem; **Then** brak dostępu do widoków `@admin_required` i `/admin/` (przekierowanie do weryfikacji kodu).
2. **Given** poprawny kod; **Then** pełny dostęp; nieudane kody liczą się do limitu z US-009.
3. **Given** utrata urządzenia; **When** superuser resetuje 2FA poleceniem `manage.py` (procedura w RUNBOOK); **Then** Administrator rejestruje nowe urządzenie.
4. **Given** Operator lub Podgląd; **Then** logowanie bez zmian.

**Testy:** `warehouse/tests_2fa.py` — `AdminTwoFactorTests` (7: samo hasło → przekierowanie na kod dla widoków admina, pulpitu i operacji; `/admin/` wymaga kodu; poprawny kod → dostęp i powrót pod `next`; zewnętrzny `next` ignorowany; 10 błędnych kodów → 429 i wpisy „Nieudane logowanie”; wylogowanie bez kodu; Administrator bez 2FA bez zmian), `OtherRolesTests` (2: Operator i Podgląd bez zmian, Operator nie włączy 2FA), `EnrollmentTests` (2: QR i pierwszy kod włączają 2FA, błędny kod nie włącza), `ResetCommandTests` (2: `reset_2fa` po utracie telefonu, nieznany login). Macierz dostępu (US-007) uzupełniona o `two_factor_setup` (A) i `two_factor_verify` (L). Decyzja PO 2026-10-16: wdrażamy 2FA (PYT-08). Założenie Z-39 (do potwierdzenia): 2FA **dobrowolne** dla Administratora. Biblioteka: `django-otp` (ADR-0003). Odbiór [BA] 2026-10-16: kryteria 1–4 spełnione. Po przeglądzie [SEC]: każde wyświetlenie `/2fa/` generuje nowy klucz (podejrzany sekret nie zostanie potwierdzony), strony 2FA `no-store`, `next` kodowany w URL (`EnrollmentSecretTests`, 2).

### US-011 — CSP, Permissions-Policy, HSTS

| | |
|---|---|
| Historyjka | Jako **[SEC]** chcę ścisłej polityki treści i ograniczenia uprawnień przeglądarki, aby przyszły błąd szablonu lub JS nie dał pełnego zasięgu (kradzież sesji operatora). |
| MoSCoW · rozmiar | Should · L |
| Status | zrobione — do akceptacji PO (PR #23, gałąź sesji); kryterium 3 — test ręczny na telefonie |
| Źródło | AUDYT §3.3 **R8** (Ś); `base.py:71-82`, `prod.py:38-40`, `scanner/base.html` |
| Wymagania | SEC-022, SEC-024, SEC-025 |
| Zależności | usunięcie 7 inline handlerów `onclick` i inline `window.CSRF`; `django-csp` (ADR); test ręczny skanera na telefonie |

**Kryteria akceptacji**

1. **Given** produkcja; **When** GET dowolnej strony HTML; **Then** `Content-Security-Policy` z `script-src` z nonce i bez `'unsafe-inline'` (wdrożenie najpierw w trybie Report-Only — decyzja [DEV]).
2. **Given** szablony; **Then** brak atrybutów `on*=` i inline `<script>` bez nonce (test przeszukuje szablony / odpowiedzi).
3. **Given** skaner na telefonie przez HTTPS; **When** start kamery i skan QR; **Then** działa (test ręczny w karcie odbioru).
4. **Given** produkcja; **Then** `Permissions-Policy` zawiera `camera=(self)` i `geolocation=()`.
5. **Given** HSTS; **Then** wartość ≥ 1 rok albo `preload` wyłączony (test ustawień).

**Testy:** `warehouse/tests_security_headers.py` — `TemplateScanTests` (2: brak `on*=`/`javascript:`, każdy `<script>` inline z nonce), `SecurityHeadersTests` (8: CSP z nonce bez `unsafe-inline`/`unsafe-eval` na 9 stronach w tym skanera, nonce z nagłówka na każdym skrypcie inline odpowiedzi, nonce inny na każde żądanie, `frame-ancestors`/`object-src`/`base-uri`, `Permissions-Policy` z `camera=(self)` i `geolocation=()`, API JSON bez CSP, przełącznik Report-Only, panel `/admin/` bez wykonywalnych skryptów inline), `HstsSettingsTests` (1: produkcja — `preload` wyłączony, CSP egzekwowana). Sprawdzenie [DEV] w Chromium (Playwright, poza CI): 22 strony demo — 0 naruszeń CSP; działają menu, auto-filtr, różnica w spisie, potwierdzenia, „Anuluj”; próba kontrolna — wstrzyknięty `<script>` i `onerror` zablokowane. Decyzja [DEV] (ADR-0004): CSP egzekwowana od razu, awaryjnie `DJANGO_CSP_REPORT_ONLY=1`. Odbiór [BA] 2026-10-16: kryteria 1, 2, 4, 5 spełnione; **3 (kamera na telefonie przez HTTPS) — do wykonania ręcznie po deployu**.

### US-012 — Backup off-site, szyfrowany, z testem odtworzenia

| | |
|---|---|
| Historyjka | Jako **administrator infrastruktury (ST-05)** chcę kopii zapasowej poza hostem bazy, szyfrowanej, z alertem i przećwiczonym odtworzeniem, aby awaria dysku lub pomyłka operatora nie niszczyły bazy i kopii naraz. |
| MoSCoW · rozmiar | Should · M |
| Status | zrobione — do akceptacji PO (PR #23, gałąź sesji); konfiguracja off-site i pierwsze ćwiczenie na kopii produkcyjnej — po stronie PO/INFRA |
| Źródło | AUDYT §3.3 **R9** (Ś); `scripts/pg_backup.sh`, COOLIFY.md §10; PROCESY P-07, L-03 |
| Wymagania | SEC-039; NFR-018, NFR-019; także: NFR-014 |
| Zależności | lokalizacja off-site i klucz szyfrujący (PYT-16); retencja kopii a RODO (PYT-09); RUNBOOK |

**Kryteria akceptacji**

1. **Given** backup wg harmonogramu; **When** zakończony; **Then** szyfrowana kopia (np. `age` / `gpg`) istnieje poza hostem bazy, a klucz deszyfrujący nie leży na tym hoście.
2. **Given** kopie starsze niż retencja off-site (propozycja audytu: 30 dni); **Then** są usuwane.
3. **Given** brak świeżej kopii przez czas dłuższy niż próg (PYT-16); **Then** alert do administratora.
4. **Given** miesięczny test odtworzenia; **When** odtworzenie na środowisku testowym; **Then** aplikacja wstaje, `manage.py check` przechodzi, a liczba palet zgadza się z produkcją; wynik zapisany w RUNBOOK.

**Testy:** `warehouse/tests_backup_script.py` — `BackupScriptTests` (8: pełny sukces — szyfrowanie, wysyłka, retencja `--min-age 30d`, heartbeat; prawdziwy `age` — kopia nieczytelna bez klucza prywatnego i odszyfrowywalna nim; błąd `pg_dump` nie daje „OK”, wysyłki ani pingu; pusta kopia odrzucona; błąd wysyłki = brak pingu; off-site bez szyfrowania odmówiony; tryb tylko lokalny bez zmian; własna retencja), `BackupFingerprintTests` (1). `shellcheck` w CI (job 1). CI job „3b”: ćwiczenie odtworzenia na PostgreSQL — seed → `pg_backup.sh` w obrazie PostgreSQL → `age` → `rclone` → odszyfrowanie → odtworzenie do pustej bazy → `check`, migracje, `backup_fingerprint` identyczny. CI job 7: build obrazu `backup`. Decyzje PO 2026-10-16 (PYT-16): rclone (dowolny S3/SFTP), age z kluczem prywatnym offline u PO, heartbeat, retencja off-site 30 dni (ADR-0005). Po przeglądzie [SEC]: domyślnie serwer nie usuwa kopii off-site (lifecycle bucketu, klucz bez prawa usuwania; `BACKUP_OFFSITE_PRUNE=1` dla SFTP, tylko własny katalog `--max-depth 1`), retencja < 1 dnia i cel bez katalogu odrzucane, trivy skanuje obraz `backup`, ćwiczenie w CI na zbudowanym obrazie (`BackupScriptReviewTests`, 4). Uwaga [DEV] rozwiązana: `pg_dump -Z 6 -f` zamiast potoku (kod wyjścia z pg_dump), kontrola rozmiaru i `gzip -t`. Odbiór [BA] 2026-10-16: kryteria 1–3 spełnione w kodzie (aktywne po ustawieniu zmiennych — RUNBOOK §5.0); 4 — mechanizm i procedura gotowe (§5.4), pierwsze ćwiczenie na kopii produkcyjnej do wykonania przez INFRA.

### US-013 — Walidacja zakresów, długości i nagłówków z danych użytkownika

| | |
|---|---|
| Historyjka | Jako **Operator** chcę, aby formularze, API skanera i importy walidowały zakres i długość danych, aby błędna wartość kończyła się komunikatem przy polu lub wierszu, a nie błędem 500 i wycofaniem całego importu. |
| MoSCoW · rozmiar | Should · M |
| Status | zrobione — do akceptacji PO (PR #23, gałąź sesji) |
| Źródło | AUDYT §2.4 **T16**, „poza listą” (Content-Disposition); `forms.py:111,132,276,332`, `views.py:370,498,1066`, `scanner_views.py:421`, `imports.py:32,59` |
| Wymagania | SEC-015, SEC-017; także: FR-001, FR-004, FR-005, FR-018, NFR-009 |
| Zależności | US-002 (wspólne stałe L_QTY); test na PostgreSQL w CI (`test-postgres`) |

**Kryteria akceptacji**

1. **Given** import z komórką w zapisie wykładniczym (wartość poza zakresem) w polu liczbowym; **When** import; **Then** wiersz pominięty z komunikatem „Wiersz N: nieprawidłowa liczba”, bez `OverflowError` i bez 500.
2. **Given** pole całkowite formularza (limit na paletę, przyjęcie, korekta, pozycja WZ) z wartością > 2^31−1; **When** zapis; **Then** błąd pola, nie `DataError` (sprawdzone na PostgreSQL).
3. **Given** `stocktake_save` lub API inwentaryzacji (`delta`) z wartością > L_QTY; **Then** odrzucone z komunikatem / JSON 400.
4. **Given** import z kodem lokalizacji > 40 znaków lub numerem HU > 30; **When** import; **Then** wiersz pominięty z komunikatem, bez częściowego importu.
5. **Given** kod lokalizacji lub numer HU zawierający `"` albo znak nowej linii; **When** pobranie etykiety; **Then** 200 PDF z poprawnym `Content-Disposition` (`django.utils.http.content_disposition_header`), bez `BadHeaderError`.

**Testy:** `warehouse/tests_input_validation.py` — `ImportNumberTests` (3: `1e999`/`1e20`/`inf`/`nan`/2^31 → „nieprawidłowa liczba” we wszystkich importach i w pojemności lokalizacji), `FormRangeTests` (3: korekta, przepakowanie, lokalizacja, materiał, pozycja WZ, inwentaryzacja z 2^31 → błąd pola, bez zmian w bazie), `QuantityLimitTests` (3: spis i API inwentaryzacji/przepakowania > L_QTY → pominięte / JSON 400), `ImportLengthTests` (3: kod lokalizacji > 40, numer HU > 30, partia > 50, referencja > 100 → wiersz pominięty, bez materiałów i lokalizacji z odrzuconych wierszy), `ContentDispositionTests` (2: `"` i nowa linia w kodzie → 200 PDF; polskie znaki → `filename*=utf-8''`). Przed poprawką 25 sprawdzeń czerwonych; kryterium 2 na PostgreSQL — CI job „3b”. Wartości: L_QTY = `services.MAX_QUANTITY` = 1 000 000 (jak US-002), pojemność lokalizacji ≤ 10 000 (Z-40, do potwierdzenia). Import stanów sprawdza długości **przed** utworzeniem materiału i lokalizacji. Po przeglądach [SEC]/[DB] (`ReviewFixTests`, 5): stan palety po korekcie/inwentaryzacji/przepakowaniu najwyżej `MAX_QUANTITY` (inaczej `DataError` na PostgreSQL po wielu dodaniach), generator numerów HU pomija numery nadane ręcznie w imporcie (kolizja wycofywała cały import), id dokumentu w API skanera tylko z cyfr ASCII (`"²".isdigit()` dawało 500). Odbiór [BA] 2026-10-16: kryteria 1–5 spełnione.

### US-014 — Walidacja adresu IP z nagłówka proxy

| | |
|---|---|
| Historyjka | Jako **Administrator** chcę, aby aplikacja ignorowała niepoprawny adres w `X-Forwarded-For`, aby błędna konfiguracja proxy nie wywalała logowania ani nie psuła limitera. |
| MoSCoW · rozmiar | Should · S |
| Status | do zrobienia |
| Źródło | AUDYT „poza listą” (`signals.py:38-48`); pitfalls/auth #5; D-12 |
| Wymagania | SEC-041 |
| Zależności | — |

**Kryteria akceptacji**

1. **Given** `TRUSTED_PROXY_COUNT=1` i `X-Forwarded-For` z wartością niebędącą adresem IP; **When** logowanie; **Then** adres z `REMOTE_ADDR`, `LoginEvent` zapisany, brak `DataError` i 500.
2. **Given** poprawny adres IPv6 w nagłówku; **Then** zapisany bez zmian.

**Test do napisania:** rozszerzenie `ClientIPTests` w `warehouse/tests_open_decisions.py`.

### US-015 — Paginacja list i limit etykiet lokalizacji

| | |
|---|---|
| Historyjka | Jako **Podgląd** chcę list podzielonych na strony i limitu wydruku etykiet lokalizacji, aby przeglądanie i drukowanie nie zajmowały workera na minuty. |
| MoSCoW · rozmiar | Should · M |
| Status | do zrobienia |
| Źródło | AUDYT §3.3 **R5** (część): `views.py:310-317,375-383,453-474,858-876` |
| Wymagania | SEC-021; NFR-006, NFR-010; także: NFR-003 |
| Zależności | — |

**Kryteria akceptacji**

1. **Given** lokalizacji > L_ETYKIET_LOK; **When** GET `/lokalizacje/etykiety/` (rola Podgląd); **Then** przekierowanie z komunikatem „Zawęź filtr” (jak `HU_LABELS_LIMIT`), bez generowania PDF.
2. **Given** rekordów > ROZMIAR_STRONY; **When** GET `/hu/`, `/lokalizacje/`, `/stany/lokalizacje/`, `/raporty/lokalizacje/`; **Then** strona zawiera ≤ ROZMIAR_STRONY wierszy i nawigację stron; filtry działają.
3. **Given** lista stronicowana; **When** eksport CSV / XLSX; **Then** zawiera wszystkie rekordy filtra, nie tylko bieżącą stronę.

**Test do napisania:** `PaginationTests`, `LocationLabelsLimitTests` w `warehouse/tests_pagination.py` (nowy).

### US-016 — Demo: limity obiektów, limiter ścieżek operatora, reset z harmonogramu

| | |
|---|---|
| Historyjka | Jako **PO** chcę ograniczyć, ile obiektów i żądań może wygenerować anonimowy Operator w demo, i przenieść reset danych demo do harmonogramu, aby demo pozostało dostępne mimo botów. |
| MoSCoW · rozmiar | Should · M |
| Status | do zrobienia — warunek: DEC-6 / PYT-22 |
| Źródło | AUDYT §3.3 **R5** (reszta), DEC-6; `demo.py:126-143` (`demo_reset`), `imports.py:119-127`, `seed_demo.py:116` |
| Wymagania | SEC-040; Z-05 |
| Zależności | US-005 (limiter wejść), parametry K / W, L_DEMO; zmiana usuwa przycisk „Przywróć dane demo” — wpływ na `DemoResetTests` i tour |

**Kryteria akceptacji**

1. **Given** `DEMO_MODE` i łączna liczba palet lub lokalizacji ≥ L_DEMO; **When** Operator próbuje przyjęcia lub importu zwiększającego liczbę; **Then** odrzucone komunikatem „limit demo”.
2. **Given** `DEMO_MODE` i więcej niż K żądań POST ze ścieżek operatora z jednego IP w oknie W; **Then** 429.
3. **Given** `DEMO_MODE`; **When** Operator wysyła POST `/demo/przywroc/`; **Then** reset z UI niedostępny (wariant wg DEC-6), a `manage.py seed_demo --reset --keep-users` wywołane z harmonogramu działa i zachowuje sesje.

**Test do napisania:** `DemoLimitsTests` w `warehouse/tests_demo_limits.py` (nowy); aktualizacja `DemoResetTests`.

### US-017 — Podział `views.py` na moduły

| | |
|---|---|
| Historyjka | Jako **[DEV]** chcę podzielić `views.py` (1405 linii, 47 widoków) na moduły, aby zmiany były tańsze, a review czytelne. |
| MoSCoW · rozmiar | Should · L |
| Status | do zrobienia |
| Źródło | AUDYT §2.4 **T2**; pitfalls/views #8 |
| Wymagania | NFR-027; SEC-007 (bez regresji) |
| Zależności | **po** US-007 (siatka bezpieczeństwa) i po US-001…US-005 (te same pliki — konflikty) |

**Kryteria akceptacji**

1. **Given** pakiet `warehouse/views/` z modułami (np. `dashboard`, `issues`, `users`, `exports` + reszta); **When** `reverse()` dla wszystkich nazw z `urls.py`; **Then** adresy identyczne jak przed zmianą.
2. **Given** istniejący zestaw testów; **When** `pytest`; **Then** wszystkie zielone bez zmian w testach; macierz z US-007 zielona.
3. **Given** każdy widok; **Then** ma te same dekoratory roli co wcześniej (macierz).
4. **Given** pitfalls/views; **Then** punkt #8 zaktualizowany (T14).

**Test do napisania:** `test_url_names_unchanged` w `warehouse/tests_urls.py` (nowy; snapshot nazw i ścieżek).

### US-018 — Domknięcie WZ w warstwie usług

| | |
|---|---|
| Historyjka | Jako **[DEV]** chcę, aby zamknięcie dokumentu WZ po ostatnim pobraniu ze skanera odbywało się w `services.py` pod blokadą, aby zmiana stanu miała jedno miejsce (D-05) i nie było wyścigu. |
| MoSCoW · rozmiar | Should · M |
| Status | do zrobienia |
| Źródło | AUDYT §2.4 **T3**; `scanner_views.py:357-363`; D-05 |
| Wymagania | NFR-026; FR-017 |
| Zależności | — |

**Kryteria akceptacji**

1. **Given** WZ z jedną pozycją; **When** API skanera pobiera ostatnią ilość; **Then** WZ „Zrealizowany” ustawia funkcja serwisu (np. `complete_if_picked`) pod `select_for_update`, a `api_pick` nie przypisuje statusu samodzielnie.
2. **Given** dokument już zrealizowany równolegle („Realizuj” w panelu); **When** skaner pobiera ostatnią ilość; **Then** brak podwójnego zamknięcia i brak błędu (idempotencja).
3. **Given** PostgreSQL; **When** skaner i „Realizuj” równolegle na tym samym WZ; **Then** łączna ilość nie przekracza żądanej (rozszerzenie `tests_concurrency_pg.py`).

**Test do napisania:** `CompleteIfPickedTests` w `warehouse/tests_services_fixes.py` (rozszerzenie) i przypadek w `tests_concurrency_pg.py`.

### US-019 — CI: pełny mypy, próg pokrycia, pytest

| | |
|---|---|
| Historyjka | Jako **[DEV]** chcę, aby CI sprawdzało typy w całym kodzie, pilnowało progu pokrycia i uruchamiało testy przez pytest, aby regresje były widoczne w kilka minut. |
| MoSCoW · rozmiar | Should · S |
| Status | **w toku: ADR-0001/CI** |
| Źródło | AUDYT §2.4 **T4, T5, T6**; Z-08, DEC-3 |
| Wymagania | NFR-022, NFR-023, NFR-024 |
| Zależności | ADR-0001 |

**Kryteria akceptacji**

1. **Given** PR z błędem typu w `warehouse/views.py`; **When** CI; **Then** krok `mypy warehouse config` jest czerwony.
2. **Given** PR obniżający pokrycie poniżej 80 % ogółem lub 90 % dla `services.py`; **When** CI; **Then** krok pokrycia jest czerwony; raport jest artefaktem.
3. **Given** CI; **Then** testy idą przez `pytest -q` z `config.settings.test` (SQLite i PostgreSQL), w tym `tests_concurrency_pg`.

**Test do napisania:** n/d — weryfikacja przebiegiem CI (PR kontrolny).

### US-020 — Lock zależności i dalsze utwardzenie łańcucha dostaw

| | |
|---|---|
| Historyjka | Jako **[DEV]** chcę zablokowanych wersji zależności z hashami i przypiętych obrazów oraz akcji, aby build był powtarzalny i odporny na podmianę. |
| MoSCoW · rozmiar | Should · M |
| Status | do zrobienia; SHA akcji GitHub — **w toku: ADR-0001/CI**; lockfile i digest obrazu bazowego — do zrobienia |
| Źródło | AUDYT §2.4 **T7**, §3.3 **R10** (reszta); `Dockerfile:4,18` |
| Wymagania | NFR-025; SEC-029, SEC-031 |
| Zależności | US-006; ADR (narzędzie: `pip-compile` lub `uv`) |

**Kryteria akceptacji**

1. **Given** lockfile z hashami wygenerowany z jednego źródła zależności; **When** `pip install --require-hashes`; **Then** instalacja przechodzi, a dwie ręczne listy zależności znikają.
2. **Given** Dockerfile; **Then** instaluje z locka, bazuje na obrazie przypiętym digestem, bez `pip install --upgrade pip` bez wersji.
3. **Given** nowa wersja zależności; **Then** Dependabot aktualizuje lock w PR przechodzącym pełne CI.

**Test do napisania:** n/d — weryfikacja przebiegiem CI i budowaniem obrazu.

### US-021 — Alerty o błędach 500

| | |
|---|---|
| Historyjka | Jako **administrator infrastruktury (ST-05)** chcę dostać powiadomienie o błędzie 500, aby awaria nie czekała na zgłoszenie użytkownika. |
| MoSCoW · rozmiar | Should · M |
| Status | do zrobienia — kanał po decyzji PO (PYT-15) |
| Źródło | AUDYT §2.4 **T15**; PROCESY L-04 |
| Wymagania | NFR-021; także: NFR-014, SEC-032 |
| Zależności | wybór kanału (Sentry / GlitchTip / `ADMINS` + `mail_admins` / alert Coolify) → ADR |

**Kryteria akceptacji**

1. **Given** nieobsłużony wyjątek w widoku; **When** żądanie kończy się 500; **Then** administrator dostaje powiadomienie w uzgodnionym kanale.
2. **Given** żądanie POST z polem `password`; **When** błąd 500; **Then** treść powiadomienia i log nie zawierają wartości hasła ani tokenów (SEC-032).

**Test do napisania:** `ServerErrorAlertTests` w `warehouse/tests_alerts.py` (nowy; przy `mail_admins` — `mail.outbox`).

### US-022 — Dziennik audytowy akcji administracyjnych i logi bez sekretów

| | |
|---|---|
| Historyjka | Jako **[SEC]** chcę, aby zmiany kont i odmowy dostępu zostawiały ślad (kto, co, kiedy, wynik), a logi nie zawierały haseł, aby dało się odtworzyć incydent bez ujawniania sekretów. |
| MoSCoW · rozmiar | Should · M |
| Status | do zrobienia |
| Źródło | prompt PO sekcja 6 (logi bez haseł + audit log); AUDYT R1 (skutek: zniszczenie śladu), R7 (wpisany login), `config/log.py` (29 % pokrycia) |
| Wymagania | SEC-032, SEC-033; NFR-020; także: FR-021, FR-024 |
| Zależności | US-001 (źródło zdarzenia „odmowa”); miejsce zapisu (model czy log) → ADR; PYT-09 |

**Kryteria akceptacji**

1. **Given** Administrator zmienia rolę, hasło lub status konta U; **When** zapis; **Then** w dzienniku audytowym jest wpis: aktor, cel (U), akcja, czas, wynik; wartość hasła nie występuje w żadnym polu ani w logu.
2. **Given** odmowa z US-001; **Then** wpis „odmowa” z aktorem i celem.
3. **Given** nieudane logowanie z loginem nieistniejącym w `auth_user`; **When** zapis `LoginEvent`; **Then** pole „wpisany login” jest przycięte do ustalonej długości (PYT-09).
4. **Given** żądanie z polami `password` i `csrfmiddlewaretoken`; **When** wyjątek jest logowany w JSON; **Then** log nie zawiera ich wartości.

**Test do napisania:** `AuditLogTests`, `LogRedactionTests` w `warehouse/tests_audit_log.py` (nowy).

### US-023 — RODO.md v0.1: rejestr czynności, retencja, prawa osób

| | |
|---|---|
| Historyjka | Jako **administrator danych (ST-07)** chcę dokumentu RODO z rejestrem czynności, podstawami i retencją oraz procedurą praw osób, aby móc odpowiedzieć organowi nadzorczemu i pracownikowi. |
| MoSCoW · rozmiar | Should · M |
| Status | **w toku: [SEC]** (`docs/bezpieczenstwo/RODO.md`) |
| Źródło | AUDYT **R7**, §3.2, §3.4 pkt 5; Z-09, Z-15; prompt PO sekcja 6 |
| Wymagania | SEC-037, SEC-038 |
| Zależności | `KLASYFIKACJA_DANYCH.md`; PYT-10 |

**Kryteria akceptacji**

1. **Given** `RODO.md`; **Then** dla każdej tabeli z danymi osobowymi (`auth_user`, `LoginEvent`, `created_by`, eksporty, logi gunicorna) podaje cel, podstawę (art. 6 ust. 1 lit. f — Z-09), retencję, odbiorców i właściciela.
2. **Given** żądanie osoby; **Then** dokument opisuje krok po kroku wydanie lub anonimizację danych, z zachowaniem integralności ruchów magazynowych.

**Test do napisania:** n/d (dokument) — odbiór [BA] / [SEC].

### US-024 — Rejestr ryzyk i zaakceptowanych wyjątków

| | |
|---|---|
| Historyjka | Jako **PO** chcę rejestr ryzyk z jawną listą wyjątków i datą przeglądu, aby wiedzieć, co świadomie akceptuję. |
| MoSCoW · rozmiar | Should · S |
| Status | **w toku: [SEC]** (`docs/bezpieczenstwo/RYZYKA.md`) |
| Źródło | AUDYT §3.3 (R1–R10), §3.5 |
| Wymagania | SEC-042 |
| Zależności | PYT-19 |

**Kryteria akceptacji**

1. **Given** `RYZYKA.md`; **Then** R1–R10 mają właściciela i status zgodny z backlogiem (US).
2. **Given** wyjątek z §3.5 (publiczny Operator w demo, logowanie GET `/demo/`, jawne hasło demo, brak 2FA do wdrożenia, backup lokalny); **Then** ma uzasadnienie, datę przeglądu i akceptację PO.

**Test do napisania:** n/d (dokument).

### US-025 — Macierz śledzenia wymaganie → historyjka → test → PR

| | |
|---|---|
| Historyjka | Jako **PO** chcę macierzy śledzenia, aby widzieć dla każdego wymagania, kto je realizuje, czym jest testowane i w którym PR weszło. |
| MoSCoW · rozmiar | Should · S |
| Status | **w toku** ([BA]; szkic [SLEDZENIE.md](SLEDZENIE.md)) |
| Źródło | AUDYT §1.2 (SLEDZENIE: brak powiązania wymaganie → historyjka → PR) |
| Wymagania | — |
| Zależności | WYMAGANIA.md, HISTORYJKI.md |

**Kryteria akceptacji**

1. **Given** każde FR, NFR i SEC; **Then** ma wiersz z historyjką, testem (istniejącym albo „brak — do napisania”) i PR.
2. **Given** wdrożenie historyjki; **When** odbiór [BA] (krok 6 procesu); **Then** macierz zaktualizowana w tym samym PR.

**Test do napisania:** n/d (dokument).

### US-026 — CONTRIBUTING, szablony PR / issue, CODEOWNERS

| | |
|---|---|
| Historyjka | Jako **PO** chcę opisanego procesu (role, Definition of Ready / Done, szablony, właściciele plików), aby każda zmiana zostawiała ślad i przechodziła te same kontrole. |
| MoSCoW · rozmiar | Should · S |
| Status | **w toku** (CONTRIBUTING.md, szablony i CODEOWNERS powstają w tej gałęzi) |
| Źródło | AUDYT §1.2 (brak CONTRIBUTING, szablonów, CODEOWNERS); Z-01, Z-02 |
| Wymagania | — |
| Zależności | — |

**Kryteria akceptacji**

1. **Given** nowy PR; **Then** szablon zawiera checklistę przeglądu [SEC] i odbioru [BA] oraz pole na numer historyjki.
2. **Given** `CONTRIBUTING.md`; **Then** zawiera Definition of Ready i Done oraz konwencje gałęzi i commitów.
3. **Given** `CODEOWNERS`; **Then** pliki wrażliwe (auth, ustawienia, CI) wymagają przeglądu wskazanego właściciela.

**Test do napisania:** n/d (dokument / konfiguracja repozytorium).

---

## 4. Could

Krótkie karty; pełne kryteria dopisujemy przy przejściu do Should.

| ID | Historyjka | Kryterium (Given / When / Then) | Wymagania | Rozm. | Zależności | Status | Źródło |
|---|---|---|---|---|---|---|---|
| US-027 | Jako **Administrator** chcę komendy eksportu i anonimizacji danych osoby, aby obsłużyć żądanie RODO bez ręcznej edycji bazy. | **Given** konto U z `LoginEvent` i ruchami `created_by=U`; **When** komenda `manage.py` (nazwa do ustalenia) eksportu; **Then** plik zawiera konto, zdarzenia logowania i ruchy; **When** anonimizacja; **Then** login zastąpiony, `LoginEvent` usunięte, ruchy zachowane. | SEC-038 | M | US-023, US-022; PYT-10 | do zrobienia — warunek: PYT-10 | R7 |
| US-028 | Jako **Kierownik** chcę eksportować ruchy z zakresu dat bez przeciążania serwera, aby raporty z dużej historii działały. | **Given** historia dużo większa niż limit listy (500); **When** eksport CSV z filtrem „od–do”; **Then** odpowiedź jest strumieniowana (`StreamingHttpResponse`), a zużycie pamięci nie rośnie liniowo z liczbą ruchów. | NFR-011, NFR-004; także: FR-022 | M | — | do zrobienia | T9, pitfalls/views #9 |
| US-029 | Jako **[DEV]** chcę usunąć martwy i zdublowany kod, aby importy miały jedno źródło funkcji pomocniczych. | **Given** `HUNumberingConfig.get_solo` bez użyć oraz zdublowane `_norm` / `_get`; **When** usunięte i wydzielone do wspólnego modułu; **Then** wszystkie testy zielone. | NFR-027 | S | — | do zrobienia | T10 |
| US-030 | Jako **Operator** chcę, aby zapis spisu był atomowy, aby błąd w środku nie zostawiał połowy pozycji. | **Given** zapis arkusza spisu, w którym jedna pozycja powoduje błąd; **When** zapis; **Then** żadna pozycja nie jest zmieniona (rollback) i widać komunikat. | NFR-026; także: FR-020 | S | — | do zrobienia | T11, `views.py:1051-1079` |
| US-031 | Jako **[DEV]** chcę ładować `demo.js` tylko w trybie demo, aby produkcja nie serwowała zbędnego skryptu. | **Given** `DEMO_MODE` wyłączony; **When** GET dowolnej strony; **Then** brak `<script src=…demo.js>`; **Given** `DEMO_MODE`; **Then** skrypt jest obecny. | — | S | aktualizacja `DemoScriptIncludedTests` | do zrobienia | T12 |
| US-032 | Jako **PO** chcę CHANGELOG i wersjonowania SemVer, aby widzieć historię wydań. | **Given** PR; **Then** ma wpis w `[Unreleased]`; **Given** wydanie; **Then** tag `vX.Y.Z` z datą (robi PO). | — | S | — | **w toku** (`CHANGELOG.md` w tej gałęzi; tag po stronie PO) | T13 |
| US-033 | Jako **nowa osoba w zespole** chcę aktualnej dokumentacji technicznej, aby nie opierać się na nieaktualnych liczbach i strukturze. | **Given** pitfalls/views #8, `wdrozenie.md` „Struktura”, docs/07 „Co dalej”; **Then** zgodne ze stanem kodu (liczba linii, `scanner_views.py`, `stock_import.py`, `demo.py`). | — | S | po US-017 | do zrobienia | T14 |
| US-034 | Jako **Operator** chcę komunikatu, gdy skaner nie wczyta zlecenia lub gdy wywołam akcję tylko-POST przez GET, aby nie zostać z pustym ekranem. | **Given** błąd wczytania zlecenia na skanerze; **When** ekran picking; **Then** widoczny komunikat i „Spróbuj ponownie”; **Given** GET na endpoint tylko-POST; **Then** przekierowanie z komunikatem. | — | S | — | do zrobienia | docs/03 „Ścieżki ślepe”, PROCESY L-07 |
| US-035 | Jako **PO** chcę testu użyteczności skanera z operatorami, aby sprawdzić go w warunkach hali. | **Given** 2 operatorów, telefon, rękawice, hala; **When** scenariusze rozmieszczenia i kompletacji WZ; **Then** raport (czas, błędy, uwagi) i lista poprawek w backlogu. | NFR-017, NFR-015 | M | PYT-04; scenariusz „wdrożenie” (Z-04) | do zrobienia — warunek: PYT-04 | AUDYT §1.3 pkt 7, PROCESY L-09 |
| US-036 | Jako **PO** chcę zmierzyć mierniki M-01…M-06, aby ocenić efekt produktu. | **Given** punkt odniesienia; **When** pomiar wg [WIZJA.md](WIZJA.md) §5; **Then** wartości z datą i źródłem wpisane w kolumnie „Baza”. M-02 może wymagać zapisu odstępstwa od FEFO w ruchu (nowe wymaganie — WIZJA, pytanie 4). | — | M | PYT-18 | do zrobienia — warunek: PYT-18 | AUDYT §1.3 pkt 3, Z-11 |
| US-037 | Jako **[SEC]** chcę, aby użytkownik runtime w kontenerze nie mógł zapisywać kodu aplikacji, aby ewentualne RCE nie zyskało trwałości między restartami. | **Given** działający kontener; **When** `app` zapisuje plik w `/app/warehouse/`; **Then** „Permission denied”, a healthcheck pozostaje zielony (`chown` tylko dla `staticfiles`). | SEC-030 | S | — | do zrobienia | AUDYT „poza listą”, `Dockerfile:32-40` |
| US-038 | Jako **Kierownik** chcę, aby dwa arkusze spisu założone jednocześnie nie obejmowały tej samej palety, aby spis był jednoznaczny. | **Given** PostgreSQL i dwa równoległe tworzenia arkusza obejmujące paletę P; **When** oba zatwierdzone; **Then** tylko jeden arkusz zawiera P (D-13). | NFR-026; BR-016; także: FR-020 | M | — | do zrobienia | docs/07 „Znane problemy” #2 |
| US-039 | Jako **Operator** chcę szybkiego wyszukiwania palety po numerze także przy tysiącach palet, aby lista nie zwalniała. | **Given** ponad 10 000 palet na PostgreSQL; **When** `number__iexact`; **Then** plan zapytania używa indeksu funkcyjnego `Upper("number")`; migracja odwracalna. | NFR-002 | S | decyzja PO o uruchomieniu (MODEL_DANYCH) | do zrobienia — gdy lista HU zwolni | docs/07 „Znane problemy” #3 |
| US-040 | Jako **PO** chcę zmierzyć czas odpowiedzi kluczowych ekranów przy skali docelowej, aby zdecydować o wymaganiu NFR-002. | **Given** baza o skali 10 × NFR-001; **When** pomiar ekranów i endpointów skanera; **Then** raport p95; PO ustala próg. | NFR-001, NFR-002 | M | PYT-01, PYT-03 | do zrobienia — warunek: PYT-03 | AUDYT §1.3 pkt 1 |
| US-041 | Jako **Operator** chcę sam zmienić swoje hasło, aby nie znał go Administrator. | **Given** zalogowany użytkownik; **When** zmiana hasła z podaniem starego; **Then** nowe hasło przechodzi walidatory (SEC-002) i zostaje zapisane w audit logu; **Given** konto demo; **Then** zmiana zablokowana (SEC-010). Odzyskiwanie przez e-mail — osobna decyzja (RODO). | SEC-002, SEC-010 | M | US-008, US-022; PYT-21 | do zrobienia — warunek: PYT-21 | PROCESY L-01, Z-16 |
| US-042 | Jako **Kierownik** chcę, aby otwarty arkusz spisu sygnalizował lub blokował ruchy na objętych paletach, aby spis nie rozjechał się ze stanem. | **Given** otwarty arkusz z paletą P; **When** Operator pobiera z P lub koryguje P; **Then** ostrzeżenie albo odmowa (wariant wg PYT-21); **Given** arkusz zamknięty; **Then** ruchy działają. | BR-007; także: FR-020 | M | PYT-21 | do zrobienia — warunek: PYT-21 (nowe wymaganie) | PROCESY L-02, Z-13, D-07 |
| US-043 | Jako **[BA]** chcę uzupełnić brakujące testy wymagań oznaczonych jako spełnione, aby każde wymaganie miało co najmniej jeden test w macierzy śledzenia. | **Given** luki z [SLEDZENIE.md](SLEDZENIE.md) §7 (FR-007 ruch PRZESUNIĘCIE, FR-009 odmowa alokacji pustej palety, SEC-005 cookie i bezczynność sesji, SEC-013 escapowanie, SEC-014 CSRF z `enforce_csrf_checks`, SEC-016 eksport XLSX, SEC-018 limit 5 MB, SEC-023 nagłówki); **When** testy dopisane; **Then** każde wymaganie `spełnione` ma w macierzy nazwę istniejącego testu, a luki są zamknięte. | FR-007, FR-009, SEC-005, SEC-013, SEC-014, SEC-016, SEC-018, SEC-023; NFR-007, NFR-012 | M | — | do zrobienia | AUDYT §2.3 (najsłabiej pokryte: `exports.py`, `views.py`, `config/log.py`); SLEDZENIE §7 |

---

## 5. Won't (na teraz) — do potwierdzenia przez PO

Świadomie poza zakresem (docs/01, docs/07). Nie piszemy kryteriów, dopóki PO nie zmieni decyzji
(PYT-17). Każda pozycja ma warunek ponownego rozpatrzenia.

| ID | Historyjka (gdyby weszła) | Uzasadnienie / źródło | Warunek powrotu do backlogu | Status |
|---|---|---|---|---|
| US-044 | Jako Kierownik chcę wymiany danych z ERP, aby nie przepisywać zamówień. | firma nie ma ERP; dane wchodzą z plików (docs/01, D-04) | firma wdraża ERP | odroczone — do potwierdzenia (PYT-17) |
| US-045 | Jako Operator chcę przyjmować zwroty i anulować WZ, aby poprawiać pomyłkowe wydania inaczej niż korektą. | w magazynie zwrotów nie ma (docs/01, BR-010); PROCESY L-08 | pojawia się proces zwrotów | odroczone — do potwierdzenia (PYT-17) |
| US-046 | Jako Kierownik chcę blokady palet po terminie ważności, aby przeterminowany towar nie wyszedł z magazynu. | decyzja zakresu — FEFO wydaje je jako pierwsze (docs/01, docs/07) | wymóg jakościowy lub prawny | odroczone — do potwierdzenia (PYT-17) |
| US-047 | Jako Kierownik chcę rezerwacji stanu pod otwarte WZ, aby dostępność nie zmieniała się między utworzeniem a realizacją. | przy tej skali dostępność liczona w chwili realizacji wystarcza (docs/01) | wzrost liczby równoległych WZ | odroczone — do potwierdzenia (PYT-17) |
| US-048 | Jako Kierownik chcę wielu magazynów, stref i ścieżek kompletacji, aby obsłużyć większy obiekt. | jeden mały magazyn (docs/01); wymagałoby separacji danych (Z-06, pitfalls/auth #4) | drugi magazyn lub firma | odroczone — do potwierdzenia (PYT-17) |
| US-049 | Jako Kierownik chcę atrybutów logistycznych materiału (wymiary, waga, EAN), aby planować miejsce i skanować EAN. | brak master daty (docs/07, D-02) | integracja z master daną | odroczone — do potwierdzenia (PYT-17) |

---

## 6. Podsumowanie

### 6.1 Liczba historyjek

| MoSCoW | Liczba | Identyfikatory |
|---|---|---|
| Must | 6 | US-001…US-006 |
| Should | 20 | US-007…US-026 |
| Could | 17 | US-027…US-043 |
| Won't (na teraz) | 6 | US-044…US-049 |
| **Razem** | **49** | |

### 6.2 Rozmiar i status

| MoSCoW | S | M | L | do zrobienia | do zrobienia — czeka na decyzję PO | w toku (całość lub część) | odroczone |
|---|---|---|---|---|---|---|---|
| Must | 2 | 4 | 0 | 5 | 0 | 1 | 0 |
| Should | 6 | 11 | 3 | 10 | 4 | 6 | 0 |
| Could | 8 | 9 | 0 | 9 | 7 | 1 | 0 |
| Won't | 0 | 0 | 0 | 0 | 0 | 0 | 6 |
| **Razem** | **16** | **24** | **3** | **24** | **11** | **8** | **6** |

### 6.3 Pokrycie audytu

| Pozycja audytu | Historyjka |
|---|---|
| R1 | US-001 |
| R2 | US-003 |
| R3 | US-002 |
| R4, T1 | US-004 |
| R5 | US-005 (limiter, sesje), US-015 (paginacja, etykiety), US-016 (demo) |
| R6 | US-008, US-009, US-010 |
| R7 | US-005, US-023, US-027 |
| R8 | US-011 |
| R9 | US-012 |
| R10 | US-006, US-020 |
| T2, T3 | US-017, US-018 |
| T4, T5, T6 | US-019 |
| T7 | US-020 |
| T8 | US-009 |
| T9, T10, T11, T12 | US-028, US-029, US-030, US-031 |
| T13, T14 | US-032, US-033 |
| T15 | US-021 |
| T16 | US-013 (oraz US-002) |
| „poza listą” (IP, Content-Disposition, `/app` zapisywalny, ADMINS) | US-014, US-013, US-037, US-021 |

---

## 7. Kolejność realizacji — propozycja pierwszych 3 iteracji

Zasady: Z-07 (R1–R4, R7, R10 przed nowymi funkcjami); w iteracji najpierw wysoka waga, potem
zależności; brak historii prędkości, więc nie podajemy pojemności — iteracja to zestaw spójny do
przeglądu [SEC] i odbioru [BA]. Przed startem każdej historyjki: Definition of Ready
([CONTRIBUTING.md](../../CONTRIBUTING.md) §3) — w szczególności odpowiedzi na wskazane PYT.

| Iteracja | Cel | Historyjki | Warunki startu / uwagi |
|---|---|---|---|
| **1 — zamknąć ryzyka wysokie** | R1–R4 | US-001 (S), US-002 (S), US-003 (M), US-004 (M) | PYT-02, PYT-05, PYT-06 odpowiedziane. US-003 dotyka `ci.yml` (klucz smoke-testu ≥ 50 znaków) — uzgodnić z ADR-0001/CI. Równolegle (dokumenty, w toku): US-006 (CI i SECURITY.md), US-023, US-024, US-025, US-026 |
| **2 — RODO, demo, siatka bezpieczeństwa** | R7, R5 (część), R10, R6 (szybkie) | US-005 (M), US-006 (dokończenie), US-007 (M), US-008 (S), US-013 (M), US-014 (S) | PYT-09, PYT-13, PYT-22. US-007 przed US-017. US-013 po US-002 (wspólne stałe) |
| **3 — uwierzytelnianie, odporność, dług** | R6, R5 (reszta), T3, T15 | US-009 (M), US-015 (M), US-016 (M), US-018 (M), US-021 (M), US-022 (M) | PYT-07, PYT-15, PYT-22; US-016 po DEC-6. Decyzje PO dla US-010, US-011, US-012 (PYT-08, PYT-16) |
| po 3 | porządkowanie i decyzje | US-017 (L, po US-007), US-020 (M), US-010 (L), US-011 (L), US-012 (M), następnie Could | US-017 po zakończeniu historyjek zmieniających `views.py` (US-001…US-005, US-013, US-015) |

## Historia zmian

| Wersja | Data | Zmiana |
|---|---|---|
| 0.1 | 2026-10-16 | Pierwszy szkic backlogu: 49 historyjek (Must 6, Should 20, Could 17, Won't 6), 3 iteracje. |

### US-050 — Rezerwacja zakresu numerów HU jednym zapisem (z przeglądu [DB] US-002)

| | |
|---|---|
| Historyjka | Jako **Operator** chcę, aby duży import nie wstrzymywał innych przyjęć na czas całego pliku, aby praca na hali nie stała przy imporcie. |
| MoSCoW · rozmiar | Could · M |
| Status | do zrobienia |
| Źródło | przegląd `db-reviewer` US-002: blokada `HUNumberingConfig` trwa do końca transakcji importu (do 2 000 palet, ~10 tys. zapytań) |
| Wymagania | NFR-003; SEC-021 |

**Kryteria akceptacji**

1. **Given** import 2 000 palet; **When** trwa zapis; **Then** blokada licznika jest brana raz (rezerwacja `next_number += N`), HU i ruchy zapisywane `bulk_create`, liczba zapytań stała względem N (`assertNumQueries`).
2. **Given** dwa równoległe przyjęcia; **When** jedno to import; **Then** numery HU nadal unikalne i ciągłe (test PostgreSQL jak `tests_concurrency_pg.py`).

### US-051 — Indeks na `LoginEvent.created_at` (z przeglądu [DB] US-005)

| | |
|---|---|
| Historyjka | Jako **administrator infrastruktury (ST-05)** chcę, aby codzienne usuwanie starego dziennika logowań i lista dziennika nie skanowały całej tabeli, aby nie spowalniały startu kontenera przy dużym dzienniku. |
| MoSCoW · rozmiar | Could · S |
| Status | do zrobienia |
| Źródło | przegląd `db-reviewer` US-005: `purge_login_events` (`created_at__lt`) i `login_log` (`-created_at`) bez indeksu; dziś tabela mała (tysiące wierszy) |
| Wymagania | SEC-036; NFR-003 |
| Zależności | nowa migracja — wdrożenie wymaga zgody PO (§8: migracje na danych produkcyjnych) |

**Kryteria akceptacji**

1. **Given** `LoginEvent.Meta.indexes` z `created_at`; **When** `makemigrations --check`; **Then** migracja `AddIndex` w repo, odwracalna.
2. **Given** PostgreSQL; **When** `EXPLAIN` zapytania `purge_login_events`; **Then** plan używa indeksu.

