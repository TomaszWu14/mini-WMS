"""
Ustawienia wspólne (base) projektu mini-WMS.

Nakładki środowiskowe: `dev.py` i `prod.py`; wybór w `__init__.py` na podstawie
DJANGO_DEBUG. Konfiguracja sterowana zmiennymi środowiskowymi; baza domyślnie
SQLite — produkcyjnie wystarczy ustawić DATABASE_URL.
"""

import os
from pathlib import Path

# config/settings/base.py → repo root to trzy poziomy wyżej.
BASE_DIR = Path(__file__).resolve().parents[2]


def env_bool(name: str, default: bool = False) -> bool:
    return os.environ.get(name, str(default)).lower() in {"1", "true", "yes", "on"}


# Domyślnie klucz deweloperski; produkcja (prod.py) wymusza własny.
SECRET_KEY = os.environ.get(
    "DJANGO_SECRET_KEY",
    "django-insecure-dev-key-zmien-mnie-w-produkcji-0123456789",
)

DEBUG = env_bool("DJANGO_DEBUG", True)

# Hosty z env; wartości domyślne (bez wildcarda w produkcji) ustawiają nakładki.
ALLOWED_HOSTS = [
    h.strip()
    for h in os.environ.get("DJANGO_ALLOWED_HOSTS", "").split(",")
    if h.strip()
]

CSRF_TRUSTED_ORIGINS = [
    o.strip()
    for o in os.environ.get("DJANGO_CSRF_TRUSTED_ORIGINS", "").split(",")
    if o.strip()
]


# Tryb demo (publiczna instancja z danymi fikcyjnymi): baner, loginy demo na
# stronie logowania, limit prób logowania, maile tylko do konsoli.
DEMO_MODE = env_bool("DEMO_MODE", False)
if DEMO_MODE:
    EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"


# Application definition

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "warehouse",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    # WhiteNoise serwuje pliki statyczne bez osobnego serwera (nginx).
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "warehouse.context_processors.role_flags",
                "warehouse.demo.demo_context",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"


# Database — SQLite domyślnie, PostgreSQL przez DATABASE_URL.
def parse_database_url(url: str):
    from urllib.parse import unquote, urlparse

    parsed = urlparse(url)
    if parsed.scheme in {"postgres", "postgresql", "psql"}:
        return {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": unquote(parsed.path.lstrip("/")),
            "USER": unquote(parsed.username or ""),
            "PASSWORD": unquote(parsed.password or ""),
            "HOST": parsed.hostname or "",
            "PORT": str(parsed.port or ""),
        }
    if parsed.scheme == "sqlite":
        return {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": parsed.path or str(BASE_DIR / "db.sqlite3"),
        }
    raise ValueError(f"Nieobsługiwany DATABASE_URL: {url}")


_database_url = os.environ.get("DATABASE_URL")
if _database_url:
    DATABASES = {"default": parse_database_url(_database_url)}
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

# Trwałe połączenia (pooling) — bez tego każdy request otwiera nowe połączenie
# do Postgresa, co przy wielu workerach gunicorna obciąża bazę.
DATABASES["default"]["CONN_MAX_AGE"] = int(os.environ.get("DJANGO_CONN_MAX_AGE", "60"))


AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"
    },
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]


# Internacjonalizacja — interfejs po polsku.
LANGUAGE_CODE = "pl"
TIME_ZONE = os.environ.get("DJANGO_TIME_ZONE", "Europe/Warsaw")
USE_I18N = True
USE_TZ = True


# Pliki statyczne (serwowane przez WhiteNoise, z kompresją i cache-busting)
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    # Domyślnie zwykła pamięć (dev/testy nie wymagają manifestu collectstatic).
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}

# Hardening produkcyjny (statyki z manifestem, nagłówki, wymóg SECRET_KEY)
# jest w prod.py — tutaj tylko domyślne, bezpieczne dla developmentu wartości.

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Logowanie / wylogowanie
LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "dashboard"
LOGOUT_REDIRECT_URL = "login"

MESSAGE_STORAGE = "django.contrib.messages.storage.session.SessionStorage"

# Auto-wylogowanie po bezczynności — sesja wygasa po X sekundach,
# a każde żądanie odświeża licznik (idle timeout). Domyślnie 30 min.
SESSION_COOKIE_AGE = int(os.environ.get("DJANGO_SESSION_AGE", "1800"))
SESSION_SAVE_EVERY_REQUEST = True

# Limit rozmiaru żądania POST (poza plikami) — zgrany z limitem importu (5 MB).
DATA_UPLOAD_MAX_MEMORY_SIZE = int(
    os.environ.get("DJANGO_MAX_UPLOAD_BYTES", str(6 * 1024 * 1024))
)

# Logowanie do stdout — żeby Coolify/Docker zbierał błędy aplikacji.
# Produkcyjnie strukturalnie (JSON), w developmencie czytelnie (tekst).
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "json": {"()": "config.log.JsonFormatter"},
        "plain": {"format": "%(asctime)s %(levelname)s %(name)s %(message)s"},
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "plain" if DEBUG else "json",
        }
    },
    "root": {"handlers": ["console"], "level": "INFO"},
    "loggers": {
        "django.request": {
            "handlers": ["console"],
            "level": "ERROR",
            "propagate": False,
        },
    },
}
