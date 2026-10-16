# Interesariusze — miniWMS

| | |
|---|---|
| Wersja | 0.1 |
| Data | 2026-10-16 |
| Status | szkic — do akceptacji Product Ownera |
| Właściciel | [BA] |

Rozszerza tabelę trzech ról z [docs/01 — Interesariusze](../01-problem-i-zakres.md#interesariusze) o osoby
i podmioty, których tam brakuje ([audyt §1.2](../AUDYT.md)): Product Owner, administrator infrastruktury,
odbiorca WZ, strona odpowiedzialna za dane osobowe. Role w aplikacji (Operator, Administrator, Podgląd):
[docs/02 — Aktorzy](../02-proces.md#aktorzy), [SLOWNIK.md](SLOWNIK.md).

**Uwaga o źródle wiedzy.** Aplikacja nie była wdrożona; wymagania pochodzą z obserwacji autora
([README](../../README.md), [audyt §1.3 pkt 7](../AUDYT.md)). ST-01…ST-03 to dziś **role-persony**
reprezentowane przez PO, nie osoby, z którymi zespół rozmawia. Dotyczy to też kolumny „Kanał kontaktu”.

## 1. Rejestr interesariuszy

Wpływ: **W** wysoki, **Ś** średni, **N** niski — na kształt i decyzje produktu. PO = autor repozytorium.

| ID | Interesariusz | Rola / potrzeba | Wpływ | Dostarcza / akceptuje | Kanał kontaktu z zespołem |
|---|---|---|---|---|---|
| ST-01 | Magazynierzy / operatorzy (rola Operator) | szybko przyjąć, odłożyć i znaleźć paletę; skanować zamiast pisać ([docs/01](../01-problem-i-zakres.md#interesariusze)) | W | wiedzę o procesie; akceptuje użyteczność skanera (dziś niezwalidowana) | przez PO; brak bezpośredniego kanału |
| ST-02 | Kierownik magazynu | aktualny stan i miejsce towaru, historia operacji, spis z natury bez chaosu | W | reguły biznesowe (np. powody korekt); akceptuje wynik spisu — czy formalnie, **do potwierdzenia** | przez PO; brak bezpośredniego kanału |
| ST-03 | Administrator systemu (rola Administrator) | konta i role, dziennik logowań, termin dostawy palety | W | zakładanie i dezaktywacja kont ([P-05](PROCESY.md)); jego konto to cel ataku (R1) | przez PO |
| ST-04 | Product Owner | decyduje o zakresie, priorytetach, wyjątkach od ryzyk; jedyny scala zmiany do `main` (Z-02) | W | decyzje DEC-1…6, odpowiedzi na pytania BA; akceptuje dokumenty i wydania | GitHub: komentarze w PR; sesja z asystentem |
| ST-05 | Administrator infrastruktury (Coolify / VPS) | wdrożenie, sekrety, backup, harmonogramy, DNS i TLS ([COOLIFY.md](../../COOLIFY.md)) | W | konfigurację środowisk; skutki R2 i R9 zależą od niego | PO; instrukcje: COOLIFY.md, `docs/operator/*.md`, `operacje/RUNBOOK.md` (planowany) |
| ST-06 | Odbiorca dokumentu WZ (klient, przewoźnik) | dostać czytelny dokument wydania; **nie ma konta**, widzi tylko PDF | N | wymagania formalne wobec treści WZ — **do potwierdzenia** | brak; pośrednio przez ST-01/ST-02 |
| ST-07 | Administrator danych w rozumieniu RODO (firma wdrażająca) | decyduje o celach i sposobach przetwarzania danych pracowników (login, IP, „kto” w ruchach) | W przy scenariuszu B (Z-04) | podstawę prawną, retencję (Z-09), procedurę praw osób; ocenę incydentu | PO / dostawca; forma umowna **do ustalenia** |
| ST-08 | Dostawca oprogramowania (autor) | utrzymać kod, naprawiać błędy, dostarczać zmiany; wobec RODO ewentualnie podmiot przetwarzający (**do oceny prawnej**) | W | kod, testy, dokument operatora per branch (`docs/operator/`) | repozytorium GitHub; dziś ta sama osoba co ST-04 |
| ST-09 | Odwiedzający publiczne demo (rekruterzy, anonimowy Operator) | w kilka minut zobaczyć działanie bez logowania ([README](../../README.md)) | Ś | ruch i opinię; ich IP trafia do `LoginEvent` (R5, R7); niedostępność demo to ryzyko wizerunkowe (Z-05) | README (brak SECURITY.md i szablonów issue — [audyt §1.2](../AUDYT.md)) |
| ST-10 | Zespół BA / DEV / SEC (sesje asystenta AI) | analiza, kod i testy, bezpieczeństwo; reviewerzy `security-reviewer`, `db-reviewer` ([CLAUDE.md](../../CLAUDE.md)) | Ś | dokumenty, PR w trybie *draft*, raporty; nie akceptuje własnej pracy (Z-02) | PR draft + raport sesji + komentarze PO |

Dziś ST-04, ST-05 i ST-08 to jedna osoba. Macierz poniżej opisuje podział odpowiedzialności, który ma sens
przy wdrożeniu (B) — rozdzielenie ról nie jest dziś wymagane.

## 2. Macierz RACI kluczowych decyzji

R — wykonuje, A — odpowiada i zatwierdza (dokładnie jedna osoba na wiersz), C — konsultowany, I — informowany.
Kolumny: ST-04 PO · ST-01 operatorzy · ST-02 kierownik · ST-03 admin systemu · ST-05 admin infrastruktury ·
ST-07 administrator danych · ST-08 dostawca · ST-10 zespół.

| Decyzja | ST-04 | ST-01 | ST-02 | ST-03 | ST-05 | ST-07 | ST-08 | ST-10 |
|---|---|---|---|---|---|---|---|---|
| Zakres (co jest, co poza zakresem — docs/01) | A | C | C | I | I | C | C | R |
| Priorytety (kolejność backlogu, Z-07) | A | C | C | I | C | I | C | R |
| Akceptacja ryzyka i wyjątków (`bezpieczenstwo/RYZYKA.md`) | A¹ | I | I | I | C | C¹ | C | R |
| Wydanie / merge do `main` (= deploy produkcji, Z-02) | A/R | I | I | I | C | I | C | R |
| Dane osobowe (retencja, podstawa prawna, prawa osób) | C¹ | I | I | C | C | A¹ | R | R |

¹ Scenariusz A (portfolio, brak realnych pracowników): ST-07 nie istnieje, wiersze „ryzyko” i „dane osobowe”
zatwierdza ST-04. Scenariusz B (wdrożenie): za ryzyko dotykające danych firmy i za dane osobowe odpowiada ST-07;
ST-04 pozostaje właścicielem produktu. Rozstrzygnięcie zależy od Z-04.

## Otwarte pytania (do PO)

1. Jaką rolę w aplikacji ma kierownik (Podgląd czy Administrator) i czy zatwierdza wynik spisu (zasada dwóch
   osób)? Dziś zamknięcie arkusza robi Operator.
2. Kto w małej firmie jest administratorem systemu — osoba inna niż operator? Od tego zależy waga R1 w praktyce.
3. Czy w scenariuszu B PO zostaje autorem, czy wskazuje przedstawiciela firmy wdrażającej?
4. Kto jest administratorem danych odwiedzających publiczne demo (IP w `LoginEvent`) — autor jako operator
   usługi? Wymaga oceny prawnej.
5. Czy odbiorca WZ ma wymagania formalne wobec dokumentu (dane stron, podpis), których PDF dziś nie spełnia?
