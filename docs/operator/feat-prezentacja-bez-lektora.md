# feat: prezentacja bez lektora — instrukcja dla operatora

| | |
|---|---|
| Branch | `ccr-93422d57-atfl7j` (nazwa techniczna sesji Claude) |
| PR | #21 (scalony) |
| Data | 2026-10-13 |
| Ryzyko | niskie — zmienia tylko prezentację `?demo=1` i film; logika magazynu i dane bez zmian |

## 1. Co zmieniono
- **Prezentacja bez lektora.** Zostają napisy, podświetlenia i przechodzenie między
  ekranami. Każdy krok trwa tyle, ile czytanie napisu (ok. 15 znaków na sekundę, min. 4 s).
  Z paska zniknęły przyciski wyciszania i głośności. Pauza, poprzedni i następny krok
  działają jak dotąd.
- Przyczyna: skończyły się kredyty ElevenLabs. Bez nich nie da się poprawić ani zmienić
  nagrań, więc lektor znika całkowicie, zamiast zostać nagraniem, którego nie da się
  zaktualizować.
- **Film na YouTube nagrany od nowa** (`docs/video/youtube/`): 2:47, napisy wypalone w
  obrazie i osobny plik `.srt`, cicha ścieżka dźwiękowa. Rozdziały: 9, bo „Rejestr ruchów”
  i „Raporty” połączyły się w „Historia ruchów i raporty” (YouTube wymaga min. 10 s na
  rozdział).
- Teksty: przycisk na pulpicie „▶ Prezentacja (3 min)”, link na ekranie logowania
  „wejdź i obejrzyj 3-minutową prezentację”, README bez słowa „lektor”.
- Technicznie: usunięte nagrania MP3 (`warehouse/static/demo/audio/`),
  `tools/generate_voiceover.py`, `config/voice.json` i ich testy. `demo.js` zgłasza
  zdarzenia `demo:step` / `demo:end`, z których `tools/record_video.py` tnie film i liczy
  napisy.

## 2. Kroki do ręcznego sprawdzenia

| # | Konto (rola) | Gdzie | Co zrobić | Oczekiwany wynik |
|---|---|---|---|---|
| 1 | — (wylogowany) | `/demo/` | kliknąć „Rozpocznij prezentację” | napisy, podświetlenie, kroki zmieniają się same, brak dźwięku |
| 2 | j.w. | pasek prezentacji | ⏸, potem ▶ | krok zatrzymuje się i rusza od miejsca pauzy |
| 3 | j.w. | pasek | ⏭ kilka razy | kolejne ekrany; brak przycisków głośności |
| 4 | `demo_operator` (Operator) | pulpit | spojrzeć na panel „Od czego zacząć” | przycisk „▶ Prezentacja (3 min)” |
| 5 | — | `docs/video/youtube/` | obejrzeć `miniwms-youtube.mp4` | 2:47, plansze, napisy, bez lektora |

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
| `ELEVENLABS_API_KEY`, `ELEVENLABS_VOICE_ID` | usunięte — były tylko lokalne, dla generatora nagrań | — | ☐ nie dotyczy |

Zaktualizowano też: `.env.example` — nie dotyczy, `.env.docker.example` — nie dotyczy,
`COOLIFY.md` — nie dotyczy.

### Przed i po deployu
- ☐ CI zielone na PR (`ci.yml`, `security.yml`)
- ☐ backup bazy prod sprzed deployu — nie dotyczy (brak migracji)
- ☐ po deployu: `/healthz` zwraca `{"status": "ok"}`
- ☐ kroki 1–4 z sekcji 2 wykonane na `https://miniwms.twapp.pl`
  (Ctrl+F5 — przeglądarka może trzymać stary `demo.js`)

### Film na YouTube
Wgraj `docs/video/youtube/miniwms-youtube.mp4` według `youtube.md` (tytuł, opis z
rozdziałami, tagi, miniatura `thumbnail.png`, napisy `.pl.srt`).
Nowe nagranie po zmianie tekstów: `DEMO_MODE=1 python manage.py seed_demo --reset`,
`DEMO_MODE=1 python manage.py runserver`, potem `python tools/record_video.py`.

## 4. Plan wycofania
1. Kod: Coolify → zasób → **Deployments** → poprzedni deployment → **Redeploy**
   (albo revert PR na `main` — przywraca też nagrania MP3).
2. Migracje: nie dotyczy.
3. Zmienne środowiskowe: nie dotyczy.
4. Weryfikacja po wycofaniu: `/healthz`, logowanie, lista HU, `/?demo=1`.
