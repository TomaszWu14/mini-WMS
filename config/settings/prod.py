"""Ustawienia produkcyjne (DJANGO_DEBUG=0). Hardening + wymogi środowiska."""

import os

from django.core.exceptions import ImproperlyConfigured

from .base import *  # noqa: F401,F403

DEBUG = False

# --- SECRET_KEY: fail-fast, nie pozwól wystartować z kluczem deweloperskim ---
if not SECRET_KEY or SECRET_KEY.startswith("django-insecure-"):  # noqa: F405
    raise ImproperlyConfigured(
        "Ustaw DJANGO_SECRET_KEY (silny, losowy) w środowisku produkcyjnym."
    )

# --- ALLOWED_HOSTS: bez wildcarda w produkcji; sensowny host domyślny ---
if not ALLOWED_HOSTS:  # noqa: F405
    ALLOWED_HOSTS = ["miniwms.example.com"]
# localhost/127.0.0.1 zawsze — healthcheck kontenera odpytuje /healthz lokalnie.
for _h in ("localhost", "127.0.0.1"):
    if _h not in ALLOWED_HOSTS:  # noqa: F405
        ALLOWED_HOSTS.append(_h)  # noqa: F405

# --- Statyki: manifest + kompresja (cache-busting) ---
STORAGES["staticfiles"]["BACKEND"] = (  # noqa: F405
    "whitenoise.storage.CompressedManifestStaticFilesStorage"
)

# --- Nagłówki i transport (za reverse-proxy: HTTPS po X-Forwarded-Proto) ---
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SESSION_COOKIE_SECURE = env_bool("DJANGO_SECURE_COOKIES", True)  # noqa: F405
CSRF_COOKIE_SECURE = env_bool("DJANGO_SECURE_COOKIES", True)  # noqa: F405
SECURE_SSL_REDIRECT = env_bool("DJANGO_SSL_REDIRECT", True)  # noqa: F405
# Healthcheck kontenera uderza po HTTP w /healthz (bez proxy/HTTPS) — nie może
# dostać 301 na HTTPS, bo wtedy kontener nigdy nie jest „healthy".
SECURE_REDIRECT_EXEMPT = [r"^healthz$"]
SECURE_HSTS_SECONDS = int(os.environ.get("DJANGO_HSTS_SECONDS", "2592000"))
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
