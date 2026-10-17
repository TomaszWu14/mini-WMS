<!-- Szablon PR: wypełnij wszystkie sekcje; „nie dotyczy” zamiast usuwania. Merge do main
     wykonuje wyłącznie Product Owner (main = auto-deploy produkcji). -->

## Co i dlaczego
<!-- 2–5 zdań: problem, rozwiązanie, alternatywy odrzucone. -->

- Historyjka / wymaganie: US-xxx, FR-xxx / NFR-xxx / SEC-xxx
- Ryzyka / dług, które zamyka: R-x, T-x, RR-xx
- ADR (jeśli decyzja istotna): `docs/architektura/adr/NNNN-….md`

## Jak przetestować
1. …
2. …

Zrzuty ekranu (jeśli zmiana UI): przed / po.

## Checklista [DEV]
- [ ] `ruff check .` i `ruff format --check .` zielone
- [ ] `mypy warehouse config` zielone
- [ ] `pytest -q` zielone, pokrycie ≥ 80 % ogółem i ≥ 90 % `services.py` (`coverage report`)
- [ ] każde kryterium akceptacji ma test (w tym kryteria bezpieczeństwa)
- [ ] migracje odwracalne, `makemigrations --check` bez zmian; migracje niszczące rozbite na dwa wdrożenia
- [ ] zmiany stanu magazynu tylko przez `warehouse/services.py`
- [ ] dokumentacja zaktualizowana: WYMAGANIA / API / MODEL_DANYCH / ADR (jeśli dotyczy)
- [ ] `CHANGELOG.md` — wpis w `[Unreleased]`
- [ ] `docs/operator/<branch>.md` wygenerowany wg `docs/operator/TEMPLATE.md`
- [ ] brak sekretów, danych osobowych i danych produkcyjnych w kodzie, testach, logach

## Checklista [SEC] — przegląd diffu
- [ ] uwierzytelnianie/autoryzacja: każdy nowy widok ma dekorator roli; test „brak dostępu” dla każdej roli
- [ ] zmiany stanu tylko na POST; CSRF (`{% csrf_token %}` / `X-CSRFToken`)
- [ ] walidacja wejścia (zakresy, długości, typy), zapytania przez ORM, escapowanie w szablonach
- [ ] upload: limit rozmiaru, typ pliku, limit wierszy, obsługa uszkodzonego pliku
- [ ] sekrety tylko w env; logi bez haseł, tokenów i zbędnych danych osobowych
- [ ] nagłówki i ustawienia bezpieczeństwa bez regresji (`check --deploy`)
- [ ] zależności: nowe pakiety uzasadnione, przypięte, bez znanych CVE (`pip-audit`)
- [ ] threat model / rejestr ryzyk zaktualizowany, jeśli zmienia się przepływ danych

**Wynik przeglądu SEC:** ✅ bez uwag / ⚠️ uwagi (poniżej) / ❌ blokada (uzasadnienie)

## Odbiór [BA]
- [ ] kryteria akceptacji sprawdzone punkt po punkcie na działającej aplikacji
- [ ] komunikaty i UI zrozumiałe dla magazyniera (język polski, numer HU/WZ w komunikacie)
- [ ] `docs/analiza/SLEDZENIE.md` zaktualizowany (wymaganie → historyjka → test → PR)

**Wynik odbioru BA:** ✅ / ⚠️ / ❌

## Ryzyka wdrożenia
<!-- migracje, zmienne środowiskowe, wpływ na demo, plan wycofania — link do docs/operator/<branch>.md -->

## Decyzje potrzebne od PO
<!-- „brak” albo lista z propozycją domyślną -->
