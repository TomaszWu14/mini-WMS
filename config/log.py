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

from django.views.debug import ExceptionReporter, SafeExceptionReporterFilter

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


class SafeReporterFilter(SafeExceptionReporterFilter):
    """US-021 / SEC-032: raport błędu 500 (e-mail `mail_admins`) bez sekretów.

    Domyślny filtr Django maskuje POST tylko w widokach z `@sensitive_post_parameters`
    i nie maskuje ciasteczka sesji. Tu maskujemy zawsze: pola formularza, nagłówki
    (META) i ustawienia o nazwach jak hasła/tokeny/sesja oraz wszystkie ciasteczka.
    """

    hidden_settings = re.compile(
        rf"API|AUTH|TOKEN|KEY|SECRET|PASS|SIGNATURE|COOKIE|SESSION|CSRF|OTP|{_WORDS}",
        flags=re.IGNORECASE,
    )

    def get_post_parameters(self, request):
        if request is None:
            return {}
        cleansed = request.POST.copy()
        for key in cleansed:
            if self.hidden_settings.search(key):
                cleansed[key] = self.cleansed_substitute
        return cleansed

    def get_safe_request_meta(self, request):
        meta = super().get_safe_request_meta(request)
        if meta.get("QUERY_STRING"):
            meta["QUERY_STRING"] = redact_text(meta["QUERY_STRING"])
        return meta

    def get_safe_cookies(self, request):
        return dict.fromkeys(getattr(request, "COOKIES", {}), self.cleansed_substitute)


class SafeExceptionReporter(ExceptionReporter):
    """US-021 (przegląd [SEC]): parametry GET w raporcie maskowane jak pola POST."""

    def get_traceback_data(self):
        data = super().get_traceback_data()
        if self.request is not None and "request_GET_items" in data:
            hidden = SafeReporterFilter.hidden_settings
            data["request_GET_items"] = [
                (k, SafeReporterFilter.cleansed_substitute if hidden.search(k) else v)
                for k, v in self.request.GET.items()
            ]
        if data.get("request_insecure_uri"):
            data["request_insecure_uri"] = redact_text(data["request_insecure_uri"])
        return data


ALERT_DEDUP_SECONDS = 600
ALERT_MAX_PER_HOUR = 20


class AlertThrottleFilter(logging.Filter):
    """US-021 (przegląd [SEC]): alert e-mail bez zalewu skrzynki i blokowania workerów.

    Ten sam błąd (typ wyjątku + ścieżka) najwyżej raz na 10 min, łącznie najwyżej 20
    maili na godzinę. W demo alertów nie ma (raport poszedłby do konsoli z danymi
    odwiedzających). Gdy cache nie działa (np. baza leży), wysyłamy — to jest awaria,
    o której administrator ma wiedzieć; limit godzinowy chroni wtedy proces lokalnie.
    """

    _local_sent: list[float] = []

    def filter(self, record: logging.LogRecord) -> bool:
        import time

        from django.conf import settings
        from django.core.cache import cache

        if settings.DEMO_MODE:
            return False
        exc = record.exc_info[1] if record.exc_info else None
        request = getattr(record, "request", None)
        key = f"alert500:{type(exc).__name__}:{getattr(request, 'path', '')}"[:200]
        hour = f"alert500-hour:{int(time.time() // 3600)}"
        try:
            if not cache.add(key, 1, ALERT_DEDUP_SECONDS):
                return False
            cache.add(hour, 0, 3600)
            return cache.incr(hour) <= ALERT_MAX_PER_HOUR
        except Exception:  # noqa: BLE001 — cache niedostępny: limit w procesie
            now = time.time()
            self._local_sent[:] = [t for t in self._local_sent if now - t < 3600]
            if len(self._local_sent) >= ALERT_MAX_PER_HOUR:
                return False
            self._local_sent.append(now)
            return True
