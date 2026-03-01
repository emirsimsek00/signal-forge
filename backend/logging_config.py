"""Structured JSON logging configuration for SignalForge."""

from __future__ import annotations

import logging
import sys

from backend.utils.time import utc_now


class JSONFormatter(logging.Formatter):
    """Formats log records as structured JSON for production observability."""

    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": utc_now().isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        if record.exc_info and record.exc_info[1]:
            log_entry["exception"] = self.formatException(record.exc_info)

        # Include request context if middleware injects it.
        for key in ("request_id", "method", "path", "status_code", "duration_ms"):
            value = getattr(record, key, None)
            if value is not None:
                log_entry[key] = value

        # Use simple key=value format for readability in dev
        parts = [f"[{log_entry['level']:<7}]", f"{log_entry['timestamp']}", f"{log_entry['message']}"]
        for key in ("request_id", "method", "path", "status_code", "duration_ms"):
            if key in log_entry:
                parts.append(f"{key}={log_entry[key]}")

        if record.exc_info and record.exc_info[1]:
            parts.append(f"\n{log_entry['exception']}")

        return " ".join(parts)


def setup_logging(level: str = "INFO") -> None:
    """Configure structured logging for the application."""
    root_logger = logging.getLogger()
    
    # Avoid adding handlers multiple times
    if root_logger.handlers:
        return

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JSONFormatter())
    root_logger.addHandler(handler)
    root_logger.setLevel(getattr(logging, level.upper(), logging.INFO))

    # Quiet noisy third-party loggers
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
