"""Prezentacja z lektorem: scenariusz, generator nagrań, podpięcie skryptu."""

import importlib.util
import json
import shutil
import tempfile
from pathlib import Path
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import SimpleTestCase, TestCase
from django.urls import resolve

from .models import Profile, Role

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "warehouse" / "static" / "demo" / "demo_script.json"

_spec = importlib.util.spec_from_file_location(
    "generate_voiceover", ROOT / "tools" / "generate_voiceover.py"
)
assert _spec is not None and _spec.loader is not None
gen = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gen)


class DemoScriptTests(SimpleTestCase):
    def setUp(self):
        self.script = json.loads(SCRIPT.read_text(encoding="utf-8"))
        self.steps = self.script["steps"]

    def test_ids_unique_and_actions_known(self):
        ids = [s["id"] for s in self.steps]
        self.assertEqual(len(ids), len(set(ids)))
        for s in self.steps:
            self.assertIn(s["action"], {"navigate", "highlight", "click"}, s["id"])
            self.assertTrue(s["text"].strip(), s["id"])
            self.assertTrue(s["selector"], s["id"])

    def test_every_url_exists_in_app(self):
        for s in self.steps:
            # Resolver404 = scenariusz wskazuje nieistniejący ekran.
            if "url" in s:
                resolve(s["url"])

    def test_first_step_has_url_so_tour_can_start_anywhere(self):
        self.assertIn("url", self.steps[0])


class SpeechTextTests(SimpleTestCase):
    def test_longer_abbreviation_wins_and_words_stay_intact(self):
        words = {"miniWMS": "mini wu-em-es", "WMS": "wu-em-es", "HU": "ha-u"}
        self.assertEqual(
            gen.speech_text("miniWMS to WMS. Paleta HU, nie HUB.", words),
            "mini wu-em-es to wu-em-es. Paleta ha-u, nie HUB.",
        )


class GeneratorTests(SimpleTestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp)
        self.script_path = self.tmp / "demo_script.json"
        self.voice_path = self.tmp / "voice.json"
        self.audio = self.tmp / "audio"
        self._write_script(["Pierwszy krok.", "Drugi krok.", "Trzeci krok."])
        self.voice_path.write_text(
            json.dumps(
                {
                    "model_id": "m",
                    "output_format": "mp3_44100_128",
                    "voice_settings": {"stability": 0.5},
                }
            ),
            encoding="utf-8",
        )
        self.calls = []
        for target, value in (("SCRIPT", self.script_path), ("VOICE", self.voice_path)):
            p = patch.object(gen, target, value)
            p.start()
            self.addCleanup(p.stop)
        env = patch.dict(
            "os.environ", {"ELEVENLABS_API_KEY": "k", "ELEVENLABS_VOICE_ID": "v"}
        )
        env.start()
        self.addCleanup(env.stop)

    def _write_script(self, texts):
        steps = [
            {"id": f"krok0{i + 1}", "selector": "h1", "action": "highlight", "text": t}
            for i, t in enumerate(texts)
        ]
        self.script_path.write_text(
            json.dumps({"pronunciation": {}, "steps": steps}), encoding="utf-8"
        )

    def _synth(self, text, prev_text, next_text, voice, key, voice_id):
        self.calls.append((text, prev_text, next_text))
        return b"mp3"

    def _run(self, *argv):
        with patch("builtins.print"):
            return gen.run(list(argv), synth=self._synth, audio_dir=self.audio)

    def test_generates_all_then_nothing(self):
        self.assertEqual(self._run(), 0)
        self.assertEqual(len(self.calls), 3)
        # Sąsiedzi idą do API dla ciągłości intonacji.
        self.assertEqual(
            self.calls[1], ("Drugi krok.", "Pierwszy krok.", "Trzeci krok.")
        )
        manifest = json.loads(
            (self.audio / "manifest.json").read_text(encoding="utf-8")
        )
        self.assertEqual(sorted(manifest), ["krok01", "krok02", "krok03"])

        self.calls.clear()
        self._run()
        self.assertEqual(self.calls, [])

    def test_changing_one_text_regenerates_only_that_step(self):
        self._run()
        old = json.loads((self.audio / "manifest.json").read_text(encoding="utf-8"))
        self.calls.clear()

        self._write_script(
            ["Pierwszy krok.", "Drugi krok, poprawiony.", "Trzeci krok."]
        )
        self._run()

        self.assertEqual([c[0] for c in self.calls], ["Drugi krok, poprawiony."])
        new = json.loads((self.audio / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(new["krok01"], old["krok01"])
        self.assertNotEqual(new["krok02"], old["krok02"])
        self.assertFalse((self.audio / old["krok02"]).exists())  # stara wersja usunięta
        self.assertEqual(len(list(self.audio.glob("*.mp3"))), 3)

    def test_dry_run_writes_nothing(self):
        self._run("--dry-run")
        self.assertEqual(self.calls, [])
        self.assertFalse(self.audio.exists())

    def test_step_flag_forces_single_step(self):
        self._run()
        self.calls.clear()
        self._run("--step", "krok03")
        self.assertEqual([c[0] for c in self.calls], ["Trzeci krok."])

    def test_voice_settings_change_regenerates_everything(self):
        self._run()
        self.calls.clear()
        voice = json.loads(self.voice_path.read_text(encoding="utf-8"))
        voice["voice_settings"]["stability"] = 0.6
        self.voice_path.write_text(json.dumps(voice), encoding="utf-8")
        self._run()
        self.assertEqual(len(self.calls), 3)


class DemoScriptIncludedTests(TestCase):
    def test_pages_load_player_script_but_nothing_else_changes(self):
        user = User.objects.create_user("u", password="x")
        Profile.objects.filter(user=user).update(role=Role.OPERATOR)
        self.client.login(username="u", password="x")
        for url in ("/", "/skaner/", "/login/"):
            if url == "/login/":
                self.client.logout()
            resp = self.client.get(url)
            self.assertContains(resp, "demo/demo.js", msg_prefix=url)
            # Arkusz i pasek dokłada dopiero JS przy ?demo=1 / trwającej prezentacji.
            self.assertNotContains(resp, "demo.css", msg_prefix=url)
            self.assertNotContains(resp, "demo-bar", msg_prefix=url)
