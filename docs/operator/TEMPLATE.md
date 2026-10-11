# <nazwa-brancha> — instrukcja dla operatora

> Plik generuje Claude na koniec brancha jako `docs/operator/<nazwa-brancha>.md`
> (`/` w nazwie brancha → `-`). Usuń sekcje oznaczone „jeśli dotyczy”, gdy nie dotyczą —
> zamiast tego wpisz „nie dotyczy”.

| | |
|---|---|
| Branch | `<nazwa>` |
| PR | `#<numer>` / jeszcze nie utworzony |
| Data | RRRR-MM-DD |
| Ryzyko | niskie / średnie / wysokie — jednym zdaniem dlaczego |

## 1. Co zmieniono
Krótko, językiem użytkownika magazynu (nie kodu). Po jednym punkcie na zmianę widoczną dla
ludzi + osobno zmiany techniczne bez wpływu na UI.

- …

## 2. Kroki do ręcznego sprawdzenia
Każdy krok: **gdzie wejść → co kliknąć/wpisać → oczekiwany wynik**. Konto i rola, jakich użyć.

| # | Konto (rola) | Gdzie | Co zrobić | Oczekiwany wynik |
|---|---|---|---|---|
| 1 | `…` (Operator) | `/…` | … | … |

## 3. Checklista wdrożenia

### Migracje — na KAŻDEJ bazie
| Baza | Polecenie | Wykonano (kto, kiedy) |
|---|---|---|
| dev (lokalny SQLite) | `python manage.py migrate` | ☐ |
| test (baza testów) | tworzona automatycznie przez `pytest` / `manage.py test` | ☐ testy zielone |
| demo (jeśli wdrożone) | automatycznie w `entrypoint.sh` przy deployu | ☐ sprawdzono log |
| prod (PostgreSQL, Coolify) | automatycznie w `entrypoint.sh` przy deployu | ☐ sprawdzono log |

Nowe migracje w tym branchu: `warehouse/migrations/…` / brak. Odwracalne: tak / nie (dlaczego).
Sprawdzenie: `python manage.py showmigrations warehouse` — wszystkie `[X]`.

### Zmienne środowiskowe
| Zmienna | Nowa / zmieniona / usunięta | Wartość prod | Ustawiona w Coolify |
|---|---|---|---|
| — | | | ☐ |

Zaktualizowano też: `.env.example` ☐, `.env.docker.example` ☐, `COOLIFY.md` §6 ☐ (jeśli dotyczy).

### Przed i po deployu
- ☐ CI zielone na PR (`ci.yml`, `security.yml`)
- ☐ backup bazy prod sprzed deployu (kontener `backup` lub ręczny `pg_dump`) — jeśli są migracje
- ☐ po deployu: `/healthz` zwraca `{"status": "ok"}`
- ☐ kroki z sekcji 2 wykonane na prod

## 4. Plan wycofania
1. Kod: Coolify → zasób → **Deployments** → poprzedni deployment → **Redeploy**
   (albo revert PR na `main`).
2. Migracje (jeśli były): `python manage.py migrate warehouse <poprzednia_migracja>` w
   kontenerze **przed** wycofaniem kodu. Nieodwracalne migracje → odtworzenie backupu
   (`COOLIFY.md` §10).
3. Zmienne środowiskowe: przywróć poprzednie wartości w Coolify.
4. Weryfikacja po wycofaniu: `/healthz`, logowanie, lista HU.
