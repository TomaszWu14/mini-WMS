"""tools/record_video.py: napisy SRT, rozdziały YouTube, plansze (bez nagrywania)."""

import importlib.util
import json
import re
from pathlib import Path

from django.test import SimpleTestCase

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "warehouse" / "static" / "demo" / "demo_script.json"
DEMO_JS = SCRIPT.with_name("demo.js")

_spec = importlib.util.spec_from_file_location(
    "record_video", ROOT / "tools" / "record_video.py"
)
assert _spec is not None and _spec.loader is not None
rec = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rec)

STEPS = [
    {
        "id": "krok01",
        "chapter": "Wstęp",
        "text": "Krótko. Dłuższe drugie zdanie.",
        "duration": 3.0,
    },
    {"id": "krok02", "text": "Bez rozdziału.", "duration": 9.0},
    {"id": "krok03", "chapter": "Dalej", "text": "Trzeci krok!", "duration": 12.0},
]
AT = {"krok01": 4.8, "krok02": 8.3, "krok03": 17.8}


class SrtTests(SimpleTestCase):
    def test_one_cue_per_sentence_within_clip(self):
        cues = rec.srt(STEPS, AT).strip().split("\n\n")
        self.assertEqual(len(cues), 4)
        self.assertEqual(
            cues[0].splitlines()[1:], ["00:00:04,800 --> 00:00:05,524", "Krótko."]
        )
        # Drugie zdanie kończy się razem z nagraniem kroku (4,8 + 3,0).
        self.assertIn("--> 00:00:07,800", cues[1])
        self.assertTrue(cues[3].startswith("4\n00:00:17,800 --> 00:00:29,800\n"))

    def test_timestamp_format(self):
        self.assertEqual(rec.ts_srt(3725.5), "01:02:05,500")
        self.assertEqual(rec.ts_short(125.9), "2:05")


class ChapterTests(SimpleTestCase):
    def test_first_at_zero_and_only_marked_steps(self):
        self.assertEqual(
            rec.chapters(STEPS, AT), [("0:00", "Wstęp"), ("0:17", "Dalej")]
        )

    def test_real_script_meets_youtube_rules(self):
        """≥ 3 rozdziały, pierwszy w kroku 1, każdy ≥ 10 s."""
        steps = json.loads(SCRIPT.read_text(encoding="utf-8"))["steps"]
        marked = [i for i, s in enumerate(steps) if s.get("chapter")]
        self.assertGreaterEqual(len(marked), 3)
        self.assertEqual(marked[0], 0)
        # Ostatni rozdział trwa jeszcze przez planszę końcową.
        bounds = [*marked, len(steps)]
        for a, b in zip(bounds, bounds[1:], strict=False):
            seconds = sum(rec.step_seconds(s["text"]) for s in steps[a:b])
            if b == len(steps):
                seconds += rec.OUTRO
            self.assertGreaterEqual(seconds, 10, steps[a]["chapter"])


class PacingTests(SimpleTestCase):
    def test_same_pace_as_tour_script(self):
        """Napisy filmu liczone tym samym tempem, co kroki w demo.js."""
        js = DEMO_JS.read_text(encoding="utf-8")
        self.assertIn(f"var MS_PER_CHAR = {rec.MS_PER_CHAR};", js)
        self.assertIn(f"var MIN_STEP_MS = {rec.MIN_STEP_MS};", js)

    def test_short_text_gets_minimum(self):
        self.assertEqual(rec.step_seconds("Krótko."), rec.MIN_STEP_MS / 1000)
        self.assertAlmostEqual(
            rec.step_seconds("x" * 200), 200 * rec.MS_PER_CHAR / 1000
        )


class CardTests(SimpleTestCase):
    def test_card_embeds_app_font_with_polish_range(self):
        page = rec.card_html("<p>Zażółć</p>")
        self.assertEqual(page.count("@font-face"), 2)
        self.assertIn("U+0100-024F", page)
        self.assertNotRegex(page, re.compile(r"https?://"))

    def test_description_links_demo_and_repo(self):
        md = rec.youtube_md([("0:00", "Wstęp"), ("0:21", "Pulpit")], 195)
        self.assertIn(rec.PUBLIC_DEMO, md)
        self.assertIn(rec.REPO, md)
        self.assertIn("0:21 Pulpit", md)
        self.assertIn("Długość: 3:15", md)
