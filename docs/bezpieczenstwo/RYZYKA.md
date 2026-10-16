# Rejestr ryzyk bezpieczeństwa

| | |
|---|---|
| Wersja | 0.1 |
| Data | 2026-10-16 |
| Status | szkic — do akceptacji Product Ownera |
| Właściciel | [SEC] |

Rejestr przenosi ryzyka R1–R10 i punkty „poza listą” z [`docs/AUDYT.md`](../AUDYT.md) §3.3
oraz zagrożenia z [`THREAT_MODEL.md`](THREAT_MODEL.md) (TM-xx) do jednej listy z oceną,
decyzją, właścicielem i terminem przeglądu. Opisów scenariuszy nie powtarzamy — patrz
audyt. Historyjki: US-001 = R1, US-002 = R3, US-003 = R2, US-004 = T1/R4, US-005 = R7 + R5
(retencja, `clearsessions`, limiter `/demo/`), US-006 = R10. „Should” oznacza pozycję
backlogu bez nadanego jeszcze numeru US.

## 1. Skala oceny

Ocena = wpływ × prawdopodobieństwo. Domyślnie oceniamy **najgorszy kontekst** (publiczne
demo, Z-05); gdy wdrożenie u klienta zmienia obraz, jest to podane w uwagach.

| Poziom | Wpływ | Prawdopodobieństwo |
|---|---|---|
| 1 | niewielki: niedostępność lub zaśmiecenie demo, kosmetyka, brak utraty danych | mało prawdopodobne: wymaga uprzywilejowanego insidera lub nietypowej konfiguracji |
| 2 | umiarkowany: przerwa w pracy magazynu, ograniczony wyciek danych wewnętrznych lub osobowych | możliwe: scenariusz opisany w audycie, wymaga wiedzy lub celowego działania |
| 3 | poważny: przejęcie konta administracyjnego, utrata lub ujawnienie danych klienta, naruszenie RODO | prawdopodobne: trywialne, anonimowe, powtarzalne (np. przez publiczny link do demo) |

| Ocena (iloczyn) | Klasa | Reakcja |
|---|---|---|
| ≥ 6 (6, 9) | **wysokie (W)** | mitygacja przed nowymi funkcjami (Z-07); przegląd co miesiąc |
| 3–4 | **średnie (Ś)** | w backlogu z priorytetem; przegląd co kwartał |
| ≤ 2 | **niskie (N)** | obserwacja; przegląd co kwartał |

## 2. Rejestr (RR-xx)

Właściciel to rola odpowiedzialna za mitygację: [DEV], [SEC], PO (Product Owner),
Admin. infrastruktury (ST-05 z [`INTERESARIUSZE.md`](../analiza/INTERESARIUSZE.md)).
Decyzja: **otwarte**, **mitygacja w US-xxx**, **do akceptacji PO**, **zaakceptowane**.

| ID | Ryzyko | Źródło | Wpływ | Praw. | Ocena | Decyzja | Właściciel | Przegląd | Uwagi |
|---|---|---|---|---|---|---|---|---|---|
| RR-01 | Konto z rolą Administrator może zmienić hasło i dezaktywować konto superusera, przejmując `/admin/` i ślad audytowy. | R1 · TM-35 | 3 | 2 | 6 (W) | zmitygowane w US-001 (#23) — do weryfikacji po wdrożeniu | [DEV] | 2026-11-15 | potwierdzone testem; poprawka to jeden warunek w `user_edit`; w demo skutek to lockout |
| RR-02 | Wdrożenie z `docker-compose.yml` startuje z publicznie znanymi sekretami (`admin` / `admin`, domyślny klucz i hasło bazy, zaślepki z `.env.docker.example`). | R2a · TM-50 | 3 | 2 | 6 (W) | zmitygowane w US-003 (#23, do akceptacji PO) | [DEV] | 2026-11-15 | oba compose mają `${VAR:?}`, `prod.py` odrzuca klucze < 50 znaków i zaślepki; sam klucz nie pozwala podrobić sesji (są w bazie), wektorem jest konto `admin` |
| RR-03 | `seed_demo` uruchomiony bez `DEMO_MODE` zakłada `demo_operator` i `demo_podglad` z hasłem `demo1234` na instancji prywatnej. | R2b · TM-49 | 3 | 2 | 6 (W) | zmitygowane w US-003 (#23, do akceptacji PO) | [DEV] | 2026-11-15 | `seed_demo` odmawia bez `DEMO_MODE` |
| RR-04 | Jedno przyjęcie lub jeden wiersz importu z milionami palet zajmuje workery i blokuje numerację HU wszystkim. | R3 · TM-12, TM-26 | 2 | 3 | 6 (W) | zmitygowane w US-002 (#23) — do weryfikacji po wdrożeniu | [DEV] | 2026-11-15 | wysokie przez demo (anonim); u klienta Ś (2 × 2 = 4) |
| RR-05 | Spreparowany lub uszkodzony XLSX wyczerpuje pamięć workera (bomba dekompresyjna) albo kończy się błędem 500. | R4, T1 · TM-24, TM-25 | 2 | 3 | 6 (W) | zmitygowane w US-004 (#23, do akceptacji PO) | [DEV] | 2026-11-15 | sygnatura ZIP, limit 50 MB po rozpakowaniu, 10 000 wierszy, `defusedxml`; uszkodzony plik daje komunikat |
| RR-06 | Brak limitera na `/demo/` i `/login/demo/` oraz brak `clearsessions` rozdyma `django_session` i `LoginEvent` i zaśmieca dziennik. | R5a · TM-44 | 2 | 2 | 4 (Ś) | zmitygowane w US-005 (#23, do akceptacji PO) | [DEV] | 2027-01-15 | limiter 10 / 300 s na IP (per proces), `clearsessions` codziennie |
| RR-07 | Listy, PDF etykiet lokalizacji, eksporty i importy bez limitów pozwalają zająć workera lub rozdąć bazę demo (wystarczy rola Podgląd lub Operator). | R5b, T9 · TM-13, TM-30, TM-31, TM-45, TM-47 | 2 | 2 | 4 (Ś) | zmitygowane — US-015 (paginacja, limit etykiet), US-016 (limit obiektów i zapisów w demo), #23 | [DEV] | 2027-01-15 | ryzyko resztkowe: wspólny NAT dzieli limit zapisów; eksporty — TM-30 |
| RR-08 | „Przywróć dane demo” dostępne anonimowo wykonuje w żądaniu HTTP `LOCK TABLE … EXCLUSIVE` na 9 tabelach (do 3 resetów na minutę). | R5c · TM-46 | 1 | 3 | 3 (Ś) | zmitygowane — US-016, #23 (przycisk i trasa usunięte; reset tylko Scheduled Task) | [DEV] | 2027-01-15 | reset wyłącznie ze Scheduled Task; blokada trwa 1–2 s |
| RR-09 | Świadome wyjątki demo (login na GET, jawne hasło, współdzielone konta, publiczny Operator) dopuszczają login CSRF i brak rozliczalności. | R5d · TM-15, TM-42, TM-43 | 1 | 3 | 3 (Ś) | do akceptacji PO (W-1) | PO | 2026-11-15 | dane fikcyjne; warunki w W-1 |
| RR-10 | Uwierzytelnianie poniżej minimum: limit per proces i per IP, brak blokady per konto, brak 2FA, hasła od 8 znaków, PBKDF2, `/admin/` z internetu. | R6 · TM-01, TM-02, TM-05, TM-08, TM-36 | 3 | 1 | 3 (Ś) | otwarte (Should; DEC-4); do akceptacji PO (W-2, W-4) | [DEV] | 2027-01-15 | po wdrożeniu u klienta z realnymi kontami P = 2, czyli 6 (W) |
| RR-11 | Dziennik logowań (IP, user-agent, dowolny wpisany tekst) i IP odwiedzających demo są przechowywane bezterminowo, bez podstawy i informacji. | R7 · TM-07, TM-39, TM-48, TM-59 | 2 | 2 | 4 (Ś) | częściowo zmitygowane w US-005 (#23) — retencja 90 dni i brak IP/UA w demo; zostaje klauzula informacyjna (US-023) | [DEV] | 2027-01-15 | retencja 90 dni (Z-09, decyzja PO), klauzula informacyjna — [`RODO.md`](RODO.md) |
| RR-12 | Brak CSP i Permissions-Policy oraz krótki HSTS zwiększają skutki ewentualnego XSS lub downgrade'u. | R8 · TM-03, TM-16 | 3 | 1 | 3 (Ś) | zmitygowane w US-011 (#23) — CSP z nonce, Permissions-Policy; HSTS 30 dni bez preload | [DEV] | 2027-01-15 | XSS dziś nie znaleziono; `django-csp` wymaga usunięcia inline handlerów |
| RR-13 | Backup na tym samym hoście, nieszyfrowany, bez off-site i testu odtworzenia: awaria dysku lub błąd operatora niszczy bazę i kopie naraz. | R9 · TM-55, TM-56 | 3 | 1 | 3 (Ś) | otwarte (Should); do akceptacji PO (W-3) | zmitygowane w kodzie (US-012, #23) — aktywne po konfiguracji off-site; ćwiczenie na kopii produkcyjnej otwarte | 2027-01-15 | dla demo dane fikcyjne; u klienta P = 2, czyli 6 (W) — wyjątek W-3 wygasa przed pierwszymi danymi produkcyjnymi |
| RR-14 | Łańcuch dostaw i CI mają kontrole doradcze (skany miesięczne, `curl … \| sh`, akcje po wersji głównej, brak Dependabota i locka). | R10 · TM-51, TM-52 | 2 | 2 | 4 (Ś) | mitygacja w US-006 | [DEV] | 2027-01-15 | zmiany CI są w toku w drzewie roboczym — zweryfikować po scaleniu |
| RR-15 | Wartości spoza zakresu i zbyt długie kody (T16) dają `DataError` lub `OverflowError`, czyli HTTP 500 i wycofanie całego importu. | T16 · TM-21, TM-27 | 1 | 2 | 2 (N) | otwarte (Should) | [DEV] | 2027-01-15 | `max_value`, `max_length`, obsługa `OverflowError` |
| RR-16 | Kod lokalizacji lub numer HU z `"` albo CR/LF psuje nagłówek `Content-Disposition` i daje 500 przy pobraniu etykiety. | AUDYT §3.3 „poza listą” · TM-32 | 1 | 2 | 2 (N) | otwarte (Should) | [DEV] | 2027-01-15 | `content_disposition_header()` |
| RR-17 | `_client_ip` nie waliduje wyniku — błędna `TRUSTED_PROXY_COUNT` daje fałszywe IP w dzienniku, obejście limitera lub 500 w sygnale logowania. | AUDYT §3.3 „poza listą” · TM-09 | 2 | 1 | 2 (N) | otwarte | [DEV] | 2027-01-15 | `ipaddress.ip_address()` z fallbackiem na `REMOTE_ADDR` |
| RR-18 | Kod aplikacji w kontenerze jest zapisywalny przez użytkownika runtime, więc RCE w parserze zyskałoby trwałość między restartami. | AUDYT §3.3 „poza listą” · TM-54 | 2 | 1 | 2 (N) | otwarte | [DEV] | 2027-01-15 | `/app` własności root, `chown` tylko `staticfiles` |
| RR-19 | Brak alertów o błędach 500 i restartach wydłuża czas wykrycia awarii lub ataku. | T15 · TM-58 | 2 | 2 | 4 (Ś) | otwarte (Should) | [DEV] | 2027-01-15 | Sentry/GlitchTip, `mail_admins` albo alert w Coolify |
| RR-20 | Publiczne repozytorium zawiera szczegółowe scenariusze niezałatanych luk (R1–R4 z parametrami żądań), które ułatwiają atak na działające demo. | meta: AUDYT §3.3, DA-02 | 2 | 2 | 4 (Ś) | do akceptacji PO | PO | 2026-11-15 | nowe względem audytu; opcje: scalić dokumenty do `main` po US-001…US-004 albo skrócić scenariusze |
| RR-21 | Przejęcie konta GitHub autora lub brak wymuszonego review pozwala wdrożyć złośliwy kod na produkcję (`main` = auto-deploy). | TM-53 | 3 | 1 | 3 (Ś) | do akceptacji PO | PO | 2026-11-15 | ustawienia GitHub poza repo: branch protection, 2FA, review — do potwierdzenia |
| RR-22 | Użytkownik nie może samodzielnie zmienić hasła — zna je Administrator, a hasło początkowe nie wygasa. | TM-38 · Z-16 | 2 | 2 | 4 (Ś) | do akceptacji PO | PO | 2027-01-15 | ASVS 2.1.5; propozycja: `PasswordChangeView` i wymuszenie zmiany przy 1. logowaniu |
| RR-23 | Superuser może zmieniać i usuwać ruchy magazynowe oraz usuwać wpisy dziennika w `/admin/`, niszcząc ślad audytowy. | TM-37 · R1 | 2 | 1 | 2 (N) | do akceptacji PO | PO | 2027-01-15 | `StockMovementAdmin` tylko do odczytu; usuwanie dziennika komendą retencji |
| RR-24 | Brak testu macierzowego rola × trasa: nowy widok bez dekoratora byłby publiczny i nikt by tego nie zauważył. | TM-10 · AUDYT Zał. A | 3 | 1 | 3 (Ś) | otwarte (Should) | [DEV] | 2027-01-15 | test iterujący po `urlpatterns` |
| RR-25 | Eksport ruchów z kolumną „Kto” jest dostępny dla każdej roli, w tym Podglądu (minimalizacja danych osobowych). | TM-29 | 1 | 2 | 2 (N) | do akceptacji PO | PO | 2027-01-15 | pytanie w [`RODO.md`](RODO.md) §10 |
| RR-26 | Sekrety w env są widoczne w panelu Coolify i przez `docker inspect`, hasło początkowe superusera zostaje w środowisku, brak procedury rotacji. | TM-57 | 3 | 1 | 3 (Ś) | otwarte | Admin. infrastruktury | 2027-01-15 | procedura rotacji i 2FA do Coolify w RUNBOOK |
| RR-27 | Zamknięcie WZ w `api_pick` poza warstwą usług i bez blokady może zostawić dokument w złym statusie przy równoległych pobraniach. | T3 · TM-22 | 2 | 1 | 2 (N) | otwarte (backlog DEV) | [DEV] | 2027-01-15 | przenieść do `services.py` |
| RR-28 | Luki rozliczalności i uprawnień: brak śladu pobrań eksportu i zmian kont, domyślna rola Operator w formularzu nowego konta. | TM-34, TM-40, TM-41 | 1 | 2 | 2 (N) | otwarte (Could) | [DEV] | 2027-01-15 | ASVS 7.1.3, 4.1.3 |
| RR-29 | Odpowiedzi bez `Cache-Control: no-store` pozostawiają dane w cache przeglądarki na współdzielonym terminalu. | TM-18 | 1 | 2 | 2 (N) | otwarte (Could) | [DEV] | 2027-01-15 | ASVS 8.2.1 |
| RR-30 | Ryzyka resztkowe z założeń: insider z uprawnieniami Operatora, brak kontroli obiektowej (jeden magazyn), pliki poza aplikacją, brak TLS web ↔ db. | TM-14, TM-15, TM-17, TM-33, TM-60 | 1 | 2 | 2 (N) | do akceptacji PO | PO | 2027-01-15 | TM-17 przestaje obowiązywać przy drugim magazynie lub firmie (Z-06) |

### Pokrycie audytu

| Ryzyko audytu | Wiersze rejestru |
|---|---|
| R1 | RR-01 (+ RR-23) |
| R2 | RR-02, RR-03 |
| R3 | RR-04 |
| R4 (T1) | RR-05 |
| R5 | RR-06, RR-07, RR-08, RR-09 |
| R6 | RR-10 |
| R7 | RR-11 |
| R8 | RR-12 |
| R9 | RR-13 |
| R10 | RR-14 |
| „poza listą” §3.3 | RR-15 (T16), RR-16, RR-17, RR-18, RR-19 (T15) |

### Podsumowanie

30 ryzyk: **5 wysokich** (RR-01…RR-05), **15 średnich**, **10 niskich**. Decyzje: 8 z
mitygacją w US-001…US-006, 15 otwartych (Should/Could lub procedura), 7 do akceptacji PO.
Wszystkie wysokie ryzyka mają przypisaną historyjkę; terminy przeglądu: 2026-11-15
(wysokie, wyjątki, RR-09, RR-20, RR-21) i 2027-01-15 (pozostałe).

| Wpływ \ Prawdopodobieństwo | 1 — mało prawdopodobne | 2 — możliwe | 3 — prawdopodobne |
|---|---|---|---|
| **3 — poważny** | RR-10, RR-12, RR-13, RR-21, RR-24, RR-26 | **RR-01, RR-02, RR-03** | — |
| **2 — umiarkowany** | RR-17, RR-18, RR-23, RR-27 | RR-06, RR-07, RR-11, RR-14, RR-19, RR-20, RR-22 | **RR-04, RR-05** |
| **1 — niewielki** | — | RR-15, RR-16, RR-25, RR-28, RR-29, RR-30 | RR-08, RR-09 |

Pogrubione komórki to ryzyka wysokie (≥ 6). Dwa z nich (RR-04, RR-05) są wysokie wyłącznie
przez anonimowy dostęp do demo (Z-05); RR-10 i RR-13 wzrosną do 6 w chwili wdrożenia u klienta.

## 3. Lista wyjątków

Wyjątek to świadoma zgoda na ryzyko, którego nie mitygujemy teraz. Każdy ma uzasadnienie,
warunki (naruszenie warunku unieważnia wyjątek), datę przeglądu i status. **Wszystkie
cztery czekają na akceptację PO** (zgodnie z Z-14: PO w scenariuszu portfolio, administrator
danych we wdrożeniu); do czasu akceptacji traktujemy je jako ryzyka otwarte.

| ID | Wyjątek | Uzasadnienie | Warunki | Data przeglądu | Status |
|---|---|---|---|---|---|
| W-1 | Publiczne demo z rolą Operator dla anonimowych i logowanie na `GET /demo/` (Z-05); jawne hasło kont demo | demo to główny sposób pokazania aplikacji (README, CV, YouTube); dane fikcyjne i odtwarzalne z `seed_demo`; niedostępność to ryzyko wizerunkowe, nie utrata danych | `DEMO_MODE=1` tylko na osobnej instancji z osobną bazą i sekretami; `/admin/` wyłączony (`config/urls.py:48-50`); reset co 24 h i przycisk; wdrożone US-002, US-004 i US-005 (limity i limiter) — do tego czasu wyjątek tymczasowy; brak danych prawdziwych ([`KLASYFIKACJA_DANYCH.md`](KLASYFIKACJA_DANYCH.md) §4); informacja o zbieraniu IP ([`RODO.md`](RODO.md)) | 2026-11-15 oraz po scaleniu US-002, US-004, US-005 | do akceptacji PO |
| W-2 | Brak 2FA i `/admin/` dostępny z internetu do czasu wdrożenia u klienta (R6) | aplikacja nie jest wdrożona u klienta; jedyne konto z dostępem do `/admin/` to superuser właściciela; koszt 2FA uzasadniony przy realnych danych | losowe hasło superusera ≥ 16 znaków; limit logowań aktywny; brak innych superuserów; `/admin/` wyłączony w demo; wygasa przed pierwszym wdrożeniem u klienta (wtedy 2FA i allowlista IP) | 2026-11-15 lub przed pierwszym wdrożeniem | do akceptacji PO |
| W-3 | Backup tylko lokalny, nieszyfrowany, bez testu odtworzenia do czasu wdrożenia (R9) | instancje demo i dev mają dane fikcyjne, odtwarzalne z `seed_demo`; brak danych produkcyjnych | stosowany wyłącznie do instancji bez danych prawdziwych; wygasa przed wprowadzeniem pierwszych danych produkcyjnych (wtedy kopia off-site szyfrowana, test odtworzenia, alert) | 2026-11-15 lub przed pierwszymi danymi produkcyjnymi | do akceptacji PO |
| W-4 | Limit logowań per proces gunicorna (LocMem) zamiast wspólnego cache | 3 workery dają ok. 30 prób / 5 min / IP — akceptowalne przy silnych hasłach; wspólny cache (baza lub Redis) to dodatkowa zależność ([`docs/07`](../07-ograniczenia.md)) | `GUNICORN_WORKERS` ≤ 3; poprawna `DJANGO_TRUSTED_PROXY_COUNT`; hasła ≥ 12 znaków po zmianie TM-02; wygasa przy wdrożeniu u klienta lub zwiększeniu liczby workerów | 2027-01-15 | do akceptacji PO |

## 4. Proces

| Zasada | Treść |
|---|---|
| Kto dodaje | każdy członek zespołu (BA, DEV, SEC) i PO; [SEC] prowadzi rejestr, nadaje identyfikatory i ocenia wpływ oraz prawdopodobieństwo; wpis musi wskazywać źródło (audyt, TM-xx, review, incydent) |
| Co wpisujemy | każde ryzyko o ocenie ≥ 3 oraz każde zgłoszenie `security-reviewera`, którego nie naprawiono w tym samym PR; odrzucone zgłoszenie — jedno zdanie dlaczego ([`CLAUDE.md`](../../CLAUDE.md)) |
| Przegląd okresowy | co 3 miesiące (najbliższy pełny: 2027-01-15); wysokie ryzyka i wyjątki W-1…W-3: 2026-11-15 |
| Przegląd przy zmianie | każdy PR dotykający uwierzytelniania i ról (`roles.py`, `signals.py`, `demo.py`, formularze kont), uploadu i importów, wdrożenia (`Dockerfile`, `entrypoint.sh`, pliki compose, workflows, `config/settings/`) — autor PR i [SEC] sprawdzają, czy RR lub TM wymaga aktualizacji |
| Zamknięcie | tylko z odwołaniem do testu albo zmiany w kodzie/konfiguracji; wiersz zostaje w rejestrze ze statusem „zamknięte” i datą |
| Akceptacja | wyłącznie wpisem w Liście wyjątków z datą przeglądu; PO (scenariusz portfolio) lub administrator danych (wdrożenie) — Z-14; brak akceptacji „po cichu” |
| Prawo weta [SEC] | [SEC] wstrzymuje merge PR, który (1) wprowadza ryzyko ≥ 6 bez mitygacji i bez wpisu w rejestrze, (2) zmienia uwierzytelnianie, upload lub wdrożenie bez przeglądu `security-reviewera`, (3) dodaje wyjątek bez daty przeglądu. Weto uchyla wyłącznie PO decyzją zapisaną w rejestrze. Zasada do potwierdzenia przez PO (propozycja Z-20) |
| Eskalacja | ryzyko ≥ 6 bez właściciela lub z przeterminowanym przeglądem trafia do PO w raporcie sesji |
