# fix/code-gaps — instrukcja dla operatora

| | |
|---|---|
| Branch | `fix/code-gaps` |
| PR | utworzony razem z tym plikiem |
| Data | 2026-10-11 |
| Ryzyko | średnie — zmienia reguły pracy (powód korekty obowiązkowy, pojemność tylko ostrzega, skaner pilnuje palety z WZ) i blokady w bazie; bez migracji |

## 1. Co zmieniono

Dla użytkownika magazynu:
- **Każda korekta ilości wymaga powodu** z listy — na ekranie „Korekta ilości” palety, w
  „Inwentaryzacji” i na skanerze.
- **Pełna lokalizacja nie blokuje odłożenia** — paleta trafia na miejsce, panel i skaner
  pokazują ostrzeżenie „ma więcej palet niż pojemność”.
- **Skaner przy kompletacji** odrzuca inną paletę niż wskazana w pozycji WZ; gdy pobierana
  paleta nie jest pierwsza wg daty ważności, pobranie przechodzi z ostrzeżeniem.
- Przyjęcie dzieli resztę po 1 szt. na ostatnie palety (np. 10 szt. na 4 palety: 2, 2, 3, 3).
- Pozycji WZ wskazujących tę samą paletę nie da się dodać ponad jej stan.
- Raport zajętości: pojemność 0 = „bez limitu”; import lokalizacji przyjmuje pojemność 0.
- Strona „Brak uprawnień” ma menu; kafel „Import wydań” tylko dla operatora; link
  „Administracja” tylko dla superusera poza trybem demo.
- Linki powrotu na szczegółach palety, WZ i spisu; „Anuluj” w przyjęciu; ostrzeżenie o
  pominiętych wartościach w spisie.
- Skaner: po wygaśnięciu sesji przechodzi na logowanie; pusty skan pokazuje komunikat.

Techniczne bez wpływu na UI:
- Blokady wierszy (`select_for_update`) w alokacji, korekcie, realizacji, pakowaniu, wysyłce i
  pobraniu (pozycja WZ i dokument przed paletą); przepakowanie blokuje palety w kolejności `pk`.
- `close_stocktake` blokuje tylko pozycje arkusza (`of=("self",)`) — wcześniej na
  PostgreSQL zamknięcie spisu z pozycją bez palety kończyło się błędem.
- Import lokalizacji w jednej transakcji. API skanera `pick` wymaga dokumentu.

## 2. Kroki do ręcznego sprawdzenia

| # | Konto (rola) | Gdzie | Co zrobić | Oczekiwany wynik |
|---|---|---|---|---|
| 1 | `demo_operator` (Operator) | HU → paleta → „Korekta” | zapisać bez powodu, potem z powodem | bez powodu: błąd pola; z powodem: ruch KOREKTA z powodem |
| 2 | `demo_operator` (Operator) | `/skaner/rozmieszczanie/` | odłożyć paletę „Do ułożenia” do `A01-01-01` (zajętej) | sukces, potem żółte ostrzeżenie „2/1” |
| 3 | `demo_operator` (Operator) | `/skaner/inwentaryzacja/` | skan palety, ilość, Potwierdź bez powodu | komunikat o wyborze powodu; po wyborze — korekta zapisana |
| 4 | `demo_operator` (Operator) | `/skaner/picking/` → zlecenie | zeskanować paletę inną niż pierwsza wg daty ważności | pobranie z ostrzeżeniem wskazującym właściwą paletę |
| 5 | `demo_podglad` (Podgląd) | `/przyjecie/` | wejść | strona „Brak uprawnień” z menu |
| 6 | `demo_operator` (Operator) | `/raporty/lokalizacje/` | lokalizacja z pojemnością 0 | „bez limitu”, nigdy „pełna” |
| 7 | Administrator (prod, PostgreSQL) | „Spis z natury” | zamknąć arkusz | zamknięcie bez błędu 500 |

## 3. Checklista wdrożenia

### Migracje — na KAŻDEJ bazie
| Baza | Polecenie | Wykonano (kto, kiedy) |
|---|---|---|
| dev (lokalny SQLite) | `python manage.py migrate` | ☐ nie dotyczy — brak migracji |
| test (baza testów) | tworzona automatycznie przez `pytest` / `manage.py test` | ☐ testy zielone (173) |
| demo (jeśli wdrożone) | automatycznie w `entrypoint.sh` przy deployu | ☐ nie dotyczy — brak migracji |
| prod (PostgreSQL, Coolify) | automatycznie w `entrypoint.sh` przy deployu | ☐ nie dotyczy — brak migracji |

Nowe migracje w tym branchu: brak (`makemigrations --check` — „No changes detected”).
Odwracalne: nie dotyczy.
Sprawdzenie: `python manage.py showmigrations warehouse` — wszystkie `[X]`.

### Zmienne środowiskowe
| Zmienna | Nowa / zmieniona / usunięta | Wartość prod | Ustawiona w Coolify |
|---|---|---|---|
| — | nie dotyczy | — | ☐ |

Zaktualizowano też: `.env.example` — nie dotyczy, `.env.docker.example` — nie dotyczy,
`COOLIFY.md` — nie dotyczy.

### Przed i po deployu
- ☐ CI zielone na PR (`ci.yml`, `security.yml`)
- ☐ poinformować operatorów: powód korekty jest teraz obowiązkowy; pełna lokalizacja tylko ostrzega
- ☐ backup bazy prod sprzed deployu — nie dotyczy (brak migracji), zalecany z ostrożności
- ☐ po deployu: `/healthz` zwraca `{"status": "ok"}`
- ☐ kroki z sekcji 2 wykonane na prod (krok 7 — tylko PostgreSQL)

## 4. Plan wycofania
1. Kod: Coolify → zasób → **Deployments** → poprzedni deployment → **Redeploy**
   (albo revert PR na `main`).
2. Migracje: nie dotyczy — branch nie zawiera migracji.
3. Zmienne środowiskowe: nie dotyczy.
4. Weryfikacja po wycofaniu: `/healthz`, logowanie, lista HU, korekta palety.
