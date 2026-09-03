"""Central logging setup — console + rotating file under ~/.camxora/logs/."""

from __future__ import annotations

import logging
import os
import sys
import threading
import traceback
from logging.handlers import RotatingFileHandler
from pathlib import Path

_CONFIGURED = False
LOG_DIR = Path.home() / ".camxora" / "logs"
LOG_FILE = LOG_DIR / "camxora.log"

# Environment overrides (all default to DEBUG for full visibility):
#   CAMXORA_LOG_LEVEL          — sets both console + file when specific vars omitted
#   CAMXORA_LOG_CONSOLE_LEVEL  — stderr console output
#   CAMXORA_LOG_FILE_LEVEL     — rotating file output
# Valid values: DEBUG, INFO, WARNING, ERROR, CRITICAL


def log_file_path() -> Path:
    return LOG_FILE


def _level_from_env(var_name: str, default: str) -> int:
    raw = os.environ.get(var_name, default).strip().upper()
    level = getattr(logging, raw, None)
    if isinstance(level, int):
        return level
    return logging.DEBUG


def setup_logging(*, level: int | None = None) -> Path:
    """Configure root logger once. Returns the log file path."""
    global _CONFIGURED
    if _CONFIGURED:
        return LOG_FILE

    base = os.environ.get("CAMXORA_LOG_LEVEL", "DEBUG").strip().upper()
    console_level = level if level is not None else _level_from_env("CAMXORA_LOG_CONSOLE_LEVEL", base)
    file_level = level if level is not None else _level_from_env("CAMXORA_LOG_FILE_LEVEL", base)
    root_level = min(console_level, file_level)

    LOG_DIR.mkdir(parents=True, exist_ok=True)

    root = logging.getLogger()
    root.setLevel(root_level)

    fmt = logging.Formatter(
        "%(asctime)s %(levelname)-8s [%(threadName)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    file_handler = RotatingFileHandler(
        LOG_FILE,
        maxBytes=5 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8",
    )
    file_handler.setLevel(file_level)
    file_handler.setFormatter(fmt)
    root.addHandler(file_handler)

    console = logging.StreamHandler(sys.stderr)
    console.setLevel(console_level)
    console.setFormatter(fmt)
    root.addHandler(console)

    _install_exception_hooks()
    _CONFIGURED = True

    logging.getLogger(__name__).info(
        "Logging enabled — console=%s file=%s path=%s",
        logging.getLevelName(console_level),
        logging.getLevelName(file_level),
        LOG_FILE,
    )
    # Numba/librosa JIT traces at DEBUG are extremely noisy and slow imports.
    for logger_name in ("numba", "numba.core", "numba.core.byteflow", "numba.core.interpreter"):
        logging.getLogger(logger_name).setLevel(logging.WARNING)
    return LOG_FILE


def _install_exception_hooks() -> None:
    log = logging.getLogger("camxora.exceptions")

    def _sys_excepthook(exc_type, exc_value, exc_tb) -> None:
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_tb)
            return
        log.critical(
            "Uncaught exception:\n%s",
            "".join(traceback.format_exception(exc_type, exc_value, exc_tb)),
        )
        sys.__excepthook__(exc_type, exc_value, exc_tb)

    sys.excepthook = _sys_excepthook

    if hasattr(threading, "excepthook"):
        def _thread_excepthook(args) -> None:  # type: ignore[no-untyped-def]
            log.critical(
                "Uncaught thread exception in %s:\n%s",
                args.thread,
                "".join(traceback.format_exception(args.exc_type, args.exc_value, args.exc_traceback)),
            )

        threading.excepthook = _thread_excepthook  # type: ignore[assignment]


def install_qt_message_handler() -> None:
    """Route Qt debug/warning/critical messages into Python logging."""
    try:
        from PySide6.QtCore import QtMsgType, qInstallMessageHandler
    except ImportError:
        return

    qt_log = logging.getLogger("camxora.qt")

    def _handler(mode, context, message) -> None:  # type: ignore[no-untyped-def]
        if mode == QtMsgType.QtDebugMsg:
            qt_log.debug("%s", message)
        elif mode == QtMsgType.QtInfoMsg:
            qt_log.info("%s", message)
        elif mode == QtMsgType.QtWarningMsg:
            qt_log.warning("%s", message)
        elif mode == QtMsgType.QtCriticalMsg:
            qt_log.error("%s", message)
        elif mode == QtMsgType.QtFatalMsg:
            qt_log.critical("%s", message)

    qInstallMessageHandler(_handler)
