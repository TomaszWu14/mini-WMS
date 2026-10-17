---
name: "Błąd"
about: Coś działa inaczej, niż opisują wymagania lub dokumentacja
title: "[BUG] <krótki opis>"
labels: ["bug"]
assignees: []
---

<!-- Nie wklejaj haseł, tokenów, adresów e-mail ani danych z produkcji. Logi i zrzuty
     ekranu z danymi osobowymi zanonimizuj. Podatności zgłaszaj wg SECURITY.md, nie tutaj. -->

## Co się dzieje
Krótki opis błędu.

## Kroki odtworzenia
1. Zaloguj się jako <rola> (demo: `demo_operator` / `demo_podglad`)
2. Wejdź na `/…/`
3. Kliknij / wpisz …

## Oczekiwany wynik
…

## Rzeczywisty wynik
… (komunikat, kod odpowiedzi, zrzut ekranu)

## Środowisko
- Instancja: lokalnie (SQLite) / demo `miniwms.twapp.pl` / własna instalacja (PostgreSQL)
- Rola konta: Operator / Administrator / Podgląd
- Urządzenie i przeglądarka (skaner: model telefonu, czy kamera działa):
- Wersja / commit (`git rev-parse --short HEAD` lub data deployu):

## Logi
```
(fragment logu kontenera `web` albo konsoli przeglądarki — bez danych osobowych)
```

## Wpływ
- Waga: blokuje pracę / utrudnia / kosmetyczny
- Powiązane wymaganie: FR-xxx / NFR-xxx (`docs/analiza/WYMAGANIA.md`)
- Czy dotyczy integralności stanu magazynu (ilości, ruchy)? tak / nie
