# Runbook operacyjny

| | |
|---|---|
| Wersja | 0.1 |
| Data | 2026-10-16 |
| Status | szkic — do akceptacji Product Ownera |
| Właściciel | [DEV] |

Procedury krok po kroku dla osoby, która uruchamia, utrzymuje i ratuje instancję miniWMS.
**Nie powtarza** instrukcji instalacji: Coolify — [COOLIFY.md](../../COOLIFY.md), Docker + Caddy —
[docs/wdrozenie.md](../wdrozenie.md); tu: konfiguracja, deploy i rollback, kopie, odtwarzanie,
reset demo, rotacja sekretów, incydenty, monitoring. Fakty pochodzą z kodu i konfiguracji repo.
Czego repo nie zawiera (parametry serwera, kontakty, konfiguracja monitoringu, ustawienia Coolify)
oznaczono **„do uzupełnienia przez administratora infrastruktury / PO”**.

Architektura: [ARCHITEKTURA.md](../architektura/ARCHITEKTURA.md) · klasy danych:
[KLASYFIKACJA_DANYCH.md](../bezpieczenstwo/KLASYFIKACJA_DANYCH.md) · ryzyka: [AUDYT](../AUDYT.md)
(R1–R10, T1–T16).

---

## 1. Role, kontakty, status przećwiczenia

| Skrót | Rola | Zakres w tym dokumencie |
|---|---|---|
| **INFRA** | administrator infrastruktury | SSH na serwer, panel Coolify, kopie, sekrety środowiska, restart usług |
| **ADM-APP** | Administrator aplikacji (rola `ADMIN` w miniWMS) | konta, role, dziennik logowań (`/uzytkownicy/`) |
| **SU** | konto superusera (`DJANGO_SUPERUSER_*`) | `/admin/` (poza demo), `manage.py` w kontenerze |
| **DEV** | developer | kod, migracje, rollback kodu, naprawy danych przez `services.py` |
| **SEC** | specjalista ds. bezpieczeństwa | ocena incydentów bezpieczeństwa, rotacje po wycieku |
| **PO** | Product Owner | decyzje (odtworzenie z kopii, zgłoszenie RODO, akceptacja ryzyka), merge do `main` (Z-02) |

**Kontakty i dyżury** — do uzupełnienia przez administratora infrastruktury / PO:

| Rola | Osoba / kanał | Zastępstwo |
|---|---|---|
| INFRA | — | — |
| DEV | — | — |
| SEC | — | — |
| PO | — | — |
| Dostawca serwera / DNS | — | — |

### Status przećwiczenia procedur

| # | Procedura | Status | Dowód / uwaga |
|---|---|---|---|
| 3.1 | Deploy | **przetestowana** | produkcyjnie (demo `miniwms.twapp.pl`) i w CI: job `docker-build` buduje obraz i sprawdza, czy kontener jest „healthy” |
| 3.2 | Rollback kodu / migracji | **nieprzećwiczona** | procedura z `docs/operator/TEMPLATE.md` §4; dostępność „Rollback/Redeploy” dla zasobu Docker Compose w Coolify — do potwierdzenia przez INFRA |
| 4 | Backup (kontener `backup`) | skonfigurowany, **nieweryfikowany automatycznie** | brak alertu o niepowodzeniu (R9); świeżość sprawdza się ręcznie |
| 5 | Odtworzenie z kopii | **nieprzećwiczona (R9, US-012)** | komendy z COOLIFY.md §10 nie były wykonane w ramach audytu; poniżej wersja rozszerzona — też nieprzećwiczona |
| 6 | Reset demo | **przetestowana** | komenda i przycisk: testy `tests_demo*.py`; harmonogram działa na demo (README), jego konfiguracja jest poza repo |
| 7 | Rotacja sekretów | **nieprzećwiczona** | polityka rotacji (okresy) nie istnieje — do ustalenia przez PO/SEC |
| 8 | Incydenty | **nieprzećwiczone** | zalecane ćwiczenie „na sucho” (tabletop) po akceptacji dokumentu |
| 9 | Monitoring | częściowy | healthcheck: przetestowany (CI); alerty, metryki: brak (T15) |

Ćwiczenie procedur 3.2, 5 i 7 jest warunkiem wdrożenia u klienta (Z-04).

### Dostęp do kontenerów — konwencja w przykładach

```bash
# na hoście z Dockerem (SSH); wzorzec nazw jak w COOLIFY.md §10 — jeśli nie pasuje, sprawdź `docker ps`
WEB=$(docker ps --format '{{.Names}}' | grep -E '^web')
DB=$(docker ps --format '{{.Names}}' | grep -E '^db')
BK=$(docker ps --format '{{.Names}}' | grep -E '^backup')
```

Wariant `docker-compose.yml` (Caddy): zamiast `docker exec "$DB" …` użyj `docker compose exec -T db …`,
zamiast `docker logs "$WEB"` — `docker compose logs web`. Polecenia `python manage.py …` można też
uruchomić w panelu Coolify: zasób → usługa `web` → **Terminal**. Nazwa użytkownika i bazy w
przykładach to domyślne `wms` (`POSTGRES_USER`, `POSTGRES_DB`) — podstaw własne, jeśli zmienione.

---

## 2. Konfiguracja — zmienne środowiskowe

Ustawia się je w Coolify (zasób → **Environment Variables**) albo w pliku `.env` (compose + Caddy;
plik jest ignorowany przez git i Docker). Wzór: [`.env.docker.example`](../../.env.docker.example),
opis kroków: [COOLIFY.md §6](../../COOLIFY.md). Wrażliwość wg [KLASYFIKACJA_DANYCH](../bezpieczenstwo/KLASYFIKACJA_DANYCH.md).

| Zmienna | Opis | Domyślnie / przykład | Wrażliwość | Uwagi |
|---|---|---|---|---|
| `DOMAIN` | domena dla Caddy (tylko compose + Caddy) | `localhost`; `:80` = sieć lokalna bez HTTPS | Wewnętrzne | rekord DNS `A` na IP serwera, porty 80/443 |
| `DJANGO_SECRET_KEY` | klucz podpisu sesji, CSRF, tokenów | brak w Coolify (wymagany); compose: `zmien-mnie-w-produkcji` | **Poufne** | 50+ znaków losowych: `python -c "import secrets;print(secrets.token_urlsafe(64))"`; `prod.py` odrzuca tylko prefiks `django-insecure-` — słaba wartość domyślna z compose **przechodzi** (R2, US-003) |
| `DJANGO_DEBUG` | wybór nakładki ustawień | `0` (ustawia obraz i compose) | Wewnętrzne | nie zmieniać w prod; brak zmiennej poza Dockerem = tryb dev |
| `DJANGO_ALLOWED_HOSTS` | dozwolone hosty | domena aplikacji | Wewnętrzne | `localhost` i `127.0.0.1` prod dodaje sam (healthcheck) |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | zaufane źródła CSRF | `https://domena` | Wewnętrzne | brak = „CSRF verification failed” przy logowaniu |
| `DJANGO_SECURE_COOKIES`, `DJANGO_SSL_REDIRECT` | cookies `Secure`, przekierowanie na HTTPS | `1`, `1` | Wewnętrzne | `0` tylko w sieci lokalnej bez HTTPS |
| `DJANGO_TRUSTED_PROXY_COUNT` | liczba proxy przed aplikacją | `1` | Wewnętrzne | zła wartość psuje IP w limicie i dzienniku logowań ([auth.md #5](../pitfalls/auth.md)); dodanie proxy (np. Cloudflare) = podbić |
| `DJANGO_SUPERUSER_USERNAME`, `_PASSWORD`, `_EMAIL` | konto tworzone przy **pierwszym** starcie | `admin`, —, — | `_PASSWORD`: **Poufne**; `_EMAIL`: dane osobowe | idempotentne: istniejącego konta **nie zmienia** (patrz 7.3); compose ma domyślne hasło `admin` (R2) |
| `POSTGRES_DB`, `POSTGRES_USER` | baza i użytkownik | `wms`, `wms` | Wewnętrzne | |
| `POSTGRES_PASSWORD` | hasło bazy | — (Coolify: wymagane) | **Poufne** | działa tylko przy inicjalizacji pustego wolumenu `db_data` (7.2); compose: domyślne `wms` (R2) |
| `DATABASE_URL` | składany w compose z `POSTGRES_*` | `postgres://wms:…@db:5432/wms` | **Poufne** (zawiera hasło) | znaki specjalne w haśle łamią URL — używaj liter i cyfr |
| `BACKUP_INTERVAL`, `BACKUP_KEEP_DAYS` | częstotliwość i retencja kopii | `86400` s, `7` dni | Wewnętrzne | zmiana retencji bez kopii off-site = mniej historii |
| `DJANGO_TIME_ZONE` | strefa czasowa | `Europe/Warsaw` | Wewnętrzne | |
| `DJANGO_SESSION_AGE` | bezczynność sesji, s | `1800` | Wewnętrzne | opcjonalna (nie ma jej w `.env.docker.example`) |
| `DJANGO_MAX_UPLOAD_BYTES` | limit żądania POST | `6291456` | Wewnętrzne | opcjonalna; limit pliku importu 5 MB jest w formularzu |
| `DJANGO_CONN_MAX_AGE` | czas trzymania połączeń z bazą, s | `60` | Wewnętrzne | opcjonalna |
| `DJANGO_HSTS_SECONDS` | czas HSTS, s | `2592000` (30 dni) | Wewnętrzne | opcjonalna; wydłużenie jest nieodwracalne po stronie przeglądarek |
| `GUNICORN_WORKERS` | liczba workerów | `3` | Wewnętrzne | opcjonalna; limit logowań rośnie z liczbą workerów (T8) |
| `DEMO_MODE` | tryb demo | `0` (Coolify), `1` tylko na demo | Publiczne | **nigdy `1` na instancji prywatnej** |
| `DEMO_USER`, `DEMO_PASSWORD` | konto „Wejdź jako demo” i hasło kont demo | `demo_operator`, `demo1234` | Publiczne (jawne z założenia) | tylko demo |
| `SERVICE_FQDN_WEB_8000` | domena dla Traefik (Coolify) | zarządza Coolify | Wewnętrzne | domenę wpisuj w UI bez `:8000` |
| `PGPASSWORD` | hasło dla kontenera `backup` | z `POSTGRES_PASSWORD` | **Poufne** | ustawiane w compose |

Zasady: sekrety tylko w środowisku (Coolify / `.env`) — nigdy w repo, dokumentach, logach ani
zgłoszeniach; lokalizacja kopii sekretów (menedżer haseł) — do uzupełnienia przez INFRA.
Zmiana listy zmiennych = aktualizacja obu plików compose, `.env.example`, `.env.docker.example`,
tabeli w COOLIFY.md §6 ([deploy.md #7](../pitfalls/deploy.md)).

---

## 3. Deploy i rollback

### 3.1 Deploy

| | |
|---|---|
| Kto | PO (merge do `main`); INFRA lub DEV obserwuje |
| Kiedy | po zaakceptowanym PR i zielonym CI |
| Status | **przetestowana** (produkcja demo, CI `docker-build`) |
| Czas | kilka minut (build obrazu + start; `start-period` healthchecku 40 s) |

Przed deployem:

1. CI zielone na PR (lint, typy, testy z progiem pokrycia, skany, build obrazu).
2. Przeczytaj `docs/operator/<branch>.md`: migracje, zmienne środowiskowe, kroki weryfikacji.
3. Nowe/zmienione zmienne ustaw w Coolify **przed** merge.
4. Jeśli są migracje: świeża kopia bazy (sekcja 4, „Kopia ręczna”) i plan wycofania (3.2).

Kroki:

1. PO scala PR do `main`. Coolify buduje i wdraża automatycznie (GitHub App lub webhook, [COOLIFY.md §9](../../COOLIFY.md)); ręcznie: zasób → **Deploy**.
2. Obserwuj **Deployments → Logs**: budowa obrazu, potem start kontenera — `entrypoint.sh` czeka na bazę (do 60 s), uruchamia `migrate --noinput`, zakłada superusera (jeśli nie istnieje), startuje gunicorn.
3. Poczekaj, aż `web` ma status **healthy**.
4. Weryfikacja: `curl -fsS https://<domena>/healthz` → `{"status": "ok", "db": true}`; zaloguj się; otwórz listę HU; w logu startu brak błędów migracji; wykonaj kroki z sekcji 2 dokumentu operatora.
5. Wpisz w `docs/operator/<branch>.md`, kto i kiedy zweryfikował.

Czego nie robić:

- nie pushować do `main` z lokalnej maszyny — `main` = produkcja (hook `guard.py` to blokuje, [deploy.md #1](../pitfalls/deploy.md));
- nie wdrażać migracji niszczących (usunięcie kolumny) w jednym kroku z kodem ([deploy.md #2](../pitfalls/deploy.md));
- nie zmieniać ścieżki `/healthz` bez zmiany `Dockerfile` i `prod.py` naraz ([deploy.md #5](../pitfalls/deploy.md));
- nie ustawiać `DEMO_MODE=1` na produkcji.

### 3.2 Rollback

| | |
|---|---|
| Kto | INFRA lub DEV; PO informowany |
| Kiedy | po deployu aplikacja nie działa albo jest krytyczna regresja |
| Status | **nieprzećwiczona** (wg `docs/operator/TEMPLATE.md` §4) |

Kolejność ma znaczenie: nowy obraz uruchamia `migrate` przy starcie, a **starszy obraz nie cofa
schematu**. Dlatego migracje cofamy **przed** kodem.

1. **Migracje** (tylko jeśli deploy je zawierał): w terminalu kontenera `web` (nowa wersja jeszcze działa):
   `python manage.py showmigrations warehouse` → wskaż ostatnią migrację sprzed deployu →
   `python manage.py migrate warehouse <poprzednia_migracja>`. Migracja nieodwracalna → odtworzenie z kopii (sekcja 5).
2. **Kod:** Coolify → zasób → **Deployments** → poprzedni deployment → **Redeploy**; albo revert PR na `main` (merge wykonuje PO) — dostępność przycisku dla zasobu Docker Compose do potwierdzenia przez INFRA.
3. **Zmienne środowiskowe:** przywróć poprzednie wartości w Coolify.
4. **Weryfikacja:** `/healthz` = 200, logowanie, lista HU, `showmigrations warehouse` — wszystkie `[X]`.

Czego nie robić: nie usuwać wolumenów (`docker volume rm`, `docker compose down -v`); nie wracać
do starszego kodu bez cofnięcia migracji; nie edytować zastosowanych migracji.

---

## 4. Backup — gdzie są kopie i jak sprawdzić świeżość

Mechanizm: kontener `backup` (`postgres:16-alpine`) wykonuje `scripts/pg_backup.sh` w pętli:
`pg_dump -h db -U $POSTGRES_USER $POSTGRES_DB | gzip > /backups/wms-RRRRMMDD-GGMMSS.sql.gz`.
Pierwszy zrzut zaraz po starcie kontenera, kolejne co `BACKUP_INTERVAL` (domyślnie 24 h); kopie
starsze niż `BACKUP_KEEP_DAYS` (7) są usuwane. Format: zwykły SQL (nie `-Fc`).

| Aspekt | Stan |
|---|---|
| Lokalizacja | wolumen Docker `db_backups` na **tym samym hoście** co `db_data` (ścieżka: `docker volume inspect`) |
| Off-site | **brak** (R9) |
| Szyfrowanie | **brak** — kopia = cała baza, klasa Poufne (DA-17) |
| Alert o niepowodzeniu | **brak** — tylko wpis w logu kontenera |
| Retencja | 7 dni; **RPO ≈ 24 h** |
| Nie obejmuje | sekretów i konfiguracji (env w Coolify), certyfikatów (Traefik/`caddy_data`), kodu |
| Wymóg Coolify | **Preserve Repository During Deployment** (skrypt montowany z repo; bez tego `backup` restartuje się w kółko) |

### Sprawdzenie świeżości

| | |
|---|---|
| Kto | INFRA |
| Kiedy | co tydzień, przed każdym deployem z migracją, po incydencie |
| Status | procedura ręczna, nieautomatyczna |

```bash
docker exec "$BK" ls -lht /backups | head -5
docker logs --tail 20 "$BK"
```

Kryteria: najnowszy plik młodszy niż ok. 26 h; rozmiar zbliżony do poprzednich; w logu `OK`, bez `BŁĄD pg_dump`.

**Uwaga — rozmiar, nie tylko log.** Skrypt używa `pg_dump … | gzip` w `sh` bez `pipefail`; kod
wyjścia potoku to kod `gzip`, więc przy błędzie `pg_dump` (np. zmienione hasło, baza
niedostępna) w logu może pojawić się `OK` przy pustym pliku (kilkadziesiąt bajtów). Sprawdzaj
rozmiar. Do weryfikacji podczas testu odtworzenia; propozycja poprawki skryptu (`pipefail`)
poza zakresem tego dokumentu.

Szybka kontrola zawartości (propozycja, nieprzećwiczona):

```bash
docker exec "$BK" sh -c 'gunzip -t /backups/<plik>.sql.gz && gunzip -c /backups/<plik>.sql.gz | grep -c "^CREATE TABLE"'
```

Liczba `CREATE TABLE` powinna odpowiadać liczbie tabel aplikacji i Django (kilkadziesiąt).

### Kopia ręczna (przed deployem z migracją) i wywiezienie poza serwer

```bash
# kopia ręczna na hoście (propozycja; nieprzećwiczona w tym repo)
docker exec "$DB" pg_dump -U wms wms | gzip > pre-deploy-$(date +%Y%m%d-%H%M).sql.gz

# skopiowanie kopii z wolumenu na host (COOLIFY.md §10), potem scp/rsync na zewnętrzny nośnik
docker cp "$BK":/backups ./backups-$(date +%F)
```

Kopia to baza produkcyjna ([KLASYFIKACJA_DANYCH §4 pkt 5](../bezpieczenstwo/KLASYFIKACJA_DANYCH.md)):
szyfruj przed wysłaniem (`age`/`gpg`), przechowuj jak sekret, **nigdy nie odtwarzaj jej na dev/demo/testach**.
Docelowo kopia off-site, retencja 30 dni i alert — kandydat na ADR „backup off-site” (R9).

---

## 5. Odtworzenie z kopii — NIEPRZEĆWICZONE (R9)

| | |
|---|---|
| Kto | INFRA (wykonanie), DEV (pomoc), PO (decyzja) |
| Kiedy | utrata/uszkodzenie danych, nieodwracalna migracja, awaria hosta |
| Status | **nieprzećwiczona** — nie wdrażać u klienta przed pierwszym udanym ćwiczeniem |
| RPO / RTO | RPO do 24 h (interwał kopii); RTO — nieustalony (do zmierzenia w ćwiczeniu) |

**Dlaczego rozszerzono COOLIFY.md §10.** Zrzut jest zwykłym SQL bez `--clean`. Wczytanie go
„na” istniejącą bazę z danymi daje błędy `already exists` i konflikty kluczy zamiast nadpisania —
docelowa baza musi być **pusta**. Poniższe kroki dodają jej odtworzenie i tryb „wszystko albo nic”.

Przed odtworzeniem (krok 0): decyzja PO — dane po czasie kopii zostaną utracone. Jeśli aplikacja
jeszcze działa: wyeksportuj ruchy i stany (`/ruchy/eksport/csv/`, `/stany/eksport/csv/`) i poproś
operatorów o wstrzymanie pracy (D-07).

1. **Zatrzymaj** `web` **i `backup`** w Coolify. Zatrzymanie `backup` jest konieczne: inaczej kolejny cykl zrzuci uszkodzoną/pustą bazę, a po `BACKUP_KEEP_DAYS` dobre kopie zostaną usunięte.
2. **Zabezpiecz obecny stan** (dowód i źródło ruchów po kopii):
   `docker exec "$DB" pg_dump -U wms wms | gzip > broken-$(date +%Y%m%d-%H%M).sql.gz`
3. **Wybierz kopię** — najnowszą sprzed incydentu: `docker exec "$BK" ls -lh /backups`; sprawdź `gunzip -t`; skopiuj ją poza wolumen: `docker cp "$BK":/backups/wms-XXXX.sql.gz .`
4. **Utwórz pustą bazę** (po wykonaniu kroku 2!):
   ```bash
   docker exec "$DB" psql -U wms -d postgres \
     -c "DROP DATABASE IF EXISTS wms WITH (FORCE);" \
     -c "CREATE DATABASE wms OWNER wms;"
   ```
5. **Wczytaj kopię** w jednej transakcji:
   ```bash
   gunzip -c wms-XXXX.sql.gz | docker exec -i "$DB" psql -U wms -d wms -v ON_ERROR_STOP=1 --single-transaction
   ```
6. **Uruchom** `web` (Start/Redeploy): `entrypoint.sh` wykona `migrate` (dopasuje schemat, jeśli kopia jest starsza niż kod) i nie zmieni istniejącego superusera. Kopia **nowsza** niż kod (po rollbacku) wymaga wdrożenia zgodnej wersji kodu. Uruchom `backup`.
7. **Weryfikacja:** `/healthz` = 200; logowanie; lista HU; `/ruchy/` — data ostatniego ruchu zgodna z czasem kopii; `python manage.py showmigrations warehouse` — wszystkie `[X]`.
8. **Ruchy po kopii:** porównaj eksport ruchów z kroku 0 (lub `broken-*.sql.gz`) z bazą odtworzoną i **powtórz poprawne operacje po czasie kopii** w kolejności chronologicznej (UI, skaner, importy); potwierdź spisem z natury wybranych lokalizacji.
9. Poinformuj użytkowników; zapisz incydent (8.0).

Czego nie robić: nie wczytywać kopii do bazy z danymi; nie kasować wolumenów `db_data`/`db_backups`;
nie odtwarzać kopii produkcyjnej na demo/dev; nie pomijać `--single-transaction` (częściowe
wczytanie jest gorsze niż żadne); nie zostawiać `backup` włączonego w trakcie odtwarzania.

### Ćwiczenie odtworzenia (wymagane; R9)

Na jednorazowej instancji, **nie na produkcji** (kopia produkcyjna zostaje w kontrolowanym
środowisku). Rola `wms` musi istnieć, bo zrzut zawiera `OWNER TO wms`:

```bash
docker run -d --name restore-test -e POSTGRES_USER=wms -e POSTGRES_PASSWORD=test -e POSTGRES_DB=wms -p 5433:5432 postgres:16-alpine
gunzip -c wms-XXXX.sql.gz | docker exec -i restore-test psql -U wms -d wms -v ON_ERROR_STOP=1 --single-transaction
DATABASE_URL=postgres://wms:test@localhost:5433/wms python manage.py showmigrations warehouse
docker rm -f restore-test
```

Zapisz wynik poniżej (po każdym ćwiczeniu, minimum raz na kwartał — częstotliwość do decyzji PO):

| Data | Kto | Plik kopii | Czas odtworzenia | Wynik (migracje `[X]`, liczba HU) | Uwagi |
|---|---|---|---|---|---|
| — | — | — | — | — | jeszcze nie wykonano |

---

## 6. Reset danych demo

| | |
|---|---|
| Kto | harmonogram Coolify; INFRA ręcznie; każdy odwiedzający (przycisk) |
| Kiedy | codziennie 03:00; po nadużyciu demo; przed prezentacją |
| Status | **przetestowana** (komenda i przycisk: testy; harmonogram: działa na demo wg README, konfiguracja poza repo) |

| Sposób | Jak | Skutek |
|---|---|---|
| Przycisk „Przywróć dane demo” | `POST /demo/przywroc/` (rola Operator; w demo ma ją każdy odwiedzający) | `seed_demo --reset --keep-users`; konta demo zostają, nikt nie traci sesji; blokada 60 s (per proces) |
| Scheduled Task Coolify | zasób → **Scheduled Tasks → + Add**: Name `reset-demo`, Command `python manage.py seed_demo --reset`, Frequency `0 3 * * *`, Container `web` | usuwa dane i konta demo, zasiewa od nowa; **wylogowuje wszystkich** ([COOLIFY.md §11](../../COOLIFY.md)) |
| Ręcznie | terminal `web`: `python manage.py seed_demo --reset` | jak wyżej; bez `DEMO_MODE=1` komenda odmawia |
| Pierwsze zasianie | po pierwszym deployu: `python manage.py seed_demo` | 15 materiałów, ~30 palet, 3 WZ, otwarty spis |

Weryfikacja: wejdź na `/demo/` — pulpit pokazuje dane początkowe; w logu brak błędów.
Reset trzyma `LOCK TABLE … IN EXCLUSIVE MODE` na tabelach domenowych — w trakcie zapisy czekają.
Reset **nie czyści** `LoginEvent` (ani sesji innych kont) — do czasu US-005 sprzątanie ręczne (8.2).

Czego nie robić: **nigdy `seed_demo` na instancji prywatnej/produkcyjnej** — bez `DEMO_MODE`
zakłada konta `demo_operator`/`demo_podglad` z hasłem `demo1234` (R2, US-003) i otwiera system
każdemu; nie ustawiać `DEMO_MODE=1` na produkcji; demo ma własną bazę i sekrety, nigdy dane produkcyjne.

---

## 7. Rotacja sekretów

Okresowość rotacji — do ustalenia przez PO/SEC (repo jej nie definiuje; propozycja: co 12 mies.).
**Natychmiast** po: podejrzeniu wycieku, odejściu osoby z dostępem do Coolify/SSH, incydencie z 8.3 lub 8.6.
Status wszystkich procedur: **nieprzećwiczone**. Każdą wykonuje INFRA; SEC ocenia zakres.

### 7.1 `DJANGO_SECRET_KEY`

- **Skutek:** unieważnia **wszystkie sesje** (hash uwierzytelnienia sesji zależy od klucza), tokeny CSRF i resetu hasła. W konfiguracji nie ma `SECRET_KEY_FALLBACKS`, więc rotacja zawsze wylogowuje wszystkich.
- **Kroki:** (1) wygeneruj nowy klucz (`python -c "import secrets;print(secrets.token_urlsafe(64))"`); (2) Coolify → Environment Variables → `DJANGO_SECRET_KEY`; (3) Redeploy; (4) uprzedź użytkowników o ponownym logowaniu (najlepiej poza godzinami pracy).
- **Weryfikacja:** `/healthz` = 200; logowanie działa; stare sesje wymagają logowania.
- **Nie robić:** nie używać klucza z prefiksem `django-insecure-` ani krótkiego; nie wklejać klucza do repo ani czatu.

### 7.2 Hasło bazy (`POSTGRES_PASSWORD`)

- **Pułapka:** zmienna działa **tylko przy inicjalizacji pustego wolumenu** `db_data`. Zmiana jej w Coolify **nie zmienia** hasła w istniejącej bazie — najpierw `ALTER USER`, potem env.
- **Kroki:** (1) świeża kopia (sekcja 4); (2) `docker exec -it "$DB" psql -U wms -d wms` → `\password wms` (nie wpisuj hasła w poleceniu — trafi do historii powłoki); (3) Coolify: nowe `POSTGRES_PASSWORD`; (4) Redeploy całego zasobu — `web` (`DATABASE_URL`) i `backup` (`PGPASSWORD`) muszą wstać z nowym hasłem.
- **Ograniczenie:** `DATABASE_URL` jest składany bez kodowania — znaki `@ : / # ? %` w haśle go łamią. Używaj liter i cyfr (min. 32 znaki).
- **Weryfikacja:** `/healthz` = 200; po restarcie `backup` w logu nowy wpis `OK` i niezerowy rozmiar pliku.
- **Przy błędzie:** `ALTER USER` do starego hasła i przywrócenie starej zmiennej. Do tego czasu `web` zwraca 503 (`db: false`), a `backup` loguje `BŁĄD pg_dump`.

### 7.3 Hasło superusera

- **Pułapka:** `entrypoint.sh` tworzy konto tylko, gdy go nie ma; zmiana `DJANGO_SUPERUSER_PASSWORD` **nie zmienia** hasła istniejącego konta.
- **Kroki:** terminal `web`: `python manage.py changepassword <login>`. (Przez UI `/uzytkownicy/<pk>/` też można, ale do czasu US-001 każdy Administrator może zmienić hasło superusera — R1.) Następnie zaktualizuj wartość w env, żeby nie zawierała nieaktualnego hasła.
- **Weryfikacja:** logowanie nowym hasłem; stare nie działa; sesje tego konta wygasają.

### 7.4 Hasła użytkowników i konto demo

- Konta pracowników: ADM-APP → `/uzytkownicy/<pk>/` → nowe hasło (walidatory Django); odejście pracownika: **dezaktywacja** konta (nie usuwanie — zostaje ślad „kto”, `created_by` przechodzi na `NULL` przy usunięciu).
- `DEMO_PASSWORD` jest publiczne z założenia; zmiana: env + `seed_demo --reset` (hasło ustawia się przy zasiewie) + aktualizacja README i ekranu logowania.

### 7.5 Sekrety poza aplikacją

Webhook/GitHub App Coolify, klucze SSH, hasło do panelu Coolify, konto GitHub właściciela (merge =
deploy, Z-02): rotacja i lista — do uzupełnienia przez INFRA/PO. `GITHUB_TOKEN` w Actions jest
tymczasowy i nie podlega rotacji ręcznej.

---

## 8. Incydenty

Ogólnie: INFRA prowadzi działania techniczne, SEC ocenia incydenty bezpieczeństwa, PO decyduje o
komunikacji i o zgłoszeniu naruszenia danych osobowych (termin 72 h — [`RODO.md`](../bezpieczenstwo/RODO.md) §8,
dokument powstaje równolegle). Najpierw **przywróć działanie i zabezpiecz ślady**, potem szukaj przyczyny.

| Ważność | Przykład | Reakcja |
|---|---|---|
| Krytyczna | brak dostępu do aplikacji, utrata/uszkodzenie danych, przejęcie konta uprzywilejowanego, wyciek sekretu | od razu INFRA + DEV + SEC + PO |
| Wysoka | degradacja (wolne działanie, błędy 500 w kluczowej operacji), atak na demo | tego samego dnia |
| Niska | pojedynczy błąd użytkownika, fałszywy alarm skanera | w zwykłym trybie pracy |

### 8.0 Zapis incydentu (szablon)

| Pole | Treść |
|---|---|
| ID, data i godzina wykrycia | |
| Kto wykrył, jak | |
| Objaw i zakres (instancja: prod/demo; użytkownicy; dane) | |
| Dane osobowe dotknięte? (tak/nie → zgłoszenie PO) | |
| Kroki naprawcze (z godzinami) | |
| Przyczyna źródłowa | |
| Czas przywrócenia | |
| Wnioski i historyjki do backlogu | |

### 8.1 Aplikacja nie odpowiada / `healthz` 503

| | |
|---|---|
| Kto | INFRA (DEV na wezwanie) |
| Kiedy | strona nie ładuje, 502/504, `web` „unhealthy”, `/healthz` ≠ 200 |
| Status | nieprzećwiczona |

1. **Którą warstwę dotyczy:** `curl -sS -o /dev/null -w "%{http_code}\n" https://<domena>/healthz` — brak odpowiedzi / 502 / 504: proxy lub `web`; **503** (`{"status": "degraded", "db": false}`): `web` żyje, baza nie; **400**: `DisallowedHost` (`DJANGO_ALLOWED_HOSTS`).
2. **Stan kontenerów:** Coolify lub `docker ps -a`; `docker inspect -f '{{.State.Health.Status}} {{.State.OOMKilled}}' "$WEB"`.
3. **Logi:** `docker logs --tail 100 "$WEB"` (JSON). Szukaj: `ImproperlyConfigured` (klucz), błędu migracji (zatrzymuje start), `Baza niedostępna — przerywam.` (entrypoint czeka 60 s na bazę).
4. **Baza:** `docker logs --tail 50 "$DB"`; `docker exec "$DB" pg_isready -U wms`; dysk pełny → 8.2.
5. **Zasoby:** `docker stats --no-stream`; `OOMKilled`/zabite workery (żądanie > 120 s zabija workera) — duże importy, wydruk wszystkich etykiet lokalizacji, spreparowany XLSX (R3, R4, R5).
6. **Po deployu?** Jeśli problem zaczął się po wdrożeniu — rollback (3.2).

Naprawa: restart `web` w Coolify; jeśli baza — restart `db` (dane w wolumenie zostają); zła zmienna — popraw i Redeploy.
Znane przyczyny: migracja nie przeszła; zły `DJANGO_ALLOWED_HOSTS`/`DJANGO_CSRF_TRUSTED_ORIGINS`; hasło bazy zmienione bez `ALTER USER` (7.2); brak certyfikatu/DNS ([COOLIFY.md, „Najczęstsze problemy”](../../COOLIFY.md)).
Weryfikacja: `/healthz` = 200, logowanie, lista HU; zapis incydentu.
Czego nie robić: `docker compose down -v`, `docker volume rm`; restartu `db` w trakcie odtwarzania; zgadywania — najpierw logi.

### 8.2 Baza pełna / brak miejsca na dysku

| | |
|---|---|
| Kto | INFRA; decyzja o usuwaniu danych — PO |
| Kiedy | `No space left on device`, `could not extend file`, 500 przy zapisie, `BŁĄD pg_dump` |
| Status | nieprzećwiczona |

1. **Diagnoza:** `df -h`; `docker system df`; największe tabele:
   `docker exec "$DB" psql -U wms -d wms -c "SELECT relname, pg_size_pretty(pg_total_relation_size(relid)) FROM pg_stat_user_tables ORDER BY pg_total_relation_size(relid) DESC LIMIT 10;"`.
   Typowi winowajcy: `django_session`, `warehouse_loginevent` (brak retencji — R5, R7), `warehouse_stockmovement`, wolumen `db_backups`.
2. **Zwolnij miejsce poza danymi:** nieużywane obrazy (`docker image prune` — **nie** `volume prune`); logi kontenerów (rotacja `json-file` — konfiguracja Dockera do uzupełnienia przez INFRA).
3. **Sesje:** `python manage.py clearsessions` w kontenerze `web` (komenda Django, usuwa tylko wygasłe).
4. **Dziennik logowań** (po decyzji PO; docelowo komenda retencji z US-005, Z-09: 90 dni): superuser w `/admin/` → Dziennik logowań → filtr po dacie → „Usuń zaznaczone”, albo w `manage.py shell`: `LoginEvent.objects.filter(created_at__lt=<data>).delete()`. Najpierw zabezpiecz ślady, jeśli to incydent (8.3).
5. **Miejsce po usunięciu:** zwykły `VACUUM` nie oddaje miejsca systemowi; `VACUUM FULL` blokuje tabelę — tylko w oknie serwisowym.
6. **Trwale:** powiększ dysk (INFRA); kopia off-site zamiast rosnącego `db_backups` (R9).

Weryfikacja: > 20% wolnego miejsca (próg propozycyjny), zapisy działają, kolejny backup `OK` i niezerowy.
Czego nie robić: nie kasować plików w katalogu danych PostgreSQL ani wolumenów; **nie usuwać `warehouse_stockmovement`** (rejestr audytowy); nie zmniejszać `BACKUP_KEEP_DAYS` bez kopii off-site.

### 8.3 Podejrzenie przejęcia konta

| | |
|---|---|
| Kto | ADM-APP (kroki 2–5), INFRA (rotacja), SEC (ocena), PO (komunikacja, RODO) |
| Kiedy | nieznane operacje w ruchach, logowania z obcych IP, zmiany ról/haseł bez zgody, zgłoszenie użytkownika |
| Status | nieprzećwiczona |

1. **Zakres:** jedno konto czy uprzywilejowane (Administrator/superuser)? Uprzywilejowane = incydent krytyczny (R1: Administrator może zmienić hasło superusera).
2. **Dezaktywuj konto** (nie usuwaj): `/uzytkownicy/<pk>/` → odznacz „aktywny”. Konto nieaktywne traci dostęp od razu, także z otwartą sesją. Superusera dezaktywuje się przez `manage.py shell` lub `/admin/` (poza demo).
3. **Zabezpiecz ślady:** zrzut/eksport dziennika logowań i ruchów (`/ruchy/eksport/csv/`) **zanim** cokolwiek zmienisz lub usuniesz.
4. **Przegląd `LoginEvent`:** `/uzytkownicy/dziennik/` (100 wpisów/stronę) lub `/admin/` (filtry, szukanie po loginie/IP): nowe IP, serie `FAILED`, nietypowe pory. Uwaga: poprawne IP wymaga właściwego `DJANGO_TRUSTED_PROXY_COUNT`.
5. **Przegląd działań:** `/ruchy/` (kolumna „Kto”) i eksport ruchów; `/uzytkownicy/` (nowe konta, zmiany ról); zmiany w panelu Django: `manage.py shell` → `from django.contrib.admin.models import LogEntry; LogEntry.objects.order_by("-action_time")[:50]` (superuser może edytować ruchy w `/admin/`).
6. **Rotacja:** hasło konta (po zabezpieczeniu śladów). Dla konta uprzywilejowanego lub gdy nie da się wykluczyć wycieku sekretu: `DJANGO_SECRET_KEY` (7.1, wyloguje wszystkich) i hasło superusera (7.3); przy podejrzeniu dostępu do serwera/bazy także 7.2 i 7.5.
7. **Skutki dla danych:** porównaj stany z kopią (sekcja 5, ćwiczebnie) lub spisem z natury; poprawki **korektami z powodem**, nie edycją ruchów.
8. **Komunikacja:** PO decyduje o powiadomieniu użytkowników i o zgłoszeniu (dane osobowe: 72 h). Zapis incydentu (8.0); wniosek do backlogu (R6: 2FA, limit per konto).

Czego nie robić: nie usuwać konta ani wpisów `LoginEvent` przed zabezpieczeniem dowodów; nie resetować hasła przed dezaktywacją i zabezpieczeniem śladów; nie edytować ani usuwać ruchów w `/admin/`.

### 8.4 Uszkodzenie danych

| | |
|---|---|
| Kto | DEV + INFRA; decyzja o odtworzeniu — PO |
| Kiedy | stany nie zgadzają się po błędnej operacji lub imporcie, usunięcie w `/admin/`, błąd migracji |
| Status | nieprzećwiczona |

Od najmniej do najbardziej inwazyjnego:

1. **Błąd ludzki lub pojedyncze palety:** popraw **korektą z powodem** (`/hu/<pk>/korekta/`, skaner „Inwentaryzacja”) lub przepakowaniem; spis z natury. Ślad zostaje; ruchów nie edytujemy.
2. **Błędny import:** importy działają w transakcji (błąd = brak zapisu), ale poprawnie zapisany zły plik trzeba skorygować korektami; przy masowym błędzie — krok 4.
3. **Pojedyncze wyjątkowe naprawy:** DEV skryptem w `manage.py shell` **przez funkcje `services.py`** (nigdy `hu.quantity = …; hu.save()` — [db.md #1](../pitfalls/db.md)), po zatwierdzeniu PO i z kopią bazy.
4. **Odtworzenie z kopii + ruchy po kopii:** (a) wstrzymaj pracę magazynu (D-07); (b) **zanim** odtworzysz — zabezpiecz uszkodzoną bazę (`pg_dump`) i wyeksportuj ruchy oraz stany do CSV; (c) odtwórz wg sekcji 5; (d) porównaj eksport ruchów z bazą odtworzoną i **powtórz poprawne operacje po czasie kopii** w kolejności chronologicznej; (e) potwierdź spisem z natury.

Weryfikacja: spis z natury wybranych lokalizacji, `/raporty/`, porównanie stanów z eksportem sprzed incydentu.
Czego nie robić: nie edytować/usuwać ruchów w `/admin/`; nie odtwarzać bez kopii obecnego stanu; nie pracować na produkcji bez świeżej kopii.

### 8.5 Atak DoS na demo

| | |
|---|---|
| Kto | INFRA (zatrzymanie, blokady), DEV/SEC (analiza), PO (decyzja o publicznym dostępie) |
| Kiedy | demo wolne lub niedostępne, skok CPU/RAM, tysiące wpisów `LoginEvent`/`django_session`, 500/timeouty na importach i etykietach |
| Status | nieprzećwiczona |

Kontekst: demo to fikcyjne dane i anonimowy Operator (Z-05, R3–R5) — zagrożona jest dostępność
i wizerunek, nie dane produkcyjne. Demo jest **osobnym zasobem** (osobna baza i sekrety).

1. **Potwierdź, że to instancja demo** (`DEMO_MODE=1`), nie produkcja.
2. **Zatrzymaj zasób demo** w Coolify (**Stop**) — najszybsze ograniczenie szkód; dane demo i tak odtworzy `seed_demo`.
3. **Źródło:** logi proxy (Traefik) i access log gunicorna — adresy IP, ścieżki (`/demo/`, `/login/demo/`, `/przyjecie/`, `*/import/`, `/lokalizacje/etykiety/`). Blokada IP/zakresu na firewallu hosta lub przed proxy — poza repo, do uzupełnienia przez INFRA.
4. **Sprzątanie:** `python manage.py clearsessions`; masowe `LoginEvent` (8.2 pkt 4); `python manage.py seed_demo --reset` (przywraca dane po atakach importami).
5. **Uruchom ponownie i obserwuj** (`docker stats`, logi).
6. **Naprawa przyczyn (backlog):** limiter na `/demo/`, `/login/demo/` i ścieżkach operatora (R5, US-005), limity liczby palet i wierszy (R3 — US-002; R4 — US-004), limit etykiet lokalizacji i paginacja, reset tylko ze Scheduled Task. Ponowne udostępnienie demo publicznie — decyzja PO (Z-05).

Czego nie robić: nie dotykać zasobu produkcyjnego; nie wyłączać `DEMO_MODE` na działającym demo „na chwilę”; nie testować DoS na cudzej instancji.

### 8.6 Wyciek sekretu w repozytorium

| | |
|---|---|
| Kto | SEC + INFRA; PO — komunikacja |
| Kiedy | gitleaks (job `secrets` w CI lub `security.yml`) zgłasza trafienie; ktoś zauważył klucz/hasło w commicie, issue, logu, zrzucie |
| Status | nieprzećwiczona |

Repozytorium jest publiczne — **zakładaj, że wyciek jest trwały** (skanery botów działają w minutach).
Zasada: **rotacja najpierw, czyszczenie historii potem.**

1. **Ustal, co wyciekło i gdzie działa:** klucz Django (prod/demo?), hasło bazy/superusera, token GitHub, webhook/GitHub App Coolify, klucz SSH. Szczegóły z raportu gitleaks (commit, plik): lokalnie `gitleaks git --no-banner .` ([CONTRIBUTING §6](../../CONTRIBUTING.md)).
2. **Fałszywy alarm** (np. klucz „CI-only”, hasło testowe): wpis w `.gitleaksignore` z uzasadnieniem w komentarzu — nie wyciszać hurtowo.
3. **Prawdziwy sekret — natychmiast rotuj** wg sekcji 7 (klucz Django → wylogowanie wszystkich; baza; superuser; token/webhook w GitHub i Coolify; klucz SSH).
4. **Sprawdź nadużycie** w okresie ekspozycji: `LoginEvent`, `/ruchy/`, logi proxy, nowe konta (8.3).
5. **Historia gita:** nowy commit usuwający sekret **nie usuwa go z historii**. Przepisanie historii (`git filter-repo`/BFG + force-push) jest operacją niszczącą — tylko za zgodą PO, wykonuje człowiek (hook `guard.py` blokuje push na `main`) — i nie cofa wycieku (forki, cache). Dlatego kluczowa jest rotacja.
6. **Zapobieganie:** pre-commit z gitleaks, gitleaks blokujący PR w CI, `.env*` w `.gitignore` i `.dockerignore`, `guard.py` blokuje zapis plików z sekretami.
7. Zapis incydentu (8.0); aktualizacja rejestru ryzyk.

Czego nie robić: nie zostawiać starego sekretu „bo to tylko demo” bez decyzji PO; nie przesyłać sekretu w zgłoszeniu ani czacie.

---

## 9. Monitoring

### Co jest

| Mechanizm | Co sprawdza | Gdzie widać | Uwagi |
|---|---|---|---|
| `HEALTHCHECK` obrazu `web` | `GET /healthz` na 127.0.0.1:8000, co 30 s, timeout 5 s, 3 próby, start 40 s | Coolify, `docker ps` | `unhealthy` **nie** powoduje samoczynnego restartu (`restart: unless-stopped` dotyczy zakończenia procesu); reakcja Coolify — do potwierdzenia przez INFRA |
| Healthcheck `db` | `pg_isready` co 5 s | `docker ps` | steruje `depends_on` |
| Logi aplikacji | stdout; JSON (`ts`, `level`, `logger`, `msg`, `exc`); błędy 5xx jako `django.request` ERROR z tracebackiem | Coolify → Logs, `docker logs` | retencja logów zależy od konfiguracji Dockera — do uzupełnienia przez INFRA |
| Access log gunicorna | każde żądanie (tekst) | j.w. | zawiera ścieżkę i `?q=`; źródło IP do analizy ataków (8.5) |
| Log kopii | `[backup] … OK/BŁĄD` | logi kontenera `backup` | patrz uwaga o rozmiarze w sekcji 4 |
| Dziennik logowań | udane, nieudane, wylogowania, IP | `/uzytkownicy/dziennik/` (ADM-APP) | brak retencji (R7) |
| CI `docker-build` | smoke test: kontener staje się „healthy” | GitHub Actions | na każdy PR |
| `security.yml`, Dependabot | skany doradcze (tygodniowo), PR-y z aktualizacjami | GitHub | ADR-0001 |

### Czego brakuje

| Luka | Konsekwencja | Powiązanie |
|---|---|---|
| **Alerty o błędach 500** (`ADMINS` puste, brak Sentry/GlitchTip) | awaria wychodzi na jaw dopiero ze zgłoszenia użytkownika | **T15**, US-021 |
| Zewnętrzny monitoring dostępności z powiadomieniem | nieobecność aplikacji niezauważona | do decyzji PO/INFRA |
| Alert, gdy kopia zawodzi lub jest nieświeża | utrata danych wykryta przy odtwarzaniu | **R9**, US-012 |
| Metryki hosta i aplikacji (CPU, RAM, dysk, opóźnienia, błędy) | brak danych do diagnozy i planowania | do uzupełnienia przez INFRA |
| Alert zajętości dysku i wolumenu `db_backups` | scenariusz 8.2 zaskakuje | do uzupełnienia przez INFRA |
| Powiadomienia Coolify (nieudany deploy, restarty) | zależą od konfiguracji panelu | do uzupełnienia przez INFRA |
| Alert wygasania certyfikatu | Traefik/Caddy odnawiają automatycznie; brak alarmu przy awarii odnowienia | niski priorytet |

### Przegląd cotygodniowy (INFRA lub ADM-APP, ~15 min)

1. `curl -fsS https://<domena>/healthz`.
2. Wolne miejsce na dysku i rozmiar `db_backups`.
3. Świeżość i rozmiar najnowszej kopii (sekcja 4).
4. Logi z poziomem `ERROR` z ostatnich 7 dni.
5. Dziennik logowań: serie `FAILED`, nowe IP.
6. Status CI/`security.yml`, otwarte PR-y Dependabota.

---

## 10. Historia zmian dokumentu

| Wersja | Data | Zmiana |
|---|---|---|
| 0.1 | 2026-10-16 | szkic: konfiguracja, deploy/rollback, backup, odtworzenie, demo, rotacja, incydenty, monitoring |
