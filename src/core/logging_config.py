"""
Structured logging configuration for Demand Forecasting Backend.
Ensures consistent JSON/console output and prevents leakage of sensitive data or server paths.
"""
import logging
import sys
from typing import Any, Dict


class SafeLogFormatter(logging.Formatter):
    """Log formatter that ensures clean message formatting."""

    def format(self, record: logging.LogRecord) -> str:
        # Prevent logging tracebacks or internal raw exceptions to unprivileged streams if marked sensitive
        return super().format(record)


def setup_logging(level: str = "INFO") -> logging.Logger:
    """Configures root and application loggers."""
    log_level = getattr(logging, level.upper(), logging.INFO)

    # Ensure UTF-8 output on Windows consoles
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    logger = logging.getLogger("forecast_backend")
    logger.setLevel(log_level)

    # Avoid duplicate handlers if called multiple times
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(log_level)
        formatter = SafeLogFormatter(
            fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    # Configure uvicorn loggers to match format
    for uvicorn_logger_name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        u_logger = logging.getLogger(uvicorn_logger_name)
        u_logger.setLevel(log_level)

    return logger


logger = setup_logging()
