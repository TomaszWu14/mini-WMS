# ccr-93422d57-atfl7j — instrukcja dla operatora

| | |
|---|---|
| Branch | `ccr-93422d57-atfl7j` |
| PR | jeszcze nie utworzony |
| Data | 2026-10-13 |
| Ryzyko | niskie — nowe adresy działają tylko przy `DEMO_MODE=1`; poza demo bez zmian zachowania |

## 1. Co zmieniono
- **Demo bez logowania:** adres `https://miniwms.twapp.pl/demo/` od razu wpuszcza do aplikacji
  kontem `demo_operator` i włącza prezentację z lektorem. Ten link można wklejać do README,
  opisu filmu i CV. Kogoś już zalogowanego link nie przelogowuje.
- **„Przywróć dane demo”:** przycisk w żółtym banerze (tylko dla roli Operator i
  Administrator). Przywraca palety, wydania i spis do stanu początkowego dla wszystkich
  odwiedzających, najwyżej raz na minutę. Konta demo zostają, więc nikt nie zostaje wylogowany.
- **Ekran logowania w demo:** link „wejdź i obejrzyj prezentację z lektorem (3 min)”.
- **Film na YouTube:** `docs/video/youtube/` — film MP4 z lektorem (3:15, 1920×1080),
  napisy `.srt`, miniatura 1280×720 i `youtube.md` (tytuł, opis z rozdziałami, tagi).
- README: link do `/demo/` i do filmu z lektorem.
- Technicznie: `tools/record_video.py` nagrywa prezentację w przeglądarce (Playwright) i
  nakłada nagrania lektora (ffmpeg); `seed_demo --reset --keep-users`; reset i zasiew w
  jednej transakcji, na PostgreSQL z blokadą tabel magazynu (zapisy innych czekają
  ułamek sekundy zamiast kończyć się błędem); rozdziały filmu w polu `chapter` w `demo_script.json`;
  `playwright` w `requirements-dev.txt`. Nagrania lektora bez zmian (brak klucza
  ElevenLabs API w środowisku — przegenerowanie z pełnymi ustawieniami głosu: §3).

## 2. Kroki do ręcznego sprawdzenia

| # | Konto (rola) | Gdzie | Co zrobić | Oczekiwany wynik |
|---|---|---|---|---|
| 1 | — (wylogowany) | `/demo/` | otworzyć | pulpit jako `demo_operator`, przycisk „▶ Rozpocznij prezentację” |
| 2 | j.w. | pulpit | „Rozpocznij prezentację” | lektor, napisy, przejście przez 14 ekranów bez logowania |
| 3 | `demo_operator` (Operator) | dowolna strona | dodać przyjęcie, potem w banerze „Przywróć dane demo” | komunikat „Przywrócono dane demo…”, nowego przyjęcia nie ma, nadal zalogowany |
| 4 | j.w. | baner | kliknąć „Przywróć dane demo” drugi raz w ciągu minuty | komunikat „…przywrócono przed chwilą” |
| 5 | `demo_podglad` (Podgląd) | pulpit | zalogować się hasłem `demo1234` | baner bez przycisku „Przywróć dane demo” |
| 6 | — | `/login/` | spojrzeć pod „Wejdź jako demo” | link do prezentacji z lektorem |
| 7 | — | `docs/video/youtube/` | obejrzeć `miniwms-youtube.mp4` | plansza tytułowa, prezentacja z lektorem, plansza z linkami |

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
| — | nie dotyczy | — | ☐ nie dotyczy |

Zaktualizowano też: `.env.example` — nie dotyczy, `.env.docker.example` — nie dotyczy,
`COOLIFY.md` — nie dotyczy (nocny `reset-demo` bez zmian).

### Przed i po deployu
- ☐ CI zielone na PR (`ci.yml`, `security.yml`)
- ☐ backup bazy prod sprzed deployu — nie dotyczy (brak migracji)
- ☐ po deployu: `/healthz` zwraca `{"status": "ok"}`
- ☐ kroki 1–6 z sekcji 2 wykonane na `https://miniwms.twapp.pl`
- ☐ w Coolify sprawdzić, że zadanie `reset-demo` istnieje i ma udane uruchomienia

### Film na YouTube
1. Wgraj `docs/video/youtube/miniwms-youtube.mp4`; tytuł, opis i tagi z `youtube.md`.
2. Miniatura: `thumbnail.png`. Napisy: `miniwms-youtube.pl.srt` (język: polski).
3. W README podmień link „Prezentacja z lektorem” na adres filmu na YouTube.

### Jak nagrać film od nowa (np. po zmianie tekstu lub nagrań)
1. `pip install -r requirements-dev.txt`; Chromium: `playwright install chromium`
   (albo `--chromium <ścieżka>`); `ffmpeg` i `ffprobe` w PATH.
2. Opcjonalnie lepszy głos: `ELEVENLABS_API_KEY`, `ELEVENLABS_VOICE_ID` w powłoce →
   usuń stare pliki z `warehouse/static/demo/audio/` → `python tools/generate_voiceover.py`.
3. `DEMO_MODE=1 python manage.py seed_demo --reset`, potem `DEMO_MODE=1 python manage.py runserver`.
4. `python tools/record_video.py` (ok. 4 min) → wynik w `docs/video/youtube/`.

## 4. Plan wycofania
1. Kod: Coolify → zasób → **Deployments** → poprzedni deployment → **Redeploy**
   (albo revert PR na `main`).
2. Migracje: nie dotyczy.
3. Zmienne środowiskowe: nie dotyczy.
4. Weryfikacja po wycofaniu: `/healthz`, logowanie, lista HU; `/demo/` zwraca 404.
