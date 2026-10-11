---
name: end
description: Retrospektywa sesji w mini-WMS — przejrzyj przebieg sesji i zaproponuj maksymalnie 3 usprawnienia harnessu (nowy strażnik w guard.py, wpis w docs/pitfalls, poprawka CLAUDE.md lub agenta). Użyj na koniec sesji albo gdy użytkownik wpisze /end. Niczego nie wdraża bez zgody.
disable-model-invocation: true
---

# /end — usprawnienia harnessu po sesji

**Tylko propozycje. Nie edytuj żadnego pliku, dopóki użytkownik nie zaakceptuje konkretnej
propozycji.**

## 1. Przejrzyj sesję
Przejdź przez przebieg tej rozmowy i wypisz (dla siebie) zdarzenia, które kosztowały czas lub
ryzyko:
- komendy zablokowane przez `guard.py` (słusznie? fałszywy alarm?) i groźne komendy, które
  przeszły, a nie powinny,
- błędy z Stop hooka (`check.py`) — powtarzające się, wolne, fałszywe,
- poprawki użytkownika („nie tak”, „cofnij”, „to już było”), ponowne czytanie tych samych
  plików, zgadywanie konwencji, błędne założenia o kodzie,
- pułapki domenowe/techniczne odkryte w trakcie (migracje, role, transakcje, deploy),
- zachowanie subagentów (`worker`, `security-reviewer`, `db-reviewer`) — za szerokie,
  za płytkie, za dużo zgłoszeń.

Sprawdź też stan harnessu, żeby nie proponować czegoś, co już jest:
`.claude/hooks/guard.py`, `.claude/hooks/check.py`, `docs/pitfalls/*.md`, `CLAUDE.md`,
`.claude/agents/*.md`.

## 2. Wybierz maksymalnie 3
Priorytet: (1) ryzyko utraty danych / produkcji, (2) powtarzalny koszt w przyszłych sesjach,
(3) jednorazowe niedogodności — te zwykle pomiń. Mniej niż 3 (albo zero) to poprawny wynik.

## 3. Format (dla każdej propozycji)

```
### N. <tytuł>
Rodzaj: strażnik | pitfall | CLAUDE.md | agent
Problem z sesji: <co konkretnie się stało — cytat komendy/komunikatu/poprawki>
Propozycja: <jedno–dwa zdania>
Gotowa zmiana:
  plik: <ścieżka>
  <dokładny fragment do wklejenia; dla guard.py także przypadek testowy do
   .claude/hooks/test_hooks.py (BLOCKED albo ALLOWED)>
```

Wpis w `docs/pitfalls/` musi zmieścić się w limicie 10 punktów na plik — jeśli plik jest
pełny, zaproponuj, który punkt zastąpić.

## 4. Zakończ pytaniem
„Którą wdrożyć? (numery / żadnej)”. Po akceptacji wdrażaj tylko wybrane; dla strażnika
uruchom `.venv/Scripts/python -m pytest .claude/hooks -q` i pokaż wynik.
