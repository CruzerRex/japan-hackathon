"""Structured (JSON-lines) logging.

Log records carry an event name plus small structured fields. Request bodies,
transcripts, passwords and tokens are never logged.
"""
from __future__ import annotations

import json
import logging
import sys
import time


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(record.created)) + "Z",
            "level": record.levelname,
            "logger": record.name,
            "event": record.getMessage(),
        }
        fields = getattr(record, "fields", None)
        if isinstance(fields, dict):
            payload.update(fields)
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False, default=str)


class PlainFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        base = f"{time.strftime('%H:%M:%S')} {record.levelname:<7} {record.name}: {record.getMessage()}"
        fields = getattr(record, "fields", None)
        if fields:
            base += " " + " ".join(f"{k}={v}" for k, v in fields.items())
        if record.exc_info:
            base += "\n" + self.formatException(record.exc_info)
        return base


def setup_logging(level: str = "INFO", json_mode: bool = True) -> None:
    root = logging.getLogger()
    root.handlers.clear()
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter() if json_mode else PlainFormatter())
    root.addHandler(handler)
    root.setLevel(level)


def log(logger: logging.Logger, level: int, event: str, **fields) -> None:
    logger.log(level, event, extra={"fields": fields})
