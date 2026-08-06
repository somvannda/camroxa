"""Helpers for desktop client filesystem paths stored in the platform DB."""

from __future__ import annotations

import re
from pathlib import Path

_WINDOWS_ABS_PATH_RE = re.compile(r"^[A-Za-z]:[\\/]")
_LINUX_PREFIXED_WINDOWS_PATH_RE = re.compile(r".*?([A-Za-z]:[\\/].+)$")


def is_windows_absolute_path(path: str) -> bool:
    text = str(path or "").strip()
    return bool(_WINDOWS_ABS_PATH_RE.match(text))


def is_portable_run_relative_path(path: str) -> bool:
    """True for ``channel\\date_album`` style keys (no drive / UNC / POSIX root)."""
    text = str(path or "").strip().replace("/", "\\")
    if not text or is_windows_absolute_path(text) or text.startswith("\\\\") or text.startswith("/"):
        return False
    # Drive-letter absolute already excluded; reject single-segment filenames.
    parts = [part for part in Path(text).parts if part not in ("/", "\\", "")]
    return len(parts) >= 1


def join_client_output_path(run_dir: str, filename: str) -> str:
    """Join a run directory with a filename without corrupting client paths on Linux.

    Absolute Windows run dirs stay Windows-shaped.
    Portable relative keys (``channel\\date_album``) stay relative — never
    ``Path.resolve()`` against the API host cwd (that used to invent
    ``/opt/camxora/.../bass-drive/...`` paths).
    """
    base = str(run_dir or "").strip().rstrip("/\\")
    name = str(filename or "").strip().lstrip("/\\")
    if not base:
        return name
    if not name:
        return base
    if is_windows_absolute_path(base):
        return f"{base}\\{name}"
    # Portable relative run key — keep Windows-style separators for the desktop.
    normalized_base = base.replace("/", "\\")
    return f"{normalized_base}\\{name}"


def denormalize_cross_platform_path(path: str) -> str:
    """Recover a client path when a Linux server cwd was prefixed to a Windows path."""
    text = str(path or "").strip()
    if not text:
        return text
    if is_windows_absolute_path(text):
        return text
    match = _LINUX_PREFIXED_WINDOWS_PATH_RE.match(text.replace("/", "\\"))
    if match:
        return match.group(1)
    return text
