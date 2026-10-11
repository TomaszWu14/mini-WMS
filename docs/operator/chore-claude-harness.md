# chore/claude-harness — instrukcja dla operatora

| | |
|---|---|
| Branch | `chore/claude-harness` |
| PR | jeszcze nie utworzony |
| Data | 2026-10-11 |
| Ryzyko | niskie — zero zmian w logice aplikacji, modelach i migracjach; zmienia się tylko narzędziownia deweloperska i praca agentów Claude |

## 1. Co zmieniono

Widoczne dla użytkowników magazynu: **nic** (żaden ekran, raport ani dane się nie zmieniają).

Techniczne (tylko praca deweloperska i agentów Claude):
- Nowe narzędzia deweloperskie: pytest + pytest-django, mutmut, pip-audit, bandit
  (`pyproject.toml`, `requirements-dev.txt`). Obraz produkcyjny ich nie zawiera.
- `config/settings/test.py` — ustawienia **tylko dla pytest** (szybki hasher haseł): testy
  trwają 11–40 s zamiast ~318 s. Produkcja i dev tego pliku nie ładują.
- Strażnik `.claude/hooks/guard.py`: blokuje agentowi groźne komendy (rekursywne
  kasowanie, wymuszony push, reset na main, niszczący SQL, zapis `.env`, deploy i połączenia z
  bazą produkcyjną).
- Stop hook `.claude/hooks/check.py`: przed zakończeniem pracy agent musi przejść ruff, mypy
  (zmienione pliki) i pełne `pytest`.
- Dokumentacja pułapek `docs/pitfalls/*.md`, `CLAUDE.md`, subagenci (`.claude/agents/`),
  skill `/end`, szablon `docs/operator/TEMPLATE.md`.
- Skrypty `scripts/mutate.sh` (testy mutacyjne) i `scripts/security_scan.sh` (CVE + SAST);
  raporty w `reports/` (ignorowany przez git).

## 2. Kroki do ręcznego sprawdzenia

| # | Konto (rola) | Gdzie | Co zrobić | Oczekiwany wynik |
|---|---|---|---|---|
| 1 | — | terminal w repo, `.venv` aktywny | `pip install -r requirements-dev.txt`, potem `python -m pytest -x -q` | `121 passed` w < 60 s |
| 2 | — | terminal | `python -m pytest .claude/hooks -q` | `44 passed` |
| 3 | — | Claude Code w tym repo | poproś Claude o uruchomienie `git push -f` | odmowa z komunikatem `[guard] ZABLOKOWANO: git push --force/-f jest zablokowany.` |
| 4 | — | Claude Code | poproś Claude o dopisanie linii do `.env` | odmowa `[guard] ZABLOKOWANO: zapis do pliku z sekretami (.env)…` |
| 5 | — | Claude Code | poproś o drobną zmianę w `warehouse/` i zakończenie | przed odpowiedzią końcową hook uruchamia testy (widać pauzę ~30–90 s); przy błędzie Claude dostaje ich wynik i poprawia |
| 6 | — | terminal (Git Bash) | `bash scripts/security_scan.sh` | plik `reports/security-<data>.md`; dziś exit 1 — 8 CVE Django 5.1 (patrz §5) |
| 7 | — | terminal z Dockerem | `bash scripts/mutate.sh warehouse/services.py split_quantity` | `30 mutantów: zabite 15, przeżyły 15` + raport w `reports/` |
| 8 | `demo_operator` (Operator) | `http://127.0.0.1:8001/` po `DEMO_MODE=1 python manage.py runserver 8001` | zaloguj się, otwórz listę HU | aplikacja działa jak przed zmianą |

## 3. Checklista wdrożenia

### Migracje — na KAŻDEJ bazie
| Baza | Polecenie | Wykonano (kto, kiedy) |
|---|---|---|
| dev (lokalny SQLite) | brak nowych migracji (`makemigrations --check` → „No changes detected”) | nie dotyczy |
| test (baza testów) | tworzona przez pytest — 121 testów zielonych | ☑ 2026-10-11, Claude |
| demo | brak nowych migracji | nie dotyczy |
| prod (PostgreSQL, Coolify) | brak nowych migracji | nie dotyczy |

Nowe migracje w tym branchu: **brak**.

### Zmienne środowiskowe
| Zmienna | Nowa / zmieniona / usunięta | Wartość prod | Ustawiona w Coolify |
|---|---|---|---|
| — | brak zmian | — | nie dotyczy |

`DJANGO_SETTINGS_MODULE=config.settings.test` ustawia tylko pytest (`pyproject.toml`) —
**nie** ustawiać go w Coolify.

### Przed i po deployu
- ☐ CI zielone na PR (`ci.yml`, `security.yml`) — CI nadal używa `manage.py test`, nie zmieniono workflow
- nie dotyczy: backup bazy (brak migracji)
- ☐ po merge/deployu: `/healthz` zwraca `{"status": "ok"}`
- ☐ krok 8 z sekcji 2 na prod (logowanie, lista HU)

## 4. Plan wycofania
1. Kod: revert PR na `main` (albo w Coolify **Redeploy** poprzedniego deploymentu). Zmiany nie
   dotykają runtime'u, więc wycofanie jest bezpieczne w każdej chwili.
2. Migracje: nie dotyczy.
3. Zmienne środowiskowe: nie dotyczy.
4. Same hooki można wyłączyć lokalnie bez revertu: usuń sekcję `hooks` z
   `.claude/settings.json` (albo nadpisz w `.claude/settings.local.json`).

## 5. Uwagi
- **pip-audit: 8 znanych podatności w Django 5.1.15**, poprawki dopiero w 5.2.15+/6.0.6+
  (seria 5.1 nie ma już łatek). Wymaga osobnego brancha z aktualizacją Django do 5.2 LTS.
- mutmut nie działa natywnie na Windowsie — `mutate.sh` używa kontenera `python:3.11-slim`
  (wymaga uruchomionego Docker Desktop).
- trivy nie jest zainstalowany lokalnie — sekcja trivy w raporcie jest pomijana; w CI działa
  `security.yml`.
