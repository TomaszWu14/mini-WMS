"""Minimalny formatter logów w JSON (bez dodatkowych zależności).

Używany na produkcji, by Coolify/Docker/agregator logów mógł parsować rekordy
strukturalnie zamiast wolnego tekstu.

US-022 / SEC-033: wartości pól wrażliwych (hasła, tokeny CSRF i 2FA, ciasteczko
sesji, sekrety) są maskowane — zarówno w polach `extra`, jak i w treści komunikatu
i śladu wyjątku (`password=…`, `"token": "…"`). Obiekt żądania trafia do logu tylko
jako metoda i ścieżka, bez danych formularza.
"""

import datetime
import json
import logging
import re

REDACTED = "[REDACTED]"
SENSITIVE = (
    "password",
    "passwd",
    "secret",
    "token",
    "csrfmiddlewaretoken",
    "sessionid",
    "csrftoken",
    "authorization",
    "cookie",
    "api_key",
)
_KEY_RE = re.compile("|".join(SENSITIVE), re.IGNORECASE)
# klucz=wartość (formularz, querystring) oraz 'klucz': 'wartość' / "klucz": "wartość" (repr, JSON)
_TEXT_RE = re.compile(
    r"(?P<key>[\w-]*(?:" + "|".join(SENSITIVE) + r")[\w-]*)"
    r"(?P<sep>['\"]?\s*[:=]\s*\[?['\"]?)"
    r"(?P<value>[^'\"&\s,\]}]+)",
    re.IGNORECASE,
)


def redact_text(text: str) -> str:
    return _TEXT_RE.sub(lambda m: f"{m['key']}{m['sep']}{REDACTED}", text)


def _redact(value, key: str = ""):
    if key and _KEY_RE.search(key):
        return REDACTED
    if isinstance(value, dict):
        return {k: _redact(v, str(k)) for k, v in value.items()}
    if isinstance(value, list | tuple):
        return [_redact(v) for v in value]
    if isinstance(value, str):
        return redact_text(value)
    return value


def _request_summary(request) -> str:
    """Żądanie w logu: metoda i ścieżka — bez POST, ciasteczek i nagłówków."""
    method = getattr(request, "method", "")
    path = getattr(request, "path", "")
    return f"{method} {path}".strip()


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": datetime.datetime.fromtimestamp(
                record.created, tz=datetime.UTC
            ).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": redact_text(record.getMessage()),
        }
        if record.exc_info:
            payload["exc"] = redact_text(self.formatException(record.exc_info))
        # Dodatkowe pola przekazane przez logger.*(..., extra={...}).
        standard = set(logging.makeLogRecord({}).__dict__)
        for key, value in record.__dict__.items():
            if key in standard or key in payload:
                continue
            if key == "request" and hasattr(value, "method"):
                payload[key] = _request_summary(value)
                continue
            value = _redact(value, key)
            try:
                json.dumps(value)
                payload[key] = value
            except (TypeError, ValueError):
                payload[key] = redact_text(str(value))
        return json.dumps(payload, ensure_ascii=False)
