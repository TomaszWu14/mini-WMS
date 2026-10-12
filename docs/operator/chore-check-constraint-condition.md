# chore/check-constraint-condition — instrukcja dla operatora

| | |
|---|---|
| Branch | `chore/check-constraint-condition` |
| PR | jeszcze nie utworzony |
| Data | 2026-10-12 |
| Ryzyko | niskie — zmiana nazwy argumentu w dwóch ograniczeniach bazy, bez migracji i bez zmiany zachowania |

## 1. Co zmieniono
- Dla użytkownika: nic.
- Technicznie: ograniczenia „ilość na palecie ≥ 0” i „limit na paletę ≥ 1” zapisane nową
  składnią Django (`condition=` zamiast `check=`, usuniętej w Django 6.0). Testy nie
  zgłaszają już żadnych ostrzeżeń (szum WhiteNoise o braku `staticfiles/` wyciszony).

## 2. Kroki do ręcznego sprawdzenia

| # | Konto (rola) | Gdzie | Co zrobić | Oczekiwany wynik |
|---|---|---|---|---|
| 1 | `demo_operator` (Operator) | `/hu/` → paleta → Korekta | ustawić ilość większą niż na palecie przy wydaniu / ujemną | odrzucone jak dotąd |

## 3. Checklista wdrożenia

### Migracje — na KAŻDEJ bazie
| Baza | Polecenie | Wykonano (kto, kiedy) |
|---|---|---|
| dev (lokalny SQLite) | `python manage.py migrate` | ☐ nie dotyczy — brak migracji |
| test (baza testów) | tworzona automatycznie przez `pytest` / `manage.py test` | ☐ testy zielone |
| demo (jeśli wdrożone) | automatycznie w `entrypoint.sh` przy deployu | ☐ nie dotyczy — brak migracji |
| prod (PostgreSQL, Coolify) | automatycznie w `entrypoint.sh` przy deployu | ☐ nie dotyczy — brak migracji |

Nowe migracje w tym branchu: brak (`makemigrations --check` = „No changes detected”).
Odwracalne: nie dotyczy. Sprawdzenie: `python manage.py showmigrations warehouse` — wszystkie `[X]`.

### Zmienne środowiskowe
| Zmienna | Nowa / zmieniona / usunięta | Wartość prod | Ustawiona w Coolify |
|---|---|---|---|
| — | nie dotyczy | — | ☐ nie dotyczy |

Zaktualizowano też: `.env.example` — nie dotyczy, `.env.docker.example` — nie dotyczy,
`COOLIFY.md` §6 — nie dotyczy.

### Przed i po deployu
- ☐ CI zielone na PR (`ci.yml`, `security.yml`)
- ☐ backup bazy prod sprzed deployu — nie dotyczy (brak migracji)
- ☐ Redeploy w Coolify (auto-deploy nie jest skonfigurowany)
- ☐ po deployu: `/healthz` zwraca `{"status": "ok"}`

## 4. Plan wycofania
1. Kod: Coolify → zasób → **Deployments** → poprzedni deployment → **Redeploy**
   (albo revert PR na `main`).
2. Migracje: nie dotyczy.
3. Zmienne środowiskowe: nie dotyczy.
4. Weryfikacja po wycofaniu: `/healthz`, logowanie, lista HU.
