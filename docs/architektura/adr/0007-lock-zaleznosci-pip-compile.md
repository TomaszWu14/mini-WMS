# ADR-0007 — Lock zależności z hashami (`pip-compile`) i obrazy przypięte digestem

| | |
|---|---|
| Status | zaakceptowany przez zespół [DEV]/[SEC] |
| Data | 2026-10-17 |
| Właściciel | [DEV] z udziałem [SEC] |
| Powiązania | US-020, NFR-025, SEC-029, SEC-031; AUDYT T7, R10; TM-52, RR-14; ADR-0001, ADR-0005 |

## Kontekst

Zależności były w dwóch ręcznych listach: `pyproject.toml` i `requirements.txt`. Lista dev miała trzecią kopię
w krokach CI (`pip install mypy==… pytest==…`). Wersje przejściowe nie były zablokowane, a `Django>=5.2,<5.3`
w obrazie zależał od dnia budowy. Hashy nie było, więc podmieniony plik na indeksie przeszedłby niezauważony.
Dockerfile robił `pip install --upgrade pip` bez wersji, a obrazy bazowe szły po tagu (`python:3.11-slim`).

## Rozważane opcje

| Opcja | Zalety | Wady |
|---|---|---|
| **`pip-compile` (pip-tools) z `--generate-hashes`** | format `requirements.txt`, który pip instaluje wprost; Dependabot aktualizuje `.in` i przegenerowuje lock z hashami | lock dla jednej wersji Pythona (rozwiązanie znaczników przy kompilacji) |
| `uv pip compile --universal` | jeden lock dla wielu wersji Pythona i systemów | obsługa przez Dependabota tego formatu niepewna; nowe narzędzie w zespole |
| `uv lock` / Poetry | pełny menedżer projektu | zmiana sposobu pracy, Dockerfile i CI; ponad potrzebę |

## Decyzja

- Jedyne źródła: `requirements.in` (produkcja), `requirements-dev.in` (dev i CI; `-r requirements.in`,
  `-c requirements.txt`) i `requirements-mutation.in` (`mutmut`). `pyproject.toml` czyta `requirements.in`
  (`dynamic = ["dependencies"]`).
- Locki generuje `pip-compile 7.4.1` na Pythonie 3.11 (wersja obrazu i CI) z opcjami
  `--generate-hashes --allow-unsafe --strip-extras`. Lock dev zawiera jawnie `colorama` i `tzdata`, bo na
  Windows potrzebują ich pytest i Django. Lock dev jest sprawdzony na 3.11 i 3.13.
- `mutmut` dostaje osobny lock. Jego zależność `libcst` wymaga na Pythonie ≥ 3.13 pakietu `pyyaml-ft`,
  którego lock 3.11 nie ma, a `--require-hashes` odrzuca wtedy instalację całego locka dev.
- Dockerfile instaluje `pip install --require-hashes --no-deps -r requirements.txt`. Lock jest pełnym
  domknięciem zależności, a `--no-deps` gwarantuje, że nic spoza niego nie trafi do obrazu.
- Obrazy `python`, `postgres` i `caddy` są przypięte digestem indeksu wieloarchitekturowego (`tag@sha256:…`).
  Dependabot (`docker` i `docker-compose`) podbija tag razem z digestem.
- CI instaluje wszystkie narzędzia z locka dev. `semgrep` ma własny lock `requirements-semgrep.txt`, z hashami,
  instalowany w osobnym venv: konflikt `tomli` z pip-audit, opisany już w ADR-0001. Obrazy w CI (usługa
  PostgreSQL, `psql` w ćwiczeniu odtworzenia) i w `scripts/mutate.sh` mają ten sam digest co compose i Dockerfile.
- `warehouse/tests_tooling.py` pilnuje, że każda pozycja czterech locków ma hashe, przypięcia w `.in` zgadzają
  się z lockiem, `pyproject` czyta jedno źródło, a obrazy mają digest. Obejmuje też workflowy CI i skrypty:
  digest i `--require-hashes` przy każdym `pip install -r`.
- `tzdata` jest w `requirements.in`, a `colorama` w `requirements-dev.in`, bo instalacja z README na Windows
  ich wymaga.

## Konsekwencje

- Zmiana zależności: edycja `.in`, potem `pip-compile` (polecenie w nagłówku pliku `.txt`). Ręczna edycja
  `.txt` jest zabroniona: kończy się czerwonym testem albo błędem hashy.
- Lokalnie na Pythonie innym niż 3.11 lub 3.13 lock dev może wymagać przegenerowania. Wersja produkcyjna to 3.11.
- `pip-compile` 7.4.1 z `click` ≥ 8.2 zapisuje w nagłówku błędne opcje (`--no-index`, `--cert=None`).
  Dependabot odtwarza polecenie z nagłówka, więc kompilujemy z `click<8.2`.
- Digest zmienia się przy każdej łatce obrazu. Bez PR Dependabota obraz się nie zmieni, co jest celem.
