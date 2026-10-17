# Słownik pojęć — miniWMS

| | |
|---|---|
| Wersja | 0.1 |
| Data | 2026-10-16 |
| Status | szkic — do akceptacji Product Ownera |
| Właściciel | [BA] |

Wspólny język dokumentów. Pojęcia z [docs/01 — Słownik](../01-problem-i-zakres.md#słownik) podajemy w jednym zdaniu
z odnośnikiem (nie kopiujemy definicji — Z-03); poniżej dopisane są te, których tam brakuje ([audyt §1.2](../AUDYT.md)).
Kolumna „W kodzie” wskazuje klasę lub enum, żeby łatwo wrócić od nazwy z ekranu do implementacji.

## 1. Pojęcia z docs/01

| Pojęcie | Znaczenie | W kodzie |
|---|---|---|
| HU (Handling Unit) | paleta z unikalnym numerem i etykietą QR; podstawowa jednostka stanu | `HandlingUnit` |
| Lokalizacja | miejsce na regale (kod, typ, informacyjna pojemność) | `Location` |
| WZ | dokument wydania zewnętrznego: lista materiałów do wydania, numer `WZ<data>-NNN` ([D-03](../06-decyzje.md)) | `IssueDocument` |
| FEFO | *First Expired, First Out* — najpierw towar z najkrótszą datą ważności | dobór palet w `services.py` |
| FIFO | *First In, First Out* — przy równych datach najpierw najstarsze przyjęcie | j.w. |
| Ruch | zapis każdej zmiany stanu: kto, kiedy, ile, skąd, dokąd; typy: Przyjęcie, Alokacja, Przesunięcie, Korekta, Wydanie, Przepakowanie | `StockMovement`, `MovementType` |
| Spis z natury | inwentaryzacja: migawka stanu → liczenie → zatwierdzenie różnic ([P-04](PROCESY.md), [P-06](PROCESY.md)) | `StocktakeSheet` |

## 2. Role i konta

| Pojęcie | Znaczenie | W kodzie |
|---|---|---|
| Operator | rola do operacji magazynowych (przyjęcie, rozmieszczenie, wydanie, korekta, spis, import) i skanera; nie zarządza kontami | `Role.OPERATOR`, `operator_required` (przepuszcza też Administratora) |
| Administrator | rola Operatora plus konta i role, dziennik logowań, termin dostawy palety | `Role.ADMIN`, `admin_required` |
| Podgląd | rola tylko do odczytu (stany, palety, wydania, ruchy, raporty, PDF, eksporty); tak wypada konto bez profilu | `Role.VIEWER` |
| superuser | konto Django z flagą `is_superuser`: aplikacja traktuje je jak Administratora, a ponadto ma panel `/admin/` (edycja i usuwanie ruchów), wyłączony w trybie demo | `roles.get_role`, `User.is_superuser` |
| Dziennik logowań | rejestr logowań, wylogowań i nieudanych prób (login, IP, przeglądarka), widoczny dla Administratora | `LoginEvent` |
| Tryb demo | tryb włączany zmienną `DEMO_MODE=1`: baner, „Wejdź jako demo”, panel „Od czego zacząć”, import do 500 wierszy, wyłączony `/admin/`, dane fikcyjne resetowane ([P-08](PROCESY.md)) | `settings.DEMO_MODE` |
| Konto demo | `demo_operator` (Operator) i `demo_podglad` (Podgląd) z jawnym hasłem; chronione przed edycją w panelu użytkowników | `DEMO_ACCOUNTS`, `demo.is_demo_account` |

## 3. Magazyn i stany

| Pojęcie | Znaczenie | W kodzie |
|---|---|---|
| LOT / partia | numer partii dostawy lub producenta zapisany na palecie; przepakować można tylko palety tego samego materiału i zgodnej partii (W-19) | `HandlingUnit.lot` |
| Status HU | **Do ułożenia** — przyjęta, jeszcze bez lokalizacji; **Zmagazynowany** — ułożona w lokalizacji; **Pusty** — cała ilość pobrana, miejsce zwolnione (korekta z 0 na więcej przywraca „Do ułożenia”) | `HUStatus` |
| Status WZ | **Otwarty** → **Zrealizowany** → (**Spakowany**) → **Wysłany**; pakowanie jest opcjonalne ([D-06](../06-decyzje.md)) | `IssueStatus` |
| PICKING / ZAPAS | typy lokalizacji: PICKING to miejsce kompletacji bliżej wydania, ZAPAS to zapas; wydanie dobiera najpierw palety z PICKING | `LocationType` |
| Picking (kompletacja) | zbieranie palet pod dokument WZ, w panelu („Realizuj”) albo skanerem | `scanner_views.api_pick` |
| Skaner | ekrany w przeglądarce telefonu lub kolektora: rozmieszczanie, picking, inwentaryzacja, przepakowanie, podglądy ([D-08](../06-decyzje.md)) | `scanner_views.py`, `/skaner/` |
| Korekta | zmiana ilości palety do ustalonej wartości, zapisana jako ruch KOREKTA (nie może zejść poniżej zera) | `services.correct_hu_quantity`, `MovementType.KOREKTA` |
| Powód korekty | obowiązkowa kategoria każdej korekty: Uszkodzenie, Strata / ubytek, Nadwyżka, Pomyłka ewidencji, Spis z natury, Inne (W-26) | `AdjustReason` |
| Przepakowanie | przeniesienie ilości między dwiema paletami tego samego materiału i partii; zostają dwa ruchy | `services.repack_hu`, `MovementType.PRZEPAKOWANIE` |
| Arkusz spisu | migawka palet (cały magazyn lub lokalizacja) z polem „Policzono”; zamknięcie zamienia różnice w korekty z powodem SPIS | `StocktakeSheet`, `StocktakeLine`, `StocktakeStatus` |

## 4. Proces pracy zespołu i bezpieczeństwo

| Pojęcie | Znaczenie | W repozytorium |
|---|---|---|
| Historyjka | opis potrzeby „Jako <rola> chcę <cel>, aby <korzyść>” z kryteriami akceptacji | `analiza/HISTORYJKI.md` (planowany) |
| DoR / DoD | *Definition of Ready* — warunki, by historyjka mogła wejść do pracy; *Definition of Done* — warunki jej ukończenia | [CONTRIBUTING.md](../../CONTRIBUTING.md) §3–4 (w trakcie powstawania); wcześniej niejawne (hook `check.py`, [CLAUDE.md](../../CLAUDE.md)) |
| ADR | *Architecture Decision Record* — zapis jednej decyzji: kontekst, opcje, decyzja, skutki | dziennik D-01…D-13 w [docs/06](../06-decyzje.md); docelowo `architektura/adr/` |
| STRIDE | mnemonik zagrożeń: podszycie, modyfikacja, wyparcie się, ujawnienie, odmowa usługi, eskalacja uprawnień | `bezpieczenstwo/` — model zagrożeń (planowany) |
| ASVS | *OWASP Application Security Verification Standard* — katalog wymagań weryfikacji bezpieczeństwa aplikacji web, poziomy L1–L3; poziom docelowy do ustalenia | `bezpieczenstwo/` (planowany) |
| RODO | rozporządzenie o ochronie danych osobowych; **administrator danych** to podmiot decydujący o celach i sposobach przetwarzania, **podmiot przetwarzający** działa na jego zlecenie (w miniWMS: firma wdrażająca i autor — [ST-07, ST-08](INTERESARIUSZE.md), do oceny prawnej) | `bezpieczenstwo/RODO.md` (planowany) |
| Dane osobowe | w aplikacji: login, e-mail, IP, przeglądarka, wpisany login przy nieudanej próbie, „kto” w ruchach i dokumentach ([audyt §3.2](../AUDYT.md)) | `auth_user`, `LoginEvent`, `created_by` |

## 5. Identyfikatory w dokumentach

| Oznaczenie | Znaczenie | Gdzie |
|---|---|---|
| W-01…W-26 | wymagania funkcjonalne | [docs/05](../05-wymagania.md) |
| D-01…D-13 | decyzje projektowe | [docs/06](../06-decyzje.md) |
| R1…R10, T1…T16 | ryzyka bezpieczeństwa, dług techniczny | [audyt §3.3, §2.4](../AUDYT.md) |
| Z-01…Z-10, DEC-1…6 | założenia, decyzje do podjęcia przez PO | [ZALOZENIA.md](ZALOZENIA.md), [audyt §5](../AUDYT.md) |
| ST-xx, P-xx, L-xx, M-xx | interesariusze, procesy, luki procesowe, mierniki | [INTERESARIUSZE.md](INTERESARIUSZE.md), [PROCESY.md](PROCESY.md), [WIZJA.md](WIZJA.md) |
| ekran 1–35, 40–47 | numeracja ekranów panelu i skanera | [docs/03](../03-user-flow.md) |

## Otwarte pytania (do PO)

1. Jaki poziom ASVS (L1, L2) jest docelowy — zależy od scenariusza A/B z [WIZJA.md](WIZJA.md).
2. Czy ujednolicić nazewnictwo „WZ” / „wydanie” / „dokument wydania” (menu mówi „Wydania”, dokument „WZ”)?
   Słownik na razie używa obu: WZ to dokument, wydania to ich lista i proces.
