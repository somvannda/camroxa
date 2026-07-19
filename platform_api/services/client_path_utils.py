"""Helpers for desktop client filesystem paths stored in the platform DB."""

from __future__ import annotations

import re
from pathlib import Path

_WINDOWS_ABS_PATH_RE = re.compile(r"^[A-Za-z]:[\\/]")
_LINUX_PREFIXED_WINDOWS_PATH_RE = re.compile(r".*?([A-Za-z]:[\\/].+)$")


def is_windows_absolute_path(path: str) -> bool:
    text = str(path or "").strip()
    return bool(_WINDOWS_ABS_PATH_RE.match(text))


def join_client_output_path(run_dir: str, filename: str) -> str:
    """Join a run directory with a filename without corrupting Windows paths on Linux."""
    base = str(run_dir or "").strip().rstrip("/\\")
    name = str(filename or "").strip().lstrip("/\\")
    if not base:
        return name
    if not name:
        return base
    if is_windows_absolute_path(base):
        return f"{base}\\{name}"
    return str((Path(base).expanduser() / name).resolve())


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
