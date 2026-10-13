"""Prezentacja z napisami: scenariusz i podpięcie skryptu."""

import json
from pathlib import Path

from django.contrib.auth.models import User
from django.test import SimpleTestCase, TestCase
from django.urls import resolve

from .models import Profile, Role

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "warehouse" / "static" / "demo" / "demo_script.json"


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
