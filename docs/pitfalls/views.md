# Pułapki: widoki, formularze, skaner

1. **Operacje zmieniające stan tylko na POST.** Konwencja w `views.py`: widok sprawdza
   `if request.method == "POST":`, a GET kończy się `redirect` bez zmian (np.
   `issue_line_delete`, `issue_execute`). Nie wykonuj zmian na GET — link w mailu/prefetch
   przeglądarki by je odpalił.
2. **Błędy biznesowe = `WMSError`.** Serwis rzuca `WMSError`, widok łapie i robi
   `messages.error(request, str(exc))`. Nie łap gołego `Exception` — ukryje bug.
3. **API skanera: `@require_GET`/`@require_POST` + JSON `{"ok": bool, ...}`.** Kody 400/404
   z polem `error`. JS skanera wysyła CSRF w nagłówku `X-CSRFToken` z `window.CSRF`
   (`scanner/base.html`) — nowy endpoint POST nie potrzebuje `csrf_exempt`.
4. **Skaner: wspólny kod w `static/warehouse/scanner.js`** (IIFE, dźwięki WebAudio, fetch z
   CSRF) — nowe ekrany skanera korzystają z niego zamiast własnego `fetch`.
   `vendor/jsQR.js` (10k linii) czytaj grepem, nie w całości.
5. **Upload: limit 5 MB w `_MaxSizeFileMixin`** (`forms.py`) + `DATA_UPLOAD_MAX_MEMORY_SIZE`
   6 MB. Każdy nowy formularz z plikiem musi dziedziczyć mixin.
6. **XLSX to zip** — 5 MB może rozpakować się do setek MB w `openpyxl.load_workbook`. Każdy import
   idzie przez `parse_locations_file` (`imports.py`): sygnatura ZIP, limit po rozpakowaniu
   (`IMPORT_MAX_UNCOMPRESSED_BYTES`), limit wierszy (`IMPORT_MAX_ROWS`) — nowy import też ma przez nią iść
   (`imports.py`). Nie zdejmuj `read_only=True`; przy nowych importach ograniczaj liczbę
   wierszy.
7. **CSV: separator zgadywany** (`;` vs `,` po próbce) i nagłówki zamieniane na lowercase —
   nowe kolumny w importach porównuj po `strip().lower()`.
8. **`views.py` ma 1405 linii** (T2 w audycie). Nowe ekrany dokładaj do osobnego modułu (jak
   `scanner_views.py`), nie do `views.py`.
9. **Eksporty (`stock_export`, `movement_export`) budują wiersze w pamięci.** Przy dużej
   historii ruchów filtruj zakres dat zanim dodasz nowe kolumny.
10a. **CSP (US-011, ADR-0004): bez `on*=`, `javascript:` i skryptów inline bez nonce.** Skrypt w szablonie:
    `<script nonce="{{ csp_nonce }}">`; potwierdzenia, auto-wysyłka, menu — `data-confirm`, `data-autosubmit`,
    `data-nav-toggle`, `data-history-back` (`static/warehouse/ui.js`). Zewnętrzne CDN są zablokowane.
10. **Teksty UI po polsku**, komunikaty z numerem dokumentu/HU (`f"Dokument {doc.number} …"`)
    — trzymaj ten styl.
