# Macierz śledzenia

| | |
|---|---|
| Wersja | 0.1 |
| Data | 2026-10-16 |
| Status | szkic — do akceptacji Product Ownera |
| Właściciel | [BA] |

Macierz łączy **wymaganie** ([WYMAGANIA.md](WYMAGANIA.md): FR, NFR, SEC) → **historyjkę**
([HISTORYJKI.md](HISTORYJKI.md): US) → **test** (`warehouse/tests*.py`) → **PR**. Jest odpowiedzią na lukę
z [AUDYTU §1.2](../AUDYT.md): brak powiązania wymaganie → historyjka → PR. Stan odniesienia testów:
226 funkcji testowych w 12 plikach `warehouse/tests*.py` (AUDYT §2.2).

## 1. Legenda

| Kolumna / wartość | Znaczenie |
|---|---|
| **US** | Historyjka, która **zmienia lub domyka** wymaganie. `—` = brak historyjki (wymaganie spełnione, bez planowanej zmiany). W tabeli FR: historyjki, które wpłyną na zachowanie wdrożonego wymagania. |
| **Test (istniejący)** | Nazwa w formacie Klasa.test_metoda albo sama klasa (wszystkie jej testy), w odwrotnych apostrofach, z `warehouse/tests*.py`; nazwy sprawdzono automatycznie 2026-10-16 (§6). Plik wynika z klasy — tabela w §2.1. |
| `brak — do napisania` | Wymaganie bez testu automatycznego; trafia do §7 (luki). |
| `n/d` | Wymaganie weryfikowane inaczej niż testem jednostkowym (CI, przegląd dokumentu, test ręczny). |
| **PR** | `historyczny (przed procesem)` — wdrożone przed wprowadzeniem procesu (PR-y #1–#22 bez śladu wymagań). `#23` — PR audytu, w którym wykryto lukę; PR z naprawą: `—` do czasu realizacji US. `—` — brak. |

### 1.1 Gdzie leżą klasy testowe użyte w macierzy

| Plik | Klasy |
|---|---|
| `tests.py` | `SplitQuantityTests`, `HUNumberingTests`, `ReceiveTests`, `AllocationTests`, `PickingTests`, `CorrectionTests`, `PickingProTests`, `ReceiptImportTests`, `StockImportTests`, `ScannerTests`, `RepackTests`, `WebInventoryTests`, `StocktakeTests`, `WebRepackTests`, `PdfAndViewTests`, `UserManagementTests`, `RoleTests`, `ViewAccessTests`, `SecurityTests`, `HardeningTests`, `AuditFixTests`, `ViewLayerTests` |
| `tests_services_fixes.py` | `SplitQuantityRemainderTests`, `ReceiveFormMatchesSplitTests`, `LocationOverCapacityTests`, `ExecuteIssueDocumentDoubleClickTests`, `AdjustHuQuantityTests`, `FirstPickableHuTests`, `CorrectionReasonRequiredTests` |
| `tests_views_fixes.py` | `HUCorrectionReasonTests`, `WebInventoryReasonTests`, `AllocateCapacityWarningTests`, `PermissionDeniedPageTests` |
| `tests_scanner_fixes.py` | `ApiPickSpecificHuTests`, `ApiPickFefoWarningTests`, `ApiInventoryReasonTests`, `ApiAllocateCapacityWarningTests` |
| `tests_open_decisions.py` | `StockImportWarningsTests`, `HULabelsLimitTests`, `ClientIPTests`, `StocktakeOverlapTests`, `HUNumberCaseTests` |
| `tests_demo.py` | `SeedDemoTests`, `DemoModeViewTests`, `AdminHiddenInDemoTests` |
| `tests_demo_entry.py` | `DemoStartTests`, `DemoResetTests`, `DemoEntryOffTests` |
| `tests_recruiter.py` | `DemoLoginTests`, `DemoImportLimitTests`, `DemoAccountPermissionTests` |
| `tests_concurrency_pg.py` | `ConcurrentIssueTests` (tylko PostgreSQL) |

---

## 2. Wymagania funkcjonalne (FR)

Wszystkie FR są wdrożone: PR = `historyczny (przed procesem)`. Wyjątki — poprawki z #10 (`fix/code-gaps`):
FR-008, FR-011, FR-025, FR-026 (domknięte po wdrożeniu pierwotnym).

| FR | W-id | US (zmiana) | Test (istniejący) | PR |
|---|---|---|---|---|
| FR-001 | W-01 | US-002, US-013 | `ReceiveTests.test_receive_creates_hus_and_movements`; `SplitQuantityTests`; `SplitQuantityRemainderTests` | historyczny (przed procesem) |
| FR-002 | W-02 | — | `ReceiveTests.test_receive_respects_max_per_pallet`; `ReceiveFormMatchesSplitTests.test_receive_10_on_4_pallets_with_max_3_succeeds` | historyczny (przed procesem) |
| FR-003 | W-03 | — | `HUNumberingTests.test_sequential_unique_numbers`; `HardeningTests.test_save_with_unique_number_retries_on_collision` | historyczny (przed procesem) |
| FR-004 | W-04 | US-013 | `PdfAndViewTests.test_hu_label_with_all_fields_single_page`; `PdfAndViewTests.test_location_label_pdf` | historyczny (przed procesem) |
| FR-005 | W-05 | US-002, US-004, US-013 | `ReceiptImportTests.test_import_receipts_creates_hus`; `ReceiptImportTests.test_import_receipts_unknown_material`; `StockImportTests`; `StockImportWarningsTests` | historyczny (przed procesem) |
| FR-006 | W-06 | — | `AllocationTests.test_allocate_sets_location_and_status`; `ScannerTests.test_api_allocate`; `ViewLayerTests.test_hu_allocate_view` | historyczny (przed procesem) |
| FR-007 | W-07 | US-043 | **brak — do napisania** (ruch PRZESUNIĘCIE z polami z / do) | historyczny (przed procesem) |
| FR-008 | W-08 | — | `AuditFixTests.test_allocate_over_capacity_succeeds_but_flagged`; `AllocateCapacityWarningTests.test_over_capacity_allocation_succeeds_with_warning`; `ApiAllocateCapacityWarningTests.test_allocate_over_capacity_warns_but_succeeds`; `LocationOverCapacityTests` | historyczny (przed procesem; #10) |
| FR-009 | W-09 | US-043 | **brak — do napisania** (odmowa alokacji palety „Pusty”) | historyczny (przed procesem) |
| FR-010 | W-10 | — | `PickingTests.test_fefo_prefers_earliest_expiry`; `PickingTests.test_picking_location_priority`; `FirstPickableHuTests` | historyczny (przed procesem) |
| FR-011 | W-11 | — | `ApiPickFefoWarningTests` | historyczny (przed procesem; #10) |
| FR-012 | W-12 | — | `PickingTests.test_overpick_blocked`; `AuditFixTests.test_hu_quantity_check_constraint` | historyczny (przed procesem) |
| FR-013 | W-13 | — | `PickingProTests.test_full_execution_raises_on_shortage`; `PickingProTests.test_partial_execution_closes_with_shortage` | historyczny (przed procesem) |
| FR-014 | W-14 | — | `AuditFixTests.test_execute_rejects_specific_hu_wrong_material` | historyczny (przed procesem) |
| FR-015 | W-15 | — | `PickingTests.test_pick_to_zero_marks_empty_and_frees_location` | historyczny (przed procesem) |
| FR-016 | W-16 | — | `PickingProTests.test_pack_and_ship_flow`; `PickingProTests.test_pack_requires_realized`; `AuditFixTests.test_cannot_add_line_to_packed_document` | historyczny (przed procesem) |
| FR-017 | W-17 | `ScannerTests.test_document_pick_completes_order`; `ScannerTests.test_document_pick_rejects_wrong_material`; `ConcurrentIssueTests` (PostgreSQL); `CompleteIfPickedTests` (US-018) | `ScannerTests.test_document_pick_completes_order`; `ScannerTests.test_document_pick_rejects_wrong_material`; `ConcurrentIssueTests` (PostgreSQL) | historyczny (przed procesem) |
| FR-018 | W-18 | US-013 | `CorrectionTests.test_correction_logs_movement`; `WebInventoryTests.test_web_inventory_add`; `AdjustHuQuantityTests`; `AuditFixTests.test_correct_reactivates_emptied_hu` | historyczny (przed procesem) |
| FR-019 | W-19 | — | `RepackTests`; `WebRepackTests` | historyczny (przed procesem) |
| FR-020 | W-20 | US-030, US-038, US-042 | `StocktakeTests`; `StocktakeOverlapTests` | historyczny (przed procesem) |
| FR-021 | W-21 | US-022 (powiązane) | `ReceiveTests.test_receive_creates_hus_and_movements` | historyczny (przed procesem) |
| FR-022 | W-22 | US-028 | `AuditFixTests.test_movement_export_respects_type_filter`; `HardeningTests.test_csv_export_neutralizes_formula_injection`; `HardeningTests.test_export_rejects_unknown_format` | historyczny (przed procesem) |
| FR-023 | W-23 | US-001, US-007 | `ViewAccessTests.test_viewer_role_forbidden_on_receive`; `RoleTests.test_new_user_default_viewer`; `PermissionDeniedPageTests.test_viewer_gets_403_with_menu` | historyczny (przed procesem) |
| FR-024 | W-24 | US-001, US-005, US-022 | `SecurityTests`; `UserManagementTests.test_cannot_deactivate_self` | historyczny (przed procesem) |
| FR-025 | W-25 | — | `ApiPickSpecificHuTests` | historyczny (przed procesem; #10) |
| FR-026 | W-26 | — | `CorrectionReasonRequiredTests`; `HUCorrectionReasonTests`; `WebInventoryReasonTests`; `ApiInventoryReasonTests` | historyczny (przed procesem; #10) |

---

## 3. Wymagania niefunkcjonalne (NFR)

PR `#23` = luka lub wymaganie wykryte w audycie (naprawa: `—`). `historyczny` = wartość wdrożona przed procesem
(zapis w WYMAGANIACH pochodzi z #23).

| NFR | US | Test (istniejący) | PR |
|---|---|---|---|
| NFR-001 | US-040 | brak — do napisania (brak testu obciążeniowego; PYT-01) | #23 |
| NFR-002 | US-040, US-039 | brak — do napisania (brak pomiarów; PYT-03) | #23 |
| NFR-003 | US-002, US-004, US-015 | brak — do napisania (limit czasu to konfiguracja gunicorna) | #23 |
| NFR-004 | US-028 | brak — do napisania (`ViewLayerTests.test_movement_list_renders_and_filters` nie sprawdza limitu 500) | historyczny (przed procesem) |
| NFR-005 | — | `HULabelsLimitTests` | historyczny (przed procesem; #13) |
| NFR-006 | US-015 | `tests_pagination.LocationLabelsLimitTests` | #23 |
| NFR-007 | US-004, US-043 | brak — do napisania (limit 5 MB bez testu) | historyczny (przed procesem) |
| NFR-008 | US-004 | `DemoImportLimitTests`; `tests_imports_hardening.RowLimitTests` (poza demo) | #23 |
| NFR-009 | US-002, US-013 | `tests_input_validation.ImportNumberTests`, `ImportLengthTests` | #23 |
| NFR-010 | US-015 | `tests_pagination.PaginationTests`, `ReportQueryCountTests`; `SecurityTests.test_login_log_pagination` | #23 |
| NFR-011 | US-028 | brak — do napisania | #23 |
| NFR-012 | US-005, US-043 | brak — do napisania (wygasanie sesji po 30 min) | historyczny (przed procesem) |
| NFR-013 | US-009 | `DemoModeViewTests.test_login_rate_limit`; `DemoModeViewTests.test_rate_limit_also_without_demo_mode` | historyczny (przed procesem; #13) |
| NFR-014 | US-021, US-012 | `AuditFixTests.test_healthz_public_and_ok` (tylko endpoint healthcheck) | #23 |
| NFR-015 | US-035 | n/d — test ręczny na urządzeniu | #23 |
| NFR-016 | — | brak — do napisania (język i strefa czasu) | historyczny (przed procesem) |
| NFR-017 | US-035 | n/d — test z użytkownikami | #23 |
| NFR-018 | US-012 | `tests_backup_script.BackupScriptTests` (8); `shellcheck` w CI | #23 |
| NFR-019 | US-012 | ćwiczenie odtworzenia w CI (job 3b); RUNBOOK §5.4 (miesięcznie, ręcznie) | #23 |
| NFR-020 | US-022 | `tests_audit_log.LogRedactionTests` | historyczny (przed procesem) |
| NFR-021 | US-021 | brak — do napisania | #23 |
| NFR-022 | US-019 | krok CI „Próg pokrycia”; `tests_tooling.MypyConfigTests.test_coverage_threshold` | #23 |
| NFR-023 | US-019 | n/d — miara CI | #23 |
| NFR-024 | US-019 | kroki CI (ruff, mypy, bandit); `tests_tooling.MypyConfigTests` (2) | #23 |
| NFR-025 | US-020 | `tests_tooling.SupplyChainTests`; build obrazu w CI (job 7) | #23 |
| NFR-026 | US-018, US-030, US-038 | `ConcurrentIssueTests` (PostgreSQL, +1 US-018); `AuditFixTests.test_hu_quantity_check_constraint`; `AuditFixTests.test_stocktake_line_unique_per_hu`; `ExecuteIssueDocumentDoubleClickTests`; `CompleteIfPickedTests` | historyczny (przed procesem; #13) |
| NFR-027 | US-017, US-029 | `tests_urls.UrlSnapshotTests`; porównanie AST przy podziale (ADR-0006) | #23 |
| NFR-028 | — | n/d — kroki CI (`check`, build obrazu) | historyczny (przed procesem) |

---

## 4. Wymagania bezpieczeństwa i RODO (SEC)

| SEC | US | Test (istniejący) | PR |
|---|---|---|---|
| SEC-001 | US-008 | `tests_passwords.PasswordHasherTests` (3), `HasherConfigTests` (3); smoke test obrazu w CI | #23 |
| SEC-002 | — (powiązane: US-041) | `SecurityTests.test_weak_password_rejected_on_create`; `SecurityTests.test_password_similar_to_username_rejected`; `SecurityTests.test_strong_password_accepted_on_create` | historyczny (przed procesem) |
| SEC-003 | US-009 | `tests_login_limits.SharedCacheTests` (3); `DemoModeViewTests.test_rate_limit_also_without_demo_mode` | #23 |
| SEC-004 | US-009 | `tests_login_limits.AccountLockoutTests` (8) | #23 |
| SEC-005 | US-005, US-043 | brak — do napisania (cookie, bezczynność, `clearsessions`) | #23 |
| SEC-006 | US-010 | `tests_2fa.py` (13 testów) | #23 |
| SEC-007 | US-007, US-017 | `ViewAccessTests.test_login_required_redirects`; `ViewAccessTests.test_viewer_cannot_receive`; `ViewAccessTests.test_viewer_role_forbidden_on_receive`; `ScannerTests.test_scanner_home_requires_operator`; `WebInventoryTests.test_web_inventory_requires_operator`; `PdfAndViewTests.test_delivery_edit_admin_only`; `UserManagementTests.test_user_list_admin_only`; `SecurityTests.test_login_log_view_admin_only`; `DemoResetTests.test_viewer_forbidden`; `tests_access_matrix.AccessMatrixTests.test_role_matrix` | historyczny (przed procesem) |
| SEC-008 | US-007 | `tests_access_matrix.AccessMatrixTests` (kompletność + 560 sprawdzeń), `DemoAccessMatrixTests`, `AdminSiteAccessTests` | #23 |
| SEC-009 | US-001 | `tests_security.SuperuserProtectionTests` (9 testów) | #23 |
| SEC-010 | — (powiązane: US-041) | `DemoModeViewTests.test_demo_account_cannot_change_password`; `AdminHiddenInDemoTests.test_admin_404_in_demo`; `DemoAccountPermissionTests.test_demo_operator_gets_403_on_admin_pages`; `DemoLoginTests.test_only_demo_accounts_can_be_entered` | historyczny (przed procesem) |
| SEC-011 | — | n/d — decyzja (Z-06) | — |
| SEC-012 | — | n/d — bandit w CI | historyczny (przed procesem) |
| SEC-013 | US-043 | brak — do napisania | historyczny (przed procesem) |
| SEC-014 | US-043 | brak — do napisania (test z `enforce_csrf_checks=True`) | historyczny (przed procesem) |
| SEC-015 | US-002, US-013 | `tests_input_limits.py` (US-002); `tests_input_validation.FormRangeTests`, `QuantityLimitTests`, `ImportNumberTests` | #23 |
| SEC-016 | US-043 | `HardeningTests.test_csv_export_neutralizes_formula_injection` (funkcja `_safe_cell`; ścieżka XLSX bez testu) | historyczny (przed procesem) |
| SEC-017 | US-013 | `tests_input_validation.ContentDispositionTests` | #23 |
| SEC-018 | US-043 | brak — do napisania | historyczny (przed procesem) |
| SEC-019 | US-004 | `tests_imports_hardening.BrokenXlsxViewTests`, `LibraryErrorTests`, `DefusedXmlTests` | #23 |
| SEC-020 | — | n/d — brak trwałego zapisu plików (brak `MEDIA_ROOT` i pól plikowych w modelach) | historyczny (przed procesem) |
| SEC-021 | US-002, US-004, US-015 | `HULabelsLimitTests`; `DemoImportLimitTests`; `tests_imports_hardening.RowLimitTests`, `test_zip_bomb_rejected_before_load_workbook`; `tests_pagination.LocationLabelsLimitTests` | #23 |
| SEC-022 | US-011 | `tests_security_headers.SecurityHeadersTests`, `TemplateScanTests`; `check --deploy` w CI | #23 |
| SEC-023 | US-043 | brak — do napisania (`check --deploy` w CI nie jest testem odpowiedzi) | historyczny (przed procesem) |
| SEC-024 | US-011 | `SecurityHeadersTests.test_permissions_policy` | #23 |
| SEC-025 | US-011 | `HstsSettingsTests.test_prod_hsts` | #23 |
| SEC-026 | US-003 | `tests_deploy_settings.ProdSecretKeyTests` (7); `ComposeSecretsTests`; `EntrypointSuperuserPasswordTests`; krok CI walidujący compose bez sekretów | #23 |
| SEC-027 | US-003 | `tests_deploy_settings.SeedDemoModeTests` (2); `SeedDemoTests.test_reset_refused_without_demo_mode` | #23 |
| SEC-028 | US-006 | n/d — CI (gitleaks, bandit) | #23 |
| SEC-029 | US-006, US-020 | n/d — CI (pip-audit, Dependabot) | #23 |
| SEC-030 | US-037 | n/d — smoke test obrazu w CI | #23 |
| SEC-031 | US-006, US-020 | n/d — CI | #23 |
| SEC-032 | US-022, US-021 | `tests_audit_log.LogRedactionTests`, `TypedUsernameTests` | #23 |
| SEC-033 | US-022 | `tests_audit_log.AuditLogTests` | #23 |
| SEC-034 | — (PYT-11) | brak — do napisania (po decyzji PO) | #23 |
| SEC-035 | US-005 | `tests_retention.LoginEventPrivacyTests`; `DemoEntryRateLimitTests.test_successful_entry_logs_no_ip` | #23 |
| SEC-036 | US-005 | `tests_retention.PurgeLoginEventsTests` (5) | #23 |
| SEC-037 | US-023 | n/d — przegląd dokumentu | #23 |
| SEC-038 | US-023, US-027 | brak — do napisania | #23 |
| SEC-039 | US-012 | `BackupScriptTests.test_encrypted_copy_decrypts_only_with_private_key`, `test_refuses_unencrypted_offsite`; CI job 3b | #23 |
| SEC-040 | US-005, US-016 | `tests_demo_entry.DemoEntryRateLimitTests` (5); `tests_demo_limits` (15) | #23 |
| SEC-041 | US-014 | `tests_open_decisions.ClientIPTests`, `ClientIPLoginTests` | historyczny (przed procesem; #13) |
| SEC-042 | US-024 | n/d — przegląd dokumentu | #23 |

---

## 5. Indeks odwrotny: historyjka → wymagania

| US | MoSCoW | Pokrywa | Źródło | Planowany test (nowy) |
|---|---|---|---|---|
| US-001 | Must | FR-023, FR-024, SEC-009 | R1 | `tests_security.SuperuserProtectionTests` — zrobione, #23 |
| US-002 | Must | FR-001, FR-005, NFR-003, NFR-009, SEC-015, SEC-021 | R3 | `tests_input_limits` (13 testów) — zrobione, #23 |
| US-003 | Must | SEC-026, SEC-027 | R2 | `tests_deploy_settings.py`, `tests_demo.py`, krok CI compose — zrobione, #23 |
| US-004 | Must | FR-005, NFR-003, NFR-007, NFR-008, SEC-019, SEC-021 | T1, R4 | `tests_imports_hardening.py` (19 testów) — zrobione, #23 |
| US-005 | Must | FR-024, NFR-012, SEC-005, SEC-035, SEC-036, SEC-040 | R7, R5 | `tests_retention.py` (8), `tests_demo_entry.DemoEntryRateLimitTests` (5) — zrobione, #23 |
| US-006 | Must | SEC-028, SEC-029, SEC-031 | R10 | n/d (CI) |
| US-007 | Should | FR-023, SEC-007, SEC-008 | sekcja 6 promptu, AUDYT Zał. A | `tests_access_matrix.py` (5 testów) — zrobione, #23 |
| US-008 | Should | SEC-001 | R6 | `tests_passwords.py` (6 testów) — zrobione, #23 |
| US-009 | Should | SEC-003, SEC-004, NFR-013 | R6, T8 | `tests_login_limits.py` (11 testów) — zrobione, #23 |
| US-010 | Should | SEC-006 | R6 | `tests_2fa.py` (13 testów) — zrobione, #23 |
| US-011 | Should | SEC-022, SEC-024, SEC-025 | R8 | `tests_security_headers.py` (11 testów) — zrobione, #23; kryterium 3 ręcznie |
| US-012 | Should | NFR-014, NFR-018, NFR-019, SEC-039 | R9 | `tests_backup_script.py` (9) + ćwiczenie w CI — zrobione, #23; ćwiczenie produkcyjne — INFRA |
| US-013 | Should | FR-001, FR-004, FR-005, FR-018, NFR-009, SEC-015, SEC-017 | T16 | `tests_input_validation.py` (14 testów) — zrobione, #23 |
| US-014 | Should | SEC-041 | „poza listą” | `tests_open_decisions.py` (+4 testy) — zrobione, #23 |
| US-015 | Should | NFR-003, NFR-006, NFR-010, SEC-021 | R5 | `tests_pagination.py` (13 testów) — zrobione, #23 |
| US-016 | Should | SEC-040 | R5, DEC-6 | `tests_demo_limits.py` (15 testów) — zrobione, #23 |
| US-017 | Should | NFR-027, SEC-007 | T2 | `tests_urls.py` (migawka tras) + macierz US-007 — zrobione, #23 |
| US-018 | Should | NFR-026, FR-017 | T3 | `CompleteIfPickedTests` (6), `test_scanner_pick_and_execute_on_same_document` (PG) — zrobione, #23 |
| US-050 | Could | NFR-003, SEC-021 | przegląd [DB] US-002 | `HUNumberReservationTests` (6) + PG (1) — zrobione, #23 |
| US-052 | Should | NFR-026, FR-016 | przegląd [DB] US-018 | `IssueLineLockTests` (9) + PG (2) — zrobione, #23 |
| US-053 | Could | NFR-026 | przegląd [DB] US-018 | `PalletLockOrderTests` (4) + PG (2) — zrobione, #23 |
| US-019 | Should | NFR-022, NFR-023, NFR-024 | T4, T5, T6 | `tests_tooling.py` (3) + przebieg CI — zrobione, #23 |
| US-020 | Should | NFR-025, SEC-029, SEC-031 | T7, R10 | `tests_tooling.SupplyChainTests` (5) + CI — zrobione, #23 |
| US-021 | Should | NFR-014, NFR-021, SEC-032 | T15 | `tests_alerts.py` |
| US-022 | Should | FR-021, FR-024, NFR-020, SEC-032, SEC-033 | prompt PO sekcja 6, R1, R7 | `tests_audit_log.py` (18 testów) — zrobione, #23 |
| US-023 | Should | SEC-037, SEC-038 | R7 | n/d (dokument) |
| US-024 | Should | SEC-042 | AUDYT §3.5 | n/d (dokument) |
| US-025 | Should | — (proces) | AUDYT §1.2 | n/d (dokument) |
| US-026 | Should | — (proces) | AUDYT §1.2 | n/d (dokument) |
| US-027 | Could | SEC-038 | R7 | do ustalenia |
| US-028 | Could | NFR-011, NFR-004, FR-022 | T9 | do ustalenia |
| US-029 | Could | NFR-027 | T10 | n/d (refaktoryzacja) |
| US-030 | Could | NFR-026, FR-020 | T11 | do ustalenia |
| US-031 | Could | — | T12 | `tests_demo_tour.py` (aktualizacja) |
| US-032 | Could | — (proces) | T13 | n/d |
| US-033 | Could | — | T14 | n/d (dokument) |
| US-034 | Could | — | docs/03 | do ustalenia |
| US-035 | Could | NFR-015, NFR-017 | AUDYT §1.3 pkt 7 | n/d (test z użytkownikami) |
| US-036 | Could | — (mierniki M-01…M-06) | AUDYT §1.3 pkt 3 | n/d |
| US-037 | Could | SEC-030 | „poza listą” | n/d (CI) |
| US-038 | Could | NFR-026, FR-020 | docs/07 #2 | `tests_concurrency_pg.py` |
| US-039 | Could | NFR-002 | docs/07 #3 | do ustalenia |
| US-040 | Could | NFR-001, NFR-002 | AUDYT §1.3 pkt 1 | n/d (pomiar) |
| US-041 | Could | SEC-002, SEC-010 | PROCESY L-01 | do ustalenia |
| US-042 | Could | FR-020 (BR-007) | PROCESY L-02 | do ustalenia |
| US-043 | Could | FR-007, FR-009, SEC-005, SEC-013, SEC-014, SEC-016, SEC-018, SEC-023, NFR-007, NFR-012 | AUDYT §2.3 | `tests.py`, `tests_security_headers.py` |
| US-044…US-049 | Won't | — (poza zakresem) | docs/01, docs/07 | — |

---

## 6. Jak utrzymywać

| Kiedy | Kto | Co |
|---|---|---|
| Nowa lub zmieniona historyjka | [BA] | Wiersz w §5 oraz kolumna **US** przy wymaganiach, które historyjka zmienia. |
| **Krok 6 procesu — odbiór [BA]** ([CONTRIBUTING.md](../../CONTRIBUTING.md) §2) | [BA] | W tym samym PR co zmiana: nazwy testów w kolumnie **Test**, numer **PR**, status wymagania w WYMAGANIACH, status historyjki `gotowe` w HISTORYJKACH. |
| Definition of Done ([CONTRIBUTING.md](../../CONTRIBUTING.md) §4) | [DEV] | Punkt „dokumentacja zaktualizowana (…, SLEDZENIE)”: [DEV] podaje w opisie PR nazwy dodanych testów; PR bez wpisu w macierzy nie spełnia DoD. |
| Nowe wymaganie lub zmiana statusu | [BA], [SEC] dla SEC | Nowy wiersz tu i w WYMAGANIACH; wymaganie dostaje status `spełnione` dopiero, gdy w kolumnie Test jest nazwa istniejącego testu (albo `n/d` z uzasadnieniem). |
| Przy wydaniu (wpis w CHANGELOG) | [BA] | Przegląd §7: luki zamknięte lub świadomie otwarte; weryfikacja nazw testów. |
| Zmiana nazwy lub usunięcie testu | [DEV] | Aktualizacja tej macierzy w tym samym PR (inaczej nazwa „wisi”). |

**Weryfikacja nazw testów** (tylko odczyt, z korzenia repozytorium; wynik pusty = wszystkie istnieją):

```bash
grep -oE '`[A-Za-z_]+(\.test_[a-z0-9_]+)?`' docs/analiza/SLEDZENIE.md | tr -d '`' | sort -u |
while IFS= read -r n; do
  case "$n" in
    *.test_*) c="${n%%.*}"; m="${n#*.}"
              grep -qE "^class $c\b" warehouse/tests*.py && grep -qE "def $m\b" warehouse/tests*.py || echo "BRAK: $n" ;;
    *Tests)   grep -qE "^class $n\b" warehouse/tests*.py || echo "BRAK: $n" ;;
  esac
done
```

Skrypt jest przybliżeniem (klasa i metoda istnieją gdzieś w `warehouse/tests*.py`). Nazwy w §2–§4 sprawdzono
2026-10-16 dokładniej, przez `ast` (metoda w tej klasie). Automatyczne sprawdzanie w CI to propozycja dla [DEV],
nie część żadnej historyjki.

---

## 7. Luki

### 7.1 Wymagania bez testu

| Luka | Wymagania | Skutek | Zamknięcie |
|---|---|---|---|
| LT-01 | FR-007 (ruch PRZESUNIĘCIE), FR-009 (odmowa alokacji palety „Pusty”) | wdrożone wymagania FR bez dedykowanego testu | US-043 |
| LT-02 | SEC-005 (cookie i bezczynność sesji), SEC-013 (escapowanie), SEC-014 (CSRF), SEC-016 (eksport XLSX), SEC-018 (limit 5 MB), SEC-023 (nagłówki) | wymagania `spełnione` bez testu regresji; zmiana ustawień mogłaby je zepsuć bez śladu | US-043 |
| LT-03 | NFR-004, NFR-007, NFR-012, NFR-016, NFR-020 | wartości (500 wierszy, 5 MB, 30 min, PL / strefa, logi JSON) zapisane tylko w konfiguracji | US-043 (007, 012), reszta — do decyzji |
| LT-04 | SEC-008 | brak systematycznej macierzy rola × trasa | US-007 |
| LT-05 | SEC/NFR o statusie `brak` lub `częściowo` (m.in. SEC-001, 004, 006, 009, 015, 017, 019, 024–027, 032–036, 038, 040; NFR-006, 009, 011, 021) | testy powstaną razem z historyjkami (kolumna US) | US-001…US-022 |
| LT-06 | NFR-001, NFR-002, NFR-014 | brak pomiarów i definicji (PYT-01, PYT-03) | US-040 |

### 7.2 Testy bez wymagania

Istniejące testy, których nie da się przypisać do FR / NFR / SEC — albo kryją funkcje bez FR w docs/05
(do decyzji PO, WYMAGANIA §6), albo nie dotyczą produktu.

| Test (klasa) | Obszar | Propozycja |
|---|---|---|
| `ViewAccessTests.test_dashboard_ok`; `ViewAccessTests.test_dashboard_heatmap_and_movement_days`; `ViewAccessTests.test_dashboard_issue_progress_and_plan`; `HeatLevelTests` | pulpit (mapa cieplna, postęp wydań) | nowe FR „Pulpit” po potwierdzeniu PO |
| `LocationImportTests`; `LocationImportCapacityTests` | import lokalizacji i słownik lokalizacji | nowe FR „Słownik materiałów i lokalizacji” |
| `ReportViewTests` | raporty ekranowe (stany, lokalizacje, historia materiału) | rozszerzenie FR-022 albo osobne FR |
| `SeedDemoTests`; `DemoStartTests`; `DemoResetTests`; `DemoEntryOffTests`; `DemoLoginTests`; `DemoLoginOffTests`; `WelcomePanelTests`; `DemoScriptTests`; `DemoScriptIncludedTests`; `DemoImportLimitTests` | tryb demo, wycieczka, panel powitalny | nowe FR „Tryb demo” (część powiązana z SEC-010, SEC-040) |
| `BrandingTests`; `BackLinkTests`; `AdminLinkVisibilityTests` | marka, nawigacja, widoczność linków wg roli | NFR użyteczności albo bez wymagania |
| `AuditFixTests.test_parse_int_cell`; `AuditFixTests.test_csv_decode_cp1250_fallback`; `AuditFixTests.test_wz_pdf_multipage_redraws_header`; `AuditFixTests.test_api_document_rejects_non_numeric_id`; `AuditFixTests.test_daily_number_is_deletion_safe` | parsowanie importów, PDF WZ, numeracja dzienna WZ (D-03, BR-013) | doprecyzować FR-005 / FR-016 |
| `SrtTests`; `ChapterTests`; `PacingTests`; `CardTests` (`tests_record_video.py`) | narzędzie do nagrywania filmu demo | poza produktem — bez wymagania |
| `.claude/hooks/test_hooks.py` | harness asystenta AI (`guard.py`) | poza produktem — bez wymagania |

### 7.3 Dostęp: testy punktowe zamiast macierzy

Audyt (§2.3, Załącznik A) wskazuje ≈ 35 asercji o 403 lub przekierowaniu i brak macierzy rola × trasa wymaganej
w sekcji 6 promptu PO. Wg przeglądu nazw testów jawne 403 sprawdzają m.in. `ScannerTests.test_scanner_home_requires_operator`,
`WebInventoryTests.test_web_inventory_requires_operator`, `PdfAndViewTests.test_delivery_edit_admin_only`,
`UserManagementTests.test_user_list_admin_only`, `ViewAccessTests.test_viewer_role_forbidden_on_receive`,
`SecurityTests.test_login_log_view_admin_only`, `DemoResetTests.test_viewer_forbidden`,
`DemoAccountPermissionTests.test_demo_operator_gets_403_on_admin_pages`, `PermissionDeniedPageTests.test_viewer_gets_403_with_menu`.
Nie widać testów roli Podgląd na pozostałych endpointach skanera (8 JSON), importach, akcjach WZ (realizuj, spakuj,
wyślij), spisie i przepakowaniu — do potwierdzenia macierzą z **US-007**.

### 7.4 Luki procesu śledzenia

- PR z naprawami nie istnieją, dopóki historyjki nie zostaną zrealizowane — kolumna PR przy US pozostaje `—`.
- Numery PR dla wymagań wdrożonych przed procesem nie są odtwarzane (poza #10 dla FR-008, FR-011, FR-025, FR-026
  i #13 dla pozycji D-09…D-13), bo historia PR #1–#22 nie wskazuje wymagań.
- Macierz nie śledzi reguł biznesowych BR-nnn osobno — wskazują one FR w WYMAGANIACH §4.

## Historia zmian

| Wersja | Data | Zmiana |
|---|---|---|
| 0.1 | 2026-10-16 | Pierwszy szkic: macierz FR / NFR / SEC → US → test → PR, indeks odwrotny, luki. |
