"""Guaranteed terminal output for Platform API logs."""

from __future__ import annotations

import logging
import sys
from typing import Any

class FlushingStreamHandler(logging.StreamHandler):
    """Stream handler that always flushes so lines appear immediately in dev terminals."""

    def emit(self, record: logging.LogRecord) -> None:
        try:
            super().emit(record)
        finally:
            self.flush()
            stream = self.stream
            if stream is not None:
                try:
                    stream.flush()
                except Exception:
                    pass


def emit(category: str, message: str, *args: object, level: int = logging.INFO) -> None:
    """Emit progress through the platform_api logging tree only (no separate print stream)."""
    text = message % args if args else message
    logging.getLogger(f"platform_api.{category}").log(level, "[%s] %s", category, text)


def configure_terminal_logging() -> None:
    """Upgrade root logging so every platform_api logger flushes to the terminal.

    Deliberately idempotent and *re-asserting* rather than a one-shot: another
    library can re-configure logging at any time, and a logger left ``disabled``
    (or whose level sits above INFO) swallows every record without raising.
    That is exactly how the API lost all request/5xx lines in production —
    the journal held zero ``[access]`` entries for a week while the process
    looked healthy (2026-10-21).
    """
    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    root = logging.getLogger()
    root.disabled = False
    root.setLevel(logging.INFO)

    replaced = False
    for index, handler in enumerate(root.handlers):
        if isinstance(handler, logging.StreamHandler):
            stream = handler.stream
            replacement = FlushingStreamHandler(stream)
            replacement.setFormatter(handler.formatter or formatter)
            replacement.setLevel(logging.NOTSET)
            root.handlers[index] = replacement
            replaced = True
            break

    if not replaced:
        handler = FlushingStreamHandler(sys.stdout)
        handler.setFormatter(formatter)
        handler.setLevel(logging.INFO)
        root.addHandler(handler)

    for name in (
        "platform_api",
        "platform_api.music",
        "platform_api.credits",
        "platform_api.images",
        "platform_api.access",
        "uvicorn",
        "uvicorn.error",
        "uvicorn.access",
    ):
        logger = logging.getLogger(name)
        logger.disabled = False
        logger.setLevel(logging.INFO)


def short_id(value: Any, *, length: int = 8) -> str:
    text = str(value or "").strip()
    return text[:length] if text else "—"
