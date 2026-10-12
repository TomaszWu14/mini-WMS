# fix/open-decisions — instrukcja dla operatora

| | |
|---|---|
| Branch | `fix/open-decisions` |
| PR | jeszcze nie utworzony |
| Data | 2026-10-12 |
| Ryzyko | średnie — zmiana wersji Django (5.1 → 5.2 LTS) i limit logowań włączony także poza demo; bez migracji |

## 1. Co zmieniono
- Import stanów początkowych mówi, ile palet ma ilość 0 (do uzupełnienia korektą) i które
  lokalizacje mają przekroczoną pojemność.
- Numer palety można wpisać/zeskanować małymi lub wielkimi literami — skaner, przepakowanie i
  inwentaryzacja znajdą paletę tak samo.
- Zbiorczy wydruk etykiet powyżej 200 palet nie obcina listy po cichu — wraca do listy z
  komunikatem „Zawęź filtr”.
- Limit prób logowania (10 prób / 5 min z jednego adresu) działa zawsze, nie tylko w demo.
- Nowy arkusz spisu pomija palety, które są już w innym otwartym arkuszu, i mówi, ile pominął.
- Technicznie: Django 5.2 LTS; adres IP klienta (limit logowań, dziennik logowań) brany z
  nagłówka proxy tylko przy `DJANGO_TRUSTED_PROXY_COUNT` > 0; CI uruchamia testy także na
  PostgreSQL 16, łącznie z testem wyścigu dwóch WZ o jedną paletę.

## 2. Kroki do ręcznego sprawdzenia

| # | Konto (rola) | Gdzie | Co zrobić | Oczekiwany wynik |
|---|---|---|---|---|
| 1 | `demo_operator` (Operator) | `/skaner/podglad/` | wpisać numer istniejącej palety małymi literami | paleta znaleziona |
| 2 | `demo_operator` (Operator) | `/hu/` | „Drukuj etykiety” bez filtra przy > 200 paletach (na demo zwykle mniej — wtedy PDF) | > 200: powrót do listy z komunikatem „Zawęź filtr”; ≤ 200: PDF |
| 3 | `demo_operator` (Operator) | `/spis/` | założyć arkusz dla całego magazynu, potem drugi | drugi arkusz: „Pominięto N palet, które są już w innym otwartym arkuszu” |
| 4 | `demo_operator` (Operator) | `/stany/import/` | zaimportować plik z wierszem bez ilości | komunikat „1 palet ma ilość 0 — uzupełnij ją korektą ilości” |
| 5 | dowolne | `/login/` | 11 razy złe hasło | 11. próba: „Zbyt wiele prób logowania” (429) |
| 6 | admin | `/uzytkownicy/dziennik/` (dziennik logowań) | sprawdzić IP nieudanych prób z kroku 5 | Twój publiczny adres IP, nie adres wewnętrzny proxy |

## 3. Checklista wdrożenia

### Migracje — na KAŻDEJ bazie
| Baza | Polecenie | Wykonano (kto, kiedy) |
|---|---|---|
| dev (lokalny SQLite) | `python manage.py migrate` | ☐ (brak nowych migracji) |
| test (baza testów) | tworzona automatycznie przez `pytest` / `manage.py test` | ☐ testy zielone |
| demo (jeśli wdrożone) | automatycznie w `entrypoint.sh` przy deployu | ☐ sprawdzono log |
| prod (PostgreSQL, Coolify) | automatycznie w `entrypoint.sh` przy deployu | ☐ sprawdzono log |

Nowe migracje w tym branchu: brak. Odwracalne: nie dotyczy.
Sprawdzenie: `python manage.py showmigrations warehouse` — wszystkie `[X]`.

### Zmienne środowiskowe
| Zmienna | Nowa / zmieniona / usunięta | Wartość prod | Ustawiona w Coolify |
|---|---|---|---|
| `DJANGO_TRUSTED_PROXY_COUNT` | nowa | `1` — domyślna w obu plikach compose, nie trzeba ustawiać | ☐ nie trzeba (chyba że przed Traefikiem jest drugie proxy, np. Cloudflare → `2`) |

Zaktualizowano też: `.env.example` — nie dotyczy (plik nie istnieje), `.env.docker.example` —
nie dotyczy (plik nie istnieje), `COOLIFY.md` §6 ☑.

### Przed i po deployu
- ☐ CI zielone na PR (`ci.yml` — w tym nowy job `test-postgres`, `security.yml`)
- ☐ backup bazy prod sprzed deployu — nie dotyczy (brak migracji); zalecany przy zmianie wersji Django
- ☐ po deployu: `/healthz` zwraca `{"status": "ok"}`
- ☐ kroki z sekcji 2 wykonane na prod (krok 6 potwierdza `DJANGO_TRUSTED_PROXY_COUNT`)

## 4. Plan wycofania
1. Kod: Coolify → zasób → **Deployments** → poprzedni deployment → **Redeploy**
   (albo revert PR na `main`).
2. Migracje: nie dotyczy (brak nowych migracji).
3. Zmienne środowiskowe: `DJANGO_TRUSTED_PROXY_COUNT` jest ignorowana przez starszy kod —
   nic do przywracania.
4. Weryfikacja po wycofaniu: `/healthz`, logowanie, lista HU.
