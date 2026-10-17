"""Ustawienia dla pytest (pyproject: DJANGO_SETTINGS_MODULE=config.settings.test).

Szybki hasher: PBKDF2 przy każdym create_user/login w setUp był głównym kosztem
testów. Tylko testy — nigdy nie importować tego modułu w dev/prod.
"""

from .dev import *  # noqa: F401,F403

PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

# Jak produkcja: DatabaseCache (tabelę w bazie testowej zakłada runner testów).
from .base import CACHES  # noqa: E402,F401
