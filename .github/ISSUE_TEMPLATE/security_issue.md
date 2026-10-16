---
name: "[SEC] Zagadnienie bezpieczeństwa"
about: Utwardzenie, luka w kontroli, wymaganie bezpieczeństwa — BEZ szczegółów exploita
title: "[SEC] <obszar>: <krótki opis>"
labels: ["security", "SEC"]
assignees: []
---

<!-- UWAGA: to repozytorium jest publiczne. Konkretne podatności (jak wykorzystać, PoC,
     dane) zgłaszaj prywatnie wg SECURITY.md. Tutaj trafiają zadania utwardzające,
     wymagania bezpieczeństwa i ustalenia z przeglądów, opisane bez instrukcji ataku. -->

## Obszar
- Kategoria OWASP Top 10 / ASVS: …
- Przepływ danych z threat modelu: DF-xx (`docs/bezpieczenstwo/THREAT_MODEL.md`)
- STRIDE: Spoofing / Tampering / Repudiation / Information disclosure / DoS / Elevation

## Opis (bez szczegółów wykorzystania)
Co jest nie tak i jaki ma to skutek dla użytkownika lub danych.

## Dane, których dotyczy
- Klasa danych (`docs/bezpieczenstwo/KLASYFIKACJA_DANYCH.md`): publiczne / wewnętrzne / poufne / osobowe
- Zasoby: DA-xx

## Ocena
- Wpływ (1–3): …
- Prawdopodobieństwo (1–3): …
- Ocena (iloczyn) i waga: niskie / średnie / wysokie / krytyczne
- Wpis w rejestrze ryzyk: RR-xx (`docs/bezpieczenstwo/RYZYKA.md`) — jeśli brak, dodać

## Proponowana mitygacja
- Zmiana: …
- Test potwierdzający (np. „rola Podgląd → 403”): …
- Czy wymaga decyzji / akceptacji ryzyka przez PO: tak / nie

## Powiązania
- Wymaganie: SEC-xxx (`docs/analiza/WYMAGANIA.md`)
- Historyjka: US-xxx (`docs/analiza/HISTORYJKI.md`)
- Kontrola ASVS: Vx.x.x (`docs/bezpieczenstwo/CHECKLISTA_ASVS.md`)
