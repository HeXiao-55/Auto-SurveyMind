#!/usr/bin/env python3
"""Centralised logging configuration for SurveyMind tools.

All tools should call ``setup_logging(__name__)`` at module load time instead
of using bare ``print()`` or custom ``debug_log()`` functions.

Usage
-----
    from logging_config import setup_logging
    logger = setup_logging(__name__)

    logger.info("Starting paper triage")
    logger.debug("Fetched %d results", len(results))
    logger.warning("Rate limited, backing off")
    logger.error("Failed to fetch metadata: %s", exc)
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

def _default_level_name() -> str:
    """Return default log level name from environment at call time."""
    return os.environ.get("SURVEYMIND_LOG_LEVEL", "INFO").upper()

# When run interactively (to a TTY), use a human-readable colour formatter.
# When run as part of a pipeline / redirected to file, use plain text.
_IS_TTY = hasattr(sys.stderr, "isatty") and sys.stderr.isatty()

_FMT_TTY = (
    "%(asctime)s "
    "%(color_levelname)s%(levelname)s%(color_reset)s "
    "%(name)s "
    "%(message)s"
    if _IS_TTY else
    "%(asctime)s %(levelname)s %(name)s %(message)s"
)

_DATE_FMT = "%H:%M:%S"


# ── Colour helpers (TTY only) ───────────────────────────────────────────────────

_LEVEL_COLORS = {
    "DEBUG":    "\033[36m",   # cyan
    "INFO":     "\033[32m",   # green
    "WARNING":  "\033[33m",   # yellow
    "ERROR":    "\033[31m",   # red
    "CRITICAL": "\033[35m",   # magenta
}
_COLOR_RESET = "\033[0m"


class _ColorFormatter(logging.Formatter):
    """Add ANSI colour codes to level names when writing to a TTY."""

    def __init__(self, fmt: str, datefmt: str = _DATE_FMT):
        super().__init__(fmt, datefmt)
        self._color_map = _LEVEL_COLORS

    def format(self, record: logging.LogRecord) -> str:
        if _IS_TTY:
            record.color_levelname = self._color_map.get(record.levelname, "")
            record.color_reset = _COLOR_RESET
        return super().format(record)


# ── Public API ─────────────────────────────────────────────────────────────────

def setup_logging(
    name: str | None = None,
    *,
    level: str | int | None = None,
    log_file: str | Path | None = None,
    propagate: bool = False,
) -> logging.Logger:
    """Configure and return a logger for the calling module.

    Parameters
    ----------
    name : str
        Logger name. Pass ``__name__`` from the calling module.
    level : str | int
        Log level e.g. ``"DEBUG"``, ``"INFO"``, or ``logging.DEBUG``.
        Defaults to the ``SURVEYMIND_LOG_LEVEL`` environment variable.
    log_file : Path
        Optional file path to also write logs to.
    propagate : bool
        Whether to also propagate to the root logger (default: False,
        meaning each module's logger is independent).

    Returns
    -------
    logging.Logger
    """
    if isinstance(level, str):
        level = getattr(logging, level.upper(), logging.INFO)

    logger = logging.getLogger(name or "surveymind")
    logger.setLevel(level or getattr(logging, _default_level_name(), logging.INFO))
    logger.propagate = propagate

    # Avoid duplicate handlers on repeated calls (e.g. module re-imported)
    if logger.handlers:
        return logger

    # Console handler
    ch = logging.StreamHandler(sys.stderr)
    ch.setLevel(logger.level)
    if _IS_TTY:
        ch.setFormatter(_ColorFormatter(_FMT_TTY, _DATE_FMT))
    else:
        ch.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s", _DATE_FMT))
    logger.addHandler(ch)

    # Optional file handler
    if log_file:
        log_path = Path(log_file).expanduser()
        log_path.parent.mkdir(parents=True, exist_ok=True)
        fh = logging.FileHandler(log_path, encoding="utf-8")
        fh.setLevel(logger.level)
        fh.setFormatter(logging.Formatter(
            "%(asctime)s %(levelname)s %(name)s %(message)s",
            "%Y-%m-%d %H:%M:%S",
        ))
        logger.addHandler(fh)

    return logger


def get_logger(name: str | None = None) -> logging.Logger:
    """Return an existing logger, or a new one with default config.

    Unlike ``setup_logging``, this never adds new handlers — it is safe to call
    after the module has already been set up.
    """
    return logging.getLogger(name or "surveymind")
