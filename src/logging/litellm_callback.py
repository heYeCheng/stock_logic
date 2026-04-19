"""LiteLLM custom callback for JSON file logging."""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

try:
    from litellm.integrations.custom_logger import CustomLogger
except ImportError:
    # LiteLLM not installed - provide stub for Phase 1
    CustomLogger = object  # type: ignore


class FileJsonLogger(CustomLogger):  # type: ignore
    """LiteLLM callback logger that writes to JSONL file.

    Logs LLM call success/failure to logs/lite_llm/calls.jsonl

    Each entry contains:
    - timestamp: ISO8601 timestamp
    - type: "success" or "failure"
    - model: Model name
    - messages: Input messages
    - response/error: Output or error details
    - usage: Token usage (if available)
    - duration_ms: Call duration
    """

    def __init__(self):
        """Initialize logger and ensure log directory exists."""
        self.log_dir = Path("logs/lite_llm")
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.log_file = self.log_dir / "calls.jsonl"

    def _write_log(self, entry: dict) -> None:
        """Append JSON entry to log file."""
        with open(self.log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    async def async_log_success_event(
        self,
        kwargs: dict,
        response_obj: Any,
        start_time: datetime,
        end_time: datetime,
    ) -> None:
        """Log successful LLM call.

        Args:
            kwargs: Call arguments (model, messages, etc.)
            response_obj: Response object from LiteLLM
            start_time: Call start time
            end_time: Call end time
        """
        duration_ms = (end_time - start_time).total_seconds() * 1000

        # Extract response data
        response_data = {}
        if hasattr(response_obj, "model_dump"):
            response_data = response_obj.model_dump()
        elif hasattr(response_obj, "__dict__"):
            response_data = response_obj.__dict__
        else:
            response_data = str(response_obj)

        entry = {
            "timestamp": datetime.now().isoformat(),
            "type": "success",
            "model": kwargs.get("model", "unknown"),
            "messages": kwargs.get("messages", []),
            "response": response_data,
            "usage": kwargs.get("usage", {}),
            "duration_ms": round(duration_ms, 2),
        }

        self._write_log(entry)

    async def async_log_failure_event(
        self,
        kwargs: dict,
        exception: Exception,
        start_time: datetime,
        end_time: datetime,
    ) -> None:
        """Log failed LLM call.

        Args:
            kwargs: Call arguments (model, messages, etc.)
            exception: Exception that was raised
            start_time: Call start time
            end_time: Call end time
        """
        duration_ms = (end_time - start_time).total_seconds() * 1000

        entry = {
            "timestamp": datetime.now().isoformat(),
            "type": "failure",
            "model": kwargs.get("model", "unknown"),
            "messages": kwargs.get("messages", []),
            "error": {
                "type": type(exception).__name__,
                "message": str(exception),
            },
            "duration_ms": round(duration_ms, 2),
        }

        self._write_log(entry)


def setup_litellm_logging() -> None:
    """Configure LiteLLM callbacks for JSON file logging.

    Registers FileJsonLogger with LiteLLM success and failure callbacks.

    Usage:
        from src.logging import setup_litellm_logging
        setup_litellm_logging()

        # Now all LiteLLM calls are logged to logs/lite_llm/calls.jsonl
    """
    import litellm

    file_logger = FileJsonLogger()
    litellm.success_callback = [file_logger]
    litellm.failure_callback = [file_logger]

    logging.info("LiteLLM JSON logging configured -> logs/lite_llm/calls.jsonl")
