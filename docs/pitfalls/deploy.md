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
9. **CI (`ci.yml`) uruchamia testy przez `pytest` z `config.settings.test`** (MD5 hasher, ~15 s),
   raz na SQLite (`test`, z pomiarem pokrycia) i raz na PostgreSQL 16 (`test-postgres`). Próg
   pokrycia: 80 % ogółem (`fail_under` w `pyproject.toml`) i 90 % dla `services.py` — nowa logika
   bez testów zatrzyma PR. Pełny opis pipeline'u: ADR-0001.
10. **Skanery w CI blokują PR:** bandit (≥ średnia waga i pewność), semgrep (ERROR), pip-audit
    (`requirements.txt`), gitleaks (historia), trivy (HIGH/CRITICAL z poprawką w obrazie). Wyjątek
    tylko z uzasadnieniem: `# nosec`/`# nosemgrep` z powodem, `.gitleaksignore`, `.trivyignore` z datą
    przeglądu. `semgrep` nie siedzi w `requirements-dev.txt` (konflikt `tomli` z pip-audit) —
    `pipx install semgrep==1.146.0`; za proxy blokującym `semgrep.dev` użyj kopii reguł z GitHuba.
    **Obraz runtime nie ma pip/setuptools/wheel** (skan trivy) — pakiety tylko przez rebuild.
11. **Backup (US-012): kontener `backup` budowany z `docker/backup.Dockerfile`** (nie montuje już skryptu).
   Zmiana `scripts/pg_backup.sh` = rebuild obrazu. Off-site wymaga `BACKUP_AGE_RECIPIENT` (bez niego skrypt odmawia
   wysyłki); klucz prywatny age nigdy na serwer. Skrypt musi działać w `sh` (busybox i dash) — bez `pipefail`,
   sprawdza `shellcheck` w CI.
12. **Zależności i obrazy są zablokowane (US-020, ADR-0007).** `requirements*.txt` to locki `pip-compile`
    z hashami — nowa zależność trafia do `requirements*.in`, lock się przegenerowuje (nagłówek pliku); ręczna
    edycja `.txt` kończy się błędem hashy w Dockerze. Obrazy w Dockerfile i compose mają `tag@sha256:…` —
    zmiana tagu bez digestu łamie `tests_tooling`. Dockerfile instaluje `--require-hashes --no-deps`.
