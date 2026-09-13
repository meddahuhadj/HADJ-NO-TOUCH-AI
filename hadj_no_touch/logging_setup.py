"""Logging configuration for HADJ NO-TOUCH AI.

Logs are written to a rotating text file in the user data directory.
Camera/video data is never written to the log.
"""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler

from .config import data_dir

_LOG_FORMAT = "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s"


def setup_logging(level: int = logging.INFO, console: bool = True) -> logging.Logger:
    root = logging.getLogger("hadj_no_touch")
    root.setLevel(level)
    root.handlers.clear()

    if console:
        ch = logging.StreamHandler()
        ch.setLevel(level)
        ch.setFormatter(logging.Formatter(_LOG_FORMAT))
        root.addHandler(ch)

    try:
        fh = RotatingFileHandler(
            data_dir() / "hadj_no_touch.log",
            maxBytes=2 * 1024 * 1024,
            backupCount=3,
            encoding="utf-8",
        )
        fh.setLevel(level)
        fh.setFormatter(logging.Formatter(_LOG_FORMAT))
        root.addHandler(fh)
    except Exception:
        pass

    root.propagate = False
    return root


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(f"hadj_no_touch.{name}")