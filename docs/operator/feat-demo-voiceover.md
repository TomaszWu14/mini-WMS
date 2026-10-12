# feat/demo-voiceover — instrukcja dla operatora

| | |
|---|---|
| Branch | `feat/demo-voiceover` |
| PR | jeszcze nie utworzony |
| Data | 2026-10-12 |
| Ryzyko | niskie — tylko frontend (skrypt ładowany na każdej stronie, aktywny wyłącznie z `?demo=1`); bez zmian w logice i danych |

## 1. Co zmieniono
- Prezentacja z lektorem: dopisanie `?demo=1` do adresu (np. `/?demo=1`) pokazuje przycisk
  „Rozpocznij prezentację”. Prezentacja sama przechodzi przez 14 ekranów (pulpit, przyjęcie,
  palety, skaner, wydanie FEFO, spis, ruchy, raporty), podświetla omawiany element, pokazuje
  napisy i czyta tekst. Pasek na dole: start/pauza, poprzedni/następny, wycisz, głośność,
  postęp, zakończ.
- Bez nagrań ElevenLabs (dziś ich brak) tekst czyta głos przeglądarki (pl-PL).
- Technicznie: `tools/generate_voiceover.py` generuje nagrania MP3 (ElevenLabs, ustawienia w
  `config/voice.json`, cache po hashu tekstu — zmiana jednego kroku = jeden nowy plik).

## 2. Kroki do ręcznego sprawdzenia

| # | Konto (rola) | Gdzie | Co zrobić | Oczekiwany wynik |
|---|---|---|---|---|
| 1 | `demo_operator` (Operator) | `/?demo=1` | kliknąć „Rozpocznij prezentację” | lektor czyta krok 1, nagłówek podświetlony, napisy na dole |
| 2 | j.w. | pasek prezentacji | ⏭ kilka razy | przejście na kolejne ekrany (przyjęcie, palety…), bez dwóch nagrań naraz |
| 3 | j.w. | pasek | ✕ | pasek znika, aplikacja jak zwykle |
| 4 | dowolne | `/` bez `?demo=1` | otworzyć | brak paska i przycisku — strona jak przed zmianą |

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
| `ELEVENLABS_API_KEY`, `ELEVENLABS_VOICE_ID` | nowe — **tylko lokalnie** przy generowaniu nagrań, nie w Coolify | — | ☐ nie dotyczy |

Zaktualizowano też: `.env.example` — nie dotyczy (zmienne tylko dla narzędzia lokalnego),
`.env.docker.example` — nie dotyczy, `COOLIFY.md` §6 — nie dotyczy.

### Przed i po deployu
- ☐ CI zielone na PR (`ci.yml`, `security.yml`)
- ☐ backup bazy prod sprzed deployu — nie dotyczy (brak migracji)
- ☐ po deployu: `/healthz` zwraca `{"status": "ok"}`
- ☐ kroki z sekcji 2 wykonane na prod

### Jak zmienić tekst i przegenerować głos
1. Popraw `text` kroku w `warehouse/static/demo/demo_script.json` (napisy = ten tekst;
   trudne skróty dopisz do słownika `pronunciation`).
2. Ustaw `ELEVENLABS_API_KEY` i `ELEVENLABS_VOICE_ID` w swojej powłoce.
3. `python tools/generate_voiceover.py --dry-run` — pokaże, które kroki się zmienią.
4. `python tools/generate_voiceover.py` — wygeneruje tylko zmienione (jeden krok:
   `--step krok03`). Zacommituj `warehouse/static/demo/audio/`.

## 4. Plan wycofania
1. Kod: Coolify → zasób → **Deployments** → poprzedni deployment → **Redeploy**
   (albo revert PR na `main`).
2. Migracje: nie dotyczy.
3. Zmienne środowiskowe: nie dotyczy.
4. Weryfikacja po wycofaniu: `/healthz`, logowanie, lista HU.
