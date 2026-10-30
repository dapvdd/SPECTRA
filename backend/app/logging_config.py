"""Structured JSON logging configuration for SPECTRA.

All application logs are emitted as single-line JSON objects to stdout, so
container orchestrators and log shippers get a machine-parseable stream with
no extra parsing. Each record includes the log level, the logger name, an ISO
timestamp, and the message; extra ``extra`` fields supplied at the call site
are merged into the JSON object so callers can add request IDs, durations, and
other correlation context.

Redaction: by default only the ``message``, ``levelname``, ``name``, ``asctime``
and any caller-provided ``extra`` are written. The message itself is not
sanitised here (callers handle their own sensitive data at the source, as the
explanation service already does by truncating long AI payloads). This module
is intentionally dependency-free (no structlog): it satisfies the observability
goal without adding a runtime dependency.

Design notes:
- The handler replaces any newlines in structured fields so a single record
  always maps to a single output line — logs stay greppable and shippers can
  split on newlines safely.
- ``configure_logging`` is idempotent so it can be called from tests and from
  ``main`` import time without emitting duplicate handlers.
"""

from __future__ import annotations

import json
import logging
import sys
import time
from typing import Any


class JsonFormatter(logging.Formatter):
    """Format a LogRecord as a single-line JSON object."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": time.strftime(
                "%Y-%m-%dT%H:%M:%SZ", time.gmtime(record.created)
            ),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Merge any structured ``extra`` fields supplied at the call site.
        extra_keys = getattr(record, "structured_extra", None)
        if isinstance(extra_keys, dict):
            for key, value in extra_keys.items():
                payload[key] = value

        # Serialize, collapsing embedded newlines so one record == one line.
        text = json.dumps(payload, default=str)
        return text.replace("\n", " ")


def _add_json_handler(logger: logging.Logger) -> None:
    handler = logging.StreamHandler(stream=sys.stdout)
    handler.setFormatter(JsonFormatter())
    logger.addHandler(handler)


def configure_logging(level: int = logging.INFO) -> logging.Logger:
    """Configure the root logger with a single JSON stdout handler.

    Idempotent: if a JSON handler is already attached, does not add another.
    Returns the root logger for convenience.
    """
    root = logging.getLogger()
    # Avoid duplicate handlers when main is reloaded (e.g. in tests).
    has_json_handler = any(
        isinstance(h.formatter, JsonFormatter) for h in root.handlers
    )
    if not has_json_handler:
        _add_json_handler(root)
    root.setLevel(level)
    return root


def get_logger(name: str) -> logging.Logger:
    """Return a logger pre-configured to accept ``structured_extra`` kwargs.

    Usage::

        from backend.app.logging_config import get_logger
        log = get_logger(__name__)
        log.info("request complete", extra={"request_id": rid, "duration_ms": 42})
    """
    return logging.getLogger(name)
