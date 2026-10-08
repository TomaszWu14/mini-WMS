"""Ustawienia deweloperskie (DJANGO_DEBUG domyślnie włączony)."""

from .base import *  # noqa: F401,F403

DEBUG = True

# W developmencie/testach akceptujemy dowolny host (runserver, test client).
if not ALLOWED_HOSTS:  # noqa: F405
    ALLOWED_HOSTS = ["*"]
