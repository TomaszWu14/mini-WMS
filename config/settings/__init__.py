"""Wybór nakładki ustawień na podstawie DJANGO_DEBUG.

DJANGO_SETTINGS_MODULE pozostaje `config.settings` (bez zmian w manage.py/wsgi/
Dockerze/CI). Domyślnie (brak zmiennej) → development.
"""

import os

_DEBUG = os.environ.get("DJANGO_DEBUG", "True").lower() in {"1", "true", "yes", "on"}

if _DEBUG:
    from .dev import *  # noqa: F401,F403
else:
    from .prod import *  # noqa: F401,F403
