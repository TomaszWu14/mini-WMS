"""Nagrywa prezentację z lektorem (?demo=1) jako film na YouTube.

    # 1. aplikacja w trybie demo, ze świeżymi danymi:
    DEMO_MODE=1 python manage.py seed_demo --reset
    DEMO_MODE=1 python manage.py runserver
    # 2. nagranie (Chromium + ffmpeg/ffprobe w PATH):
    python tools/record_video.py
    python tools/record_video.py --chromium /opt/pw-browsers/chromium

Wynik w docs/video/youtube/: film MP4 (1920×1080, H.264 + AAC), napisy SRT,
miniatura PNG 1280×720 i youtube.md (tytuł, opis z rozdziałami, tagi).

Jak to działa: Playwright odtwarza prezentację w przeglądarce i nagrywa
obraz; headless Chromium nie nagrywa dźwięku, więc skrypt notuje moment
startu każdego nagrania (podmienione HTMLMediaElement.play) i ffmpeg nakłada
te same pliki MP3 w tych miejscach. Rozdziały = kroki z polem "chapter"
w demo_script.json. Plansza początkowa i końcowa to HTML ze stylami aplikacji.
"""

from __future__ import annotations

import argparse
import base64
import html
import json
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "warehouse" / "static" / "demo"
OUT = ROOT / "docs" / "video" / "youtube"

PUBLIC_DEMO = "https://miniwms.twapp.pl/demo/"
REPO = "https://github.com/TomaszWu14/miniWMS-public"
W, H = 1920, 1080
FPS = 30
INTRO = 4.0  # s, plansza tytułowa
OUTRO = 7.0  # s, plansza końcowa
LEAD = 0.8  # s obrazu przed pierwszym słowem lektora
TAIL = 2.0  # s po ostatnim nagraniu

# Pierwsze wywołanie play() dla pliku z audio/ → window.__demoClip(src, ms).
HOOK = """
(() => {
  const play = HTMLMediaElement.prototype.play;
  HTMLMediaElement.prototype.play = function () {
    const src = this.currentSrc || this.src || "";
    if (src.includes("/demo/audio/") && window.__demoClip) window.__demoClip(src, Date.now());
    return play.apply(this, arguments);
  };
})();
"""


# --- Dane ---------------------------------------------------------------------


def load_steps() -> list[dict]:
    script = json.loads((DEMO / "demo_script.json").read_text(encoding="utf-8"))
    manifest = json.loads(
        (DEMO / "audio" / "manifest.json").read_text(encoding="utf-8")
    )
    steps = script["steps"]
    for step in steps:
        if step["id"] not in manifest:
            sys.exit(
                f"Brak nagrania dla {step['id']} — uruchom tools/generate_voiceover.py"
            )
        step["clip"] = DEMO / "audio" / manifest[step["id"]]
        step["duration"] = probe_duration(step["clip"])
    return steps


def probe_duration(path: Path) -> float:
    out = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "csv=p=0",
            str(path),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    return float(out.stdout.strip())


# --- Plansze (HTML → PNG) -----------------------------------------------------

CARD_CSS = """
body { margin: 0; font-family: "Manrope", system-ui, sans-serif; }
.card { width: 100vw; height: 100vh; box-sizing: border-box; display: flex;
  flex-direction: column; justify-content: center; padding: 0 9vw;
  background: radial-gradient(circle at 85% 15%, #2e8b66 0, #14533f 45%, #0b3427 100%);
  color: #fff; }
.brand { display: flex; align-items: center; gap: 2.2vw; }
.brand svg { width: 9vw; height: 9vw; }
.name { font-size: 7.5vw; font-weight: 800; letter-spacing: -0.03em; }
.name span { color: #9fe0bf; }
.lead { font-size: 2.6vw; font-weight: 600; margin: 2.5vw 0 0; max-width: 70vw; line-height: 1.3; }
.meta { font-size: 1.5vw; color: #bfe9d3; margin-top: 4vw; letter-spacing: 0.04em; }
.cta { font-size: 2.3vw; margin: 1.2vw 0; font-weight: 600; }
.cta b { color: #9fe0bf; }
.shot { position: absolute; right: -7vw; top: 50%; width: 54vw; transform: translateY(-50%)
  perspective(1600px) rotateY(-14deg); border-radius: 1.2vw; box-shadow: 0 3vw 6vw rgba(0,0,0,.45); }
.thumb > :not(.shot) { position: relative; z-index: 1; max-width: 44vw; }
.thumb .brand svg { width: 7vw; height: 7vw; }
.thumb .name { font-size: 7vw; }
.thumb .lead { font-size: 4.2vw; font-weight: 800; line-height: 1.15; }
"""

BRAND_SVG = (
    '<svg viewBox="0 0 40 40" aria-hidden="true">'
    '<rect x="4" y="29" width="32" height="3" rx="1" fill="#9fe0bf"/>'
    '<rect x="6" y="32" width="4" height="3" fill="#9fe0bf"/>'
    '<rect x="18" y="32" width="4" height="3" fill="#9fe0bf"/>'
    '<rect x="30" y="32" width="4" height="3" fill="#9fe0bf"/>'
    '<rect x="6" y="17" width="14" height="12" rx="2" fill="#2e8b66"/>'
    '<rect x="21" y="17" width="13" height="12" rx="2" fill="#9fe0bf"/>'
    '<rect x="12" y="5" width="15" height="12" rx="2" fill="#ffffff"/></svg>'
)


def font_css() -> str:
    """Manrope aplikacji wprost w CSS (strona z file:// nie pobierze fontu przez HTTP)."""
    fonts = ROOT / "warehouse" / "static" / "warehouse" / "fonts"
    # Dwa pliki = dwa zakresy znaków (polskie litery są w latin-ext).
    ranges = {
        "latin-ext": "U+0100-024F, U+1E00-1EFF",
        "latin": "U+0000-00FF, U+2000-206F, U+20AC, U+2122, U+2190-2193",
    }
    rules = []
    for subset, unicode_range in ranges.items():
        woff = fonts / f"manrope-{subset}-wght-normal.woff2"
        data = base64.b64encode(woff.read_bytes()).decode("ascii")
        rules.append(
            '@font-face { font-family: "Manrope"; font-weight: 200 800; '
            f'src: url(data:font/woff2;base64,{data}) format("woff2"); '
            f"unicode-range: {unicode_range}; }}"
        )
    return "\n".join(rules)


def card_html(body: str, cls: str = "") -> str:
    return (
        f'<!doctype html><html lang="pl"><head><meta charset="utf-8">'
        f"<style>{font_css()}{CARD_CSS}</style></head>"
        f'<body><div class="card {cls}">{body}</div></body></html>'
    )


def brand() -> str:
    return f'<div class="brand">{BRAND_SVG}<div class="name"><span>mini</span>WMS</div></div>'


def render_cards(browser, shot: Path, tmp: Path) -> dict[str, Path]:
    intro = brand() + (
        '<p class="lead">Lekki system magazynowy dla małego magazynu — '
        "od przyjęcia palety do wydania.</p>"
        '<p class="meta">PREZENTACJA Z LEKTOREM · 3 MINUTY · DANE FIKCYJNE</p>'
    )
    demo_host = html.escape(PUBLIC_DEMO.removeprefix("https://"))
    repo_host = html.escape(REPO.removeprefix("https://"))
    outro = brand() + (
        f'<p class="cta">Wypróbuj bez logowania: <b>{demo_host}</b></p>'
        f'<p class="cta">Kod źródłowy: <b>{repo_host}</b></p>'
        '<p class="meta">DJANGO · POSTGRESQL · SKANER QR W PRZEGLĄDARCE</p>'
    )
    thumb = (
        f'<img class="shot" src="{shot.as_uri()}">'
        + brand()
        + '<p class="lead">Magazyn palet bez papieru</p>'
        '<p class="meta">DJANGO · SKANER QR · FEFO</p>'
    )
    cards = {
        "intro": (intro, "", W, H),
        "outro": (outro, "", W, H),
        "thumbnail": (thumb, "thumb", 1280, 720),
    }
    out = {}
    page = browser.new_page(viewport={"width": W, "height": H})
    for name, (body, cls, width, height) in cards.items():
        page.set_viewport_size({"width": width, "height": height})
        # file:// (zrzut pulpitu) wymaga strony z file:// — zapis i goto.
        src = tmp / f"{name}.html"
        src.write_text(card_html(body, cls), encoding="utf-8")
        page.goto(src.as_uri())
        page.evaluate("document.fonts.ready")
        out[name] = tmp / f"{name}.png"
        page.screenshot(path=str(out[name]))
    page.close()
    return out


# --- Nagranie -------------------------------------------------------------------


def record(browser, base_url: str, steps: list[dict], tmp: Path):
    """Nagrywa prezentację; zwraca (plik webm, {id kroku: sekunda w nagraniu})."""
    context = browser.new_context(
        viewport={"width": W, "height": H},
        locale="pl-PL",
        record_video_dir=str(tmp / "raw"),
        record_video_size={"width": W, "height": H},
    )
    starts: dict[str, float] = {}
    by_file = {step["clip"].name: step["id"] for step in steps}

    def on_clip(_source, src: str, ms: float) -> None:
        step_id = by_file.get(src.rsplit("/", 1)[-1])
        if step_id and step_id not in starts:
            starts[step_id] = ms / 1000 - t0
            print(f"  {step_id} @ {starts[step_id]:6.2f} s")

    context.expose_binding("__demoClip", on_clip)
    context.add_init_script(HOOK)
    page = context.new_page()
    t0 = time.time()  # nagranie startuje razem ze stroną
    page.goto(f"{base_url}/demo/")
    hide_welcome(page)
    page.goto(f"{base_url}/?demo=1")
    page.click(".demo-start-btn")
    total = sum(s["duration"] for s in steps)
    page.wait_for_function(
        "document.querySelector('.demo-caption')?.textContent.startsWith('Koniec')",
        timeout=(total + 120) * 1000,
    )
    page.wait_for_timeout(TAIL * 1000)
    video = page.video.path()
    context.close()
    missing = [s["id"] for s in steps if s["id"] not in starts]
    if missing:
        sys.exit(f"Nie zarejestrowano startu nagrań: {missing}")
    return Path(video), starts


def hide_welcome(page) -> None:
    """Bez panelu „Od czego zacząć” pulpit jest czytelniejszy (ukryty do końca sesji)."""
    hide = "form[action$='/powitanie/ukryj/']"
    if page.locator(hide).count():
        with page.expect_navigation():
            page.evaluate(f'document.querySelector("{hide}").submit()')


def dashboard_shot(browser, base_url: str, tmp: Path) -> Path:
    context = browser.new_context(
        viewport={"width": 1440, "height": 900}, device_scale_factor=2, locale="pl-PL"
    )
    page = context.new_page()
    page.goto(f"{base_url}/demo/")
    hide_welcome(page)
    page.goto(f"{base_url}/")  # bez ?demo=1 — sam pulpit
    path = tmp / "dashboard.png"
    page.screenshot(path=str(path))
    context.close()
    return path


# --- Montaż ---------------------------------------------------------------------


def compose(
    video: Path, cards: dict[str, Path], steps, starts, out: Path
) -> dict[str, float]:
    """Plansza + nagranie (przycięte) + plansza, z lektorem. Zwraca starty kroków w filmie."""
    cut_from = starts[steps[0]["id"]] - LEAD
    last = steps[-1]
    cut_to = starts[last["id"]] + last["duration"] + TAIL
    main = cut_to - cut_from
    total = INTRO + main + OUTRO
    at = {s["id"]: INTRO + starts[s["id"]] - cut_from for s in steps}

    inputs = ["-loop", "1", "-t", str(INTRO), "-i", str(cards["intro"])]
    inputs += ["-i", str(video)]
    inputs += ["-loop", "1", "-t", str(OUTRO), "-i", str(cards["outro"])]
    for s in steps:
        inputs += ["-i", str(s["clip"])]

    norm = f"scale={W}:{H},fps={FPS},format=yuv420p,setsar=1"
    parts = [
        f"[0:v]{norm},fade=out:st={INTRO - 0.4}:d=0.4[v0]",
        f"[1:v]trim=start={cut_from:.3f}:end={cut_to:.3f},setpts=PTS-STARTPTS,{norm},"
        f"fade=in:st=0:d=0.4,fade=out:st={main - 0.5:.3f}:d=0.5[v1]",
        f"[2:v]{norm},fade=in:st=0:d=0.5[v2]",
        "[v0][v1][v2]concat=n=3:v=1:a=0[v]",
    ]
    labels = []
    for i, s in enumerate(steps):
        ms = round(at[s["id"]] * 1000)
        parts.append(f"[{3 + i}:a]aresample=48000,adelay={ms}|{ms}[a{i}]")
        labels.append(f"[a{i}]")
    parts.append(
        f"{''.join(labels)}amix=inputs={len(labels)}:normalize=0:duration=longest,"
        f"apad,atrim=0:{total:.3f}[a]"
    )
    cmd = ["ffmpeg", "-y", "-v", "error", *inputs, "-filter_complex", ";".join(parts)]
    cmd += ["-map", "[v]", "-map", "[a]", "-t", f"{total:.3f}"]
    cmd += ["-c:v", "libx264", "-preset", "slow", "-crf", "20", "-pix_fmt", "yuv420p"]
    cmd += [
        "-c:a",
        "aac",
        "-b:a",
        "160k",
        "-ar",
        "48000",
        "-movflags",
        "+faststart",
        str(out),
    ]
    subprocess.run(cmd, check=True)
    return at


# --- Napisy, rozdziały, opis ----------------------------------------------------


def ts_srt(sec: float) -> str:
    ms = round(sec * 1000)
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def ts_short(sec: float) -> str:
    m, s = divmod(int(sec), 60)
    return f"{m}:{s:02d}"


def srt(steps, at: dict[str, float]) -> str:
    """Jedna pozycja na zdanie; czas zdania proporcjonalny do jego długości."""
    cues = []
    for step in steps:
        sentences = [x for x in re.split(r"(?<=[.!?])\s+", step["text"].strip()) if x]
        chars = sum(len(x) for x in sentences)
        t = at[step["id"]]
        for sentence in sentences:
            dur = step["duration"] * len(sentence) / chars
            cues.append((t, t + dur, sentence))
            t += dur
    return "\n".join(
        f"{n}\n{ts_srt(a)} --> {ts_srt(b)}\n{text}\n"
        for n, (a, b, text) in enumerate(cues, 1)
    )


def chapters(steps, at: dict[str, float]) -> list[tuple[str, str]]:
    """YouTube: pierwszy rozdział od 0:00, każdy ≥ 10 s."""
    out = []
    for i, step in enumerate(s for s in steps if s.get("chapter")):
        start = 0.0 if i == 0 else max(0.0, at[step["id"]] - 0.5)
        out.append((ts_short(start), step["chapter"]))
    return out


def youtube_md(chaps, duration: float) -> str:
    chapter_lines = "\n".join(f"{t} {title}" for t, title in chaps)
    return f"""# Film na YouTube — dane do wgrania

Wygenerowane przez `tools/record_video.py`. Długość: {ts_short(duration)}.

| Pole | Wartość |
|---|---|
| Plik | `miniwms-youtube.mp4` |
| Miniatura | `thumbnail.png` (1280×720) |
| Napisy | `miniwms-youtube.pl.srt` — język: polski |
| Język filmu | polski |
| Kategoria | Nauka i technika |
| Dla dzieci | Nie |
| Widoczność | Publiczny (albo Niepubliczny — tylko z linkiem) |

## Tytuł

miniWMS — system magazynowy w Django w 3 minuty (przyjęcie, skaner QR, FEFO)

## Opis

```
miniWMS to lekki system magazynowy dla małego magazynu: przyjęcie dostawy,
palety z etykietą QR, rozmieszczanie skanerem w telefonie, wydanie według FEFO,
spis z natury i pełna historia ruchów. Projekt portfolio — Django 5.2, PostgreSQL.

▶ Wypróbuj bez logowania: {PUBLIC_DEMO}
💻 Kod źródłowy: {REPO}

Rozdziały:
{chapter_lines}

Dane w filmie i w demo są fikcyjne.
```

## Tagi

WMS, system magazynowy, Django, Python, magazyn, skaner QR, FEFO, logistyka, portfolio

## Po wgraniu

1. W README podmień link „Prezentacja działania” na adres filmu na YouTube.
2. Sprawdź, że rozdziały pojawiły się na osi czasu (YouTube wymaga min. 3 rozdziałów po 10 s).
"""


# --- Główna -------------------------------------------------------------------


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument(
        "--chromium", help="ścieżka do Chromium (domyślnie z Playwright)"
    )
    parser.add_argument("--out", type=Path, default=OUT)
    args = parser.parse_args(argv)
    base_url = args.base_url.rstrip("/")

    for tool in ("ffmpeg", "ffprobe"):
        if not shutil.which(tool):
            sys.exit(f"Brak {tool} w PATH.")
    from playwright.sync_api import sync_playwright  # tylko dev (requirements-dev.txt)

    steps = load_steps()
    args.out.mkdir(parents=True, exist_ok=True)
    mp4 = args.out / "miniwms-youtube.mp4"
    with tempfile.TemporaryDirectory() as d, sync_playwright() as p:
        tmp = Path(d)
        browser = p.chromium.launch(
            executable_path=args.chromium,
            args=["--autoplay-policy=no-user-gesture-required"],
        )
        print("Zrzut pulpitu i plansze…")
        shot = dashboard_shot(browser, base_url, tmp)
        cards = render_cards(browser, shot, tmp)
        print("Nagrywanie prezentacji (w czasie rzeczywistym, ok. 3 min)…")
        video, starts = record(browser, base_url, steps, tmp)
        browser.close()
        print("Montaż (ffmpeg)…")
        at = compose(video, cards, steps, starts, mp4)
        shutil.copy(cards["thumbnail"], args.out / "thumbnail.png")

    duration = probe_duration(mp4)
    (args.out / "miniwms-youtube.pl.srt").write_text(srt(steps, at), encoding="utf-8")
    (args.out / "youtube.md").write_text(
        youtube_md(chapters(steps, at), duration), encoding="utf-8"
    )
    size = mp4.stat().st_size / 1_000_000
    print(f"Gotowe: {mp4.relative_to(ROOT)} ({ts_short(duration)}, {size:.1f} MB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
