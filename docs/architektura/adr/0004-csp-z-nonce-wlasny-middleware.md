# ADR-0004 — CSP z nonce: własny middleware zamiast `django-csp`

| | |
|---|---|
| Status | zaakceptowany przez zespół [DEV]/[SEC] |
| Data | 2026-10-16 |
| Właściciel | [DEV] z udziałem [SEC] |
| Powiązania | US-011, SEC-022, SEC-024, SEC-025; AUDYT R8; TM-16; ASVS 14.4.3; `warehouse/csp.py`, `static/warehouse/ui.js` |

## Kontekst

Aplikacja nie wysyłała `Content-Security-Policy` ani `Permissions-Policy`. Szablony miały 8 atrybutów
`on*=`, 10 bloków `<script>` inline i jeden link `javascript:`, więc ewentualny błąd szablonu (XSS)
dawałby atakującemu pełny dostęp do sesji operatora. Django 5.2 nie ma wbudowanej obsługi CSP (pojawia się w 6.0).

## Rozważane opcje

| Opcja | Zalety | Wady |
|---|---|---|
| `django-csp` 4.x | dojrzała, konfiguracja w settings, raportowanie | nowa zależność; przy jednej, stałej polityce daje niewiele ponad 40 linii kodu |
| **własny middleware** (`warehouse/csp.py`) | brak zależności; jedna polityka w jednym miejscu; nonce w `request.csp_nonce` i w szablonach `{{ csp_nonce }}` | sami utrzymujemy (mało kodu, testy) |
| tylko hash skryptów inline | bez nonce | każdy edycja skryptu zmienia hash; trudne w utrzymaniu |

## Decyzja

Własny `SecurityHeadersMiddleware`: na każdej odpowiedzi HTML `Content-Security-Policy` z
`script-src 'self' 'nonce-…'` (losowy nonce na żądanie), `object-src 'none'`, `frame-ancestors 'none'`,
`base-uri 'self'`, `form-action 'self'`; na każdej odpowiedzi `Permissions-Policy` z `camera=(self)` (skaner)
i wyłączoną geolokalizacją, mikrofonem itd. `style-src` dopuszcza `'unsafe-inline'` (atrybuty `style="…"`
w szablonach — poza zakresem; kradzież sesji wymaga skryptu, nie stylu).

Atrybuty `on*=` zastąpiono `data-confirm`, `data-autosubmit`, `data-nav-toggle`, `data-history-back`
obsługiwanymi przez `static/warehouse/ui.js`; skrypty inline mają `nonce="{{ csp_nonce }}"`.

**Tryb: egzekwowanie od razu** (kryterium 1 zostawia wybór [DEV]): sprawdzenie w Chromium nie wykazało
naruszeń na 22 stronach (także skaner, wydanie, spis, paleta), a test szablonów pilnuje nowych zmian.
Awaryjnie `DJANGO_CSP_REPORT_ONLY=1` przełącza na `Content-Security-Policy-Report-Only` bez wdrożenia kodu.

HSTS: `SECURE_HSTS_PRELOAD = False` (wpis na listę preload jest praktycznie nieodwracalny); czas 30 dni
zostaje domyślny, wydłużenie do roku — `DJANGO_HSTS_SECONDS=31536000`, gdy domena i HTTPS są stabilne.

## Konsekwencje

- Nowy skrypt inline w szablonie **musi** mieć `nonce="{{ csp_nonce }}"`, a zachowania — `data-*` + `ui.js`;
  inaczej test `TemplateScanTests` jest czerwony, a przeglądarka zablokuje skrypt.
- Zewnętrzne skrypty i style (CDN) są zablokowane — wszystko z `static/`.
- Kamera skanera działa tylko na tej samej domenie (`camera=(self)`); test ręczny na telefonie — karta odbioru US-011.
