"""Generuje nagrania lektora ElevenLabs dla prezentacji demo (?demo=1).

    python tools/generate_voiceover.py              # tylko zmienione kroki
    python tools/generate_voiceover.py --step krok03  # wymuś jeden krok
    python tools/generate_voiceover.py --dry-run    # pokaż, co by się zmieniło

Wymaga zmiennych ELEVENLABS_API_KEY i ELEVENLABS_VOICE_ID (nigdy w repo).
Ustawienia głosu: config/voice.json. Scenariusz: warehouse/static/demo/demo_script.json.

Plik nagrania = <id>-<hash>.mp3, hash z tekstu dla lektora i ustawień głosu —
zmiana tekstu jednego kroku generuje tylko ten jeden plik. Tekst sąsiednich
kroków (previous_text/next_text) idzie do API dla ciągłości intonacji, ale nie
wchodzi do hasha. Odtwarzacz czyta mapę id → plik z audio/manifest.json.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "warehouse" / "static" / "demo" / "demo_script.json"
VOICE = ROOT / "config" / "voice.json"
AUDIO_DIR = ROOT / "warehouse" / "static" / "demo" / "audio"
API = "https://api.elevenlabs.io/v1/text-to-speech/{voice_id}?output_format={fmt}"


def speech_text(text: str, pronunciation: dict[str, str]) -> str:
    """Tekst dla lektora: skróty podmienione całymi słowami, dłuższe najpierw
    (inaczej „WMS” zjadłby końcówkę „miniWMS”)."""
    for word in sorted(pronunciation, key=len, reverse=True):
        text = re.sub(rf"(?<!\w){re.escape(word)}(?!\w)", pronunciation[word], text)
    return text


def clip_name(step_id: str, spoken: str, voice: dict) -> str:
    payload = json.dumps([spoken, voice], sort_keys=True, ensure_ascii=False)
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:10]
    return f"{step_id}-{digest}.mp3"


def plan(script: dict, voice: dict, audio_dir: Path, force: str | None = None):
    """Lista (krok, tekst dla lektora, sąsiedzi, plik, czy generować)."""
    steps = script["steps"]
    spoken = [speech_text(s["text"], script.get("pronunciation", {})) for s in steps]
    out = []
    for i, step in enumerate(steps):
        name = clip_name(step["id"], spoken[i], voice)
        todo = step["id"] == force if force else not (audio_dir / name).exists()
        prev_text = spoken[i - 1] if i > 0 else ""
        next_text = spoken[i + 1] if i + 1 < len(steps) else ""
        out.append((step, spoken[i], prev_text, next_text, name, todo))
    return out


def synthesize(text, prev_text, next_text, voice, api_key, voice_id) -> bytes:
    body = {
        "text": text,
        "model_id": voice["model_id"],
        "voice_settings": voice["voice_settings"],
        "previous_text": prev_text or None,
        "next_text": next_text or None,
    }
    if "seed" in voice:
        body["seed"] = voice["seed"]
    req = urllib.request.Request(
        API.format(voice_id=voice_id, fmt=voice["output_format"]),
        data=json.dumps(body).encode("utf-8"),
        headers={"xi-api-key": api_key, "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:  # noqa: S310 (stały https)
            return resp.read()
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:300]
        raise SystemExit(f"ElevenLabs {exc.code}: {detail}") from exc


def run(argv=None, *, synth=synthesize, audio_dir: Path = AUDIO_DIR) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--step", help="przegeneruj tylko ten krok (np. krok03)")
    parser.add_argument("--dry-run", action="store_true", help="tylko pokaż zmiany")
    args = parser.parse_args(argv)

    script = json.loads(SCRIPT.read_text(encoding="utf-8"))
    voice = json.loads(VOICE.read_text(encoding="utf-8"))
    ids = {s["id"] for s in script["steps"]}
    if args.step and args.step not in ids:
        parser.error(f"nie ma kroku {args.step}; dostępne: {', '.join(sorted(ids))}")

    items = plan(script, voice, audio_dir, force=args.step)
    todo = [it for it in items if it[5]]
    for step, *_rest, name, _ in todo:
        print(f"{'[dry-run] ' if args.dry_run else ''}generuję {step['id']} → {name}")
    if not todo:
        print("Wszystkie nagrania aktualne.")
    if args.dry_run:
        return 0

    api_key = os.environ.get("ELEVENLABS_API_KEY")
    voice_id = os.environ.get("ELEVENLABS_VOICE_ID")
    if todo and not (api_key and voice_id):
        print("Ustaw ELEVENLABS_API_KEY i ELEVENLABS_VOICE_ID.", file=sys.stderr)
        return 2

    audio_dir.mkdir(parents=True, exist_ok=True)
    for _step, spoken, prev_text, next_text, name, _ in todo:
        audio = synth(spoken, prev_text, next_text, voice, api_key, voice_id)
        (audio_dir / name).write_bytes(audio)

    # Manifest + sprzątanie starych wersji nagrań (inny hash tego samego kroku).
    manifest = {
        step["id"]: name
        for step, *_rest, name, _ in items
        if (audio_dir / name).exists()
    }
    (audio_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    keep = set(manifest.values())
    for old in audio_dir.glob("*.mp3"):
        if old.name not in keep:
            old.unlink()
            print(f"usunięto stare nagranie {old.name}")
    return 0


if __name__ == "__main__":
    sys.exit(run())
