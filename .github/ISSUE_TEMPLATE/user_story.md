---
name: "[BA] Historyjka użytkownika"
about: Nowa funkcja lub zmiana opisana jako historyjka z kryteriami akceptacji
title: "[US-xxx] Jako <rola> chcę <cel>, aby <korzyść>"
labels: ["user story", "BA"]
assignees: []
---

<!-- Wypełnia [BA]. Numer US-xxx nadaje się z docs/analiza/HISTORYJKI.md. -->

## Historyjka

**Jako** <rola: Operator / Administrator / Podgląd / PO / …>
**chcę** <cel>
**aby** <korzyść biznesowa>.

## Wartość i kontekst
- Problem / obserwacja: …
- Powiązane wymagania: FR-xxx / NFR-xxx / SEC-xxx (`docs/analiza/WYMAGANIA.md`)
- Powiązane ryzyka / dług: R-x, T-x (`docs/AUDYT.md`), RR-xx (`docs/bezpieczenstwo/RYZYKA.md`)

## Kryteria akceptacji (Given / When / Then)

1. **Given** … **When** … **Then** …
2. **Given** … **When** … **Then** …

### Kryteria bezpieczeństwa (wypełnia [SEC])
- **Given** użytkownik z rolą <bez uprawnień> **When** <akcja> **Then** 403 i brak zmiany stanu.
- Dane w zakresie historyjki i ich klasa (`docs/bezpieczenstwo/KLASYFIKACJA_DANYCH.md`): …
- Mini threat model (STRIDE) — nowe zagrożenia lub „bez zmian w modelu”: …

## Wymagania niefunkcjonalne
- Wydajność / skala: …
- Użyteczność (telefon, rękawice, hala): …
- RODO (dane osobowe, retencja): …

## Dane i uprawnienia
- Role z dostępem do funkcji: …
- Zmiany w modelu danych (migracja?): tak / nie
- Zmiany w API skanera (`docs/architektura/API.md`): tak / nie

## Priorytet i rozmiar
- MoSCoW: Must / Should / Could / Won't
- Rozmiar: S / M / L
- Zależności: …

## Definition of Ready
- [ ] cel i korzyść jasne, PO potwierdził zakres
- [ ] kryteria akceptacji testowalne (każde da się zamienić w test)
- [ ] kryteria bezpieczeństwa dopisane przez [SEC]
- [ ] dane, role i uprawnienia określone
- [ ] zależności znane, brak blokad
