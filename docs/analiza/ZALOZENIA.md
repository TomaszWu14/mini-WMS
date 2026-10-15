# Założenia — rejestr [BA]

Założenia przyjęte przez zespół, gdy Product Owner nie odpowiedział (jeszcze) na pytanie.
Każde ma status **do potwierdzenia** do czasu decyzji PO; potwierdzone przenosimy do
właściwego dokumentu (WIZJA, WYMAGANIA, RYZYKA) i tu zostawiamy ślad.

| ID | Założenie | Dlaczego tak (bezpieczne minimum) | Źródło pytania | Status |
|---|---|---|---|---|
| Z-01 | Dokumentacja po polsku; kod, nazwy, komunikaty commitów po angielsku w konwencji Conventional Commits (`feat:`, `fix:`, `docs:`, `security:`…). | Tak jest w historii repo (25 commitów po angielsku z prefiksami), docs po polsku. | AUDYT §4 pyt. 5a | do potwierdzenia |
| Z-02 | Praca na gałęziach z PR w trybie *draft*; merge do `main` wykonuje wyłącznie PO (`main` = auto-deploy produkcji przez Coolify). Push na gałąź roboczą sesji jest dozwolony, bo sesja w chmurze nie zachowuje plików inaczej. | `docs/pitfalls/deploy.md` #1, `guard.py` blokuje push na `main`. | prompt §8 („nie rób push bez zgody”) | do potwierdzenia |
| Z-03 | Istniejące `docs/01–07` są źródłem prawdy o wymaganiach; nowa struktura (`docs/analiza`, `docs/architektura`, `docs/bezpieczenstwo`…) uzupełnia je, nie nadpisuje. Przeniesienie plików pod nowe nazwy tylko po zgodzie PO, z aktualizacją linków w README. | prompt §2 („nie nadpisując istniejących treści bez pytania”). | AUDYT §4 pyt. 5b, DEC-1 | do potwierdzenia |
| Z-04 | Aplikacja jest oceniana jak produkt do realnego wdrożenia u klienta (nie tylko portfolio) — ryzyka bezpieczeństwa i RODO ważone jak dla produkcji. | Bezpieczniej założyć wyższy reżim; łatwo obniżyć niż nadrobić. | AUDYT §4 pyt. 1 | do potwierdzenia |
| Z-05 | Publiczne demo pozostaje i jest traktowane jako powierzchnia ataku dostępna anonimowo z rolą Operator; jego niedostępność to ryzyko wizerunkowe, nie utrata danych. | README, `COOLIFY.md §11`. | AUDYT §4 pyt. 4, R3 | do potwierdzenia |
| Z-06 | Jeden magazyn, jedna firma, brak separacji danych między użytkownikami (każdy zalogowany widzi wszystko w ramach swojej roli). | `docs/pitfalls/auth.md` #4, docs/01 „poza zakresem”. | — | do potwierdzenia |
| Z-07 | Pilne poprawki bezpieczeństwa z audytu (R1, R2, T1/R4, R7, R9) mają pierwszeństwo przed nowymi funkcjami. | prompt §7 pkt 4. | AUDYT §4 pyt. 3 | do potwierdzenia |
| Z-08 | Próg pokrycia testami: 80 % ogółem, 90 % dla `warehouse/services.py` (stan: 81 % / 91 %). | prompt §5 (domyślnie 80 % dla logiki domenowej). | DEC-3 | do potwierdzenia |
| Z-09 | Retencja dziennika logowań: 90 dni; podstawa przetwarzania: prawnie uzasadniony interes (bezpieczeństwo systemu). | Minimalizacja danych; typowa praktyka. | DEC-5, R7 | do potwierdzenia |
| Z-10 | Skany bezpieczeństwa na PR: bandit, pip-audit (zależności produkcyjne), gitleaks — blokujące; trivy i semgrep — tygodniowo, doradczo. | Koszt minut Actions vs. szybkość wykrycia CVE. | DEC-2, R9 | do potwierdzenia |

Historia zmian: 2026-10-15 — utworzenie rejestru po audycie (`docs/AUDYT.md`).
