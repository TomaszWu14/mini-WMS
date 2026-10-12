# Pułapki: konfiguracja i wdrożenie

1. **Push/merge do `main` = deploy na produkcję** (auto-deploy Coolify, `COOLIFY.md` §9).
   Hook `guard.py` blokuje `git push … main` i `gh pr merge` — to robi człowiek.
2. **Migracje uruchamia `entrypoint.sh` przy starcie kontenera** (`migrate --noinput`).
   Migracja, która wywali się na danych produkcyjnych, zatrzyma start aplikacji. Migracje
   niszczące (usunięcie kolumny) rozbijaj na dwa wdrożenia.
3. **`DJANGO_DEBUG` wybiera nakładkę ustawień** (`config/settings/__init__.py`): brak
   zmiennej = **dev** (DEBUG, SQLite, `ALLOWED_HOSTS=*`). Obraz Dockera ustawia
   `DJANGO_DEBUG=0`; uruchomienie poza Dockerem bez tej zmiennej to tryb dev.
4. **`prod.py` odmawia startu z kluczem `django-insecure-…`** — `DJANGO_SECRET_KEY` musi być
   ustawiony w Coolify. `collectstatic` w Dockerfile używa tymczasowego klucza build-only.
5. **Healthcheck `/healthz` jest zwolniony z przekierowania HTTPS**
   (`SECURE_REDIRECT_EXEMPT`). Zmiana ścieżki healthchecku wymaga zmiany w Dockerfile i
   `prod.py` jednocześnie, inaczej kontener nigdy nie będzie „healthy”.
6. **`DJANGO_CSRF_TRUSTED_ORIGINS` z `https://`** — brak = „CSRF verification failed” przy
   logowaniu na produkcji.
7. **Dwa warianty compose:** `docker-compose.yml` (własny Caddy, auto-HTTPS) i
   `docker-compose.coolify.yml` (Traefik Coolify, bez Caddy). Zmiana zmiennych środowiskowych
   → zaktualizuj oba + `.env.example`/`.env.docker.example` + tabelę w `COOLIFY.md` §6.
8. **Backup to osobny kontener `backup`** (`scripts/pg_backup.sh`, retencja 7 dni) na tym
   samym serwerze co baza — to nie jest kopia off-site. Skrypt jest montowany z repo, więc
   w Coolify musi być włączone **Preserve Repository During Deployment** — bez tego
   `backup` restartuje się w kółko. Domenę w Coolify wpisuj bez `:8000` (port z
   `SERVICE_FQDN_WEB_8000`).
9. **CI (`ci.yml`) uruchamia testy przez `manage.py test` (bez MD5 hashera) — ~5 min**, raz na
   SQLite (`test`) i raz na PostgreSQL 16 (`test-postgres`).
   Lokalnie i w Stop hooku: `pytest` (~11–40 s). Wyniki powinny być identyczne; różnica to
   tylko hasher.
10. **mypy w CI sprawdza tylko `services.py`, `config/log.py`, `config/urls.py`**; Stop hook
    sprawdza każdy zmieniony plik `warehouse/`/`config/` — dotknięcie `documents.py` lub
    `issue_import.py` ujawni ich istniejące błędy typów (6 sztuk).
