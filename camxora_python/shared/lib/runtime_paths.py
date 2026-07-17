"""Runtime install location helpers for packaged vs development builds."""

from __future__ import annotations

import os
import sys
from pathlib import Path


def is_frozen_runtime() -> bool:
    return bool(getattr(sys, "frozen", False))


def get_install_dir() -> Path | None:
    """Directory containing the running desktop app binaries."""
    if is_frozen_runtime():
        return Path(sys.executable).resolve().parent

    entry = Path(sys.argv[0]).resolve()
    if entry.suffix.lower() in {".exe", ".bat", ".cmd"}:
        return entry.parent
    return None


def get_launch_executable() -> Path | None:
    if is_frozen_runtime():
        return Path(sys.executable).resolve()

    install_dir = get_install_dir()
    if install_dir is None:
        return None
    for name in ("Camxora.exe", "MusicGenerator.exe", "camxora.exe"):
        candidate = install_dir / name
        if candidate.is_file():
            return candidate
    return None


def get_updates_work_dir() -> Path:
    from shared.lib.app_paths import get_user_data_dir

    path = get_user_data_dir() / "updates"
    path.mkdir(parents=True, exist_ok=True)
    return path


def allow_zip_swap_update() -> bool:
    return is_frozen_runtime() or os.environ.get("CAMXORA_ALLOW_ZIP_UPDATE", "").strip() == "1"
