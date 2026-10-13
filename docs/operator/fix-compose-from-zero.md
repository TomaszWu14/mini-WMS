# fix/compose-from-zero — instrukcja dla operatora

| | |
|---|---|
| Branch | `fix/compose-from-zero` |
| PR | jeszcze nie utworzony |
| Data | 2026-10-12 |
| Ryzyko | niskie — dotyczy tylko wariantu `docker-compose.yml` (własny Caddy); Coolify (`docker-compose.coolify.yml`) bez zmian |

## 1. Co zmieniono
- `docker compose up` działa od zera po sklonowaniu repo na Windows. Wcześniej Git
  (`core.autocrlf=true`) zapisywał `entrypoint.sh` i `scripts/pg_backup.sh` z końcami linii
  CRLF i kontenery `web` oraz `backup` restartowały się w kółko („bash\r: No such file”).
  Nowy `.gitattributes` wymusza LF dla `*.sh`, `Dockerfile` i `Caddyfile`.
- Caddy nie pada przy pustym `ACME_EMAIL` — dyrektywa `email` usunięta (Let's Encrypt jej
  nie wymaga); zmienna `ACME_EMAIL` nie jest już używana.
- Tryb „sieć lokalna” (`DOMAIN=:80`) działa: compose przekazuje `DJANGO_SSL_REDIRECT`, a
  `docs/wdrozenie.md` wymienia wszystkie potrzebne zmienne.

## 2. Kroki do ręcznego sprawdzenia

| # | Konto (rola) | Gdzie | Co zrobić | Oczekiwany wynik |
|---|---|---|---|---|
| 1 | — | Windows, czysty katalog | `git clone …`, w `.env`: `DOMAIN=:80`, `DJANGO_SECURE_COOKIES=0`, `DJANGO_SSL_REDIRECT=0`, `DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1`, hasła; `docker compose up -d --build` | 4 kontenery „Up”, `web` i `db` „healthy” |
| 2 | admin (z `DJANGO_SUPERUSER_*`) | `http://localhost/` | zalogować się | pulpit, `/admin/` działa |
| 3 | — | `docker compose logs backup` | odczekać chwilę | `[backup] … OK -> /backups/wms-….sql.gz` |

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
| `DJANGO_SSL_REDIRECT` | przekazywana w `docker-compose.yml` (domyślnie `1`) | `1` | ☐ nie dotyczy (Coolify nie używa tego pliku) |
| `ACME_EMAIL` | usunięta (nieużywana) | — | ☐ nie dotyczy |

Zaktualizowano też: `.env.example` — nie dotyczy, `.env.docker.example` ☑ (uzupełnione w
`chore/env-examples`: bez `ACME_EMAIL`, z `DJANGO_SSL_REDIRECT`), `COOLIFY.md` §6 — nie dotyczy.

### Przed i po deployu
- ☐ CI zielone na PR (`ci.yml` — w tym `docker-build`)
- ☐ backup bazy prod sprzed deployu — nie dotyczy (brak migracji)
- ☐ Redeploy w Coolify nie jest potrzebny dla działania demo (zmiana dotyczy innego pliku compose)

## 4. Plan wycofania
1. Kod: revert PR na `main`.
2. Migracje: nie dotyczy.
3. Zmienne środowiskowe: nie dotyczy.
4. Weryfikacja po wycofaniu: `docker compose up -d --build` na Linuksie.
