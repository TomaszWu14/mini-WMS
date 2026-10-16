# ADR-0001 — Narzędzia jakości i bezpieczeństwa w CI

| | |
|---|---|
| Status | zaakceptowany przez zespół [DEV]/[SEC]; do potwierdzenia przez PO (DEC-2, DEC-3) |
| Data | 2026-10-16 |
| Właściciel | [DEV] z udziałem [SEC] |
| Powiązania | AUDYT R10, T4–T7; ZALOZENIA Z-08, Z-10; CONTRIBUTING §6; `.github/workflows/ci.yml`, `security.yml`, `dependabot.yml`, `.pre-commit-config.yaml` |

## Kontekst

Prompt PO (sekcja 5) wymaga pipeline'u: lint → testy → SAST → SCA → skan sekretów → build obrazu →
skan obrazu, z wynikami jako artefaktami i blokadą przy błędzie wysokiej wagi; do tego Dependabot,
pre-commit i próg pokrycia (domyślnie 80 % dla logiki domenowej). Audyt (R10, T4–T7) wykazał, że
dotychczasowe `ci.yml` nie mierzyło pokrycia, sprawdzało mypy w trzech plikach i uruchamiało testy przez
`manage.py test` (~5 min), a `security.yml` działało raz w miesiącu i tylko doradczo (trivy
`--exit-code 0`, pip-audit `|| true`), instalując trivy przez `curl … | sh` z gałęzi `main`.

Repozytorium jest **publiczne**, więc minuty GitHub Actions nie kosztują — argument „oszczędzamy
minuty” z komentarza w starym `security.yml` przestał obowiązywać. Zespół nie ma budżetu na płatne
usługi (SaaS SAST, Snyk, Semgrep AppSec Platform).

## Rozważane opcje

| Obszar | Opcje | Wybór i powód |
|---|---|---|
| Lint/format | ruff · flake8+black+isort | **ruff** — już w repo, jedno narzędzie, szybkie |
| Typy | mypy na 3 plikach (stan) · mypy na całym kodzie · pyright | **mypy `warehouse config`** — cały kod przechodzi dziś bez błędów (audyt), koszt 0 |
| Testy i pokrycie | `manage.py test` · `pytest` + `pytest-cov` · `coverage run -m pytest` | **`coverage run -m pytest`** — `coverage` jest już w zależnościach; `pytest-cov` dodawałby pakiet bez nowej funkcji; `pytest` z `config.settings.test` skraca job z ~5 min do ~15 s |
| Próg pokrycia | brak · 80 % globalnie · 80 % + 90 % dla `services.py` | **80 % ogółem (`fail_under` w pyproject) + 90 % `warehouse/services.py`** (Z-08) — logika domenowa ma wyższy próg; stan dziś 81 % / 91 %, więc próg jest realny, ale wymusza testy przy każdej nowej gałęzi kodu |
| SAST | bandit · semgrep · oba · CodeQL | **bandit (≥ średnia waga i pewność) + semgrep (`p/owasp-top-ten`, `p/django`, blokuje przy ERROR)**; CodeQL odrzucony (wolniejszy, mniej reguł Django, zależny od GitHub Advanced Security w prywatnych repo) |
| SCA | pip-audit · safety · trivy fs | **pip-audit** — baza OSV/PyPI Advisory, bez konta; prod blokuje, dev doradczo (narzędzia deweloperskie nie trafiają do obrazu) |
| Sekrety | gitleaks · trufflehog · detect-secrets | **gitleaks** — już w repo (`.gitleaksignore`), akcja GitHub bez licencji dla repo użytkownika, hook pre-commit |
| Obraz | trivy · grype · docker scout | **trivy** — jedno narzędzie do obrazu i konfiguracji (Dockerfile, compose); akcja z przypiętym SHA zamiast `curl … \| sh` |
| Aktualizacje | ręcznie · Dependabot · Renovate | **Dependabot** — wbudowany, bez instalacji; pip + github-actions + docker, co tydzień, grupa narzędzi dev |
| Pre-commit | brak · pre-commit (ruff, gitleaks, higiena plików) | **pre-commit** — te same kontrole przed commitem; nie zastępuje CI |
| Pinning akcji | tag (`@v4`) · SHA | **SHA z komentarzem wersji** — ochrona przed podmianą tagu; Dependabot utrzymuje |

## Decyzja

1. `ci.yml` (każdy push i PR), job po jobie, blokujące o ile nie zaznaczono inaczej:
   1. **lint** — `ruff check`, `ruff format --check`.
   2. **typecheck** — `mypy warehouse config`.
   3. **test** — `check`, `check --deploy`, `makemigrations --check`, `coverage run -m pytest`,
      próg 80 % ogółem i 90 % `services.py`; artefakt `reports-coverage` (XML + HTML).
      **test-postgres** — ten sam zestaw na PostgreSQL 16 (test wyścigu).
   4. **sast** — bandit `-ll -ii` (konfiguracja z `pyproject`), semgrep `--severity ERROR --error`;
      artefakt `reports-sast` (JSON, SARIF).
   5. **sca** — pip-audit `requirements.txt` (blokuje), `requirements-dev.txt` (doradczo, ostrzeżenie w logu);
      artefakt `reports-sca`.
   6. **secrets** — gitleaks na pełnej historii (`fetch-depth: 0`).
   7. **docker-build** — build, smoke test (kontener `healthy`), trivy obraz: **HIGH/CRITICAL z dostępną
      poprawką blokują** (`--ignore-unfixed`), trivy config (Dockerfile, compose) doradczo; artefakt
      `reports-image` (SARIF).
2. `security.yml` co tydzień (poniedziałek 06:00 UTC) i na żądanie, **doradczo**: gitleaks (historia), trivy fs
   (vuln+secret+misconfig, wszystkie poziomy), semgrep z szerszymi pakietami (`p/python`, `p/security-audit`,
   `p/secrets`), pip-audit prod+dev, bandit na wszystkich poziomach — artefakty 30 dni.
3. `dependabot.yml`: pip (grupa `dev-tools`, Django tylko łatki 5.2.x), github-actions, docker (tylko 3.11.x).
4. `.pre-commit-config.yaml`: higiena plików, ruff (fix + format), gitleaks.
5. `permissions: contents: read` na poziomie workflow; `concurrency` anuluje przestarzałe uruchomienia.
6. Wyjątki od skanerów tylko z uzasadnieniem w kodzie/konfiguracji: `# nosec <id> — powód` (bandit),
   `# nosemgrep: <id> — powód`, `.gitleaksignore` z komentarzem, `.trivyignore` z CVE, powodem i datą
   przeglądu. Hurtowe wyciszanie reguł jest zabronione (CONTRIBUTING §7).

## Konsekwencje

- Czas CI: dotąd ~5 min (testy), teraz równoległe joby po 1–3 min; najdłuższy to build + skan obrazu (~3–4 min).
- **Próg pokrycia 80 % jest blisko stanu (81 %)** — każda nowa logika bez testów zatrzyma PR. To celowe
  (DoD), ale PO może obniżyć próg decyzją DEC-3.
- Trivy może zablokować pipeline przez CVE w obrazie bazowym `python:3.11-slim` zanim pojawi się
  poprawiony obraz; wtedy: `.trivyignore` z datą przeglądu albo bump obrazu — nigdy `exit-code: 0`.
- Semgrep pobiera reguły z rejestru `semgrep.dev` i przy tym wysyła anonimowe metryki
  (`SEMGREP_SEND_METRICS=off` ogranicza je do minimum). Lokalnie za proxy blokującym `semgrep.dev`
  można użyć kopii reguł: `git clone --depth 1 --sparse https://github.com/semgrep/semgrep-rules` i
  `--config semgrep-rules/python`.
- `semgrep` nie trafia do `requirements-dev.txt`: wymaga `tomli~=2.0`, a `pip-audit` `tomli>=2.2`
  (konflikt zależności). Instalacja osobno: `pipx install semgrep==1.146.0`; w CI w osobnym jobie.
- pip-audit dla zależności deweloperskich pozostaje doradczy, bo narzędzia dev nie są w obrazie
  produkcyjnym; podatność w nich to zadanie dla Dependabota, nie blokada PR.
- Dependabot otworzy kilka PR tygodniowo; każdy przechodzi pełne CI, scala PO.
- `.gitleaksignore` zawiera fingerprinty dla trybu historii (`git`, CI) i trybu drzewa (`dir`,
  pre-commit) — numery linii różnią się, bo plik testów urósł od commitu, który wprowadził hasła testowe.

## Jak uruchomić lokalnie

Pełna tabela poleceń: CONTRIBUTING §6. Skrót: `pip install -r requirements-dev.txt`, potem
`ruff check . && mypy warehouse config && coverage run -m pytest -q && coverage report`;
skany: `bandit -c pyproject.toml -r warehouse config manage.py -ll -ii`, `pip-audit -r requirements.txt`,
`gitleaks git --no-banner .`, `trivy config .`; obraz: `docker build -t miniwms:local . && trivy image
--severity HIGH,CRITICAL --ignore-unfixed miniwms:local`.

## Weryfikacja przed wdrożeniem tej decyzji (2026-10-16, lokalnie)

ruff, ruff format, mypy (41 plików), pytest (224 passed, 2 skipped), coverage 81 % / 91 %, bandit `-ll -ii`
bez zgłoszeń, pip-audit prod i dev bez znanych podatności, gitleaks (historia i drzewo) bez wycieków —
wszystko zielone na stanie `main` + ta gałąź. Semgrep z pakietami rejestru i trivy na obrazie
zweryfikowano dopiero w CI tej gałęzi (lokalne proxy blokuje `semgrep.dev`; brak demona Dockera).
