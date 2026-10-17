# Wymagania — miniWMS

| | |
|---|---|
| Wersja | 0.1 |
| Data | 2026-10-16 |
| Status | szkic — do akceptacji Product Ownera |
| Właściciel | [BA] |

Katalog wymagań: funkcjonalnych (FR), niefunkcjonalnych (NFR), bezpieczeństwa i RODO (SEC) oraz
reguł biznesowych (BR). Powiązania z historyjkami i testami: [SLEDZENIE.md](SLEDZENIE.md);
backlog: [HISTORYJKI.md](HISTORYJKI.md).

## 0. Zasady czytania

- **Źródło prawdy o FR to [docs/05](../05-wymagania.md)** (Z-03). Tu: te same 26 wymagań w formacie
  Given/When/Then, 1:1 (FR-nnn = W-nn). Pełne odnośniki do kodu — w docs/05; tu tylko skrót.
- **NFR i SEC** wyprowadzono z kodu, audytu ([AUDYT.md](../AUDYT.md) §1.3, §2.4, §3.3–3.5) oraz
  minimalnych wymagań bezpieczeństwa z promptu PO (sekcja 6). Nic spoza tych źródeł nie jest
  tu wymaganiem — wątpliwości są oznaczone „do potwierdzenia” i zebrane w sekcji 5 (PYT-nn).
- **Status:** `spełnione` (jest w kodzie i działa), `częściowo`, `brak`, `do potwierdzenia`
  (brak decyzji PO lub pomiaru). Status SEC/NFR odzwierciedla stan audytu (`main` @ `f5be158`,
  2026-10-15); numery linii pochodzą z audytu i mogą się przesunąć.
- **Identyfikatory:** R1–R10 (ryzyka) i T1–T16 (dług) z AUDYT; Z-nn założenia
  ([ZALOZENIA.md](ZALOZENIA.md)); DEC-1…6 decyzje PO; US-nnn historyjki; ADR-0001 narzędzia CI.
- **Priorytet MoSCoW:** wszystkie istniejące FR to Must (wdrożone). Priorytety nowych prac są
  w [HISTORYJKI.md](HISTORYJKI.md).

| Zbiór | Liczba |
|---|---|
| FR (funkcjonalne) | 26 |
| NFR (niefunkcjonalne) | 28 |
| SEC (bezpieczeństwo / RODO) | 42 |
| BR (reguły biznesowe) | 16 |
| PYT (otwarte pytania do PO) | 22 |

---

## 1. Wymagania funkcjonalne (FR)

Wszystkie: priorytet **Must**, status **spełnione**.

### 1.1 Przyjęcie i etykiety

| FR | W-id | Wymaganie | Kryterium akceptacji (Given / When / Then) | MoSCoW | Status | Gdzie (kod / test) |
|---|---|---|---|---|---|---|
| FR-001 | W-01 | Operator przyjmuje towar, podając materiał, ilość i liczbę palet. | **Given** Operator i materiał; **When** przyjmuje 100 szt. na 3 palety; **Then** powstają 3 palety po 33, 33 i 34 szt., każda „Do ułożenia”, z ruchem PRZYJĘCIE. | Must | spełnione | `services.py` `split_quantity`, `receive_material`; `ReceiveTests`, `SplitQuantityTests` |
| FR-002 | W-02 | Ilość na palecie nie przekracza limitu materiału. | **Given** materiał z limitem 50 szt./paletę; **When** przyjęcie 120 szt. na 2 palety; **Then** odrzucone z komunikatem o limicie, bez palet i ruchów. | Must | spełnione | `services.py:114`, `forms.py:244`; `test_receive_respects_max_per_pallet` |
| FR-003 | W-03 | Każda paleta ma unikalny numer nadawany automatycznie. | **Given** dwa kolejne przyjęcia; **When** zapisane; **Then** numery HU są kolejne, bez duplikatów. | Must | spełnione | `generate_hu_number`; `test_sequential_unique_numbers` |
| FR-004 | W-04 | Etykieta palety z kodem QR do druku. | **Given** paleta z kompletem pól; **When** pobranie etykiety PDF; **Then** PDF zawiera numer, materiał, ilość i kod QR na jednej stronie A4. | Must | spełnione | `labels.py`; `test_hu_label_with_all_fields_single_page` |
| FR-005 | W-05 | Przyjęcia i stany początkowe można wczytać z CSV/XLSX. | **Given** plik z jednym wierszem z nieznanym materiałem; **When** import; **Then** poprawne wiersze wczytane, błędny pominięty z komunikatem „Wiersz N…”. | Must | spełnione | `receipt_import.py`, `stock_import.py`; `ReceiptImportTests`, `StockImportTests` |

### 1.2 Rozmieszczanie

| FR | W-id | Wymaganie | Kryterium akceptacji (Given / When / Then) | MoSCoW | Status | Gdzie (kod / test) |
|---|---|---|---|---|---|---|
| FR-006 | W-06 | Operator odkłada paletę w lokalizacji — w panelu lub skanerem. | **Given** paleta „Do ułożenia” i lokalizacja; **When** skan palety i miejsca (lub wybór w panelu); **Then** paleta ma status „Zmagazynowany”, lokalizację i ruch ALOKACJA. | Must | spełnione | `allocate_hu`, `scanner_views.api_allocate`; `test_allocate_sets_location_and_status`, `test_api_allocate` |
| FR-007 | W-07 | Zmiana miejsca palety jest zapisywana jako przesunięcie. | **Given** paleta w lokalizacji A; **When** przeniesiona do B; **Then** powstaje ruch PRZESUNIĘCIE z polami „z” = A i „do” = B. | Must | spełnione | `services.py:182` (brak dedykowanego testu — luka LT-01) |
| FR-008 | W-08 | Pojemność lokalizacji jest informacyjna. | **Given** lokalizacja o przekroczonej pojemności; **When** odkładana kolejna paleta; **Then** odłożenie się udaje, a panel i skaner pokazują ostrzeżenie. | Must | spełnione | `allocate_hu`, `location_over_capacity`; `test_allocate_over_capacity_succeeds_but_flagged`, `test_over_capacity_allocation_succeeds_with_warning`, `test_allocate_over_capacity_warns_but_succeeds` |
| FR-009 | W-09 | Pustej palety nie da się odłożyć. | **Given** paleta ze statusem „Pusty”; **When** próba alokacji; **Then** komunikat odmowy, stan bez zmian. | Must | spełnione | `services.py:153`, `views.py` `hu_allocate` (brak dedykowanego testu — luka LT-01) |

### 1.3 Wydania

| FR | W-id | Wymaganie | Kryterium akceptacji (Given / When / Then) | MoSCoW | Status | Gdzie (kod / test) |
|---|---|---|---|---|---|---|
| FR-010 | W-10 | Wydanie po materiale dobiera palety: PICKING przed ZAPAS, potem najkrótsza data ważności, potem najstarsze przyjęcie. | **Given** dwie palety materiału z datami 2026-01 i 2026-03; **When** wydanie po materiale; **Then** najpierw pobrana paleta z 2026-01; **Given** paleta w PICKING i w ZAPAS; **Then** PICKING ma pierwszeństwo. | Must | spełnione | `services.py:305` `_pickable_hus`; `test_fefo_prefers_earliest_expiry`, `test_picking_location_priority` |
| FR-011 | W-11 | Kolejność FEFO obowiązuje także przy kompletacji skanerem. | **Given** paleta z wcześniejszą datą ważności i paleta z późniejszą; **When** operator skanuje paletę z późniejszą datą; **Then** pobranie przechodzi z ostrzeżeniem wskazującym właściwą paletę (docs/05: „ostrzeżeniem lub odmową” — wdrożono ostrzeżenie, PYT-14). | Must | spełnione | `scanner_views.api_pick`, `services.first_pickable_hu`; `ApiPickFefoWarningTests` |
| FR-012 | W-12 | Stan palety nie może spaść poniżej zera. | **Given** paleta 50 szt.; **When** wydanie 60 szt.; **Then** odrzucone, a baza odrzuca ilość < 0. | Must | spełnione | `services.py:341-347`, `models.py:216`; `test_overpick_blocked`, `test_hu_quantity_check_constraint` |
| FR-013 | W-13 | Dokument WZ realizowany w całości albo z brakami. | **Given** WZ z pozycją ponad stan; **When** „Realizuj”; **Then** błąd i brak ruchów; **When** „Zamknij z brakami”; **Then** wydana dostępna ilość, brak pokazany. | Must | spełnione | `services.py:407` `execute_issue_document`; `test_full_execution_raises_on_shortage`, `test_partial_execution_closes_with_shortage` |
| FR-014 | W-14 | Pozycję WZ można wskazać jako konkretną paletę. | **Given** pozycja WZ wskazuje paletę innego materiału; **When** realizacja; **Then** odrzucona. | Must | spełnione | `forms.py:327`, `services.py:421`; `test_execute_rejects_specific_hu_wrong_material` |
| FR-015 | W-15 | Po pobraniu całej palety jest ona „Pusta” i zwalnia miejsce. | **Given** paleta 50 szt. w lokalizacji; **When** wydanie 50 szt.; **Then** status „Pusty”, brak lokalizacji. | Must | spełnione | `services.py:231`; `test_pick_to_zero_marks_empty_and_frees_location` |
| FR-016 | W-16 | WZ przechodzi: Otwarty → Zrealizowany → (Spakowany) → Wysłany. | **Given** WZ „Otwarty”; **When** „Spakuj”; **Then** odrzucone; **Given** WZ „Zrealizowany”; **When** „Wyślij” bez pakowania; **Then** zmiana na „Wysłany”; **Given** WZ spakowany; **When** dodanie pozycji; **Then** odrzucone. | Must | spełnione | `services.py:477,489`, `views.py` `issue_add_line`; `test_pack_and_ship_flow`, `test_pack_requires_realized`, `test_cannot_add_line_to_packed_document` |
| FR-017 | W-17 | Skaner prowadzi kompletację dokumentu i zamyka go po pobraniu wszystkiego. | **Given** WZ w kompletacji skanerem; **When** pobrana ostatnia pozycja; **Then** WZ „Zrealizowany”; **When** skan materiału spoza dokumentu; **Then** odmowa. | Must | spełnione | `scanner_views.api_pick`; `test_document_pick_completes_order`, `test_document_pick_rejects_wrong_material` |
| FR-025 | W-25 | Skaner respektuje paletę wskazaną w pozycji WZ. | **Given** pozycja WZ z „konkretnym HU”; **When** skan innej palety tego samego materiału; **Then** odmowa. | Must | spełnione | `scanner_views.api_pick`; `ApiPickSpecificHuTests` |

### 1.4 Kontrola stanu

| FR | W-id | Wymaganie | Kryterium akceptacji (Given / When / Then) | MoSCoW | Status | Gdzie (kod / test) |
|---|---|---|---|---|---|---|
| FR-018 | W-18 | Korekta ilości palety z powodem i historią. | **Given** paleta; **When** korekta +5 z powodem; **Then** ruch KOREKTA +5 z powodem; **When** korekta o 0; **Then** odrzucona. | Must | spełnione | `services.py:198` `correct_hu_quantity`; `test_correction_logs_movement`, `test_web_inventory_add` |
| FR-019 | W-19 | Łączenie palet tylko tego samego materiału i partii. | **Given** palety różnych materiałów; **When** przepakowanie; **Then** odrzucone; **Given** ten sam materiał i partia, całe źródło; **Then** źródło „Puste”. | Must | spełnione | `services.py:242` `repack_hu`; `RepackTests` |
| FR-020 | W-20 | Spis z natury: migawka → liczenie → zatwierdzenie różnic. | **Given** arkusz spisu z migawką; **When** zamknięcie z różnicą; **Then** korekta z powodem „Spis z natury”; pozycje niepoliczone nie zmieniają stanu. | Must | spełnione | `services.py:534,560`; `StocktakeTests` |
| FR-026 | W-26 | Każda korekta ilości ma powód. | **Given** korekta ilości; **When** zapis bez powodu (ekran palety, inwentaryzacja, skaner); **Then** odrzucony. | Must | spełnione | `correct_hu_quantity`; `CorrectionReasonRequiredTests`, `HUCorrectionReasonTests`, `ApiInventoryReasonTests` |

### 1.5 Raporty i dostęp

| FR | W-id | Wymaganie | Kryterium akceptacji (Given / When / Then) | MoSCoW | Status | Gdzie (kod / test) |
|---|---|---|---|---|---|---|
| FR-021 | W-21 | Każda zmiana stanu zostawia ślad: kto, kiedy, ile, skąd, dokąd. | **Given** dowolna operacja z FR-001…FR-020; **When** wykonana; **Then** w rejestrze ruchów jest wpis z autorem, czasem, ilością, lokalizacją źródłową i docelową. | Must | spełnione | `models.py` `StockMovement`, `services.py`; `test_receive_creates_hus_and_movements` |
| FR-022 | W-22 | Stany i ruchy można wyeksportować do CSV i Excel. | **Given** filtr typu ruchu; **When** eksport; **Then** plik zawiera tylko ruchy tego typu; **Given** komórka zaczynająca się od `=`; **Then** jest zneutralizowana. | Must | spełnione | `exports.py`; `test_movement_export_respects_type_filter`, `test_csv_export_neutralizes_formula_injection` |
| FR-023 | W-23 | Trzy role: Podgląd (odczyt), Operator (operacje), Administrator (konta). | **Given** użytkownik z rolą Podgląd; **When** GET `/przyjecie/`; **Then** 403; **Given** konto utworzone bez wskazania roli (bez profilu); **Then** rola to Podgląd. Uwaga: formularz „Nowy użytkownik” podpowiada rolę Operator (`forms.py:141`, AUDYT §3.1) — PYT-20. | Must | spełnione | `roles.py`; `test_viewer_role_forbidden_on_receive`, `test_new_user_default_viewer` |
| FR-024 | W-24 | Dziennik logowań i ochrona kont. | **Given** udane i nieudane logowanie; **When** wystąpi; **Then** jest zapisane w dzienniku; **When** Administrator odbiera sobie rolę; **Then** odmowa; **When** słabe hasło przy zakładaniu konta; **Then** odrzucone. | Must | spełnione | `signals.py`, `views.py` `user_edit`; `SecurityTests` |

---

## 2. Wymagania niefunkcjonalne (NFR)

Wartości pochodzą z kodu, konfiguracji i audytu; „źródło” wskazuje, skąd. Wymagania ze statusem
`brak`/`częściowo` mają historyjkę w backlogu (kolumna „Źródło” → R/T → US w
[SLEDZENIE.md](SLEDZENIE.md)).

| NFR | Kategoria | Wymaganie | Wartość | Status | Źródło |
|---|---|---|---|---|---|
| NFR-001 | wydajność (skala) | System obsługuje skalę docelowego magazynu. | ≈200 palet (liczba rośnie), ≈30 nowych palet tygodniowo, 2 operatorów na zmiany. Brak górnej granicy wzrostu i testu obciążeniowego. | do potwierdzenia (PYT-01) | docs/01 |
| NFR-002 | wydajność | Czas odpowiedzi ekranów i API skanera. | Nie zdefiniowany; brak pomiarów. | do potwierdzenia (PYT-03) | AUDYT §1.3 |
| NFR-003 | wydajność | Żądanie mieści się w limicie czasu workera. | gunicorn: 3 workery, timeout 120 s; pojedyncze żądanie może go przekroczyć (R3, R5). | częściowo | `entrypoint.sh:54-57`, R3, R5 |
| NFR-004 | wydajność | Lista ruchów i raport historii materiału są ucinane. | 500 wierszy (bez filtra dat). | spełnione | `views.py:1162,1387` |
| NFR-005 | wydajność | Zbiorczy wydruk etykiet palet ma limit. | ≤ 200 etykiet; powyżej komunikat „Zawęź filtr”. | spełnione | `views.py:502`, D-11; `HULabelsLimitTests` |
| NFR-006 | wydajność | Wydruk etykiet lokalizacji ma limit. | Limit 200 etykiet na wydruk (`LOCATION_LABELS_LIMIT`, jak dla palet); powyżej komunikat „Zawęź filtr”. | spełnione — US-015 | R5 |
| NFR-007 | wydajność / bezpieczeństwo | Rozmiar pliku importu jest ograniczony. | ≤ 5 MB; `DATA_UPLOAD_MAX_MEMORY_SIZE` 6 MB. | spełnione | `forms.py:23`, `base.py:189` |
| NFR-008 | wydajność / bezpieczeństwo | Rozmiar XLSX po rozpakowaniu i liczba wierszy importu są ograniczone. | Wiersze: 100 w demo (`DEMO_IMPORT_MAX_ROWS`, Z-46), poza demo bez limitu. Po rozpakowaniu: bez limitu. Propozycja audytu: ≤ 50 MB po rozpakowaniu, ≤ 10 000 wierszy (PYT-02). | brak | `base.py:51`, `imports.py:123`, R4 |
| NFR-009 | wydajność / bezpieczeństwo | Liczba palet i ilości w jednym przyjęciu mają górną granicę. | Brak (`min_value` bez `max_value`); propozycja audytu: palety ≤ 500 (PYT-02). | brak | `forms.py:207-213`, R3, T16 |
| NFR-010 | wydajność | Listy HU, lokalizacji, stanów i raport lokalizacji są stronicowane. | 100 wierszy na stronę (`warehouse/pagination.py`) na listach HU, lokalizacji, stanów wg lokalizacji, raporcie lokalizacji i dzienniku logowań. | spełnione — US-015 | R5 |
| NFR-011 | wydajność | Eksport nie wyczerpuje pamięci przy dużej historii. | Wiersze budowane w pamięci, bez filtra dat. | częściowo | T9, pitfalls/views #9 |
| NFR-012 | bezpieczeństwo | Sesja wygasa po bezczynności. | 30 min (`DJANGO_SESSION_AGE=1800`), każde żądanie odświeża licznik. | spełnione | `base.py:185-186` |
| NFR-013 | bezpieczeństwo | Limit prób logowania. | 10 prób POST / 300 s / IP; licznik w pamięci procesu (3 workery → realnie ≈ 30). | częściowo | `demo.py:32-33`, T8, D-12 |
| NFR-014 | dostępność | Dostępność usługi. | Brak SLA. Healthcheck `/healthz` co 30 s (3 próby). Niedostępność publicznego demo = ryzyko wizerunkowe, nie utrata danych (Z-05). | do potwierdzenia (PYT-03) | `Dockerfile:51`, Z-05 |
| NFR-015 | zgodność | Środowisko skanera. | Przeglądarka telefonu lub kolektora z kamerą; wymaga HTTPS (kamera). Lista wspieranych przeglądarek i urządzeń niepodana. | do potwierdzenia (PYT-04) | D-08 |
| NFR-016 | użyteczność | Język i strefa czasu. | Interfejs po polsku; strefa `Europe/Warsaw`. | spełnione | `base.py:156-157` |
| NFR-017 | użyteczność | Skaner użyteczny w warunkach hali (telefon, rękawice). | Niezweryfikowane z użytkownikami. | do potwierdzenia (PYT-04) | AUDYT §1.3 pkt 7 |
| NFR-018 | utrzymanie (odtwarzalność) | Automatyczny backup bazy. | `pg_dump` → gzip co 24 h (`BACKUP_INTERVAL=86400`), retencja 7 dni (`BACKUP_KEEP_DAYS`), na tym samym hoście. | częściowo | `scripts/pg_backup.sh`, R9 |
| NFR-019 | dostępność | Cele odtwarzania. | RPO ≤ 24 h wynika z interwału backupu; RTO nie określony; odtworzenie nieprzećwiczone. | do potwierdzenia (PYT-03) | R9, COOLIFY.md §10 |
| NFR-020 | utrzymanie | Logi aplikacji. | JSON na stdout w produkcji (wartości wrażliwe maskowane), tekst w dev; dziennik audytowy także jako linia logu `warehouse.audit`. | spełnione | `base.py:195`, `config/log.py` |
| NFR-021 | utrzymanie | Powiadomienie o błędach 500. | E-mail `mail_admins` do `DJANGO_ADMINS` (Z-43): tekst bez haseł, tokenów i ciasteczek; 1 mail na błąd i ścieżkę / 10 min, 20 / h; w demo wyłączone. | spełnione (US-021, #23) | T15 |
| NFR-022 | utrzymanie | Pokrycie testami. | ≥ 80 % ogółem i ≥ 90 % dla `services.py` (Z-08); CI pilnuje progu (`fail_under`, `--include=warehouse/services.py --fail-under=90`), raport jako artefakt. Stan: 91 % / 92 %. | spełnione — US-019 | Z-08, DEC-3, T5 |
| NFR-023 | utrzymanie | Szybki feedback z testów. | `pytest` ≈ 25 s (421 testów, SQLite); CI uruchamia `pytest -q` (SQLite + PostgreSQL 16) — kilka minut na cały pipeline. | spełnione — US-019 | AUDYT §2.2, T6 |
| NFR-024 | utrzymanie | Statyczna analiza w CI. | CI: ruff, ruff format, mypy całego kodu z `check_untyped_defs` (kod aplikacji), bandit, semgrep. | spełnione — US-019 | T4 |
| NFR-025 | utrzymanie | Odtwarzalny build. | Locki `pip-compile` z hashami z jednego źródła (`requirements*.in`), obrazy przypięte digestem, akcje po SHA (ADR-0007). | spełnione — US-020 | T7 |
| NFR-026 | zgodność (integralność) | Spójność danych przy współbieżności. | Transakcje + `select_for_update` (D-05), `CheckConstraint` ilość ≥ 0, cały zestaw testów na PostgreSQL 16 w CI. | spełnione | D-05, docs/07, `tests_concurrency_pg.py` |
| NFR-027 | utrzymanie | Utrzymywalność kodu widoków. | pakiet `warehouse/views/`: 10 modułów po 76–257 linii (ADR-0006). | spełnione — US-017 | T2 |
| NFR-028 | zgodność | Platforma. | Django 5.2 LTS; PostgreSQL 16 (prod), SQLite (lokalnie); obraz dwuetapowy, non-root, `HEALTHCHECK`. | spełnione | AUDYT §2.1 |

---

## 3. Wymagania bezpieczeństwa i RODO (SEC)

Źródła: minimalne wymagania bezpieczeństwa z promptu PO (sekcja 6) i ustalenia audytu (R1–R10,
T1/T16, „poza listą”). Kryteria są sformułowane tak, by dało się je zamienić w test lub krok CI.
Kolumna „Status” = stan wg audytu.

### 3.1 Uwierzytelnianie i sesje

| SEC | Wymaganie | Kryterium (Given / When / Then) | Status (audyt) | US |
|---|---|---|---|---|
| SEC-001 | Hasła hashowane algorytmem odpornym na ataki sprzętowe (argon2 lub bcrypt). | **Given** nowe konto lub zmiana hasła; **When** zapis; **Then** hash w `auth_user.password` zaczyna się od `argon2$`; **Given** konto z hashem PBKDF2; **When** poprawne logowanie; **Then** hash zostaje podniesiony do argon2. | brak — PBKDF2 (R6, DEC-4) | US-008 |
| SEC-002 | Polityka haseł. | **Given** zakładanie konta; **When** hasło za krótkie, popularne, numeryczne lub podobne do loginu; **Then** odrzucone z komunikatem. Minimalna długość = domyślne 8 znaków Django (wartość docelowa — PYT-12). | spełnione — 4 walidatory Django | — (powiązane: US-041) |
| SEC-003 | Limit prób logowania per IP, wspólny dla wszystkich workerów. | **Given** 10 nieudanych POST `/login/` z jednego IP w 5 min; **When** 11. próba; **Then** 429 — niezależnie od `DEMO_MODE` i procesu gunicorna. | częściowo — działa per proces, ≈ 30 prób (R6, T8) | US-009 |
| SEC-004 | Limit prób logowania per konto. | **Given** N nieudanych prób na ten sam login z różnych IP w oknie; **When** kolejna próba (także z poprawnym hasłem); **Then** odmowa do końca okna, a konta innych użytkowników nie są blokowane. | brak (R6, T8) | US-009 |
| SEC-005 | Bezpieczne sesje: `HttpOnly`, `SameSite=Lax`, `Secure` w produkcji, wygasanie po bezczynności, czyszczenie wygasłych. | **Given** produkcja; **When** odpowiedź z logowania; **Then** `Set-Cookie` sesji ma `HttpOnly`, `Secure`, `SameSite=Lax`; **Given** sesja nieaktywna > 30 min; **When** żądanie; **Then** przekierowanie na `/login/`; **Given** wygasłe sesje w bazie; **When** `clearsessions`; **Then** usunięte. | częściowo — cookie i 30 min są, brak `clearsessions` i testów (R5, R7) | US-005, US-043 |
| SEC-006 | 2FA dla Administratora i `/admin/` (opcjonalnie wg promptu PO). | **Given** Administrator z włączonym TOTP; **When** hasło bez kodu; **Then** brak dostępu do widoków administracyjnych i `/admin/`; **When** poprawny kod; **Then** dostęp. | brak (R6, DEC-4) | US-010 |

### 3.2 Autoryzacja

| SEC | Wymaganie | Kryterium (Given / When / Then) | Status (audyt) | US |
|---|---|---|---|---|
| SEC-007 | Autoryzacja po stronie serwera na każdej trasie; zmiany stanu tylko metodą POST. | **Given** anonim; **When** GET dowolnej trasy chronionej; **Then** 302 na `/login/`; **Given** Podgląd; **When** POST `/przyjecie/`; **Then** 403; **Given** Operator; **When** GET `/uzytkownicy/`; **Then** 403. | spełnione — dekorator na 47 widokach i 16 endpointach skanera | US-007 (utrzymanie), US-017 (bez regresji) |
| SEC-008 | Test „brak dostępu” dla każdej roli na każdej trasie (macierz rola × trasa). | **Given** lista tras z `urls.py` z wymaganą rolą minimalną; **When** test przechodzi po rolach anonim / Podgląd / Operator / Administrator; **Then** rola poniżej minimum dostaje 302 lub 403, nigdy 200 ani 5xx; **Given** nowa trasa bez wpisu w macierzy; **Then** test jest czerwony. | częściowo — ≈ 35 asercji, bez macierzy (AUDYT Zał. A) | US-007 |
| SEC-009 | Administrator (nie superuser) nie modyfikuje konta superusera. | **Given** Administrator bez `is_superuser`; **When** POST `/uzytkownicy/<pk superusera>/` ze zmianą hasła lub bez `is_active`; **Then** 403, konto superusera bez zmian. | spełnione — US-001 (`tests_security.SuperuserProtectionTests`) | US-001 |
| SEC-010 | Konta demo chronione przed zmianą hasła, roli i statusu; `/admin/` wyłączony w demo. | **Given** `DEMO_MODE`; **When** POST edycji konta demo; **Then** 403 „Konta demo są chronione”; **When** GET `/admin/`; **Then** 404. | spełnione | — (powiązane: US-041) |
| SEC-011 | Brak separacji danych między użytkownikami (jeden magazyn, jedna firma) — świadoma decyzja. | **Given** zalogowany użytkownik dowolnej roli; **When** otwiera dowolną paletę lub WZ; **Then** widzi ją (zamierzone). Przy drugim magazynie wymaga filtrowania w każdym querysecie. | do potwierdzenia (Z-06) | — |

### 3.3 Walidacja wejścia i wyjścia

| SEC | Wymaganie | Kryterium (Given / When / Then) | Status (audyt) | US |
|---|---|---|---|---|
| SEC-012 | Dostęp do bazy tylko przez ORM; brak surowego SQL z danych użytkownika. | **Given** kod aplikacji; **When** bandit i wyszukanie `.raw(`, `.extra(`, `cursor.execute`; **Then** brak trafień poza `LOCK TABLE` z nazw modeli w `seed_demo.py`. | spełnione | — |
| SEC-013 | Escapowanie wyjścia w szablonach i JS skanera. | **Given** materiał o nazwie `<script>alert(1)</script>`; **When** strona listy, szczegółów i ekrany skanera; **Then** tekst jest wyescapowany, bez wykonania. | spełnione — brak `\|safe`, `mark_safe` (test do napisania) | US-043 (test) |
| SEC-014 | Ochrona CSRF na wszystkich żądaniach zmieniających stan (formularze i API skanera). | **Given** klient z `enforce_csrf_checks=True`; **When** POST bez tokenu na endpoint zmieniający stan; **Then** 403; **When** z nagłówkiem `X-CSRFToken`; **Then** przyjęty. | spełnione — brak `csrf_exempt` (test do napisania) | US-043 (test) |
| SEC-015 | Walidacja zakresów i długości wejścia w formularzach, API skanera i importach. | **Given** liczba palet lub ilość powyżej granicy, kod > 40 znaków, numer HU > 30, wartość `1e999`; **When** formularz, API lub import; **Then** błąd pola lub wiersza, nigdy 500 ani `DataError`, bez częściowego zapisu. | brak (R3, T16) | US-002, US-013 |
| SEC-016 | Neutralizacja formuł w eksportach CSV i XLSX. | **Given** materiał o nazwie `=1+1`; **When** eksport CSV lub XLSX; **Then** komórka zaczyna się od `'`. | spełnione — XLSX bez testu (exports.py 53 %) | US-043 (test XLSX) |
| SEC-017 | Nagłówki odpowiedzi z danych użytkownika kodowane bezpiecznie (`Content-Disposition`). | **Given** kod lokalizacji z `"` lub znakiem nowej linii; **When** pobranie etykiety; **Then** 200 z poprawnym nagłówkiem, nie 500 `BadHeaderError`. | brak (T16, „poza listą”) | US-013 |

### 3.4 Upload i zasoby

| SEC | Wymaganie | Kryterium (Given / When / Then) | Status (audyt) | US |
|---|---|---|---|---|
| SEC-018 | Limit rozmiaru uploadu. | **Given** plik > 5 MB; **When** wysłany do dowolnego importu; **Then** „Plik jest za duży (maks. 5 MB)”. | spełnione (test do napisania) | US-043 (test) |
| SEC-019 | Walidacja typu po zawartości, ochrona przed bombą dekompresyjną i XML, uszkodzony plik = komunikat. | **Given** plik `.xlsx` niebędący ZIP-em lub ZIP z `sharedStrings.xml` powyżej limitu po rozpakowaniu; **When** dowolny import; **Then** komunikat „Plik nie jest poprawnym XLSX” lub odmowa, bez 500 i bez skoku pamięci workera. | brak (R4, T1) | US-004 |
| SEC-020 | Pliki uploadu: losowe nazwy, poza katalogiem publicznym. | **Given** import pliku; **When** przetworzony; **Then** plik nie trafia do katalogu publicznego ani `MEDIA_ROOT` (brak pól plikowych w modelach); pliki > 2,5 MB Django buforuje chwilowo w katalogu tymczasowym pod losową nazwą i usuwa po żądaniu. Gdyby trwały zapis się pojawił — losowa nazwa i katalog poza webrootem. | spełnione — brak trwałego zapisu plików | — |
| SEC-021 | Ochrona zasobów przed nadużyciem (DoS aplikacyjny): palety, import, etykiety, listy. | **Given** Operator; **When** POST `/przyjecie/` z liczbą palet powyżej limitu; **Then** odrzucone przed zapisem; **Given** Podgląd; **When** GET `/lokalizacje/etykiety/` dla > limit lokalizacji; **Then** komunikat „Zawęź filtr”. | brak (R3, R4, R5) | US-002, US-004, US-015 |

### 3.5 Transport i nagłówki

| SEC | Wymaganie | Kryterium (Given / When / Then) | Status (audyt) | US |
|---|---|---|---|---|
| SEC-022 | HTTPS wymuszony; HSTS skuteczny. | **Given** produkcja; **When** GET przez HTTP (poza `/healthz`); **Then** przekierowanie na HTTPS; odpowiedź zawiera `Strict-Transport-Security` (≥ 1 rok albo bez `preload`). | częściowo — HSTS 30 dni z `preload` (R8) | US-011 |
| SEC-023 | `X-Content-Type-Options: nosniff`, `Referrer-Policy: same-origin`, `X-Frame-Options: DENY`. | **Given** produkcja; **When** dowolna odpowiedź HTML; **Then** trzy nagłówki obecne. | spełnione (`check --deploy`; test do napisania) | US-043 (test) |
| SEC-024 | Content-Security-Policy bez `unsafe-inline` dla skryptów. | **Given** produkcja; **When** odpowiedź HTML; **Then** CSP z nonce; szablony bez atrybutów `on*=`; skaner z kamerą działa. | brak (R8) | US-011 |
| SEC-025 | Permissions-Policy. | **Given** produkcja; **When** odpowiedź HTML; **Then** `Permissions-Policy` zawiera `camera=(self)` i `geolocation=()`. | brak (R8) | US-011 |

### 3.6 Sekrety, konfiguracja, łańcuch dostaw

| SEC | Wymaganie | Kryterium (Given / When / Then) | Status (audyt) | US |
|---|---|---|---|---|
| SEC-026 | Sekrety wyłącznie w zmiennych środowiskowych; start odrzuca słabe i zaślepkowe wartości. | **Given** brak `DJANGO_SECRET_KEY`, `DJANGO_SUPERUSER_PASSWORD` lub `POSTGRES_PASSWORD`; **When** `docker compose config`; **Then** błąd (nie wartość domyślna); **Given** klucz `zmien-mnie-w-produkcji`, zaślepka lub < 50 znaków; **When** start produkcji; **Then** `ImproperlyConfigured`. | częściowo — repo bez sekretów, ale domyślne `zmien-mnie…`, `admin`, `wms` przechodzą (R2) | US-003 |
| SEC-027 | Konta demo nie powstają poza `DEMO_MODE` z działającym hasłem. | **Given** brak `DEMO_MODE`; **When** `manage.py seed_demo`; **Then** komenda odmawia (domyślnie) i nie tworzy kont `demo_operator` / `demo_podglad` z hasłem `demo1234`. | brak (R2) | US-003 |
| SEC-028 | Skan sekretów i SAST blokujące na PR (gitleaks, bandit). | **Given** PR z wzorcem sekretu lub problemem bandit ≥ średni; **When** CI; **Then** job czerwony i blokuje merge. | częściowo — skany raz w miesiącu, doradcze (R10, Z-10); naprawa w toku: ADR-0001/CI | US-006 |
| SEC-029 | Zależności bez znanych podatności: pip-audit blokujący na PR, Dependabot. | **Given** PR z zależnością z CVE; **When** CI; **Then** job pip-audit czerwony; **Given** nowa wersja zależności; **Then** Dependabot otwiera PR. | częściowo — `\|\| true`, brak Dependabota (R10); naprawa w toku: ADR-0001/CI | US-006, US-020 |
| SEC-030 | Obraz kontenera: non-root, kod aplikacji niezapisywalny przez użytkownika runtime. | **Given** działający kontener; **When** `app` próbuje zapisać plik w `/app/warehouse/`; **Then** „Permission denied”. | częściowo — non-root jest, `/app` zapisywalny („poza listą”) | US-037 |
| SEC-031 | CI z minimalnymi uprawnieniami tokenu i przypiętymi narzędziami. | **Given** `ci.yml`; **Then** top-level `permissions: contents: read`; narzędzia bezpieczeństwa w przypiętych wersjach, bez `curl … \| sh`. | brak (R10); naprawa w toku: ADR-0001/CI | US-006, US-020 |

### 3.7 Logi, audyt, RODO

| SEC | Wymaganie | Kryterium (Given / When / Then) | Status (audyt) | US |
|---|---|---|---|---|
| SEC-032 | Logi bez haseł i tokenów. | **Given** żądanie POST z polem `password` lub tokenem; **When** błąd 500 jest logowany; **Then** log JSON nie zawiera ich wartości; **Given** nieudane logowanie z nieistniejącym loginem; **Then** pole „wpisany login” jest przycięte (PYT-09). | spełnione — US-022 (`config/log.py`, `LogRedactionTests`) | US-022 |
| SEC-033 | Dziennik audytowy akcji administracyjnych i odmów. | **Given** Administrator zmienia rolę, hasło lub status konta; **When** zapis lub odmowa (np. 403 z SEC-009); **Then** wpis: aktor, cel, akcja, czas, wynik — bez wartości haseł. | spełnione — US-022 (`AuditEvent`, ADR-0008) | US-022 |
| SEC-034 | Niezmienność śladu audytowego (ruchy, dziennik logowań). | **Given** superuser w `/admin/`; **When** próba edycji lub usunięcia `StockMovement` / `LoginEvent`; **Then** niemożliwa (tylko odczyt). | do potwierdzenia (PYT-11) — dziś superuser może (R1) | — |
| SEC-035 | RODO — minimalizacja danych w dzienniku logowań. | **Given** `DEMO_MODE`; **When** wejście `/demo/`; **Then** `LoginEvent.ip` pusty; **Given** user-agent dłuższy niż ustalony limit lub polityka „bez UA”; **Then** zgodnie z decyzją PO (PYT-09). | brak (R7) | US-005 |
| SEC-036 | RODO — retencja: dziennik logowań 90 dni (Z-09, DEC-5). | **Given** `LoginEvent` starsze niż 90 dni i nowsze; **When** `manage.py purge_login_events`; **Then** starsze usunięte, nowsze zostają. | brak (R7) | US-005 |
| SEC-037 | RODO — rejestr czynności, podstawa prawna, klasyfikacja danych. | **Given** `RODO.md` v0.1; **Then** dla każdej tabeli z danymi osobowymi podaje cel, podstawę (art. 6 ust. 1 lit. f — Z-09), retencję, odbiorców i właściciela. | brak (R7) | US-023 |
| SEC-038 | RODO — prawa osób: dostęp/eksport i usunięcie lub anonimizacja danych osoby. | **Given** żądanie osoby; **When** Administrator wykonuje procedurę; **Then** dane osoby (konto, `LoginEvent`, `created_by`) są wydane lub zanonimizowane, a ruchy magazynowe zachowane. Procedura ręczna czy narzędzie — PYT-10. | brak (R7) | US-023, US-027 |

### 3.8 Odtwarzalność, demo, proxy

| SEC | Wymaganie | Kryterium (Given / When / Then) | Status (audyt) | US |
|---|---|---|---|---|
| SEC-039 | Backup: kopia off-site, szyfrowana, z testem odtworzenia i alertem. | **Given** backup nocny; **When** zakończony; **Then** szyfrowana kopia jest poza hostem bazy; **When** miesięczny test odtworzenia; **Then** baza wstaje na środowisku testowym (zapis w RUNBOOK); **Given** brak świeżej kopii powyżej progu; **Then** alert. | częściowo — lokalny, nieszyfrowany, nieprzećwiczony (R9) | US-012 |
| SEC-040 | Limit żądań na anonimowych wejściach demo (`/demo/`, `/login/demo/`). | **Given** `DEMO_MODE`; **When** > K żądań w oknie W z jednego IP; **Then** 429 bez nowej sesji i bez `LoginEvent`. | spełnione — wejścia US-005; zapisy i limit obiektów US-016 | US-005, US-016 |
| SEC-041 | IP klienta tylko od zaufanego proxy i zwalidowany. | **Given** `TRUSTED_PROXY_COUNT=1` i `X-Forwarded-For` z wartością niebędącą IP; **When** logowanie; **Then** fallback na `REMOTE_ADDR`, bez `DataError`. | spełnione — `ClientIPTests`, `ClientIPLoginTests` (US-014) | US-014 |
| SEC-042 | Zaakceptowane wyjątki bezpieczeństwa zapisane w rejestrze z datą przeglądu. | **Given** `RYZYKA.md`; **Then** każdy wyjątek (publiczny Operator w demo, logowanie GET `/demo/`, jawne hasło demo, brak 2FA do wdrożenia, backup lokalny) ma uzasadnienie, właściciela, datę przeglądu i akceptację PO. | brak (AUDYT §3.5) | US-024 |

---

## 4. Reguły biznesowe (BR)

Reguły z [docs/02](../02-proces.md#punkty-decyzyjne) (punkty decyzyjne i założenia procesu),
[docs/06](../06-decyzje.md) i [docs/07](../07-ograniczenia.md). Zmiana reguły = zmiana FR i testu.

| BR | Reguła (1 linia) | Źródło | FR |
|---|---|---|---|
| BR-001 | Ilość na jednej palecie ≤ limit materiału (jeśli ustawiony). | docs/02, `services.py:114` | FR-002 |
| BR-002 | Pojemność lokalizacji jest informacyjna — przekroczenie nie blokuje odłożenia, tylko ostrzega. | docs/02, `location_over_capacity` | FR-008 |
| BR-003 | Wydanie po materiale wymaga pełnej dostępnej ilości; tryb „z brakami” wydaje, ile jest. | docs/02, `services.py:381,407` | FR-013 |
| BR-004 | Dobór palet: PICKING przed ZAPAS, potem najkrótsza data ważności (FEFO), potem najstarsze przyjęcie (FIFO). | docs/02, `services.py:305` | FR-010 |
| BR-005 | Wydanie z rampy: gdy na regałach brakuje, system bierze też palety „Do ułożenia” (bez lokalizacji), na końcu kolejki. | docs/02, docs/07 „reguła celowa”, `services.py:315` | FR-010 |
| BR-006 | Łączenie palet: ten sam materiał, zgodna partia, cel niepusty. | docs/02, `services.py:251-269` | FR-019 |
| BR-007 | Spis z natury: różnica policzone ≠ stan → korekta z powodem „Spis z natury”; na czas spisu magazyn jest zamrożony. | docs/02, D-07, `services.py:560` | FR-020 |
| BR-008 | Korekta pustej palety z 0 na więcej przywraca status „Do ułożenia” (bez lokalizacji). | docs/02, `services.py:212` | FR-018 |
| BR-009 | Wysyłka bez pakowania jest dozwolona — pakowanie to krok opcjonalny. | docs/02, D-06 | FR-016 |
| BR-010 | Zwrotów nie ma — proces kończy się na wysyłce (zwroty i anulowanie WZ poza zakresem). | docs/02, docs/01 | — (US-045) |
| BR-011 | Każda zmiana stanu przechodzi przez warstwę usług, w transakcji, razem z zapisem ruchu. | D-05 | FR-021 |
| BR-012 | Skaner przy FEFO ostrzega (nie blokuje); paletę wskazaną w pozycji WZ egzekwuje twardo. | docs/05 W-11, W-25 | FR-011, FR-025 |
| BR-013 | Numer WZ liczony od nowa każdego dnia (`WZ<data>-NNN`). | D-03 | FR-021 |
| BR-014 | Import stanów z ilością 0 zostaje, z ostrzeżeniem o takich paletach i o przekroczonej pojemności. | D-09 | FR-005 |
| BR-015 | Numery palet bez rozróżniania wielkości liter we wszystkich ścieżkach. | D-10 | FR-003 |
| BR-016 | Paleta może być naraz tylko w jednym otwartym arkuszu spisu; nowy arkusz pomija palety z otwartego. | D-13 | FR-020 |

---

## 5. Otwarte pytania do PO

Maksymalnie 5 naraz zadaje [PM]; tu pełna lista, uporządkowana wagą. „Domyślnie” = co przyjmujemy
do czasu odpowiedzi (pozycje z numerem Z-nn są w [ZALOZENIA.md](ZALOZENIA.md)).

| PYT | Pytanie | Dotyczy | Domyślnie |
|---|---|---|---|
| PYT-01 | Jaka jest docelowa skala za 12–24 miesiące (palety, operatorzy, ruchy)? | NFR-001 | ≈ 200 palet, 2 operatorów (docs/01) |
| PYT-02 | Jakie limity wejścia: palet na przyjęcie (audyt: „np. 500”), maks. ilość, palet na plik importu, wierszy na plik (audyt: „np. 10 000”), rozmiar po rozpakowaniu (audyt: „np. 50 MB”)? | NFR-008, NFR-009, SEC-015, SEC-019, US-002, US-004 | wartości z audytu jako start; reszta oznaczona symbolem w kryteriach |
| PYT-03 | Czy jest wymagany SLA / okno serwisowe, czas odpowiedzi, RPO i RTO? | NFR-002, NFR-014, NFR-019 | brak SLA; RPO ≤ 24 h |
| PYT-04 | Jakie urządzenia i przeglądarki ma wspierać skaner; czy robimy test użyteczności w hali? | NFR-015, NFR-017, US-035 | dowolny telefon z kamerą i HTTPS |
| PYT-05 | `seed_demo` bez `DEMO_MODE`: odmowa czy konta z nieużywalnym hasłem (`set_unusable_password()`)? | SEC-027, US-003 | odmowa |
| PYT-06 | Administrator wchodzący na konto superusera: 403 także na GET czy podgląd tylko do odczytu? Czy zmiana cudzego hasła wymaga potwierdzenia własnym hasłem? | SEC-009, US-001 | 403 na GET i POST; bez potwierdzenia hasłem |
| PYT-07 | Limit per konto: blokada czasowa (ryzyko zablokowania cudzego konta) czy rosnące opóźnienie? Jakie N i okno? | SEC-004, US-009 | blokada czasowa, okno 5 min |
| PYT-08 | Czy wdrażamy 2FA, dla kogo (Administrator / wszyscy / tylko `/admin/`) i kiedy? | SEC-006, US-010, DEC-4 | **odpowiedziane 2026-10-16:** wdrażamy (US-010); tryb dobrowolny dla Administratora — Z-39 do potwierdzenia |
| PYT-09 | Dziennik logowań: czy zapisywać user-agent (skracać / wcale)? Jak traktować „wpisany login”, którego nie ma w bazie? Czy retencja kopii zapasowych (7 / 30 dni) wystarcza wobec prawa do usunięcia? | SEC-032, SEC-035, US-005, US-022 | retencja 90 dni (Z-09); UA bez zmian do decyzji |
| PYT-10 | Kto jest administratorem danych, czy jest IOD? Czy prawa osób obsługujemy procedurą ręczną, czy narzędziem? Czy kolumna „Kto” w eksporcie ruchów jest potrzebna? | SEC-037, SEC-038, US-023, US-027 | procedura ręczna w `RODO.md` |
| PYT-11 | Czy `/admin/` Django ma pozwalać superuserowi edytować i usuwać ruchy (`StockMovement`) oraz dziennik logowań? | SEC-034 | bez zmian do decyzji |
| PYT-12 | Minimalna długość hasła: zostaje 8 znaków (domyślne Django)? | SEC-002 | 8 |
| PYT-13 | Trivy: Z-10 mówi „tygodniowo, doradczo”, audyt R10 — „blokujący dla CRITICAL”, a robocze `ci.yml` (ADR-0001, w toku) blokuje HIGH/CRITICAL z poprawką. Które obowiązuje i czy zaktualizować Z-10? | SEC-028, US-006, ADR-0001 | wariant z ADR-0001 po akceptacji PO |
| PYT-14 | FEFO przy skanerze: zostaje ostrzeżenie (wdrożone), czy ma być odmowa (docs/05: „ostrzeżeniem lub odmową”)? | FR-011, BR-012 | ostrzeżenie |
| PYT-15 | Kanał alertów o błędach 500 (Sentry / GlitchTip / `ADMINS` / alert Coolify)? | NFR-021, US-021 | do decyzji |
| PYT-16 | Backup off-site: gdzie (S3 / B2 / inny host), retencja (audyt: 30 dni), próg alertu przy braku kopii? | SEC-039, US-012 | **odpowiedziane 2026-10-16:** rclone (dowolny S3/SFTP), age z kluczem offline u PO, heartbeat (~26 h), off-site 30 dni |
| PYT-17 | Czy pozycje „poza zakresem” (ERP, zwroty / anulowanie WZ, blokada po terminie, rezerwacje, wiele magazynów, atrybuty logistyczne) pozostają poza zakresem? | US-044…US-049 | tak (docs/01) |
| PYT-18 | Czy zestaw mierników M-01…M-06 z [WIZJA.md](WIZJA.md) jest właściwy i kto zmierzy punkt odniesienia (pytania 2–4 w WIZJA)? | US-036 | M-01…M-06 „do potwierdzenia”, baza: brak danych |
| PYT-19 | Które wyjątki z AUDYT §3.5 akceptujesz (publiczny Operator w demo, brak 2FA do wdrożenia, backup lokalny)? Czy cel repo to portfolio, wdrożenie, czy oba (Z-04)? | SEC-042, US-024 | Z-04, Z-05 |
| PYT-20 | Formularz „Nowy użytkownik” podpowiada rolę Operator, a konto bez profilu dostaje Podgląd. Czy podpowiedź ma być Podgląd (najmniejsze uprawnienia)? | FR-023 | bez zmian do decyzji |
| PYT-21 | Czy użytkownik ma sam zmieniać lub odzyskiwać hasło, zamiast ustawiać je przez Administratora, który je zna (PROCESY L-01, Z-16)? Czy blokada ruchów na czas spisu ma być techniczna (PROCESY L-02, Z-13)? | US-041, US-042 | stan obecny: hasło ustawia Administrator; zamrożenie organizacyjne |
| PYT-22 | Demo: jakie parametry limitera wejść i ścieżek operatora (K żądań / W sekund), jaki limit obiektów w demo (L_DEMO) i czy reset danych demo przenosimy wyłącznie do harmonogramu (DEC-6)? | SEC-040, US-005, US-016 | **odpowiedź PO 2026-10-16:** wejścia 10 / 300 s (Z-37); zapisy 60 / 300 s; L_DEMO 2000 HU / 500 lokalizacji; reset tylko z harmonogramu (Z-41) |

---

## 6. Luki w samych wymaganiach (do domknięcia przez BA)

- Funkcje bez FR w docs/05: pulpit, ręczny słownik materiałów i lokalizacji, import lokalizacji
  (`LocationImportTests`), termin dostawy palety (Administrator), tryb demo z wycieczką. Propozycja:
  nowe FR po potwierdzeniu przez PO (nie dopisuję ich bez pytania — Z-03).
- Luki procesowe z [PROCESY.md](PROCESY.md) §7 (L-01 zmiana hasła, L-02 blokada spisu) nie są wymaganiami, dopóki PO nie
  zdecyduje (PYT-21; Z-13, Z-16) — trafiły do backlogu jako Could (US-041, US-042).
- FR-007 i FR-009 nie mają dedykowanego testu (szczegóły: [SLEDZENIE.md](SLEDZENIE.md) §6).
- Kryteria docs/05 były opisowe; w tym dokumencie zapisano je w G/W/T — przy rozbieżności
  rozstrzyga docs/05 do czasu akceptacji PO.

## Historia zmian

| Wersja | Data | Zmiana |
|---|---|---|
| 0.1 | 2026-10-16 | Pierwszy szkic: 26 FR (G/W/T), NFR, SEC, BR, pytania do PO. |
