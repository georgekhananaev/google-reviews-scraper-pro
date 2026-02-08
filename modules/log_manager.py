"""
Structured logging setup for Google Maps Reviews Scraper.

Rich colored output → stderr (safe for piped output).
Rotating JSON log files → configurable directory.
"""

import json
import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.logging import RichHandler


class _JsonFormatter(logging.Formatter):
    """Format log records as single-line JSON objects."""

    def format(self, record: logging.LogRecord) -> str:
        entry = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        if record.exc_info and record.exc_info[0] is not None:
            entry["exc"] = self.formatException(record.exc_info)
        return json.dumps(entry, ensure_ascii=False)


def setup_logging(
    level: str = "INFO",
    log_dir: str = "logs",
    log_file: str = "scraper.log",
    max_bytes: int = 5 * 1024 * 1024,
    backup_count: int = 5,
    console: Optional[Console] = None,
) -> None:
    """Configure structured logging for the application.

    Args:
        level: Log level name (DEBUG, INFO, WARNING, ERROR, CRITICAL).
        log_dir: Directory for log files.
        log_file: Log file name inside log_dir.
        max_bytes: Max size per log file before rotation.
        backup_count: Number of rotated log files to keep.
        console: Optional Rich Console instance (created if None).
    """
    numeric_level = getattr(logging, level.upper(), logging.INFO)

    root = logging.getLogger()
    root.setLevel(numeric_level)

    # Remove any existing handlers to avoid duplicates on re-init.
    root.handlers.clear()

    # --- Rich console handler → stderr ---
    if console is None:
        console = Console(stderr=True)
    rich_handler = RichHandler(
        console=console,
        show_time=True,
        show_path=False,
        markup=True,
        rich_tracebacks=True,
    )
    rich_handler.setLevel(numeric_level)
    root.addHandler(rich_handler)

    # --- Rotating JSON file handler ---
    log_path = Path(log_dir)
    log_path.mkdir(parents=True, exist_ok=True)
    file_path = log_path / log_file

    file_handler = RotatingFileHandler(
        str(file_path),
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding="utf-8",
    )
    file_handler.setLevel(numeric_level)
    file_handler.setFormatter(_JsonFormatter())
    root.addHandler(file_handler)

    # --- Suppress noisy third-party loggers ---
    for noisy in ("selenium", "urllib3", "botocore", "boto3", "s3transfer",
                   "asyncio", "websockets", "httpcore", "httpx"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
