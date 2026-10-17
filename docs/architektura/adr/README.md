# Decyzje architektoniczne (ADR) — zasady i indeks

| | |
|---|---|
| Wersja | 0.1 |
| Data | 2026-10-16 |
| Status | szkic — do akceptacji Product Ownera |
| Właściciel | [DEV] |

## 1. Czym jest ADR

**ADR (Architecture Decision Record)** to krótki, niezmienny zapis jednej decyzji, która
kształtuje architekturę, narzędzia lub sposób pracy zespołu: **jaki był kontekst, jakie opcje
rozważono, co wybrano i jakie są konsekwencje**. Służy temu, by za pół roku nie zgadywać,
dlaczego jest tak, a nie inaczej — i by zmiana decyzji była świadoma, a nie przypadkowa.

W repozytorium istnieje już dziennik decyzji domenowych [docs/06](../../06-decyzje.md)
(D-01…D-13). ADR-y go **uzupełniają** (decyzje o architekturze, narzędziach, bezpieczeństwie,
procesie) i nie zastępują (Z-03). Decyzje z docs/06 są w indeksie poniżej jako **ADR-H-01…H-13** —
bez przepisywania treści.

## 2. Kiedy pisać ADR

Zasada: ADR powstaje w **kroku 3 procesu zespołu (projektowanie rozwiązania), przed
implementacją**, a nie po fakcie. Pisz, gdy decyzja spełnia co najmniej jeden warunek:

| Warunek | Przykład z tego repo |
|---|---|
| zmienia strukturę kodu lub granice modułów | podział `views.py` (T2), przeniesienie domknięcia WZ do `services.py` (T3) |
| dodaje lub zmienia usługę/technologię w obrazie lub infrastrukturze | Redis zamiast LocMem (T8), kopia off-site (R9) |
| zmienia narzędzia lub bramki jakości w CI | ADR-0001 |
| wpływa na bezpieczeństwo, dane osobowe lub model zagrożeń | CSP (R8), 2FA/argon2 (R6), publiczne demo (Z-05) |
| jest trudna do odwrócenia albo odwrócenie kosztuje (migracja danych, zmiana kontraktu API) | lock zależności (T7), polityka API |
| odstępuje od zasady z `CLAUDE.md` / `docs/pitfalls/` lub od wcześniejszego ADR | — |

**Nie** pisz ADR dla: poprawek błędów, drobnych refaktorów, wyboru nazwy zmiennej, decyzji
czysto produktowych (te idą do [docs/06](../../06-decyzje.md) lub do wymagań/zakresu przez [BA]).

## 3. Konwencje

| Aspekt | Zasada |
|---|---|
| Lokalizacja | `docs/architektura/adr/` |
| Nazwa pliku | `NNNN-krotka-nazwa.md` — 4 cyfry kolejno, nazwa małymi literami z myślnikami, **bez polskich znaków** (np. `0002-cache-wspolny.md`); numerów się nie recyklinguje |
| Język | polski (Z-01); identyfikatory i kod po angielsku |
| Metadane | tabela na początku pliku: Wersja, Data, Status, Właściciel (jak w pozostałych dokumentach architektury) + pola ADR z szablonu |
| Statusy | `zaproponowany` → `zaakceptowany` albo `odrzucony`; później `zastąpiony przez ADR-NNNN` albo `wycofany` |
| Akceptacja | Product Owner (merge do `main` wykonuje wyłącznie PO — Z-02); ADR zmerge'owany do `main` = zaakceptowany |
| Niezmienność | zaakceptowanego ADR nie przepisujemy. Zmiana decyzji = **nowy ADR**, który go zastępuje; w starym zmieniamy tylko status i dopisujemy link do nowego |
| Długość | jedna strona; szczegóły techniczne linkujemy (kod, `docs/pitfalls/`, audyt) |
| Powiązania | ADR linkuje identyfikatory: ryzyka R1–R10, dług T1–T16, założenia Z-01…, decyzje D-xx / ADR-H-xx, historyjki US-xxx |
| Odwołania | w kodzie i dokumentach wskazuj `ADR-NNNN` oraz ścieżkę pliku |
| Operator | gałąź wdrażająca ADR ma `docs/operator/<branch>.md` (CLAUDE.md); w nim odwołanie do ADR |

## 4. Szablon

Skopiuj do `docs/architektura/adr/NNNN-krotka-nazwa.md`:

```markdown
# ADR-NNNN — Tytuł decyzji (czasownik lub rzeczownik, konkretnie)

| | |
|---|---|
| Wersja | 0.1 |
| Data | RRRR-MM-DD |
| Status | zaproponowany / zaakceptowany / odrzucony / zastąpiony przez ADR-NNNN |
| Właściciel | [DEV] / [SEC] / [BA] |
| Powiązania | R?, T?, Z-??, D-??, US-??? |

## Kontekst
Jaki problem rozwiązujemy i jakie siły działają (wymagania, ograniczenia, ryzyka, skala).
Fakty z kodu lub dokumentów, z linkami. Bez rozwiązania.

## Opcje
| Opcja | Zalety | Wady / koszt |
|---|---|---|
| A. … | | |
| B. … | | |
| C. Nic nie zmieniać | | |

## Decyzja
Wybrana opcja jednym zdaniem w trybie oznajmującym („Używamy …”) i krótkie uzasadnienie
względem opcji odrzuconych.

## Konsekwencje
- Co zyskujemy.
- Co tracimy lub co dochodzi do utrzymania.
- Zmiany w kodzie, CI, dokumentach i procedurach (RUNBOOK) — z odwołaniami.
- Ryzyka rezydualne i sposób ich monitorowania.
- Kiedy wrócić do decyzji (warunek rewizji).
```

## 5. Indeks

### 5.1 ADR

| ID | Tytuł | Status | Data | Plik |
|---|---|---|---|---|
| ADR-0001 | Narzędzia jakości i bezpieczeństwa w CI | zaakceptowany (przez zespół [DEV]/[SEC]; do potwierdzenia przez PO — DEC-2, DEC-3) | 2026-10-16 | [0001-narzedzia-jakosci-i-bezpieczenstwa.md](0001-narzedzia-jakosci-i-bezpieczenstwa.md) |
| ADR-0002 | Cache wspólny dla workerów: DatabaseCache w PostgreSQL | zaakceptowany (PO, 2026-10-16) | 2026-10-16 | [0002-cache-wspolny-w-bazie.md](0002-cache-wspolny-w-bazie.md) |
| ADR-0003 | Weryfikacja dwuetapowa (TOTP) przez `django-otp` | zaakceptowany (zespół; tryb dobrowolny — Z-39 do potwierdzenia przez PO) | 2026-10-16 | [0003-2fa-totp-django-otp.md](0003-2fa-totp-django-otp.md) |
| ADR-0004 | CSP z nonce: własny middleware zamiast `django-csp` | zaakceptowany (zespół) | 2026-10-16 | [0004-csp-z-nonce-wlasny-middleware.md](0004-csp-z-nonce-wlasny-middleware.md) |
| ADR-0005 | Backup poza serwerem: age + rclone + heartbeat | zaakceptowany (PO, 2026-10-16) | 2026-10-16 | [0005-backup-off-site-age-rclone.md](0005-backup-off-site-age-rclone.md) |
| ADR-0006 | Podział `views.py` na pakiet `warehouse/views/` | zaakceptowany ([DEV]) | 2026-10-16 | [0006-podzial-views-na-pakiet.md](0006-podzial-views-na-pakiet.md) |
| ADR-0007 | Lock zależności z hashami (`pip-compile`) i obrazy przypięte digestem | zaakceptowany ([DEV]/[SEC]) | 2026-10-17 | [0007-lock-zaleznosci-pip-compile.md](0007-lock-zaleznosci-pip-compile.md) |

Powiązania ADR-0001: T4, T5, T6, R10, Z-08, Z-10 ([AUDYT](../../AUDYT.md)).

### 5.2 Decyzje historyczne (ADR-H) — z dziennika [docs/06](../../06-decyzje.md)

Treść pozostaje w docs/06 (źródło prawdy). Status „przyjęta”: potwierdzone przez autora
projektu ([docs/06](../../06-decyzje.md), nagłówek); daty nie są w docs/06 zapisane (historia:
`git log -- docs/06-decyzje.md`).

| ID | Dawne ID | Tytuł | Obszar | Link |
|---|---|---|---|---|
| ADR-H-01 | D-01 | Stan prowadzony na poziomie palety (HU), nie sumy w lokalizacji | model danych | [docs/06](../../06-decyzje.md#d-01-stan-prowadzony-na-poziomie-palety-hu-nie-sumy-w-lokalizacji) |
| ADR-H-02 | D-02 | Brak zewnętrznej master daty — słownik materiałów prowadzony w aplikacji | dane | [docs/06](../../06-decyzje.md#d-02-brak-zewnętrznej-master-daty--słownik-materiałów-prowadzony-w-aplikacji) |
| ADR-H-03 | D-03 | Numer WZ liczony od nowa każdego dnia (`WZ<data>-NNN`) | numeracja | [docs/06](../../06-decyzje.md#d-03-numer-wz-liczony-od-nowa-każdego-dnia-wzdata-nnn) |
| ADR-H-04 | D-04 | Wymiana danych plikami CSV/XLSX zamiast integracji | integracje | [docs/06](../../06-decyzje.md#d-04-wymiana-danych-plikami-csvxlsx-zamiast-integracji) |
| ADR-H-05 | D-05 | Każda zmiana stanu przez jedną warstwę usług, razem z zapisem ruchu | architektura | [docs/06](../../06-decyzje.md#d-05-każda-zmiana-stanu-przez-jedną-warstwę-usług-razem-z-zapisem-ruchu) |
| ADR-H-06 | D-06 | Wysyłka bez pakowania jest dozwolona | proces | [docs/06](../../06-decyzje.md#d-06-wysyłka-bez-pakowania-jest-dozwolona) |
| ADR-H-07 | D-07 | Spis z natury przy zamrożonym magazynie | proces | [docs/06](../../06-decyzje.md#d-07-spis-z-natury-przy-zamrożonym-magazynie) |
| ADR-H-08 | D-08 | Skaner jako strona w przeglądarce telefonu lub kolektora | interfejs | [docs/06](../../06-decyzje.md#d-08-skaner-jako-strona-w-przeglądarce-telefonu-lub-kolektora) |
| ADR-H-09 | D-09 | Import stanów z ilością 0 zostaje — z ostrzeżeniem | importy | [docs/06](../../06-decyzje.md#d-09-import-stanów-z-ilością-0-zostaje--z-ostrzeżeniem) |
| ADR-H-10 | D-10 | Numery palet bez rozróżniania wielkości liter | wyszukiwanie | [docs/06](../../06-decyzje.md#d-10-numery-palet-bez-rozróżniania-wielkości-liter) |
| ADR-H-11 | D-11 | Zbiorczy wydruk etykiet: limit 200 z komunikatem | etykiety PDF | [docs/06](../../06-decyzje.md#d-11-zbiorczy-wydruk-etykiet-limit-200-z-komunikatem) |
| ADR-H-12 | D-12 | Limit logowań zawsze; IP tylko od zaufanego proxy | bezpieczeństwo | [docs/06](../../06-decyzje.md#d-12-limit-logowań-zawsze-ip-tylko-od-zaufanego-proxy) |
| ADR-H-13 | D-13 | Paleta tylko w jednym otwartym arkuszu spisu | spis | [docs/06](../../06-decyzje.md#d-13-paleta-tylko-w-jednym-otwartym-arkuszu-spisu) |

Zmiana decyzji historycznej: nowy ADR `NNNN-…` ze wskazaniem „zastępuje ADR-H-xx” plus
jednowierszowy dopisek z linkiem w docs/06.

## 6. Kandydaci na kolejne ADR

Z audytu ([AUDYT](../../AUDYT.md)) i założeń ([ZALOZENIA](../../analiza/ZALOZENIA.md)). Kolejność
i priorytety ustala Product Owner; poniżej pytanie, na które ADR ma odpowiedzieć.

| Kandydat | Źródło | Pytanie decyzyjne | Opcje wstępne | Wymaga decyzji PO? |
|---|---|---|---|---|
| **Cache współdzielony** | T8, R6 (US-009) | czym zastąpić LocMem per proces dla limitu logowań i blokady resetu demo, by limit nie rósł z liczbą workerów i dało się wprowadzić blokadę per konto | `DatabaseCache` (bez nowej usługi) · Redis (nowy kontener) · zostawić LocMem z udokumentowanym ×N | tak (koszt utrzymania nowej usługi) |
| **Podział `views.py`** — ADR-0006 | T2 (US-017) | jak rozbić plik 1405 linii bez zmiany URL-i i bez blokowania równoległych prac | pakiet `views/` (`dashboard`, `issues`, `users`, `exports`) · moduły obok `views.py` · bez zmian | nie (decyzja techniczna), ale termin koliduje z innymi PR |
| **Lock zależności** | T7, R10 (US-020) | jak uzyskać powtarzalny build i jedno źródło prawdy o zależnościach | `pip-compile --generate-hashes` · `uv lock` · Poetry; `pyproject.toml` jako źródło, Dockerfile instaluje z locka; współpraca z Dependabotem | nie |
| **CSP i nagłówki** | R8 (US-011) | jak wprowadzić Content-Security-Policy mimo inline `onclick` i `window.CSRF` | `django-csp` z nonce · przeniesienie handlerów do plików JS · `Permissions-Policy: camera=(self)`; HSTS 1 rok albo bez `preload` | nie |
| **2FA i argon2** | R6, DEC-4 (US-008, US-010) | jak podnieść uwierzytelnianie Administratora i `/admin/` | `argon2-cffi` jako hasher · `django-otp` dla ADMIN i `/admin/` · allowlista IP dla `/admin/` na proxy | tak (wpływ na użytkowników, zależy od decyzji o wdrożeniu) |
| **Backup off-site** | R9 (US-012) | gdzie i jak trzymać szyfrowaną kopię poza hostem oraz jak ją weryfikować | `rclone` do S3/B2/innego hosta · szyfrowanie `age`/`gpg` · retencja 30 dni · alert przy braku świeżej kopii · cykliczny test odtworzenia ([RUNBOOK](../../operacje/RUNBOOK.md) §5) | tak (koszt, lokalizacja danych) |
| **Publiczne demo** | Z-05, R5, DEC-6 (US-016) | w jakiej formie demo zostaje i jakie limity ponosi | limiter per IP na `/demo/` i ścieżkach operatora · reset tylko ze Scheduled Task · limity liczby obiektów · wyjątki w `RYZYKA.md` z datą przeglądu | tak (akceptacja ryzyka) |
| Harness asystenta AI w repozytorium (`.claude/`) | [AUDYT §1.2](../../AUDYT.md) (brak decyzji) | czy i jak utrzymujemy hooki, agentów i `docs/pitfalls/` jako element procesu | utrzymać jak dziś · przenieść do dokumentu procesu · usunąć | tak |
| Udostępnienie API na zewnątrz | [API.md §8](../API.md#8-wersjonowanie-i-stabilność) | czy i na jakich warunkach JSON API przestaje być wewnętrzne | tokeny + wersjonowanie w URL + limity · pozostać przy plikach CSV/XLSX (D-04) | tak (zakres) |

## 7. Jak dodać ADR — lista kontrolna

1. Sprawdź indeks: czy decyzja już zapadła (ADR lub ADR-H)?
2. Weź kolejny numer, skopiuj szablon (sekcja 4), status `zaproponowany`.
3. Wypełnij kontekst faktami z kodu/dokumentów; wypisz co najmniej dwie opcje, w tym „nic nie zmieniać”.
4. Dodaj wiersz do indeksu (sekcja 5.1) i — jeśli dotyczy — usuń kandydata z sekcji 6.
5. Zaktualizuj dokumenty, których decyzja dotyczy ([ARCHITEKTURA](../ARCHITEKTURA.md), [RUNBOOK](../../operacje/RUNBOOK.md), [STRATEGIA_TESTOW](../../testy/STRATEGIA_TESTOW.md)).
6. PO akceptuje przez merge; status zmienia się na `zaakceptowany` w tym samym PR.
