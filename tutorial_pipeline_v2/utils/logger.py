"""Structured logging setup."""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler

from config import settings
from utils.paths import ensure_dirs, p


def setup_logging() -> None:
    """Configure root logging once."""
    ensure_dirs()
    root_logger = logging.getLogger()
    if root_logger.handlers:
        return

    level = getattr(logging, settings.LOG_LEVEL, logging.INFO)
    root_logger.setLevel(level)

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    file_handler = RotatingFileHandler(
        p("logs", "tutorial_pipeline.log"),
        maxBytes=1_000_000,
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)

    root_logger.addHandler(file_handler)
    root_logger.addHandler(stream_handler)


def get_logger(name: str) -> logging.Logger:
    """Return logger with project configuration applied."""
    setup_logging()
    return logging.getLogger(name)
