"""Guaranteed terminal output for Platform API logs."""

from __future__ import annotations

import logging
import sys
from typing import Any

_CONFIGURED = False


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
    """Upgrade root logging so every platform_api logger flushes to the terminal."""
    global _CONFIGURED
    if _CONFIGURED:
        return

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    root = logging.getLogger()
    root.setLevel(logging.INFO)

    replaced = False
    for index, handler in enumerate(root.handlers):
        if isinstance(handler, logging.StreamHandler):
            stream = handler.stream
            replacement = FlushingStreamHandler(stream)
            replacement.setFormatter(handler.formatter or formatter)
            replacement.setLevel(handler.level)
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
        logging.getLogger(name).setLevel(logging.INFO)

    _CONFIGURED = True


def short_id(value: Any, *, length: int = 8) -> str:
    text = str(value or "").strip()
    return text[:length] if text else "—"
