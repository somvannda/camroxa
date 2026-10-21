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
    # Check the POSIX root on the raw text: normalising "/" to "\\" first turned
    # "/tmp/.../run" into "\\tmp\\...", which no longer looked rooted, so an
    # absolute POSIX path was misread as a portable key and the API host skipped
    # writing it.
    raw = str(path or "").strip()
    if not raw or raw.startswith("/") or is_windows_absolute_path(raw) or raw.startswith("\\\\"):
        return False
    # Drive-letter absolute already excluded; a key needs at least one segment.
    parts = [part for part in raw.replace("/", "\\").split("\\") if part]
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
    if base.startswith("/"):
        # POSIX absolute path - the API host's own output dir. Joining it as if it
        # were a portable run key turned "/tmp/.../run" into "\tmp\...\run", so the
        # file was written to a literal backslash-named path elsewhere.
        return f"{base.rstrip('/')}/{name}"
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
