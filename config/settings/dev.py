"""Ustawienia deweloperskie (DJANGO_DEBUG domyślnie włączony)."""

from .base import *  # noqa: F401,F403

DEBUG = True

# runserver to jeden proces — cache w pamięci wystarcza i nie wymaga
# `createcachetable`. Testy (test.py) wracają do DatabaseCache z base.py.
CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}

# W developmencie/testach akceptujemy dowolny host (runserver, test client).
if not ALLOWED_HOSTS:  # noqa: F405
    ALLOWED_HOSTS = ["*"]
