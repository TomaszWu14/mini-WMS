# feat/recruiter-ready — instrukcja dla operatora

| | |
|---|---|
| Branch | `feat/recruiter-ready` |
| PR | jeszcze nie utworzony |
| Data | 2026-10-12 |
| Ryzyko | niskie — nowe funkcje działają tylko przy `DEMO_MODE=1`; poza demo jedyna zmiana to tekst przycisku logowania bez zmian zachowania |

## 1. Co zmieniono
- Ekran logowania w demo: przycisk **„Wejdź jako demo”** (bez wpisywania hasła, konto
  `demo_operator`) nad zwykłym formularzem.
- Pulpit w demo: panel **„Od czego zacząć — 5 minut”** z czterema krokami (palety z etykietą
  QR, skaner, wydanie FEFO, raport zajętości) i przyciskiem „Prezentacja z lektorem”
  (działa po scaleniu PR z prezentacją). „Ukryj” chowa panel do końca sesji.
- Baner: „Wersja demonstracyjna — dane fikcyjne, przywracane co noc. Możesz klikać śmiało.”
- W demo import pliku (lokalizacje, przyjęcia, wydania, stany) przyjmuje najwyżej 500 wierszy.
- README: sekcja „Od czego zacząć (5 minut)” i zrzuty logowania oraz pulpitu z danymi demo.
- Technicznie: konto przycisku i hasło kont demo z env (`DEMO_USER`, `DEMO_PASSWORD`).

## 2. Kroki do ręcznego sprawdzenia

| # | Konto (rola) | Gdzie | Co zrobić | Oczekiwany wynik |
|---|---|---|---|---|
| 1 | — | `/login/` | kliknąć „Wejdź jako demo” | pulpit, zalogowany `demo_operator`, panel „Od czego zacząć” |
| 2 | `demo_operator` (Operator) | pulpit | przejść kroki 1–4 z panelu | każdy link otwiera właściwy ekran; etykieta to PDF |
| 3 | `demo_operator` (Operator) | `/uzytkownicy/` | wpisać adres ręcznie | 403 |
| 4 | `demo_operator` (Operator) | pulpit | „Ukryj” | panel znika, wraca po ponownym zalogowaniu |
| 5 | `demo_podglad` (Podgląd) | pulpit | zalogować się hasłem `demo1234` | panel bez kroku „Skaner” |

## 3. Checklista wdrożenia

### Migracje — na KAŻDEJ bazie
| Baza | Polecenie | Wykonano (kto, kiedy) |
|---|---|---|
| dev (lokalny SQLite) | `python manage.py migrate` | ☐ nie dotyczy — brak migracji |
| test (baza testów) | tworzona automatycznie przez `pytest` / `manage.py test` | ☐ testy zielone |
| demo (jeśli wdrożone) | automatycznie w `entrypoint.sh` przy deployu | ☐ nie dotyczy — brak migracji |
| prod (PostgreSQL, Coolify) | automatycznie w `entrypoint.sh` przy deployu | ☐ nie dotyczy — brak migracji |

Nowe migracje w tym branchu: brak. Odwracalne: nie dotyczy.
Sprawdzenie: `python manage.py showmigrations warehouse` — wszystkie `[X]`.

### Zmienne środowiskowe
| Zmienna | Nowa / zmieniona / usunięta | Wartość prod | Ustawiona w Coolify |
|---|---|---|---|
| `DEMO_USER` | nowa, opcjonalna | domyślnie `demo_operator` (w compose) | ☐ nie trzeba |
| `DEMO_PASSWORD` | nowa, opcjonalna | domyślnie `demo1234` (w compose); zmiana działa po `seed_demo --reset` | ☐ nie trzeba |

Zaktualizowano też: `.env.example` ☐ — **do dopisania ręcznie** (hook repo blokuje
odczyt plików `.env*`), `.env.docker.example` — nie dotyczy (demo tylko w Coolify),
`COOLIFY.md` §11 (Instancja demo) ☑.

### Przed i po deployu
- ☐ CI zielone na PR (`ci.yml`, `security.yml`)
- ☐ backup bazy prod sprzed deployu — nie dotyczy (brak migracji)
- ☐ **Redeploy ręcznie w Coolify** (auto-deploy po merge nie zadziałał 2026-10-12)
- ☐ po deployu: `/healthz` zwraca `{"status": "ok"}`
- ☐ kroki z sekcji 2 wykonane na `https://miniwms.twapp.pl`

## 4. Plan wycofania
1. Kod: Coolify → zasób → **Deployments** → poprzedni deployment → **Redeploy**
   (albo revert PR na `main`).
2. Migracje: nie dotyczy.
3. Zmienne środowiskowe: `DEMO_USER`/`DEMO_PASSWORD` starszy kod ignoruje — nic do przywracania.
4. Weryfikacja po wycofaniu: `/healthz`, logowanie, lista HU.
