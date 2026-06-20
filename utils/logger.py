"""
Novel-Claude Fusion — Centralized Logging System (v2)

Daily rotating logs + comprehensive step-level execution tracing.
Configure once at CLI/WebUI startup, used everywhere via get_logger(__name__).

Features:
  - Daily log files: ~/.novel_claude_logs/novel_claude_2026-06-19.log
  - Per-step execution tracing: log_step(), @trace_step decorator
  - Dual output: colored console + rotating daily file
  - Session markers for debugging across restarts
  - Runtime level control: set_level("DEBUG")

Design: 2025-2026 Python logging best practices
  - TimedRotatingFileHandler (daily rotation, 30-day retention)
  - RotatingFileHandler (5MB safety cap within same day)
  - Module-level loggers via `get_logger(__name__)`
"""

from __future__ import annotations

import functools
import logging
import logging.config
import logging.handlers
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Optional, Callable


# ── config ────────────────────────────────────────────────────────────────────

LOG_DIR = Path(os.path.expanduser("~/.novel_claude_logs"))
LOG_DIR.mkdir(parents=True, exist_ok=True)

# Daily file: novel_claude_2026-06-19.log
LOG_FILE_PATTERN = str(LOG_DIR / "novel_claude")

# Formats
CONSOLE_FORMAT = "%(message)s"
FILE_FORMAT = (
    "%(asctime)s.%(msecs)03d | %(levelname)-7s | %(name)-25s | "
    "%(funcName)s:%(lineno)d | %(message)s"
)
FILE_DATEFMT = "%H:%M:%S"

# Rotation: daily primary + 5MB safety cap
DAILY_BACKUP_COUNT = 30    # keep 30 days
SIZE_MAX_BYTES = 5 * 1024 * 1024  # 5 MB safety cap
SIZE_BACKUP_COUNT = 3

SESSION_START = "═" * 72
SESSION_END = "─" * 72


# ── colored console handler ──────────────────────────────────────────────────

class ColoredConsoleHandler(logging.StreamHandler):
    """Console handler with ANSI colors matching old print() style."""

    COLORS = {
        "DEBUG": "\033[90m",
        "INFO": "\033[0m",
        "WARNING": "\033[33m",
        "ERROR": "\033[31m",
        "CRITICAL": "\033[1;31m",
        "SUCCESS": "\033[32m",
        "STEP": "\033[36m",        # cyan for step markers
    }
    RESET = "\033[0m"

    def emit(self, record):
        color = self.COLORS.get(record.levelname, "")
        msg = self.format(record)
        try:
            self.stream.write(f"{color}{msg}{self.RESET}\n")
            self.flush()
        except UnicodeEncodeError:
            # Windows GBK 控制台无法编码 ✓ 等 Unicode 字符时，用纯 ASCII 回退
            safe_msg = msg.encode(self.stream.encoding or 'ascii', errors='replace').decode(self.stream.encoding or 'ascii', errors='replace')
            self.stream.write(f"{color}{safe_msg}{self.RESET}\n")
            self.flush()


# ── custom levels ─────────────────────────────────────────────────────────────

STEP_LEVEL = 21     # between INFO(20) and WARNING(30)
logging.addLevelName(STEP_LEVEL, "STEP")
SUCCESS_LEVEL = 25
logging.addLevelName(SUCCESS_LEVEL, "SUCCESS")


def _step(self, message, *args, **kwargs):
    if self.isEnabledFor(STEP_LEVEL):
        self._log(STEP_LEVEL, message, args, **kwargs)


def _success(self, message, *args, **kwargs):
    if self.isEnabledFor(SUCCESS_LEVEL):
        self._log(SUCCESS_LEVEL, message, args, **kwargs)


logging.Logger.step = _step
logging.Logger.success = _success


# ── session tracking ──────────────────────────────────────────────────────────

class SessionFilter(logging.Filter):
    """Injects session_id into every log record."""
    session_id: str = ""

    @classmethod
    def new_session(cls):
        cls.session_id = datetime.now().strftime("%Y%m%d-%H%M%S")

    def filter(self, record):
        record.session_id = self.session_id or "-"
        return True


# ── setup ─────────────────────────────────────────────────────────────────────

_is_configured = False

# Store handlers for runtime access
_console_handler: Optional[ColoredConsoleHandler] = None
_daily_handler: Optional[logging.handlers.TimedRotatingFileHandler] = None


def setup_logging(level: int = logging.DEBUG, log_dir: Path = None):
    """
    Configure logging ONCE at application startup.
    Creates daily-rotating log files + console output.

    Log files: ~/.novel_claude_logs/novel_claude_2026-06-19.log
    """
    global _is_configured, _console_handler, _daily_handler
    if _is_configured:
        return

    SessionFilter.new_session()

    # Daily rotation: new file each midnight, keep 30 days
    daily_handler = logging.handlers.TimedRotatingFileHandler(
        filename=LOG_FILE_PATTERN,
        when="midnight",
        interval=1,
        backupCount=DAILY_BACKUP_COUNT,
        encoding="utf-8",
    )
    daily_handler.suffix = "%Y-%m-%d"  # appended to filename
    daily_handler.setLevel(logging.DEBUG)
    daily_handler.setFormatter(logging.Formatter(FILE_FORMAT, datefmt=FILE_DATEFMT))
    daily_handler.addFilter(SessionFilter())

    # Console handler
    console_handler = ColoredConsoleHandler(stream=sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(logging.Formatter(CONSOLE_FORMAT))

    # Configure root logger
    root = logging.getLogger()
    root.setLevel(logging.DEBUG)
    root.handlers.clear()
    root.addHandler(console_handler)
    root.addHandler(daily_handler)

    # Suppress noisy third-party
    for lib in ("openai", "httpx", "httpcore", "urllib3", "chromadb",
                "sentence_transformers", "asyncio", "uvicorn"):
        logging.getLogger(lib).setLevel(logging.WARNING)

    _is_configured = True
    _console_handler = console_handler
    _daily_handler = daily_handler

    # Write session header
    root.info(SESSION_START)
    root.info("  Session: %s  |  PID: %d  |  Python: %s",
              SessionFilter.session_id, os.getpid(), sys.version.split()[0])
    root.info("  Log: %s", _daily_handler.baseFilename)
    root.info(SESSION_START)


# ── public API ────────────────────────────────────────────────────────────────

def get_logger(name: str = None) -> logging.Logger:
    """Get a logger for the calling module."""
    if name is None:
        import inspect
        frame = inspect.currentframe().f_back
        name = frame.f_globals.get("__name__", "novel_claude")
    return logging.getLogger(name)


def set_level(level: str):
    """Change console log level at runtime."""
    level_map = {
        "DEBUG": logging.DEBUG, "INFO": logging.INFO,
        "WARNING": logging.WARNING, "ERROR": logging.ERROR,
    }
    numeric = level_map.get(level.upper(), logging.INFO)
    if _console_handler:
        _console_handler.setLevel(numeric)
        print(f"[Log] Console level -> {level.upper()}")


def get_log_path() -> Path:
    """Return current daily log file path."""
    if _daily_handler:
        return Path(_daily_handler.baseFilename)
    return LOG_DIR / "novel_claude.log"


def shutdown():
    """Write session end marker and close handlers."""
    root = logging.getLogger()
    root.info(SESSION_END)
    root.info("  Session ended: %s", datetime.now().isoformat())
    root.info(SESSION_END)
    logging.shutdown()


# ── step-level tracing ────────────────────────────────────────────────────────

def log_step(operation: str, **details):
    """
    Record a step in the execution pipeline.
    Use for key operations: generation, saving, gate evaluation, etc.

    Usage:
        log_step("Chapter generation", chapter_id=5, volume_id=1, words=5230)
        log_step("Quality gate", verdict="PASS", score=82, round=1)
    """
    detail_str = " | ".join(f"{k}={v}" for k, v in details.items())
    if detail_str:
        msg = f"[{operation}] {detail_str}"
    else:
        msg = f"[{operation}]"
    logger = get_logger("steps")
    logger.step(msg)


def trace_step(func: Callable = None, *, log_args: bool = True, log_result: bool = False):
    """
    Decorator: auto-log function entry, exit, and exceptions.
    Use on key pipeline functions for automatic step tracing.

    Usage:
        @trace_step
        def generate_chapter_content(volume_id, chapter_id, ...):
            ...

        @trace_step(log_result=True)
        def evaluate_quality(continuity_findings, ...):
            ...
    """
    def decorator(f):
        @functools.wraps(f)
        def wrapper(*args, **kwargs):
            logger = get_logger(f.__module__)
            func_name = f.__qualname__

            # Build arg string for logging
            if log_args:
                # Skip 'self' for methods
                arg_dict = {}
                arg_names = f.__code__.co_varnames[:f.__code__.co_argcount]
                for i, val in enumerate(args):
                    name = arg_names[i] if i < len(arg_names) else f"arg{i}"
                    if name != "self":
                        arg_dict[name] = repr(val)[:80]
                arg_dict.update({k: repr(v)[:80] for k, v in kwargs.items()})
                arg_str = ", ".join(f"{k}={v}" for k, v in list(arg_dict.items())[:5])
            else:
                arg_str = ""

            logger.debug("-> %s(%s)", func_name, arg_str)
            start = time.perf_counter()

            try:
                result = f(*args, **kwargs)
                elapsed = time.perf_counter() - start
                if log_result:
                    logger.debug("<- %s -> %s (%.3fs)", func_name, repr(result)[:120], elapsed)
                else:
                    logger.debug("<- %s (%.3fs)", func_name, elapsed)
                return result
            except Exception as e:
                elapsed = time.perf_counter() - start
                logger.error("!! %s FAILED: %s (%.3fs)", func_name, e, elapsed, exc_info=True)
                raise

        return wrapper

    if func is not None:
        return decorator(func)
    return decorator
