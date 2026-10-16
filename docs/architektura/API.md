# API JSON skanera i pozostałe punkty końcowe

| | |
|---|---|
| Wersja | 0.1 |
| Data | 2026-10-16 |
| Status | szkic — do akceptacji Product Ownera |
| Właściciel | [DEV] |

Dokument opisuje **8 endpointów JSON skanera** (`/skaner/api/…`) oraz inne trasy, które nie
są ekranami HTML: `healthz`, logowanie i tryb demo, eksporty CSV/XLSX, PDF-y. Źródło: kod
(`warehouse/scanner_views.py`, `warehouse/urls.py`, `config/urls.py`, `warehouse/demo.py`,
`warehouse/exports.py`) oraz sprawdzenie na lokalnej instancji z danymi demo (SQLite,
`DEMO_MODE=1`, 2026-10-16). Przykłady odpowiedzi poniżej pochodzą z **rzeczywistych**
odpowiedzi tej instancji (dla czytelności bez sekwencji `\uXXXX`, a tam, gdzie zaznaczono
wielokropkiem — skrócone).

To API jest **wewnętrzne**: jedynym klientem jest `static/warehouse/scanner.js` wdrażany razem
z serwerem. Nie jest przeznaczone dla integracji zewnętrznych (D-04: wymiana danych przez pliki);
patrz [„Wersjonowanie i stabilność”](#8-wersjonowanie-i-stabilność).

Architektura: [ARCHITEKTURA.md](ARCHITEKTURA.md) · pułapki: [views.md #3–4](../pitfalls/views.md),
[auth.md #10](../pitfalls/auth.md).

---

## 1. Konwencje wspólne

| Aspekt | Zasada |
|---|---|
| Ścieżka bazowa | `/skaner/api/` (bez wersji w URL) |
| Uwierzytelnianie | ciasteczko sesji Django (logowanie formularzem `/login/` albo „Wejdź jako demo”); brak tokenów API |
| Uprawnienie | `@operator_required` na **każdym** z 8 endpointów: rola Operator lub Administrator (superuser = Administrator) |
| Metody | GET — odczyt (`@require_GET`), POST — zmiana stanu (`@require_POST`); dekoratory ról stoją **przed** metodą, więc niezalogowany dostaje przekierowanie, a nie 405 |
| Kodowanie | `application/json`; znaki spoza ASCII są zapisane jako `\uXXXX` (standardowy JSON) |
| Sukces | HTTP 200, `{"ok": true, …}` |
| Błąd biznesowy / walidacji | HTTP 400 albo 404, `{"ok": false, "error": "<komunikat po polsku>"}` |
| Pusty/białe znaki | wartości są obcinane (`strip()`); pusty kod = 400 |
| Kody HU | wyszukiwanie **bez rozróżniania wielkości liter** (`number__iexact`, D-10) |
| Kody lokalizacji | wyszukiwanie **dokładne** (z rozróżnieniem wielkości liter) |
| CSRF (POST) | nagłówek `X-CSRFToken` równy ciasteczku `csrftoken`; w aplikacji token jest w `window.CSRF` (`scanner/base.html`), `scanner.js` wysyła go automatycznie; **nie ma** `csrf_exempt` |
| Typ treści POST | `application/x-www-form-urlencoded` (pola formularza, nie JSON) |
| Idempotencja | brak — ponowienie POST wykona operację drugi raz (sekcja 9) |

### 1.1 Odpowiedzi poza kontraktem JSON

| Sytuacja | Odpowiedź | Uwaga |
|---|---|---|
| Brak sesji (niezalogowany lub sesja wygasła po 30 min bezczynności) | **302** na `/login/?next=<ścieżka>` | `fetch` podąża za przekierowaniem i dostaje **HTML logowania z kodem 200** ([auth.md #10](../pitfalls/auth.md)). `scanner.js` wykrywa to po `response.redirected` i przenosi na `/login/`; własny klient musi sam obsłużyć 302 |
| Rola Podgląd | **403**, HTML (strona `403.html`) | nie JSON |
| POST bez/z błędnym tokenem CSRF | **403**, HTML | nie JSON |
| Zła metoda (zalogowany operator) | **405**, pusta treść | np. POST na `/skaner/api/hu/` |
| Nieobsłużony wyjątek | **500**, HTML | np. wartości spoza zakresu liczby (T16, sekcja 9) |

### 1.2 Obiekty współdzielone

**`hu`** — `_hu_payload` (zwracany przez `hu`, `rozmiesc`, `pick`, `inwentaryzacja`, `przepakuj`)

| Pole | Typ | Znaczenie |
|---|---|---|
| `number` | string | numer palety (HU), np. `HU00000001` |
| `material_index` | string | indeks materiału |
| `material_name` | string | nazwa materiału |
| `quantity` | integer | aktualna ilość na palecie (≥ 0) |
| `unit` | string | **kod** jednostki, np. `PCS` |
| `status` | string | `DO_ULOZENIA` · `ZMAGAZYNOWANY` · `PUSTY` |
| `status_label` | string | etykieta po polsku („Do ułożenia”, „Zmagazynowany”, „Pusty”) |
| `lot` | string | partia; pusty ciąg, gdy brak |
| `location` | string \| null | kod lokalizacji; `null`, gdy paleta nie jest ułożona |

**`location`** — `_location_payload` (zwracany przez `lokalizacja` i `lokalizacja-zawartosc`)

| Pole | Typ | Znaczenie |
|---|---|---|
| `code` | string | kod lokalizacji, np. `A01-01-01` |
| `type` | string | `PICKING` · `ZAPAS` |
| `type_label` | string | „Picking”, „Zapas” |
| `occupancy` | integer | liczba aktywnych HU (niepusty status i ilość > 0) |
| `capacity` | integer | pojemność w HU; **0 = bez limitu** |

**`document`** — `_doc_payload` (zwracany przez `zlecenie` i `pick`)

| Pole | Typ | Znaczenie |
|---|---|---|
| `id` | integer | klucz dokumentu |
| `number` | string | numer WZ, np. `WZ20261016-003` |
| `reference` | string | referencja (może zawierać nazwę klienta — dane wewnętrzne) |
| `status` | string | `OTWARTY` · `ZREALIZOWANY` · `SPAKOWANY` · `WYSLANY` |
| `lines[]` | array | pozycje (niżej) |
| `remaining_total` | integer | suma pozostałych ilości z pozycji |
| `completed` | boolean | `true` **tylko** dla statusu `ZREALIZOWANY` (po spakowaniu/wysłaniu znów `false`) |

Pozycja `lines[]`: `id`, `material_index`, `material_name`, `unit` (kod), `requested`,
`picked`, `remaining` (= `max(0, requested − picked)`) — wszystkie liczby całkowite poza tekstami.

---

## 2. Przegląd endpointów

| # | Metoda | Ścieżka | Nazwa URL | Zmienia stan | Serwis | Używany przez ekran skanera |
|---|---|---|---|---|---|---|
| 1 | GET | `/skaner/api/hu/` | `scanner_api_hu` | nie | — | rozmieszczanie, picking, inwentaryzacja, przepakowanie, podgląd HU |
| 2 | GET | `/skaner/api/lokalizacja/` | `scanner_api_location` | nie | — | rozmieszczanie |
| 3 | GET | `/skaner/api/zlecenie/` | `scanner_api_document` | nie | — | lista zleceń, picking |
| 4 | POST | `/skaner/api/rozmiesc/` | `scanner_api_allocate` | **tak** | `allocate_hu` | rozmieszczanie |
| 5 | POST | `/skaner/api/pick/` | `scanner_api_pick` | **tak** | `pick_from_hu` (+ domknięcie WZ w widoku, T3) | picking |
| 6 | POST | `/skaner/api/inwentaryzacja/` | `scanner_api_inventory` | **tak** | `adjust_hu_quantity` → `correct_hu_quantity` | inwentaryzacja |
| 7 | POST | `/skaner/api/przepakuj/` | `scanner_api_repack` | **tak** | `repack_hu` | przepakowanie |
| 8 | GET | `/skaner/api/lokalizacja-zawartosc/` | `scanner_api_location_contents` | nie | — | podgląd lokalizacji |

Wszystkie wymagają roli Operator/Administrator. Każda zmiana stanu zapisuje `StockMovement`
w tej samej transakcji (D-05).

### Przykłady `curl` — przygotowanie sesji

Przetestowane lokalnie na HTTP (`runserver`, `DEMO_MODE=1`). Wariant HTTPS (Django sprawdza
wtedy nagłówek `Origin` lub `Referer` — dodaj `-H "Origin: $BASE"`) — **nieprzetestowany**.

```bash
BASE=http://127.0.0.1:8000          # produkcyjnie: https://twoja-domena
JAR=cookies.txt

# a) logowanie formularzem (konto z rolą Operator/Administrator)
curl -s -c $JAR -b $JAR "$BASE/login/" -o /dev/null
TOKEN=$(awk '$6=="csrftoken"{print $7}' $JAR)
curl -s -c $JAR -b $JAR -X POST "$BASE/login/" \
     -d "username=demo_operator&password=demo1234&csrfmiddlewaretoken=$TOKEN" \
     -o /dev/null -w "%{http_code}\n"            # 302 = zalogowano

#    …albo, tylko przy DEMO_MODE=1: wejście kontem demo bez hasła
curl -s -c $JAR -b $JAR "$BASE/demo/" -o /dev/null

# b) odśwież token CSRF (logowanie go rotuje) — wymagany w każdym POST
curl -s -c $JAR -b $JAR "$BASE/skaner/" -o /dev/null
TOKEN=$(awk '$6=="csrftoken"{print $7}' $JAR)
```

W przykładach niżej `-b $JAR` przekazuje sesję, a w POST-ach dodano `-H "X-CSRFToken: $TOKEN"`.

---

## 3. Endpointy odczytu (GET)

### 3.1 `GET /skaner/api/hu/` — dane palety

| Parametr (query) | Wymagany | Opis |
|---|---|---|
| `code` | tak | numer HU, bez rozróżniania wielkości liter |

```bash
curl -s -b $JAR "$BASE/skaner/api/hu/?code=HU00000001"
```

```json
{"ok": true, "hu": {"number": "HU00000001", "material_index": "DEMO-001",
  "material_name": "Rękawice nitrylowe M", "quantity": 18, "unit": "PCS",
  "status": "ZMAGAZYNOWANY", "status_label": "Zmagazynowany", "lot": "L0011",
  "location": "A01-01-01"}}
```

| Status | `error` | Kiedy |
|---|---|---|
| 400 | `Pusty kod.` | brak lub pusty `code` |
| 404 | `Nie znaleziono HU „<code>”.` | nie ma takiej palety |

### 3.2 `GET /skaner/api/lokalizacja/` — dane lokalizacji

| Parametr (query) | Wymagany | Opis |
|---|---|---|
| `code` | tak | kod lokalizacji, **dokładny** |

```bash
curl -s -b $JAR "$BASE/skaner/api/lokalizacja/?code=A01-01-01"
```

```json
{"ok": true, "location": {"code": "A01-01-01", "type": "PICKING",
  "type_label": "Picking", "occupancy": 1, "capacity": 1}}
```

| Status | `error` | Kiedy |
|---|---|---|
| 400 | `Pusty kod.` | brak lub pusty `code` |
| 404 | `Nie znaleziono lokalizacji „<code>”.` | brak lokalizacji |

### 3.3 `GET /skaner/api/zlecenie/` — szczegóły zlecenia (WZ)

| Parametr (query) | Wymagany | Opis |
|---|---|---|
| `id` | jeden z dwóch | klucz dokumentu (tylko cyfry); ma pierwszeństwo |
| `number` | jeden z dwóch | numer WZ; używany, gdy `id` nie jest liczbą |

```bash
curl -s -b $JAR "$BASE/skaner/api/zlecenie/?id=3"
```

```json
{"ok": true, "document": {"id": 3, "number": "WZ20261016-003",
  "reference": "Zamówienie demo 3", "status": "OTWARTY",
  "lines": [
    {"id": 4, "material_index": "DEMO-002", "material_name": "Rękawice nitrylowe L",
     "unit": "PCS", "requested": 40, "picked": 0, "remaining": 40},
    {"id": 5, "material_index": "DEMO-007", "material_name": "Etykiety termiczne 100×150",
     "unit": "PCS", "requested": 10, "picked": 0, "remaining": 10}],
  "remaining_total": 50, "completed": false}}
```

| Status | `error` | Kiedy |
|---|---|---|
| 404 | `Nie znaleziono zlecenia.` | nie ma dokumentu — także gdy **brak obu parametrów** (nie ma kodu 400) |

Endpoint zwraca dokument w **dowolnym** statusie (także zamkniętym).

### 3.4 `GET /skaner/api/lokalizacja-zawartosc/` — „co tu leży”

| Parametr (query) | Wymagany | Opis |
|---|---|---|
| `code` | tak | kod lokalizacji, dokładny |

```bash
curl -s -b $JAR "$BASE/skaner/api/lokalizacja-zawartosc/?code=A01-01-01"
```

```json
{"ok": true,
 "location": {"code": "A01-01-01", "type": "PICKING", "type_label": "Picking",
              "occupancy": 1, "capacity": 1},
 "hus": [{"number": "HU00000001", "material_index": "DEMO-001",
          "material_name": "Rękawice nitrylowe M", "quantity": 18, "unit": "PCS",
          "status": "ZMAGAZYNOWANY"}]}
```

`hus[]` zawiera palety w lokalizacji **bez** statusu `PUSTY`, posortowane wg indeksu materiału
i numeru; element ma tylko pola `number`, `material_index`, `material_name`, `quantity`,
`unit`, `status` (nie ma `status_label`, `lot`, `location`). **Brak paginacji** (sekcja 9).

| Status | `error` | Kiedy |
|---|---|---|
| 400 | `Pusty kod.` | brak lub pusty `code` |
| 404 | `Nie znaleziono lokalizacji „<code>”.` | brak lokalizacji |

---

## 4. Endpointy zmieniające stan (POST)

Wszystkie wymagają `X-CSRFToken`. Błąd reguły biznesowej (`WMSError` z `services.py`) daje
**400** i **nie zostawia śladu w bazie** (transakcja się wycofuje).

### 4.1 `POST /skaner/api/rozmiesc/` — rozmieszczenie / przesunięcie palety

| Pole formularza | Wymagane | Opis |
|---|---|---|
| `hu` | tak | numer HU (bez rozróżniania wielkości liter) |
| `location` | tak | kod lokalizacji (dokładny) |

Pierwsza alokacja tworzy ruch `ALOKACJA`, zmiana miejsca — `PRZESUNIECIE`; paleta dostaje
status `ZMAGAZYNOWANY`. Pojemność lokalizacji jest **informacyjna** (W-08) — przekroczenie nie
blokuje, tylko daje `warning`.

```bash
curl -s -b $JAR -X POST "$BASE/skaner/api/rozmiesc/" -H "X-CSRFToken: $TOKEN" \
     -d "hu=HU00000028&location=A01-02-01"
```

```json
{"ok": true, "message": "HU HU00000028 → A01-02-01",
 "hu": {"number": "HU00000028", "material_index": "DEMO-014",
        "material_name": "Maseczka ochronna FFP2", "quantity": 36, "unit": "PCS",
        "status": "ZMAGAZYNOWANY", "status_label": "Zmagazynowany", "lot": "L0142",
        "location": "A01-02-01"},
 "warning": "Lokalizacja A01-02-01 ma więcej palet niż pojemność (2/1)."}
```

Pole `warning` występuje tylko przy przekroczeniu pojemności.

| Status | `error` | Kiedy |
|---|---|---|
| 404 | `Nieznany HU.` | nie ma palety |
| 404 | `Nieznana lokalizacja.` | nie ma lokalizacji |
| 400 | `HU <numer> jest pusty — nie można go ulokować.` | paleta ma status `PUSTY` |

Kolejność sprawdzania: najpierw HU, potem lokalizacja. Brak pola = traktowany jak pusty kod = 404.

### 4.2 `POST /skaner/api/pick/` — pobranie palety na zlecenie WZ

| Pole formularza | Wymagane | Opis |
|---|---|---|
| `hu` | tak | numer HU, z którego pobieramy |
| `quantity` | tak | liczba całkowita ≥ 1, nie większa niż pozostało na pozycji |
| `document` | tak | **klucz** (`id`) otwartego dokumentu WZ |

Działanie: widok wybiera pozycję WZ danego materiału z pozostałą ilością — pozycja przypisana do
**tej** palety (`specific_hu`) ma pierwszeństwo przed pozycją ogólną (W-25); dla pozycji ogólnej,
gdy operator bierze inną paletę niż pierwsza wg FEFO→FIFO, odpowiedź zawiera `warning` (W-11).
Serwis `pick_from_hu` blokuje pozycję i paletę, zdejmuje ilość, zapisuje ruch `WYDANIE`; po
ostatnim pobraniu **widok** (nie serwis — T3) zmienia status dokumentu na `ZREALIZOWANY`.

```bash
curl -s -b $JAR -X POST "$BASE/skaner/api/pick/" -H "X-CSRFToken: $TOKEN" \
     -d "hu=HU00000003&quantity=5&document=3"
```

```json
{"ok": true, "message": "Wydano 5 z HU HU00000003",
 "hu": {"number": "HU00000003", "material_index": "DEMO-002",
        "material_name": "Rękawice nitrylowe L", "quantity": 19, "unit": "PCS",
        "status": "ZMAGAZYNOWANY", "status_label": "Zmagazynowany", "lot": "L0021",
        "location": "A01-03-01"},
 "warning": "Wg kolejności FEFO najpierw paleta HU00000004 (A01-04-01)",
 "document": {"id": 3, "number": "WZ20261016-003", "reference": "Zamówienie demo 3",
              "status": "OTWARTY", "lines": ["… jak w 3.3, picked i remaining zaktualizowane …"],
              "remaining_total": 45, "completed": false}}
```

Po ostatnim pobraniu `document.status` = `ZREALIZOWANY`, `remaining_total` = 0, `completed` = `true`.
Pole `warning` jest opcjonalne; `document` jest zawsze.

Kolejność walidacji i błędy:

| # | Warunek | Status | `error` |
|---|---|---|---|
| 1 | brak/pusty `document` | 400 | `Brak zlecenia.` |
| 2 | nie ma palety `hu` | 404 | `Nieznany HU.` |
| 3 | `quantity` nie jest liczbą całkowitą (także pusta) | 400 | `Niepoprawna ilość.` |
| 4 | `document` nie jest liczbą, nie istnieje albo nie jest `OTWARTY` | 404 | `Zlecenie zamknięte lub nieznane.` |
| 5 | materiał palety jest na zleceniu, ale pozycja wskazuje inną paletę | 400 | `Pozycja wskazuje paletę <numer> — zeskanuj ją.` |
| 6 | materiał nie występuje na zleceniu albo pozycja już skompletowana | 400 | `Materiał <indeks> nie jest na tym zleceniu albo już skompletowany.` |
| 7 | `quantity` > pozostało na pozycji | 400 | `Na zleceniu pozostało <n>.` |
| 8 | `quantity` < 1 | 400 | `Ilość wydania musi być dodatnia.` |
| 9 | paleta pusta | 400 | `HU <numer> jest pusty.` |
| 10 | `quantity` > ilość na palecie | 400 | `Brak stanu na HU <numer>: dostępne <a>, żądane <b>.` |
| 11 | inny `WMSError` z serwisu (np. dokument zamknięty w trakcie) | 400 | komunikat serwisu |

### 4.3 `POST /skaner/api/inwentaryzacja/` — korekta ilości na palecie

| Pole formularza | Wymagane | Opis |
|---|---|---|
| `hu` | tak | numer HU |
| `delta` | tak | liczba całkowita ≠ 0; dodatnia dodaje, ujemna odejmuje |
| `reason` | tak | jedna z: `USZKODZENIE`, `STRATA`, `NADWYZKA`, `POMYLKA`, `SPIS`, `INNE` |

Serwis liczy nową ilość od **zablokowanego** stanu (nie od odczytu widoku), zapisuje ruch
`KOREKTA` z powodem i notatką „Inwentaryzacja (skaner)”. Zejście do 0 ustawia status `PUSTY`
i zwalnia lokalizację.

```bash
curl -s -b $JAR -X POST "$BASE/skaner/api/inwentaryzacja/" -H "X-CSRFToken: $TOKEN" \
     -d "hu=HU00000002&delta=-2&reason=STRATA"
```

```json
{"ok": true, "message": "−2 → HU HU00000002: 50 PCS",
 "hu": {"number": "HU00000002", "material_index": "DEMO-001", "…": "pola jak w obiekcie hu",
        "quantity": 50, "location": "A01-02-01"}}
```

W `message` znak zmiany to `+` albo `−` (U+2212, nie myślnik ASCII).

| Status | `error` | Kiedy |
|---|---|---|
| 404 | `Nieznany HU.` | nie ma palety |
| 400 | `Niepoprawna ilość.` | `delta` nie jest liczbą całkowitą |
| 400 | `Podaj ilość.` | `delta` = 0 |
| 400 | `Wybierz powód korekty.` | `reason` spoza listy |
| 400 | `Stan nie może być ujemny (na HU <numer> jest <n>).` | wynik < 0 |

### 4.4 `POST /skaner/api/przepakuj/` — przeniesienie ilości między paletami

| Pole formularza | Wymagane | Opis |
|---|---|---|
| `source` | tak | numer HU źródłowego |
| `target` | tak | numer HU docelowego |
| `quantity` | tak | liczba całkowita ≥ 1, nie większa niż stan źródła |

Warunki serwisu: ten sam materiał, docelowa paleta nie jest `PUSTY`, partie (`lot`) zgodne lub
jedna pusta. Źródło zerowe → `PUSTY` i zwolnienie lokalizacji. Zapisywane są dwa ruchy
`PRZEPAKOWANIE`; blokady palet w kolejności `pk` (brak zakleszczeń).

```bash
curl -s -b $JAR -X POST "$BASE/skaner/api/przepakuj/" -H "X-CSRFToken: $TOKEN" \
     -d "source=HU00000001&target=HU00000002&quantity=3"
```

```json
{"ok": true, "message": "Przepakowano 3 z HU00000001 → HU00000002",
 "source": {"number": "HU00000001", "quantity": 15, "lot": "", "location": "A01-01-01", "…": "…"},
 "target": {"number": "HU00000002", "quantity": 53, "lot": "L0012", "location": "A01-02-01", "…": "…"}}
```

(`source` i `target` to pełne obiekty `hu`; skrócone w przykładzie.)

| Status | `error` | Kiedy |
|---|---|---|
| 404 | `Nieznany HU źródłowy.` / `Nieznany HU docelowy.` | brak palety (źródło sprawdzane pierwsze) |
| 400 | `Niepoprawna ilość.` | `quantity` nie jest liczbą całkowitą |
| 400 | `Paleta źródłowa i docelowa są takie same.` | `source` = `target` |
| 400 | `Różny materiał — łączyć można tylko ten sam towar (<a> ≠ <b>).` | różne materiały |
| 400 | `Paleta docelowa <numer> jest pusta/zamknięta.` | cel `PUSTY` |
| 400 | `Ilość do przepakowania musi być dodatnia.` | `quantity` < 1 |
| 400 | `Brak stanu na palecie <numer>: dostępne <n>.` | za mało na źródle |
| 400 | `Różne partie (LOT <a> ≠ <b>) — nie można łączyć.` | różne partie |

---

## 5. Pozostałe punkty końcowe

### 5.1 `GET /healthz` — kontrola żywotności

Bez logowania. Sprawdza tylko połączenie z bazą (`SELECT 1`).

| Status | Treść | Znaczenie |
|---|---|---|
| 200 | `{"status": "ok", "db": true}` | baza odpowiada |
| 503 | `{"status": "degraded", "db": false}` | brak połączenia z bazą |

Zwolniony z przekierowania HTTPS (`SECURE_REDIRECT_EXEMPT`) — kontener sprawdza go po HTTP.
`Host` musi być w `ALLOWED_HOSTS` (`localhost` i `127.0.0.1` prod dodaje zawsze). Nie sprawdza
migracji, miejsca na dysku ani kopii zapasowych. Konsumenci: `HEALTHCHECK` w `Dockerfile`
(co 30 s), healthcheck Coolify, smoke test w CI ([RUNBOOK.md](../operacje/RUNBOOK.md) §9).

### 5.2 Logowanie i wylogowanie

| Trasa | Metoda | Opis |
|---|---|---|
| `/login/` | GET, POST | formularz (`username`, `password`, `csrfmiddlewaretoken`); **limit 10 prób POST / 5 min na IP** — po przekroczeniu **429** (`text/plain`); limit liczony per proces gunicorna (T8) |
| `/logout/` | POST | wylogowanie (Django 5: tylko POST); zapis w dzienniku logowań |
| `/powitanie/ukryj/` | POST | ukrywa panel „Od czego zacząć” do końca sesji (`login_required`) |

### 5.3 Tryb demo (tylko `DEMO_MODE=1`; poza demo → 404)

| Trasa | Metoda | Uprawnienie | Działanie |
|---|---|---|---|
| `/demo/` | GET | publiczne | jeśli nikt nie jest zalogowany — loguje kontem `DEMO_USER` (musi być z listy `demo_operator`, `demo_podglad`) **na GET**, potem 302 na `/?demo=1`; zalogowanego nie przelogowuje. Świadomy wyjątek od „zmiany tylko na POST” ([auth.md #12](../pitfalls/auth.md)); limit 10 wejść / 300 s / IP (US-005) |
| `/login/demo/` | POST | publiczne, CSRF | „Wejdź jako demo” — logowanie bez hasła; opcjonalne `next` (sprawdzane `url_has_allowed_host_and_scheme`); brak konta → komunikat i 302 na `/login/` |
| ~~`/demo/przywroc/`~~ | — | — | usunięte w US-016 (DEC-6): reset danych demo tylko ze Scheduled Task; 404 |

### 5.4 Eksporty CSV / XLSX

`login_required` (każda rola, także Podgląd). Eksport buduje wszystkie wiersze w pamięci, bez
limitu i bez strumieniowania (T9). Wartości tekstowe zaczynające się od `=`, `+`, `-`, `@`,
tabulatora lub CR dostają prefiks `'` (neutralizacja formuł).

| Trasa | Parametry | Zawartość |
|---|---|---|
| `GET /stany/eksport/<fmt>/` | `fmt` = `csv` albo `xlsx`, inaczej **404** | kolumny: Indeks, Nazwa, Jednostka, Ilość, Liczba HU (palety bez statusu `PUSTY`, suma po materiale); plik `stany_magazynowe.<fmt>`, arkusz „Stany” |
| `GET /ruchy/eksport/<fmt>/` | `fmt` jak wyżej; opcjonalnie `?type=<typ ruchu>` (`PRZYJECIE`, `ALOKACJA`, `PRZESUNIECIE`, `KOREKTA`, `WYDANIE`, `PRZEPAKOWANIE`; nieznana wartość = tylko nagłówek) | kolumny: Data, Typ, Materiał, HU, Zmiana ilości, Z lokalizacji, Do lokalizacji, Dokument, **Kto** (login — dane osobowe), Uwagi; wszystkie ruchy; plik `ruchy_magazynowe.<fmt>`, arkusz „Ruchy”; czas w strefie lokalnej `RRRR-MM-DD GG:MM` |

| Format | `Content-Type` | Szczegóły |
|---|---|---|
| CSV | `text/csv; charset=utf-8` | separator `;`, UTF-8 **z BOM** (Excel), `Content-Disposition: attachment` |
| XLSX | `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet` | nagłówek pogrubiony, `Content-Disposition: attachment` |

### 5.5 PDF

Wszystkie `login_required` (każda rola); `Content-Type: application/pdf`, `Content-Disposition: inline`.
Kod QR zawiera numer HU (etykieta palety) albo kod lokalizacji (etykieta lokalizacji).

| Trasa | Parametry | Plik | Limit / uwagi |
|---|---|---|---|
| `GET /hu/<pk>/etykieta/` | — | `<numer HU>.pdf` | jedna etykieta |
| `GET /hu/etykiety/` | filtry jak na liście HU: `status`, `q` | `etykiety_hu.pdf` | **limit 200** palet; powyżej — przekierowanie na listę z komunikatem „Zawęź filtr” (D-11) |
| `GET /lokalizacje/<pk>/etykieta/` | — | `LOK-<kod>.pdf` | jedna etykieta |
| `GET /lokalizacje/etykiety/` | opcjonalnie `type` (`PICKING` / `ZAPAS`) | `etykiety_lokalizacji.pdf` | **bez limitu** (R5) |
| `GET /wydania/<pk>/pdf/` | — | `<numer WZ>.pdf` | dokument wydania |

Pozostałe trasy (≈ 70) to ekrany HTML; pełna lista w `warehouse/urls.py`, mapa ról w
[AUDYT, Załącznik A](../AUDYT.md).

---

## 6. Uprawnienia — skrót

| Trasa | Anonim | Podgląd | Operator | Administrator |
|---|---|---|---|---|
| `/skaner/api/*` (8) | 302 → `/login/` | 403 | 200 / 400 / 404 | 200 / 400 / 404 |
| `/healthz` | 200 / 503 | 200 / 503 | 200 / 503 | 200 / 503 |
| `/stany/eksport/…`, `/ruchy/eksport/…`, PDF-y | 302 | 200 | 200 | 200 |

Zasada dla nowych endpointów: **test odmowy dla każdej roli**
([STRATEGIA_TESTOW.md](../testy/STRATEGIA_TESTOW.md) §5).

---

## 7. Mapowanie na ekrany skanera

| Ekran (`/skaner/…`) | Wywołuje |
|---|---|
| `rozmieszczanie/` | `hu` → `lokalizacja` → `rozmiesc` |
| `picking/` (lista) | `zlecenie?number=` |
| `picking/<id>/` | `zlecenie?id=` → `hu` → `pick` |
| `inwentaryzacja/` | `hu` → `inwentaryzacja` |
| `przepakowanie/` | `hu` (×2) → `przepakuj` |
| `podglad/` | `hu` |
| `lokalizacja/` | `lokalizacja-zawartosc` |

---

## 8. Wersjonowanie i stabilność

| Zasada | Treść |
|---|---|
| Brak wersji w URL | endpointy są wewnętrzne; klient (`scanner.js`, szablony) i serwer wdrażane są razem |
| Zmiany **niełamiące** | nowe opcjonalne pola w odpowiedzi, nowe endpointy — klient ignoruje nieznane pola; opis w tym pliku |
| Zmiany **łamiące** | zmiana nazwy/typu/usunięcie pola, zmiana kodu statusu, zmiana znaczenia parametru, nowy wymagany parametr — wymagają wpisu w [CHANGELOG](../../CHANGELOG.md) (sekcja „Changed”/„Removed”), aktualizacji tego pliku, `scanner.js`/szablonów i testów w **tym samym PR** |
| Kontrakt w testach | `ScannerTests` w `warehouse/tests.py`, `warehouse/tests_scanner_fixes.py`; zmiana kontraktu = zmiana testów |
| Stabilność dla stron trzecich | **brak gwarancji.** Udostępnienie API na zewnątrz wymaga osobnej decyzji (ADR): tokeny, wersjonowanie, limity, polityka zmian |
| Komunikaty błędów | teksty po polsku, przeznaczone dla człowieka — klient nie powinien ich parsować (brak kodów maszynowych) |

---

## 9. Znane ograniczenia

| # | Ograniczenie | Skutek | Powiązanie |
|---|---|---|---|
| 1 | **Brak paginacji** w `lokalizacja-zawartosc` | odpowiedź rośnie z liczbą palet w lokalizacji | R5, US-015 |
| 2 | **Brak limitera** na endpointach API i na `/demo/`, `/login/demo/` (limit tylko `/login/`) | anonimowy Operator w demo może generować dowolny ruch | R5, US-005, US-016 |
| 3 | Po wygaśnięciu sesji API zwraca 302 → HTML logowania (200 po `fetch`) | własny klient widzi HTML zamiast JSON | [auth.md #10](../pitfalls/auth.md); `scanner.js` to obsługuje |
| 4 | **Brak idempotencji** — ponowienie POST (np. po timeoucie sieci) wykona operację drugi raz | podwójne pobranie lub korekta | po błędzie sieci sprawdź stan (`GET …/hu/`) przed ponowieniem |
| 5 | **Brak górnej granicy** `quantity` / `delta` | liczba spoza zakresu bazy (SQLite: > 2^63; PostgreSQL: > 2^31−1) kończy się **500 (HTML)**, nie 400. Potwierdzone lokalnie: wartość poza zakresem → `OverflowError` | T16, US-013 |
| 6 | Domknięcie WZ (`ZREALIZOWANY`) w widoku `api_pick`, poza `services.py` i bez blokady dokumentu | logika w dwóch miejscach | T3, D-05, US-018 |
| 7 | Niespójne dopasowanie kodów: HU bez rozróżniania wielkości liter, lokalizacje z rozróżnianiem | `a01-01-01` nie znajdzie `A01-01-01` | do decyzji PO |
| 8 | `zlecenie` bez parametrów → 404 (nie 400) | niejednolity kod błędu | kosmetyka |
| 9 | `document.completed` jest `true` tylko dla `ZREALIZOWANY` | po spakowaniu/wysłaniu znów `false` | klient nie powinien używać do rozpoznawania „zamknięte” |
| 10 | Odpowiedzi 403/405/500 nie są JSON-em | klient musi sprawdzać status i `Content-Type` | sekcja 1.1 |
| 11 | Endpointy nie są objęte macierzą testów „rola × trasa” | regresja uprawnień możliwa | US-007; [STRATEGIA_TESTOW.md](../testy/STRATEGIA_TESTOW.md) §5 |

---

## 10. Historia zmian dokumentu

| Wersja | Data | Zmiana |
|---|---|---|
| 0.1 | 2026-10-16 | szkic: 8 endpointów skanera, healthz, demo, eksporty, PDF |
