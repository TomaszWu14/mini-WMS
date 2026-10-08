"""Minimalny formatter logów w JSON (bez dodatkowych zależności).

Używany na produkcji, by Coolify/Docker/agregator logów mógł parsować rekordy
strukturalnie zamiast wolnego tekstu.
"""

import datetime
import json
import logging


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": datetime.datetime.fromtimestamp(
                record.created, tz=datetime.UTC
            ).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        # Dodatkowe pola przekazane przez logger.*(..., extra={...}).
        standard = set(logging.makeLogRecord({}).__dict__)
        for key, value in record.__dict__.items():
            if key not in standard and key not in payload:
                try:
                    json.dumps(value)
                    payload[key] = value
                except (TypeError, ValueError):
                    payload[key] = str(value)
        return json.dumps(payload, ensure_ascii=False)
