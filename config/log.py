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
_WORDS = "|".join(SENSITIVE)
_KEY_RE = re.compile(_WORDS, re.IGNORECASE)
_KEY = rf"[\w-]*(?:{_WORDS})[\w-]*"
# Wartość: w cudzysłowie (z obsługą \"), lista w nawiasach albo goły ciąg do separatora.
_VALUE = r"""(?:'(?:\\.|[^'\\])*'|"(?:\\.|[^"\\])*"|\[[^\]]*\]|[^\s&,;)}\]]+)"""
# 'klucz': wartość / "klucz": wartość (repr słownika, JSON) — tylko klucz w cudzysłowie,
# żeby zwykłe zdanie „tokens: 5 usuniętych” nie traciło wartości (przegląd [SEC] US-022).
_QUOTED_KEY_RE = re.compile(
    rf"""(?P<k>(?P<q>['"]){_KEY}(?P=q)\s*:\s*){_VALUE}""", re.IGNORECASE
)
# klucz=wartość (formularz, querystring; także zakodowane %3D).
_ASSIGN_RE = re.compile(rf"(?P<k>\b{_KEY}\s*(?:=|%3D)\s*){_VALUE}", re.IGNORECASE)
# Nagłówki w treści (np. zrzut żądania): wszystko do końca linii.
_HEADER_RE = re.compile(
    r"(?P<k>\b(?:Authorization|Proxy-Authorization|Cookie|Set-Cookie)\s*:\s*)[^\r\n]*",
    re.IGNORECASE,
)


def redact_text(text: str) -> str:
    text = _HEADER_RE.sub(lambda m: m["k"] + REDACTED, text)
    text = _QUOTED_KEY_RE.sub(lambda m: m["k"] + repr(REDACTED), text)
    return _ASSIGN_RE.sub(lambda m: m["k"] + REDACTED, text)


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
