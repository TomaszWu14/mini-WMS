"""US-008 / R6: hasła w argon2, podnoszenie starych hashy PBKDF2."""

from pathlib import Path

from django.contrib.auth.hashers import make_password
from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import SimpleTestCase, TestCase, override_settings

from config.settings import base

ROOT = Path(__file__).resolve().parents[1]


@override_settings(PASSWORD_HASHERS=base.PASSWORD_HASHERS)
class PasswordHasherTests(TestCase):
    def setUp(self):
        cache.clear()  # limit prób logowania

    def test_new_password_uses_argon2(self):
        user = User.objects.create_user("nowy", password="NoweHaslo123!")
        self.assertTrue(user.password.startswith("argon2$"))
        user.set_password("InneHaslo456!")
        user.save()
        self.assertTrue(user.password.startswith("argon2$"))

    def test_pbkdf2_hash_upgraded_on_login(self):
        user = User.objects.create_user("stary", password="x")
        legacy = make_password("StareHaslo123!", hasher="pbkdf2_sha256")
        User.objects.filter(pk=user.pk).update(password=legacy)
        resp = self.client.post(
            "/login/", {"username": "stary", "password": "StareHaslo123!"}
        )
        self.assertEqual(resp.status_code, 302)
        user.refresh_from_db()
        self.assertTrue(user.password.startswith("argon2$"))
        self.assertTrue(user.check_password("StareHaslo123!"))

    def test_wrong_password_does_not_upgrade(self):
        user = User.objects.create_user("stary2", password="x")
        legacy = make_password("StareHaslo123!", hasher="pbkdf2_sha256")
        User.objects.filter(pk=user.pk).update(password=legacy)
        self.client.post("/login/", {"username": "stary2", "password": "zle"})
        user.refresh_from_db()
        self.assertEqual(user.password, legacy)


class HasherConfigTests(SimpleTestCase):
    def test_argon2_first_in_base(self):
        self.assertEqual(
            base.PASSWORD_HASHERS[0], "django.contrib.auth.hashers.Argon2PasswordHasher"
        )

    def test_md5_only_in_test_settings(self):
        """Kryterium 3 (pitfalls/auth #11): szybki hasher tylko w test.py."""
        for name in ("base.py", "dev.py", "prod.py"):
            text = (ROOT / "config" / "settings" / name).read_text(encoding="utf-8")
            self.assertNotIn("MD5PasswordHasher", text, name)
        test_py = (ROOT / "config" / "settings" / "test.py").read_text(encoding="utf-8")
        self.assertIn("MD5PasswordHasher", test_py)

    def test_argon2_pinned_in_requirements(self):
        req = (ROOT / "requirements.txt").read_text(encoding="utf-8")
        self.assertRegex(req, r"(?m)^argon2-cffi==\d")
