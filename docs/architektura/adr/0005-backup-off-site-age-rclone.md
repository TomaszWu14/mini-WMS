# ADR-0005 — Backup poza serwerem: age + rclone + heartbeat

| | |
|---|---|
| Status | zaakceptowany (decyzje PO 2026-10-16: rclone, age z kluczem offline, heartbeat, 30 dni) |
| Data | 2026-10-16 |
| Właściciel | [DEV] z udziałem [SEC] |
| Powiązania | US-012, SEC-039, NFR-018, NFR-019; AUDYT R9; RYZYKA RR-13, W-3; `scripts/pg_backup.sh`, `docker/backup.Dockerfile`; RUNBOOK §5 |

## Kontekst

Kontener `backup` robił `pg_dump | gzip` do wolumenu na **tym samym** hoście co baza: awaria dysku,
przejęcie serwera lub pomyłka niszczą bazę i kopie naraz. Kopie nie były szyfrowane, nikt nie
dostawał alertu o braku kopii, a odtworzenie nie było przećwiczone. Potok `pg_dump | gzip` bez
`pipefail` logował „OK” przy pustym pliku.

## Decyzja

| Obszar | Wybór | Powód |
|---|---|---|
| Wysyłka | **rclone**, cel z env `RCLONE_CONFIG_OFFSITE_*`, ścieżka `BACKUP_RCLONE_REMOTE` | jeden kod dla S3 (B2, R2, AWS), SFTP (Hetzner Storage Box) i innych; dostawcę PO wybiera w Coolify bez zmiany kodu |
| Szyfrowanie | **age**, na serwerze tylko klucz publiczny (`BACKUP_AGE_RECIPIENT`); klucz prywatny offline u PO | przejęcie serwera nie daje odczytu kopii (kryterium 1); age jest prosty i bez konfiguracji |
| Alert | **heartbeat** (`BACKUP_HEARTBEAT_URL`) po pełnym sukcesie | „dead man's switch” alarmuje też, gdy kontener backupu w ogóle nie działa; usługa (Healthchecks.io, Uptime Kuma) wysyła e-mail/SMS |
| Retencja | lokalnie 7 dni (`BACKUP_KEEP_DAYS`), off-site **30 dni**: domyślnie reguła lifecycle bucketu, a klucz serwera bez prawa usuwania; `BACKUP_OFFSITE_PRUNE=1` (SFTP) — skrypt usuwa tylko `wms-*.sql.gz.age` w swoim katalogu (`--max-depth 1`) | kopia sprzed błędu zauważonego po tygodniach; 30 dni mieści się w RODO obok retencji dziennika 90 dni |
| Zrzut | `pg_dump -Z 6 -f plik` (bez potoku), kontrola rozmiaru i `gzip -t` | kod wyjścia pochodzi z pg_dump; pusta/uszkodzona kopia = błąd, brak pingu |
| Obraz | `docker/backup.Dockerfile`: `postgres:16-alpine` + `age rclone curl` | ta sama wersja `pg_dump` co serwer; skrypt w obrazie zamiast montowania |

Off-site bez szyfrowania jest odrzucany (kod wyjścia 2). Bez konfiguracji off-site kontener działa jak dotąd
(tylko kopia lokalna).

## Zmiana po przeglądzie [SEC] (2026-10-16)

Przejęty serwer z kluczem z prawem usuwania mógłby skasować wszystkie kopie off-site (ransomware) —
dlatego retencja domyślnie po stronie bucketu, a usuwanie przez skrypt jest opcją. Usuwanie ograniczone do
jednego katalogu; retencja < 1 dnia i cel bez ścieżki są odrzucane. Obraz `backup` skanuje trivy w CI, a
ćwiczenie odtworzenia używa tego samego obrazu. Obraz bazowy jest przypięty tagiem `postgres:16-alpine`
(Dependabot śledzi `docker/`); przypięcie digestem — zrobione w US-020 (ADR-0007).

## Konsekwencje

- PO musi wygenerować parę kluczy (`age-keygen`) na własnym komputerze i **przechować klucz prywatny w dwóch
  miejscach** (menedżer haseł + wydruk/pendrive w sejfie). Utrata klucza = kopie off-site nie do odczytu.
- Coolify buduje obraz `backup` (pierwszy deploy trwa dłużej); `apk` pobiera pakiety przy budowie.
- CI ćwiczy cały łańcuch na PostgreSQL: seed → skrypt backupu → age → rclone (katalog) → odszyfrowanie → odtworzenie
  do pustej bazy → `check`, migracje i `backup_fingerprint` zgodne. Ćwiczenie na prawdziwej kopii produkcyjnej —
  raz w miesiącu, RUNBOOK §5.4.
