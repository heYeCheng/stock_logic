"""Application logger with JSON formatter."""

import json
import logging
import os
from datetime import datetime
from pathlib import Path

from src.config.settings import settings


class JsonFormatter(logging.Formatter):
    """JSON log formatter for structured logging.

    Output format:
    {"timestamp": ISO8601, "level": str, "logger": str, "message": str, "extra": dict}
    """

    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "extra": {},
        }

        # Add extra fields if present
        if hasattr(record, "extra"):
            log_entry["extra"] = record.extra

        # Add exception info if present
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_entry, ensure_ascii=False)


def get_logger(name: str) -> logging.Logger:
    """Get logger instance with propagation enabled.

    Args:
        name: Logger name (typically module name)

    Returns:
        logging.Logger instance that propagates to root handler.
    """
    logger = logging.getLogger(name)
    logger.propagate = True  # Ensure logs reach root handler
    return logger


def setup_app_logging() -> None:
    """Configure application logging.

    Creates logs/ directory and configures:
    - Root logger with level from settings.log_level
    - FileHandler writing JSON to logs/app.log
    - StreamHandler for console output
    """
    # Create logs directory
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, settings.log_level.upper(), logging.INFO))

    # Clear existing handlers
    root_logger.handlers.clear()

    # JSON formatter
    json_formatter = JsonFormatter()

    # File handler - logs/app.log
    file_handler = logging.FileHandler(log_dir / "app.log", encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(json_formatter)
    root_logger.addHandler(file_handler)

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    console_handler.setFormatter(console_formatter)
    root_logger.addHandler(console_handler)

    logging.info("Application logging initialized")
