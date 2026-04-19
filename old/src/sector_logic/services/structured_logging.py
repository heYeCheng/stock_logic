# -*- coding: utf-8 -*-
"""
Structured logging formatter for sector logic analysis.

Usage:
    import logging
    from src.sector_logic.services.structured_logging import setup_structured_logging
    setup_structured_logging()

Outputs JSON-formatted log entries with:
  - timestamp, level, module, action
  - sector, date, logic_category, logic_strength, flip_detected
"""

import json
import logging
import sys
from datetime import datetime, timezone


class JsonFormatter(logging.Formatter):
    """JSON log formatter with sector logic fields."""

    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
            "message": record.getMessage(),
        }

        # Add extra fields
        for attr in (
            "sector", "date", "logic_category", "logic_strength",
            "logic_status", "issue_count", "flip_detected",
            "action", "duration_ms",
        ):
            if hasattr(record, attr):
                log_entry[attr] = getattr(record, attr)

        # Add exception info
        if record.exc_info and record.exc_info[0] is not None:
            log_entry["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_entry, ensure_ascii=False, default=str)


def setup_structured_logging(
    level: int = logging.INFO,
    output: str = "stdout",
    json_format: bool = False,
) -> None:
    """
    Configure structured logging for sector logic analysis.

    Args:
        level: Log level (default: INFO)
        output: "stdout" or file path
        json_format: Use JSON formatting (default: False for local dev)
    """
    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    if output == "stdout":
        handler = logging.StreamHandler(sys.stdout)
    else:
        handler = logging.FileHandler(output, encoding="utf-8")

    handler.setLevel(level)

    if json_format:
        formatter = JsonFormatter()
    else:
        formatter = logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

    handler.setFormatter(formatter)
    root_logger.addHandler(handler)

    # Reduce noisy third-party loggers
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
