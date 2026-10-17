# Polityka bezpieczeństwa (Security Policy)

| | |
|---|---|
| Wersja | 0.2 |
| Data | 2026-10-17 |
| Status | szkic — do akceptacji Product Ownera |
| Właściciel | [SEC] |

> **English summary.** mini-WMS is a Django warehouse-management app; only the `main` branch
> is supported. To report a vulnerability, use GitHub's **Report a vulnerability** (private
> vulnerability reporting) on this repository — it is the only channel. Please do not open a public issue, and do not run
> denial-of-service tests or bulk imports against the shared public demo
> (`miniwms.twapp.pl`). Proposed targets: acknowledgement within 5 business days,
> assessment within 14 days. Good-faith research that follows this policy will not lead to
> legal action by the maintainer. The rest of this document is in Polish.

## Jak zgłosić podatność

1. **Jedyny kanał** (decyzja PO 2026-10-17): zakładka **Security → Report a vulnerability**
   w repozytorium
   [TomaszWu14/miniWMS-public](https://github.com/TomaszWu14/miniWMS-public/security/advisories/new)
   (GitHub Private Vulnerability Reporting). Zgłoszenie widzi tylko właściciel repozytorium.
   Publicznego adresu e-mail celowo nie podajemy.
2. **Nie zakładaj publicznego issue ani PR z opisem luki** i nie publikuj szczegółów przed
   uzgodnieniem terminu ujawnienia.

Co warto zawrzeć w zgłoszeniu:

- opis podatności i jej wpływ (co może zrobić atakujący, jakie dane zagrożone),
- kroki odtworzenia: commit lub data, rola konta (Podgląd, Operator, Administrator, brak
  konta), minimalne żądanie lub plik,
- sugerowaną poprawkę (opcjonalnie),
- czy chcesz być wymieniony w podziękowaniach.

## Zakres

| W zakresie | Poza zakresem |
|---|---|
| kod aplikacji (`warehouse/`, `config/`, szablony, JS) | infrastruktura Coolify i VPS autora, DNS, certyfikaty, konta GitHub i Coolify |
| obraz Docker (`Dockerfile`, `entrypoint.sh`) i pliki compose (`docker-compose.yml`, `docker-compose.coolify.yml`, `Caddyfile`) | ataki wolumetryczne DoS, testy obciążeniowe, masowe importy na publicznym demo |
| skrypty (`scripts/`) i workflow CI (`.github/`) | socjotechnika, phishing, ataki fizyczne |
| domyślne ustawienia i dokumentacja wdrożenia, jeśli prowadzą do niebezpiecznej konfiguracji (np. słabe sekrety domyślne) | podatności w zależnościach bez ścieżki wykorzystania w mini-WMS (zgłoś upstream; zależności sprawdzamy `pip-audit`) |
| uwierzytelnianie, role, sesje, CSRF/XSS i wstrzyknięcia, importy i upload, eksporty i PDF, dane osobowe (dziennik logowań), łańcuch dostaw | świadome wyjątki demo: publiczna rola Operator, logowanie na `GET /demo/`, jawne hasło kont demo, wyłączony `/admin/` w demo |

Znane problemy są opisane w [`docs/AUDYT.md`](docs/AUDYT.md) (R1–R10, T1–T16) i
[`docs/bezpieczenstwo/RYZYKA.md`](docs/bezpieczenstwo/RYZYKA.md). Zgłoszenie znanego
problemu nie szkodzi, ale nowy wektor, wariant lub działający dowód koncepcji jest mile
widziany.

## Zasady testowania

- **Nie wykonuj testów DoS ani masowych importów lub przyjęć na publicznym demo
  `miniwms.twapp.pl`** — to wspólna instancja, z której korzystają inni.
- **Nie próbuj logować się na cudze konta**, nie zgaduj haseł, nie używaj skanerów
  automatycznych w trybie agresywnym.
- Do testów aktywnych uruchom **własną lokalną kopię** (instrukcja w
  [`README.md`](README.md); dane fikcyjne: `DEMO_MODE=1 python manage.py seed_demo`).
  Kod jest publiczny do wglądu, ale objęty licencją „all rights reserved” (`LICENSE`);
  uruchomienie lokalnej kopii wyłącznie w celu badania bezpieczeństwa i zgłoszenia traktujemy
  jako dozwolone — **do potwierdzenia przez PO**.
- Nie pobieraj ani nie modyfikuj danych ponad minimum potrzebne do wykazania luki. Jeśli
  trafisz na dane osobowe, zatrzymaj się i zgłoś to.

## Czas reakcji

Propozycja — **do potwierdzenia przez PO**. Projekt prowadzi jedna osoba z pomocą
asystenta AI, więc terminy są celami, nie gwarancją.

| Etap | Cel |
|---|---|
| Potwierdzenie przyjęcia zgłoszenia | 5 dni roboczych |
| Wstępna ocena (ważność, zakres, plan) | 14 dni |
| Poprawka: ważność wysoka | 30 dni |
| Poprawka: ważność średnia | 90 dni |
| Poprawka: ważność niska | zgodnie z backlogiem |
| Ujawnienie | koordynowane ze zgłaszającym; domyślnie po poprawce lub po 90 dniach od zgłoszenia |

Ważność oceniamy skalą z [`RYZYKA.md`](docs/bezpieczenstwo/RYZYKA.md) §1 (wpływ ×
prawdopodobieństwo). Poprawka trafia do PR w trybie *draft*, a merge do `main` wykonuje
wyłącznie Product Owner (`main` = automatyczne wdrożenie produkcji).

## Wspierane wersje

| Wersja | Wsparcie |
|---|---|
| gałąź `main` (wersja `0.1.0`, brak tagowanych wydań) | tak — poprawki bezpieczeństwa tylko tutaj |
| gałęzie robocze, forki, starsze commity | nie |

## Safe harbor

Jeśli działasz w dobrej wierze, stosujesz się do tej polityki (zakres, zasady testowania) i
nie naruszasz prywatności ani dostępności innych osób, autor nie podejmie wobec Ciebie
kroków prawnych za badanie i zgłoszenie podatności. Zapis nie obejmuje działań poza zakresem
i nie wiąże stron trzecich (hosting, GitHub). Brzmienie — **do potwierdzenia przez PO**,
ze względu na licencję. Nie prowadzimy programu bug bounty (brak nagród pieniężnych).

## Podziękowania

Na dzień 2026-10-16 nie ma zgłoszeń. Osoby, które zgłoszą podatność i wyrażą zgodę, zostaną
tu wymienione (nick lub imię, data, krótki opis).

## Dokumenty powiązane

[`docs/bezpieczenstwo/THREAT_MODEL.md`](docs/bezpieczenstwo/THREAT_MODEL.md) ·
[`docs/bezpieczenstwo/RYZYKA.md`](docs/bezpieczenstwo/RYZYKA.md) ·
[`docs/bezpieczenstwo/KLASYFIKACJA_DANYCH.md`](docs/bezpieczenstwo/KLASYFIKACJA_DANYCH.md) ·
[`docs/bezpieczenstwo/RODO.md`](docs/bezpieczenstwo/RODO.md) ·
[`docs/bezpieczenstwo/CHECKLISTA_ASVS.md`](docs/bezpieczenstwo/CHECKLISTA_ASVS.md) ·
[`docs/AUDYT.md`](docs/AUDYT.md)
