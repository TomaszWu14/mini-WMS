# Wdrożenie mini-WMS na Coolify — krok po kroku

Coolify to self-hostowany panel (jak własne Heroku/Vercel), który deployuje
aplikacje z repozytorium Git. Ma **wbudowany reverse-proxy (Traefik) z
automatycznym SSL**, więc nie używamy tu własnego Caddy — wystarczy wariant
`docker-compose.coolify.yml`.

---

## 0. Wymagania

- Serwer (VPS) z systemem Linux, publicznym IP, otwartymi portami **80** i **443**.
- Domena, np. `miniwms.example.com`, z rekordem **A** skierowanym na IP serwera.
- Repozytorium: `https://github.com/TomaszWu14/mini-WMS` (publiczne).

---

## 1. Instalacja Coolify (pomiń, jeśli już działa)

Na serwerze (przez SSH) jako root:

```bash
curl -fsSL https://cdn.coollabs.io/coolify/install.sh | bash
```

Po instalacji otwórz panel: **`http://IP_SERWERA:8000`** i załóż konto
administratora (pierwszy użytkownik = właściciel instancji).

> Sprawdzenie, czy Coolify już działa: `docker ps | grep coolify`.

---

## 2. (Opcjonalnie) Domena samego panelu Coolify

W panelu: **Settings → General → Instance domain** — możesz ustawić domenę dla
samego Coolify (np. `coolify.example.com`). Nie jest to wymagane do wdrożenia WMS.

---

## 3. Utwórz projekt

1. Lewy panel → **Projects → + Add**.
2. Nazwa: `mini-wms` → **Continue**.
3. Wejdź w środowisko **Production**.

---

## 4. Dodaj zasób z repozytorium (Docker Compose)

1. **+ New Resource**.
2. Wybierz **Docker Compose** (lub „Public Repository”, a typ ustaw na Compose).
3. **Repository URL:** `https://github.com/TomaszWu14/mini-WMS`
4. **Branch:** `main`
5. **Docker Compose file location:** `docker-compose.coolify.yml`
6. Zatwierdź — Coolify wczyta usługi `web` i `db`.

---

## 5. Ustaw domenę aplikacji

W ustawieniach zasobu, sekcja **Domains** dla usługi **web**:

- Wpisz: `https://miniwms.example.com`
- Port docelowy: **8000** (jeśli pytane).

Coolify automatycznie wystawi certyfikat Let's Encrypt dla tej domeny.

> Alternatywnie zadziała to przez zmienną `SERVICE_FQDN_WEB_8000` (patrz niżej),
> ale ustawienie domeny w UI jest najczytelniejsze.

---

## 6. Ustaw zmienne środowiskowe

Zakładka **Environment Variables** zasobu → dodaj (Twoje własne wartości!):

| Zmienna | Wartość (przykład) |
|---|---|
| `DJANGO_SECRET_KEY` | długi losowy ciąg (50+ znaków) |
| `DJANGO_ALLOWED_HOSTS` | `miniwms.example.com` |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | `https://miniwms.example.com` |
| `DJANGO_SECURE_COOKIES` | `1` |
| `DJANGO_SUPERUSER_USERNAME` | `admin` |
| `DJANGO_SUPERUSER_PASSWORD` | mocne hasło |
| `DJANGO_SUPERUSER_EMAIL` | `admin@example.com` |
| `POSTGRES_DB` | `wms` |
| `POSTGRES_USER` | `wms` |
| `POSTGRES_PASSWORD` | mocne hasło bazy |

> Wygenerowanie klucza (lokalnie): `python -c "import secrets;print(secrets.token_urlsafe(64))"`.

---

## 7. Deploy

Kliknij **Deploy**. Coolify:

1. sklonuje repo i zbuduje obraz z `Dockerfile`,
2. uruchomi PostgreSQL + aplikację,
3. `entrypoint.sh` wykona migracje i utworzy konto administratora,
4. Traefik podłączy domenę i wystawi HTTPS.

Podgląd postępu: zakładka **Deployments / Logs**.

---

## 8. Sprawdzenie

- Aplikacja: **`https://miniwms.example.com/`**
- Panel admina Django: **`https://miniwms.example.com/admin/`** (login z `DJANGO_SUPERUSER_*`).

---

## 9. Auto-deploy po każdym push do `main`

Żeby nie klikać ręcznie **Redeploy** — aplikacja ma się aktualizować sama po
merge do `main`. Dwie drogi:

### Wariant A — GitHub App (zalecany)

1. W Coolify: **Sources → + Add → GitHub App**.
2. Kliknij **Install/Connect** i autoryzuj konto GitHub; wybierz repozytorium
   `TomaszWu14/mini-WMS` (lub „All repositories”).
3. Wróć do zasobu `mini-wms` → zakładka **Source** → zmień źródło na właśnie
   dodaną **GitHub App** i to samo repo/branch (`main`).
4. Włącz **Automatic Deployment** (czasem: „Auto Deploy” / „Deploy on push”).
5. Gotowe — po każdym merge do `main` Coolify sam zbuduje i wdroży.

### Wariant B — Webhook (gdy zostajesz przy publicznym repo po URL)

1. W zasobie w Coolify znajdź **Webhook URL** (sekcja Webhooks / General) i
   **skopiuj** go; włącz **Automatic Deployment**.
2. W GitHub: repo **Settings → Webhooks → Add webhook**:
   - **Payload URL:** wklejony URL z Coolify,
   - **Content type:** `application/json`,
   - **Secret:** jeśli Coolify go podał — wklej,
   - **Events:** „Just the push event”.
3. Zapisz. Po push do `main` GitHub powiadomi Coolify, a ten zrobi deploy.

> Sprawdzenie: zrób drobny commit do `main` i obserwuj zakładkę
> **Deployments** w Coolify — powinien ruszyć automatycznie.

---

## 10. Backup bazy danych

`docker-compose.coolify.yml` zawiera usługę **`backup`**, która automatycznie
robi zrzut bazy (`pg_dump` → `gzip`) i trzyma kopie w wolumenie `db_backups`.

- Częstotliwość i retencja w `.env`:
  - `BACKUP_INTERVAL` — co ile sekund (domyślnie `86400` = 24h),
  - `BACKUP_KEEP_DAYS` — ile dni trzymać kopie (domyślnie `7`).
- Podgląd logów backupu: w Coolify wybierz kontener **backup → Logs** (wpisy
  `[backup] ... OK -> /backups/wms-...sql.gz`).

### Pobranie / odtworzenie kopii (przez SSH na serwerze)

```bash
# Lista kopii:
docker exec $(docker ps --format '{{.Names}}' | grep -E '^backup') ls -lh /backups

# Odtworzenie wybranej kopii do bazy (UWAGA: nadpisuje dane!):
B=$(docker ps --format '{{.Names}}' | grep -E '^backup')
DB=$(docker ps --format '{{.Names}}' | grep -E '^db')
docker exec "$B" sh -c 'gunzip -c /backups/wms-XXXX.sql.gz' \
  | docker exec -i "$DB" psql -U wms -d wms
```

> Podmień `wms-XXXX.sql.gz` na właściwą nazwę pliku. Do przechowywania kopii
> poza serwerem skopiuj pliki z wolumenu `db_backups` (np. `docker cp`) na
> zewnętrzny dysk / chmurę.

---

## 11. Instancja demo (opcjonalnie)

Publiczne demo to osobny zasób z tym samym `docker-compose.coolify.yml` —
z własną bazą, nigdy na danych produkcyjnych.

1. Domena, np. `https://wms-demo.twapp.pl` (przykład), oraz zmienne jak w kroku 6
   plus **`DEMO_MODE=1`**. Tryb demo włącza baner „DEMO — dane przykładowe…”,
   pokazuje loginy kont demo na stronie logowania, blokuje edycję kont demo,
   ogranicza logowania (10 prób / 5 min / IP) i wysyła maile tylko do konsoli.
2. Po pierwszym deployu zasiej dane (terminal kontenera `web` w Coolify):
   `python manage.py seed_demo`
3. **Reset co 24 h** — zakładka zasobu **Scheduled Tasks → + Add**:
   - Name: `reset-demo`
   - Command: `python manage.py seed_demo --reset`
   - Frequency: `0 3 * * *` (codziennie 03:00)
   - Container: `web`

   `--reset` czyści wszystkie dane magazynowe i konta demo, po czym zasiewa
   je od nowa (deterministycznie). Bez `DEMO_MODE=1` komenda odmawia resetu.
   Cron nie jest częścią obrazu — harmonogram trzyma Coolify.

Konta demo: `demo_operator` (Operator) i `demo_podglad` (Podgląd), hasło
`demo1234`. Konto administratora z `DJANGO_SUPERUSER_*` zostaje prywatne.
Przy `DEMO_MODE=1` panel `/admin/` jest wyłączony (404); dane demo odnawia Scheduled Task
`python manage.py seed_demo --reset`, a zadania serwisowe robi się przez `manage.py` w kontenerze.

---

## Najczęstsze problemy

- **Brak certyfikatu / błąd SSL** → sprawdź, czy rekord DNS `A` wskazuje na IP
  serwera i czy porty 80/443 są otwarte. Certyfikatu nie da się wystawić dla
  samego IP — wymagana domena.
- **`DisallowedHost` / `400 Bad Request`** → ustaw `DJANGO_ALLOWED_HOSTS` na
  domenę (lub `*`) i zrób ponowny deploy.
- **`CSRF verification failed` przy logowaniu** → ustaw
  `DJANGO_CSRF_TRUSTED_ORIGINS=https://miniwms.example.com`.
- **Baza „nie gotowa” przy starcie** → to normalne przy pierwszym uruchomieniu;
  `entrypoint.sh` czeka na bazę, a healthcheck pilnuje kolejności.
