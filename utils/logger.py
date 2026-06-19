"""
Novel-Claude Fusion — Centralized Logging System

Replaces scattered print() calls with structured logging.
Configure once at CLI/WebUI startup, used everywhere via get_logger(__name__).

Features:
  - Dual output: colored console (human-readable) + rotating file (full detail)
  - RotatingFileHandler: 10MB per file, 5 backups
  - Session markers for debugging across restarts
  - Module-level loggers via `get_logger(__name__)`
  - Backward compatible: print() still works during migration

Design: 2025-2026 Python logging best practices
  - Single dictConfig at application entry point
  - logging.getLogger(__name__) in every module
  - RotatingFileHandler for predictable disk usage
  - JSON format option for future observability integration
"""

from __future__ import annotations

import logging
import logging.config
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional


# ── config ────────────────────────────────────────────────────────────────────

LOG_DIR = Path(os.path.expanduser("~/.novel_claude_logs"))
LOG_FILE = LOG_DIR / "novel_claude.log"
SESSION_START_MARKER = "=" * 72

# Console format: clean, with emoji status
CONSOLE_FORMAT = "%(message)s"

# File format: full detail for debugging
FILE_FORMAT = (
    "%(asctime)s | %(levelname)-7s | %(name)s | "
    "%(funcName)s:%(lineno)d | %(message)s"
)

# Log rotation: 10MB per file, keep 5 backups, compress old ones when possible
MAX_BYTES = 10 * 1024 * 1024  # 10 MB
BACKUP_COUNT = 5


# ── colored console handler ──────────────────────────────────────────────────

class ColoredConsoleHandler(logging.StreamHandler):
    """Console handler with ANSI colors for level-based output.
    Keeps the visual style of the old print() output but with log levels."""

    COLORS = {
        "DEBUG": "\033[90m",     # gray
        "INFO": "\033[0m",       # default
        "WARNING": "\033[33m",   # yellow
        "ERROR": "\033[31m",     # red
        "CRITICAL": "\033[1;31m", # bold red
        "SUCCESS": "\033[32m",   # green
    }
    RESET = "\033[0m"

    def emit(self, record):
        color = self.COLORS.get(record.levelname, "")
        msg = self.format(record)
        # Add color wrapper
        if color:
            self.stream.write(f"{color}{msg}{self.RESET}\n")
        else:
            self.stream.write(f"{msg}\n")
        self.flush()


# ── session tracking filter ──────────────────────────────────────────────────

class SessionFilter(logging.Filter):
    """Adds session_id to every log record for multi-session debugging."""
    session_id: str = ""

    @classmethod
    def new_session(cls):
        cls.session_id = datetime.now().strftime("%Y%m%d-%H%M%S")

    def filter(self, record):
        record.session_id = self.session_id or "-"
        return True


# ── setup ─────────────────────────────────────────────────────────────────────

_is_configured = False


def setup_logging(level: int = logging.DEBUG, log_dir: Path = None):
    """
    Configure logging ONCE at application startup.
    Call this before any module tries to log.

    Args:
        level: Default log level (DEBUG for development, INFO for production)
        log_dir: Optional custom log directory
    """
    global _is_configured
    if _is_configured:
        return

    log_path = log_dir or LOG_DIR
    log_path.mkdir(parents=True, exist_ok=True)
    log_file = log_path / "novel_claude.log"

    SessionFilter.new_session()

    config = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "console": {
                "format": CONSOLE_FORMAT,
            },
            "file": {
                "format": FILE_FORMAT,
                "datefmt": "%Y-%m-%d %H:%M:%S",
            },
        },
        "filters": {
            "session": {
                "()": "utils.logger.SessionFilter",
            },
        },
        "handlers": {
            "console": {
                "()": "utils.logger.ColoredConsoleHandler",
                "level": "INFO",
                "formatter": "console",
                "stream": "ext://sys.stdout",
            },
            "file": {
                "class": "logging.handlers.RotatingFileHandler",
                "level": "DEBUG",
                "formatter": "file",
                "filename": str(log_file),
                "maxBytes": MAX_BYTES,
                "backupCount": BACKUP_COUNT,
                "encoding": "utf-8",
                "filters": ["session"],
            },
        },
        "loggers": {
            "": {  # root logger
                "level": "DEBUG",
                "handlers": ["console", "file"],
            },
            # Suppress noisy third-party loggers
            "openai": {"level": "WARNING"},
            "httpx": {"level": "WARNING"},
            "httpcore": {"level": "WARNING"},
            "urllib3": {"level": "WARNING"},
            "chromadb": {"level": "WARNING"},
            "sentence_transformers": {"level": "WARNING"},
        },
    }

    logging.config.dictConfig(config)
    _is_configured = True

    # Write session start marker to file only
    root = logging.getLogger()
    for h in root.handlers:
        if isinstance(h, logging.handlers.RotatingFileHandler):
            record = logging.LogRecord(
                name="session", level=logging.INFO,
                pathname="", lineno=0, msg="", args=(),
                exc_info=None,
            )
            h.emit(logging.LogRecord(
                name="session", level=logging.INFO,
                pathname="", lineno=0,
                msg=SESSION_START_MARKER, args=(),
                exc_info=None,
            ))
            h.emit(logging.LogRecord(
                name="session", level=logging.INFO,
                pathname="", lineno=0,
                msg=f"  Session: {SessionFilter.session_id}", args=(),
                exc_info=None,
            ))
            h.emit(logging.LogRecord(
                name="session", level=logging.INFO,
                pathname="", lineno=0,
                msg=SESSION_START_MARKER, args=(),
                exc_info=None,
            ))


# ── public API ────────────────────────────────────────────────────────────────

# Custom log level for success messages
SUCCESS_LEVEL = 25
logging.addLevelName(SUCCESS_LEVEL, "SUCCESS")


def _success(self, message, *args, **kwargs):
    if self.isEnabledFor(SUCCESS_LEVEL):
        self._log(SUCCESS_LEVEL, message, args, **kwargs)


logging.Logger.success = _success  # type: ignore


def get_logger(name: str = None) -> logging.Logger:
    """
    Get a logger for the calling module.

    Usage in any module:
        from utils.logger import get_logger
        logger = get_logger(__name__)

        logger.info("Starting chapter generation")
        logger.debug("beat_data=%s", beat_data)
        logger.warning("Continuity check found 3 issues")
        logger.error("LLM call failed", exc_info=True)
        logger.success("Chapter completed")
    """
    if name is None:
        import inspect
        frame = inspect.currentframe().f_back
        name = frame.f_globals.get("__name__", "novel_claude")

    return logging.getLogger(name)


def set_level(level: str):
    """Change console log level at runtime: DEBUG, INFO, WARNING, ERROR."""
    level_map = {
        "DEBUG": logging.DEBUG,
        "INFO": logging.INFO,
        "WARNING": logging.WARNING,
        "ERROR": logging.ERROR,
    }
    numeric = level_map.get(level.upper(), logging.INFO)
    root = logging.getLogger()
    for h in root.handlers:
        if isinstance(h, ColoredConsoleHandler):
            h.setLevel(numeric)
            print(f"[Log] Console level set to {level.upper()}")


def get_log_path() -> Path:
    """Return current log file path for inspection."""
    return LOG_FILE
