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
# Konta demo są publiczne z założenia (README, ekran logowania) — env tylko po to,
# by hasło i konto „Wejdź jako demo” dało się zmienić bez zmiany kodu.
DEMO_USER = os.environ.get("DEMO_USER", "demo_operator")
DEMO_PASSWORD = os.environ.get("DEMO_PASSWORD", "demo1234")
DEMO_IMPORT_MAX_ROWS = 100  # RR-31: mniejsze operacje w demo
# US-005 / SEC-036: dziennik logowań starszy niż tyle dni usuwa `purge_login_events`
# (decyzja PO 2026-10-16, Z-09).
LOGIN_EVENT_RETENTION_DAYS = 90
# US-022: dziennik audytowy (zmiany kont, odmowy) — decyzja PO 2026-10-17 (Z-42).
AUDIT_EVENT_RETENTION_DAYS = 365
# US-004 / R4: limity każdego importu CSV/XLSX poza demo (Z-23: L_WIERSZE, L_ROZP).
IMPORT_MAX_ROWS = 10_000
# Suma rozmiarów plików w archiwum XLSX po rozpakowaniu (zip bomb).
IMPORT_MAX_UNCOMPRESSED_BYTES = 50 * 1024 * 1024

# Liczba zaufanych proxy przed aplikacją (Traefik/Caddy = 1). 0 = nagłówek
# X-Forwarded-For jest ignorowany, IP klienta to REMOTE_ADDR. Od tego zależy
# limit prób logowania i adres w dzienniku logowań.
TRUSTED_PROXY_COUNT = int(os.environ.get("DJANGO_TRUSTED_PROXY_COUNT", "0"))


# Application definition

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django_otp",
    "django_otp.plugins.otp_totp",
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
    # US-022: kto zmienia konto — dla sygnałów dziennika audytowego.
    "warehouse.audit.AuditActorMiddleware",
    # US-010: sesja zna stan 2FA; konto z TOTP po samym haśle → ekran kodu.
    "django_otp.middleware.OTPMiddleware",
    "warehouse.two_factor.TwoFactorRequiredMiddleware",
    # US-016: limit POST zalogowanych w DEMO_MODE (poza demo — przepuszcza).
    "warehouse.demo.DemoWriteRateLimitMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    # US-011: CSP z nonce i Permissions-Policy (ADR-0004).
    "warehouse.csp.SecurityHeadersMiddleware",
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
                "warehouse.csp.csp_context",
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


# US-009 / ADR-0002: cache wspólny dla wszystkich workerów gunicorna (limity logowań,
# wejść demo, blokada resetu demo). Tabelę zakłada `createcachetable` w entrypoint.sh.
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.db.DatabaseCache",
        "LOCATION": "miniwms_cache",
        # Domyślne 300 wpisów pozwalało zalać tabelę i wyrzucić liczniki limitów (culling).
        "OPTIONS": {"MAX_ENTRIES": 100_000},
    }
}
# Limit nieudanych logowań na konto (niezależnie od IP) — decyzja PO 2026-10-16.
LOGIN_ACCOUNT_LIMIT = 10
LOGIN_ACCOUNT_WINDOW = 15 * 60  # sekund

# US-011: CSP egzekwowana; awaryjnie tryb raportowania (DJANGO_CSP_REPORT_ONLY=1).
CSP_REPORT_ONLY = env_bool("DJANGO_CSP_REPORT_ONLY", False)

# US-010: nazwa wydawcy w aplikacji uwierzytelniającej.
OTP_TOTP_ISSUER = "mini-WMS"

# US-008 / R6: nowe hasła w argon2; stare hashe PBKDF2 Django podnosi przy
# kolejnym udanym logowaniu (pierwszy hasher = docelowy, reszta = odczyt).
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.Argon2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2SHA1PasswordHasher",
    "django.contrib.auth.hashers.ScryptPasswordHasher",
]

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
    "filters": {
        "require_debug_false": {"()": "django.utils.log.RequireDebugFalse"},
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "plain" if DEBUG else "json",
        },
        # US-021: e-mail do ADMINS przy błędzie 500 (bez HTML, filtr `SafeReporterFilter`).
        "mail_admins": {
            "class": "django.utils.log.AdminEmailHandler",
            "level": "ERROR",
            "filters": ["require_debug_false"],
            "include_html": False,
        },
    },
    "root": {"handlers": ["console"], "level": "INFO"},
    "loggers": {
        "django.request": {
            "handlers": ["console", "mail_admins"],
            "level": "ERROR",
            "propagate": False,
        },
        # US-022: dziennik audytowy także w logu (poziom INFO, JSON na produkcji).
        "warehouse.audit": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
    },
}


# --- Alerty o błędach 500 (US-021, decyzja PO PYT-15: e-mail `mail_admins`) ---------
# Bez DJANGO_ADMINS alert jest wyłączony (Django nie wysyła), błąd zostaje w logu JSON.
# DJANGO_ADMINS: adresy rozdzielone przecinkami. SMTP z DJANGO_EMAIL_*; w demo maile
# idą do konsoli (wyżej).
ADMINS = [
    (addr.strip(), addr.strip())
    for addr in os.environ.get("DJANGO_ADMINS", "").split(",")
    if addr.strip()
]
DEFAULT_EXCEPTION_REPORTER_FILTER = "config.log.SafeReporterFilter"
SERVER_EMAIL = os.environ.get("DJANGO_SERVER_EMAIL", "mini-wms@localhost")
EMAIL_SUBJECT_PREFIX = "[mini-WMS] "
EMAIL_HOST = os.environ.get("DJANGO_EMAIL_HOST", "localhost")
EMAIL_PORT = int(os.environ.get("DJANGO_EMAIL_PORT", "587"))
EMAIL_HOST_USER = os.environ.get("DJANGO_EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.environ.get("DJANGO_EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = env_bool("DJANGO_EMAIL_USE_TLS", True)
# Wysyłka idzie w wątku żądania — krótki timeout, żeby awaria SMTP nie wieszała workera.
EMAIL_TIMEOUT = 10
