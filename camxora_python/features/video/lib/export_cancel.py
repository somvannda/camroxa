"""Cooperative export cancel via a per-job flag file (daemon + subprocess)."""

from __future__ import annotations

import os
import tempfile
import uuid
from pathlib import Path


CANCEL_ENV = "CAMXORA_EXPORT_CANCEL_PATH"


def new_cancel_path() -> str:
    """Return a unique cancel-flag path under the system temp directory."""
    name = f"camxora_export_cancel_{uuid.uuid4().hex}.flag"
    return str(Path(tempfile.gettempdir()) / name)


def request_export_cancel(path: str | None) -> None:
    text = str(path or "").strip()
    if not text:
        return
    try:
        Path(text).write_text("1", encoding="utf-8")
    except OSError:
        pass


def clear_export_cancel(path: str | None) -> None:
    text = str(path or "").strip()
    if not text:
        return
    try:
        Path(text).unlink(missing_ok=True)
    except OSError:
        pass


def export_cancel_requested(path: str | None = None) -> bool:
    """True when the cancel flag exists (path arg or CAMXORA_EXPORT_CANCEL_PATH)."""
    text = str(path or os.environ.get(CANCEL_ENV) or "").strip()
    if not text:
        return False
    try:
        return Path(text).is_file()
    except OSError:
        return False
