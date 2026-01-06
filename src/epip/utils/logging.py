"""Shared logging helpers for EPIP."""

from __future__ import annotations

import logging
from typing import Any

try:  # pragma: no cover - optional dependency
    import structlog
except ImportError:  # pragma: no cover - fallback if structlog is unavailable
    structlog = None  # type: ignore[assignment]

_LOGGER_NAME = "epip"
_IS_CONFIGURED = False


def configure_logging(level: str = "INFO") -> None:
    """Configure structlog if available, else fall back to stdlib logging."""
    global _IS_CONFIGURED
    if _IS_CONFIGURED:
        return

    numeric_level = getattr(logging, level.upper(), logging.INFO)
    logging.basicConfig(level=numeric_level)
    if structlog:
        structlog.configure(
            processors=[
                structlog.processors.TimeStamper(fmt="iso"),
                structlog.processors.add_log_level,
                structlog.dev.ConsoleRenderer(),
            ],
            wrapper_class=structlog.make_filtering_bound_logger(numeric_level),
            logger_factory=structlog.PrintLoggerFactory(),
        )
    _IS_CONFIGURED = True


def _structlog_logger() -> Any:
    if structlog:
        return structlog.get_logger(_LOGGER_NAME)
    return logging.getLogger(_LOGGER_NAME)


def get_logger(level: str = "INFO") -> Any:
    """Return a configured logger instance."""
    configure_logging(level)
    return _structlog_logger()


__all__ = ["configure_logging", "get_logger"]
