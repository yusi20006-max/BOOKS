"""Privacy-conscious runtime logging and request diagnostics."""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from typing import Any

_LOGGER = logging.getLogger("books.runtime")
_ALLOWED_FIELDS = {"request_id", "method", "route", "status", "duration_ms", "error_type"}


def configure_logging(level: str | None = None) -> None:
    """Configure one-line JSON logs; never log request bodies, headers, or query strings."""
    configured = (level or os.getenv("BOOKS_LOG_LEVEL", "INFO")).strip().upper()
    levels = {
        "DEBUG": logging.DEBUG,
        "INFO": logging.INFO,
        "WARNING": logging.WARNING,
        "ERROR": logging.ERROR,
        "CRITICAL": logging.CRITICAL,
    }
    if configured not in levels:
        raise ValueError("BOOKS_LOG_LEVEL must be DEBUG, INFO, WARNING, ERROR, or CRITICAL")
    logging.basicConfig(level=levels[configured], format="%(message)s")
    _LOGGER.setLevel(levels[configured])


def log_event(level: str, event: str, **fields: Any) -> None:
    """Emit a bounded, allow-listed diagnostic event without user-controlled text."""
    record: dict[str, Any] = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "service": "books.runtime",
        "level": level.upper(),
        "event": event,
    }
    for key in _ALLOWED_FIELDS:
        value = fields.get(key)
        if isinstance(value, (str, int, float, bool)) or value is None:
            record[key] = value
    message = json.dumps(record, ensure_ascii=True, separators=(",", ":"), allow_nan=False)
    _LOGGER.log(getattr(logging, level.upper(), logging.INFO), message)
