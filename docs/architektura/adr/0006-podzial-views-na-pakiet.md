# ADR-0006 — Podział `views.py` na pakiet `warehouse/views/` według obszarów

| | |
|---|---|
| Status | zaakceptowany przez zespół [DEV] (decyzja techniczna, bez zmiany działania) |
| Data | 2026-10-16 |
| Właściciel | [DEV] |
| Powiązania | US-017, NFR-027, SEC-007; AUDYT T2; `warehouse/views/`, `warehouse/tests_urls.py`, `warehouse/tests_access_matrix.py` |

## Kontekst

`warehouse/views.py` urósł do 1483 linii i 61 definicji (47 widoków panelu plus pomocnicze). Każda historyjka
US-001…US-016 dotykała tego pliku, więc diffy były długie, a review trudne. Plik był już podzielony komentarzami
`# --- …` na 13 sekcji, między którymi nie ma żadnych wzajemnych odwołań (sprawdzone analizą AST).

## Rozważane opcje

| Opcja | Zalety | Wady |
|---|---|---|
| **pakiet `views/` z re-eksportem w `__init__.py`** | `urls.py` (`views.<nazwa>`) i importy `from .views import …` działają bez zmian; moduł = obszar biznesowy | `__init__.py` trzeba uzupełniać przy nowym widoku |
| moduły obok `views.py` (`views_issues.py` …) | brak pakietu | płaska lista ~10 plików `views_*`; `urls.py` do przepisania |
| zostawić jeden plik | zero pracy | koszt zmian i konflikty rosną z każdą historyjką |

## Decyzja

Pakiet `warehouse/views/` z dziesięcioma modułami: `dashboard`, `masterdata` (materiały, lokalizacje),
`receiving`, `handling_units` (HU, przepakowanie), `issues`, `stock`, `stocktake` (spis, inwentaryzacja palety),
`movements`, `users`, `reports`. Każda sekcja przeniesiona bez zmian (porównanie AST: 61 definicji identycznych,
łącznie z dekoratorami ról). `__init__.py` re-eksportuje wszystkie nazwy z jawnym `__all__`. Widoki skanera
zostają w `scanner_views.py`.

Siatki bezpieczeństwa: `tests_urls.py` (migawka 72 tras: nazwa → wzorzec adresu i nazwa widoku, zapisana przed
podziałem) oraz macierz dostępu z US-007.

## Konsekwencje

- Nowy ekran: funkcja w module swojego obszaru, wpis w `views/__init__.py`, trasa w `urls.py`, wiersz w
  `tests_urls.EXPECTED` i w macierzy dostępu.
- `patch()` w testach musi celować w moduł, w którym widok czyta nazwę (np.
  `warehouse.views.handling_units.HU_LABELS_LIMIT`), a nie w pakiet — zmieniono tak 3 cele w 2 testach.
- Numery linii `views.py:NNN` w audycie i threat modelu odnoszą się do stanu sprzed podziału (dokumenty historyczne).
