"""Application logger configuration."""

from __future__ import annotations

import logging
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path
from typing import Any, Optional

from config import Config
from logger.formatters import build_console_formatter, build_file_formatter
from storage.database import db


class SQLiteHandler(logging.Handler):
    """Persist log records to the meta_logs table."""

    def emit(self, record: logging.LogRecord) -> None:
        try:
            details: Optional[dict[str, Any]] = None
            if hasattr(record, "details") and isinstance(record.details, dict):
                details = record.details

            db.log_meta_log(
                level=record.levelname,
                component=getattr(record, "component", record.name),
                message=record.getMessage(),
                details=details,
                check_name=getattr(record, "check_name", None),
                error_type=getattr(record, "error_type", None),
            )
        except Exception:
            # Last-resort fallback: never raise from logging.
            pass


def _ensure_log_dir() -> Path:
    log_dir = Path(Config.LOG_DIR)
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir


def setup_logger() -> logging.Logger:
    logger = logging.getLogger("netbird_sentinel")
    if logger.handlers:
        return logger

    logger.setLevel(Config.LOG_LEVEL)
    db.initialize()

    console_handler = logging.StreamHandler()
    console_handler.setLevel(Config.LOG_LEVEL)
    console_handler.setFormatter(build_console_formatter())

    log_dir = _ensure_log_dir()
    file_handler = TimedRotatingFileHandler(
        log_dir / "sentinel.log",
        when="midnight",
        backupCount=Config.LOG_RETENTION_DAYS,
        encoding="utf-8",
    )
    file_handler.setLevel(Config.LOG_LEVEL)
    file_handler.setFormatter(build_file_formatter())

    sqlite_handler = SQLiteHandler()
    sqlite_handler.setLevel(Config.LOG_LEVEL)

    logger.addHandler(console_handler)
    logger.addHandler(file_handler)
    logger.addHandler(sqlite_handler)

    logger.propagate = False
    return logger


logger = setup_logger()
