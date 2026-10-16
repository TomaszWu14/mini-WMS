# Checklista OWASP ASVS 4.0.3

| | |
|---|---|
| Wersja | 0.1 |
| Data | 2026-10-16 |
| Status | szkic — do akceptacji Product Ownera |
| Właściciel | [SEC] |

## 1. Poziom docelowy i uzasadnienie

**Cel: ASVS 4.0.3 poziom 1 dla całej aplikacji oraz wybrane kontrole poziomu 2 dla
uwierzytelniania i sesji** (V2, V3, a z V7/V8/V12/V14 te, które dotyczą danych osobowych,
backupu i plików).

| Dlaczego | Treść |
|---|---|
| L1 jako baza | mała aplikacja wewnętrzna: ewidencja magazynowa, dane osobowe ograniczone do loginu, IP i znaczników „kto”; brak płatności i danych szczególnych |
| L2 dla V2/V3 | przejęcie konta Administratora oznacza pełny dostęp do danych i śladu audytowego (R1, R6); hasła i sesje to najtańszy wektor ataku, a koszt kontroli niski |
| Publiczne demo | anonimowy Operator (Z-05) i działające demo w internecie podnoszą wagę kontroli dostępności i walidacji wejścia (R3, R4, R5), choć dane są fikcyjne |
| Nie L3 | brak danych krytycznych (medycznych, finansowych) — poziom 3 byłby nieproporcjonalny |

Wymagania zapisano skrótem własnymi słowami; wiążący jest oficjalny tekst ASVS 4.0.3.
Numery i treść należy zweryfikować z oficjalnym dokumentem przed użyciem checklisty jako
dowodu w audycie zewnętrznym. Wiersz może łączyć kilka numerów ASVS dotyczących tej samej
kontroli, więc 48 wierszy obejmuje więcej niż 48 numerów. Rozdziały V1 (architektura),
V6 (kryptografia) i V11 (logika biznesowa) pominięto jako poza zakresem wersji 0.1.

Legenda statusu: ✅ spełnione · ⚠️ częściowo · ❌ brak · n/d nie dotyczy.
Numery TM-xx: [`THREAT_MODEL.md`](THREAT_MODEL.md); R/T: [`docs/AUDYT.md`](../AUDYT.md);
RR-xx: [`RYZYKA.md`](RYZYKA.md); W-x: wyjątki w [`RYZYKA.md`](RYZYKA.md) §3.
Numery linii dotyczą stanu `main` @ `f5be158` z audytu; zmiany wykonywane równolegle (US-006) nie są uwzględnione.

## 2. Checklista

### V2 — Uwierzytelnianie

| ASVS | L | Wymaganie | Status | Dowód | Działanie |
|---|---|---|---|---|---|
| 2.1.1, 2.1.7 | 1 | Hasła mają co najmniej 12 znaków i są sprawdzane względem znanych list wycieków | ⚠️ | `base.py:145-152`: 4 walidatory Django, min. 8 znaków, lista popularnych haseł; TM-02 | R6 (Should) |
| 2.1.5, 2.1.6, 2.3.1 | 1 | Użytkownik sam zmienia hasło (podając obecne); hasło początkowe nie staje się trwałe | ❌ | brak widoku zmiany hasła, hasło ustawia Administrator (`views.py:1296-1335`); TM-38, Z-16 | RR-22 (decyzja PO) |
| 2.2.1 | 1 | Skuteczna ochrona przed zgadywaniem haseł i credential stuffing | ⚠️ | limit 10 prób / 5 min / IP per proces (`demo.py:32-75`), brak blokady per konto; TM-01, W-4 | R6 (Should) |
| 2.4.1, 2.4.3 | 2 | Hasła solone i hashowane zatwierdzonym algorytmem (PBKDF2, ≥ 100 tys. iteracji) | ✅ | domyślny `PASSWORD_HASHERS` Django 5.2 (PBKDF2-SHA256, iteracje ≫ 100 tys.); MD5 tylko w `config/settings/test.py` | — (argon2 od US-008, #23; stare hashe PBKDF2 podnoszone przy logowaniu) |
| 2.5.4 | 1 | Brak kont współdzielonych i domyślnych (`admin`, `root`) | ⚠️ | domyślne `admin` / `admin` w `docker-compose.yml:53` (R2); jawne konta demo (W-1) | US-003 |
| 2.10.4 | 2 | Hasła i klucze nie leżą w kodzie źródłowym | ⚠️ | sekrety w env (`prod.py`, `COOLIFY.md` §6); wartości domyślne w `docker-compose.yml:18,53,65` (R2) | US-003 |

### V3 — Zarządzanie sesją

| ASVS | L | Wymaganie | Status | Dowód | Działanie |
|---|---|---|---|---|---|
| 3.1.1, 3.2.1, 3.2.2 | 1 | Identyfikator sesji poza URL, nowy po zalogowaniu, o wystarczającej entropii | ✅ | ciasteczko sesji Django; `login()` rotuje klucz (`demo.py:94,120`); TM-04 | — |
| 3.3.1 | 1 | Wylogowanie i wygaśnięcie unieważniają sesję po stronie serwera | ✅ | `LogoutView` na POST (`config/urls.py:44`), zdarzenie `LOGOUT` (`signals.py:119-127`) | — |
| 3.3.2 | 1 | Sesja wygasa po bezczynności i po czasie bezwzględnym | ⚠️ | bezczynność 30 min (`base.py:185-186`); `SESSION_SAVE_EVERY_REQUEST` odnawia sesję, brak limitu bezwzględnego; TM-05 | RR-10 (Could) |
| 3.3.3 | 2 | Po zmianie hasła pozostałe sesje użytkownika są unieważniane | ✅ | Django weryfikuje hash hasła zapisany w sesji; zmiana hasła (`views.py:1322`) i dezaktywacja kończą sesje; TM-05 | — |
| 3.3.4 | 2 | Użytkownik widzi i kończy swoje aktywne sesje | ❌ | brak ekranu sesji | — (poza zakresem 0.1) |
| 3.4.1–3.4.3 | 1 | Ciasteczka sesji mają `Secure`, `HttpOnly` i `SameSite` | ✅ | `prod.py:32-33` (`Secure`), domyślnie `HttpOnly` i `SameSite=Lax`; `DJANGO_SECURE_COOKIES=0` wyłącznie dla sieci lokalnej | — |

### V4 — Kontrola dostępu

| ASVS | L | Wymaganie | Status | Dowód | Działanie |
|---|---|---|---|---|---|
| 4.1.1 | 1 | Kontrola dostępu egzekwowana po stronie serwera | ✅ | `roles.py:30-51`; 47 widoków i 16 endpointów z dekoratorem (AUDYT Zał. A); macierz rola × trasa dla wszystkich 70 tras (`tests_access_matrix.py`, US-007) | — |
| 4.1.3 | 1 | Zasada najmniejszych uprawnień | ⚠️ | trzy role; R1 naprawione w US-001; nadal domyślna rola Operator (`forms.py:141`); TM-35, TM-41 | US-001 |
| 4.1.5 | 1 | Kontrola dostępu domyślnie odmawia, także przy wyjątku | ⚠️ | `PermissionDenied` → 403 (`roles.py:38-41`), lecz nowy widok bez dekoratora jest publiczny; brak testu macierzowego; TM-10 | RR-24 (Should) |
| 4.2.1 | 1 | Brak dostępu do cudzych obiektów przez zmianę identyfikatora (IDOR) | n/d | jeden magazyn, jedna firma (Z-06); TM-17 | wraca przy drugim magazynie |
| 4.2.2 | 1 | Silna ochrona przed CSRF | ✅ | `CsrfViewMiddleware` (`base.py:78`), tokeny w formularzach i `X-CSRFToken`; wyjątek `GET /demo/` (W-1) | — |
| 4.3.1 | 1 | Interfejsy administracyjne chronione uwierzytelnianiem wieloskładnikowym | ⚠️ | 2FA TOTP dla Administratora i `/admin/` (US-010, ADR-0003) — **dobrowolne** (Z-39); w demo `/admin/` wyłączony | wymuszenie — decyzja PO |

### V5 — Walidacja, sanityzacja i kodowanie

| ASVS | L | Wymaganie | Status | Dowód | Działanie |
|---|---|---|---|---|---|
| 5.1.3 | 1 | Pozytywna walidacja wejścia: dozwolone wartości, zakresy, długości | ⚠️ | formularze Django z `min_value`; brak `max_value` i limitów długości w importach (R3, T16); TM-12, TM-27 | US-002; T16 (Should) |
| 5.2.2 | 1 | Dane niestrukturalne sanityzowane, także formuły CSV/XLSX w eksportach (najbliższy punkt ASVS) | ✅ | `_safe_cell` (`exports.py:9-15,27,46`), test CSV; TM-28 (test XLSX do dopisania) | — |
| 5.3.3, 5.3.4 | 1 | Kontekstowe kodowanie wyjścia (XSS) i zapytania parametryzowane | ✅ | autoescape, brak `\|safe` i `mark_safe` (AUDYT §3.1); ORM, jedyny surowy SQL to `LOCK TABLE` z nazw modeli (`seed_demo.py:116`) | — |
| 5.5.2 | 1 | Parsery XML bez niebezpiecznych funkcji (XXE, rozwijanie encji) | ⚠️ | `openpyxl` bez `defusedxml` w obrazie (R4); TM-24 | US-004 |
| 5.5.3 | 1 | Brak deserializacji niezaufanych danych | ✅ | serializer sesji JSON (domyślny), brak `pickle` w kodzie aplikacji | — |

### V7 — Obsługa błędów i logowanie

| ASVS | L | Wymaganie | Status | Dowód | Działanie |
|---|---|---|---|---|---|
| 7.1.1 | 1 | Poświadczenia nie trafiają do logów | ⚠️ | hasła nie są logowane, ale hasło wpisane w pole login trafia do `LoginEvent.username` (`signals.py:130-140`); TM-07 | US-005 |
| 7.1.2 | 1 | Dane osobowe w logach ograniczone do niezbędnych | ⚠️ | IP i user-agent w `LoginEvent` bez retencji; TM-39, TM-48 | US-005 |
| 7.1.3 | 2 | Rejestrowane są zdarzenia bezpieczeństwa: logowania, odmowy dostępu, zmiany uprawnień | ⚠️ | logowania, wylogowania i nieudane próby są (`signals.py:108-140`); brak odmów 403 i zmian kont; TM-40 | RR-28 (Could) |
| 7.4.1 | 1 | Ogólny komunikat błędu bez danych technicznych | ✅ | `DEBUG=False` (`prod.py:9`), `403.html`, JSON z komunikatem biznesowym; TM-23 | — |

### V8 — Ochrona danych

| ASVS | L | Wymaganie | Status | Dowód | Działanie |
|---|---|---|---|---|---|
| 8.1.5 | 2 | Regularne kopie zapasowe i test odtworzenia | ⚠️ | `pg_backup.sh` co 24 h, odtworzenie opisane (`COOLIFY.md` §10), nieprzećwiczone; TM-55 | R9 (Should); W-3 |
| 8.2.1 | 1 | Nagłówki anti-cache dla odpowiedzi z danymi wrażliwymi | ❌ | brak `Cache-Control: no-store`; TM-18 | RR-29 (Could) |
| 8.3.2 | 1 | Użytkownik może wyeksportować lub usunąć swoje dane | ❌ | brak komend; procedura ręczna w [`RODO.md`](RODO.md) §7 | Should (`export_user_data`, `anonymize_user`) |
| 8.3.4 | 1 | Dane wrażliwe zidentyfikowane, istnieje polityka postępowania | ⚠️ | [`KLASYFIKACJA_DANYCH.md`](KLASYFIKACJA_DANYCH.md) v0.1 — szkic do akceptacji PO | akceptacja PO |
| 8.3.7 | 2 | Dane wrażliwe szyfrowane zatwierdzonymi algorytmami | ❌ | backup i baza bez szyfrowania na poziomie aplikacji; TM-56 | R9 (Should) |
| 8.3.8 | 2 | Dane osobowe mają zdefiniowaną retencję | ❌ | Z-09 do potwierdzenia, brak mechanizmu ([`RODO.md`](RODO.md) §6); TM-39 | US-005 |

### V9 — Komunikacja

| ASVS | L | Wymaganie | Status | Dowód | Działanie |
|---|---|---|---|---|---|
| 9.1.1, 9.1.2 | 1 | TLS dla całego ruchu klienta bez fallbacku; aktualna konfiguracja TLS | ⚠️ | przekierowanie na HTTPS i HSTS (`prod.py:31-42`), Let's Encrypt na proxy; konfiguracja TLS proxy niezweryfikowana; TM-03 | RUNBOOK (weryfikacja) |

### V10 — Złośliwy kod

| ASVS | L | Wymaganie | Status | Dowód | Działanie |
|---|---|---|---|---|---|
| 10.3.2 | 1 | Aplikacja nie ładuje kodu z niezaufanych źródeł (CDN, SRI) | ✅ | skrypty lokalne (`static/warehouse/`, `vendor/jsQR.js`); brak zewnętrznych URL w szablonach i JS aplikacji (grep) | — |

### V12 — Pliki i zasoby

| ASVS | L | Wymaganie | Status | Dowód | Działanie |
|---|---|---|---|---|---|
| 12.1.1 | 1 | Limit rozmiaru wgrywanych plików | ✅ | `_MaxSizeFileMixin` 5 MB (`forms.py:20-31`), `DATA_UPLOAD_MAX_MEMORY_SIZE` (`base.py:189-191`) | — |
| 12.1.2 | 2 | Limit rozmiaru po rozpakowaniu archiwów (XLSX to zip) | ❌ | brak limitu; R4; TM-24 | US-004 |
| 12.2.1 | 1 | Typ pliku zgodny z oczekiwanym | ⚠️ | tylko rozszerzenie (`imports.py`, `parse_locations_file`), brak magic bytes; uszkodzony plik → 500 (T1); TM-25 | US-004 |
| 12.3.1, 12.3.4 | 1 | Nazwa pliku od użytkownika nie steruje systemem plików ani nagłówkiem odpowiedzi | ⚠️ | pliki importu nie są zapisywane (pamięć lub plik tymczasowy); `Content-Disposition` z kodów z importu (`views.py:370,498`); TM-32 | T16 (Should) |

### V13 — API

| ASVS | L | Wymaganie | Status | Dowód | Działanie |
|---|---|---|---|---|---|
| 13.2.1 | 1 | Dozwolone metody HTTP adekwatne do akcji | ✅ | `@require_GET` / `@require_POST` na endpointach skanera (`scanner_views.py:150-411`); zmiany stanu tylko na POST; TM-19 | — |
| 13.2.2 | 1 | Dane JSON walidowane przed użyciem | ⚠️ | ręczne parsowanie w widokach, błędy jako `WMSError`; brak górnych granic (T16); TM-21 | T16 (Should) |
| 13.2.3 | 1 | API z ciasteczkami chronione przed CSRF | ✅ | `X-CSRFToken` z `window.CSRF` (`scanner/base.html:21`); TM-20 | — |

### V14 — Konfiguracja

| ASVS | L | Wymaganie | Status | Dowód | Działanie |
|---|---|---|---|---|---|
| 14.1.1 | 2 | Build i wdrożenie powtarzalne i zautomatyzowane | ⚠️ | CI, Dockerfile, auto-deploy Coolify; brak locka zależności (T7), obraz po tagu; R10; TM-52 | US-006 |
| 14.2.1 | 1 | Komponenty aktualne, sprawdzane narzędziem do zależności | ⚠️ | `pip-audit` miesięcznie i doradczo, brak Dependabota; R10 | US-006 |
| 14.3.2 | 1 | Tryb debug wyłączony w produkcji | ✅ | `DJANGO_DEBUG=0` w obrazie (`Dockerfile:23`), `prod.py:9`; uwaga: brak zmiennej poza Dockerem = dev (`docs/pitfalls/deploy.md` #3) | — |
| 14.4.3 | 1 | Content-Security-Policy ogranicza skutki XSS | ✅ | `script-src 'self' 'nonce-…'` bez `unsafe-inline` (US-011, ADR-0004, `tests_security_headers.py`); TM-16 | R8 (Should) |
| 14.4.4, 14.4.6, 14.4.7 | 1 | `X-Content-Type-Options`, `Referrer-Policy`, ochrona przed osadzaniem w ramkach | ✅ | `prod.py:41-42`; `XFrameOptionsMiddleware` (`base.py:81`), domyślnie `DENY` | — |
| 14.4.5 | 1 | HSTS na wszystkich odpowiedziach, minimum rok | ⚠️ | `SECURE_HSTS_SECONDS` 30 dni (`DJANGO_HSTS_SECONDS`), `preload` wyłączony (US-011); rok — po stabilizacji domeny; TM-03 | R8 (Should) |

## 3. Podsumowanie

48 wierszy (kontroli zgrupowanych), z czego 47 stosuje się do aplikacji (1 × n/d).

| Status | Liczba | Udział w 47 |
|---|---|---|
| ✅ spełnione | 17 | 36 % |
| ⚠️ częściowo | 21 | 45 % |
| ❌ brak | 9 | 19 % |
| n/d | 1 | — |

**Procent spełnienia:** ściśle (tylko ✅) **36 %** (17 / 47); ważony (⚠️ liczone jako połowa)
**59 %**. Per poziom: L1 — 15 z 37 ✅ (41 %, ważony 64 %); L2 — 2 z 10 ✅ (20 %, ważony 40 %).

| Rozdział | ✅ | ⚠️ | ❌ | n/d | Razem |
|---|---|---|---|---|---|
| V2 Uwierzytelnianie | 1 | 4 | 1 | 0 | 6 |
| V3 Sesje | 4 | 1 | 1 | 0 | 6 |
| V4 Kontrola dostępu | 2 | 2 | 1 | 1 | 6 |
| V5 Walidacja i kodowanie | 3 | 2 | 0 | 0 | 5 |
| V7 Logowanie i błędy | 1 | 3 | 0 | 0 | 4 |
| V8 Ochrona danych | 0 | 2 | 4 | 0 | 6 |
| V9 Komunikacja | 0 | 1 | 0 | 0 | 1 |
| V10 Złośliwy kod | 1 | 0 | 0 | 0 | 1 |
| V12 Pliki | 1 | 2 | 1 | 0 | 4 |
| V13 API | 2 | 1 | 0 | 0 | 3 |
| V14 Konfiguracja | 2 | 3 | 1 | 0 | 6 |
| **Razem** | **17** | **21** | **9** | **1** | **48** |

**Prognoza po US-001…US-006:** pełne zamknięcie 9 wierszy (2.5.4, 2.10.4, 5.5.2, 7.1.1,
7.1.2, 8.3.8, 12.1.2, 12.2.1, 14.2.1) daje 26 z 47 ✅ (ok. 55 %); 4.1.3, 5.1.3 i 14.1.1
poprawią się tylko częściowo (zostają T16, domyślna rola, lock zależności). Szacunek,
nie zobowiązanie.

**Największe luki poza historyjkami US:** 2FA dla Administratora i `/admin/` (4.3.1; R6),
CSP i HSTS (14.4.3, 14.4.5; R8), szyfrowanie i test odtworzenia backupu (8.1.5, 8.3.7; R9),
samodzielna zmiana hasła (2.1.5; Z-16), prawa osób (8.3.2) — to pozycje Should lub decyzje PO.

**Jak używać:** statusy aktualizujemy w PR, który zamyka historyjkę (ten sam commit co
zmiana wiersza w [`RYZYKA.md`](RYZYKA.md)); wiersz przechodzi na ✅ dopiero z odwołaniem do
testu lub konfiguracji. Pełny przegląd razem z rejestrem ryzyk co 3 miesiące.
