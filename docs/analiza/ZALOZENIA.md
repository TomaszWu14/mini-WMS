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
| Z-05 | Publiczne demo pozostaje i jest traktowane jako powierzchnia ataku dostępna anonimowo z rolą Operator; jego niedostępność to ryzyko wizerunkowe, nie utrata danych. | README, `COOLIFY.md §11`. | AUDYT §4 pyt. 4, R5 | do potwierdzenia |
| Z-06 | Jeden magazyn, jedna firma, brak separacji danych między użytkownikami (każdy zalogowany widzi wszystko w ramach swojej roli). | `docs/pitfalls/auth.md` #4, docs/01 „poza zakresem”. | — | do potwierdzenia |
| Z-07 | Pilne poprawki bezpieczeństwa z audytu (R1–R4, R7, R10) mają pierwszeństwo przed nowymi funkcjami. | prompt §7 pkt 4. | AUDYT §4 pyt. 3 | do potwierdzenia |
| Z-08 | Próg pokrycia testami: 80 % ogółem, 90 % dla `warehouse/services.py` (stan: 81 % / 91 %). | prompt §5 (domyślnie 80 % dla logiki domenowej). | DEC-3 | do potwierdzenia |
| Z-09 | Retencja dziennika logowań: 90 dni; podstawa przetwarzania: prawnie uzasadniony interes (bezpieczeństwo systemu). | Minimalizacja danych; typowa praktyka. | DEC-5, R7 | do potwierdzenia |
| Z-10 | Skany bezpieczeństwa na PR: bandit, pip-audit (zależności produkcyjne), gitleaks — blokujące; trivy i semgrep — tygodniowo, doradczo. | Koszt minut Actions vs. szybkość wykrycia CVE. | DEC-2, R10 | do potwierdzenia |
| Z-11 | Mierniki sukcesu M-01…M-06 (`WIZJA.md`) są propozycją; wartość bazowa „brak danych”, cele ustala PO po pierwszym pomiarze; M-01…M-04 mierzalne dopiero po wdrożeniu lub pilotażu. | Liczb nie zbierano (docs/01); aplikacja nie była wdrożona. | WIZJA §mierniki | do potwierdzenia |
| Z-12 | Interesariusze ST-01…ST-03 (magazynierzy, kierownik, administrator systemu) to role-persony reprezentowane przez PO; kanał kontaktu = PO. | Wymagania pochodzą z obserwacji autora (README, AUDYT §1.3). | INTERESARIUSZE | do potwierdzenia |
| Z-13 | Zamrożenie magazynu na czas spisu (D-07) pozostaje procedurą organizacyjną bez blokady technicznej; kod niczego nie blokuje. | `services.create_stocktake`/`close_stocktake` nie blokują ruchów. | PROCESY P-06 | do potwierdzenia |
| Z-14 | Akceptacja ryzyk i decyzje o danych osobowych: w scenariuszu „portfolio” zatwierdza PO, w scenariuszu „wdrożenie” administrator danych (firma wdrażająca). | Macierz RACI w INTERESARIUSZE, zależne od Z-04. | INTERESARIUSZE | do potwierdzenia |
| Z-15 | RODO: firma wdrażająca = administrator danych, autor = ewentualnie podmiot przetwarzający; dla publicznego demo autor jest operatorem usługi. Wymaga oceny prawnej. | Brak rozstrzygnięć w repo; R7. | RODO.md | do potwierdzenia |
| Z-16 | Brak samoobsługowej zmiany i odzyskiwania hasła traktujemy jako stan obecny, nie wymaganie; hasło ustawia Administrator. | Brak tras w `urls.py`; PROCESY P-05. | PROCESY P-05 | do potwierdzenia |
| Z-17 | RPO i RTO nie są zdefiniowane; faktyczne RPO ≤ interwał backupu (domyślnie 24 h), RTO nieznane (odtworzenie nieprzećwiczone). | COOLIFY.md §10; R9. | RUNBOOK | do potwierdzenia |

Historia zmian: 2026-10-15 — utworzenie rejestru po audycie (`docs/AUDYT.md`); 2026-10-16 — Z-11…Z-17 z dokumentów [BA] (krok 3).
