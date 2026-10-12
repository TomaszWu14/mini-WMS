# mini-WMS — instrukcje dla Claude

Django 5.2 LTS, jeden app `warehouse`, ustawienia `config/settings/{base,dev,prod,test}.py`.
Testy: `.venv/Scripts/python -m pytest -x -q` (~11–40 s). Hooki w `.claude/settings.json`:
`guard.py` (PreToolUse — blokuje groźne komendy), `check.py` (Stop — ruff/mypy na zmienionych
plikach + pytest).

## Pułapki — czytaj przed pracą w danym obszarze

| Praca dotyczy… | Czytaj |
|---|---|
| modeli, migracji, `services.py`, zapytań, transakcji | `docs/pitfalls/db.md` |
| logowania, ról, dekoratorów widoków, kont demo, `signals.py` | `docs/pitfalls/auth.md` |
| widoków, formularzy, importów CSV/XLSX, eksportów, skanera, szablonów | `docs/pitfalls/views.md` |
| Dockera, `entrypoint.sh`, compose, Coolify, zmiennych środowiskowych, CI | `docs/pitfalls/deploy.md` |

## Duże zadania: worker + reviewerzy (`.claude/agents/`)

1. **Główna sesja planuje** — dzieli zadanie na niezależne wycinki (pliki + kryterium
   ukończenia), bez nakładania się plików między wycinkami.
2. **`worker`** (Sonnet) wykonuje jeden wycinek: kod + test + ruff/mypy/pytest. Niezależne
   wycinki — równolegle.
3. Główna sesja scala wyniki i uruchamia pełne `pytest`.
4. **Reviewerzy raz, na końcu:** `security-reviewer` (zawsze przy widokach/formularzach/
   uploadzie/auth) i `db-reviewer` (gdy diff dotyka modeli, migracji, `services.py`,
   querysetów). Równolegle, na diffie `main...HEAD`.
5. Zgłoszenia reviewerów naprawia główna sesja (lub worker) **bez ponownego review** —
   żadnej pętli review → poprawka → review. Odrzucone zgłoszenia: jedno zdanie dlaczego.

Małe zadania (1–2 pliki): bez workerów, reviewer tylko gdy zmiana dotyka auth/danych.

## Koniec brancha: dokument dla operatora

Przed ostatnim commitem każdego brancha wygeneruj `docs/operator/<nazwa-brancha>.md`
(`/` → `-`) według `docs/operator/TEMPLATE.md`. Wypełnij wszystkie sekcje faktami z diffu
(`git diff main...HEAD`); czego nie dotyczy — wpisz „nie dotyczy”, nie usuwaj wiersza
migracji ani planu wycofania.
