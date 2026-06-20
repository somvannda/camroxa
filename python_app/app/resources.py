from __future__ import annotations

import sys
from pathlib import Path


def python_app_dir() -> Path:
    base = getattr(sys, "_MEIPASS", None)
    if base:
        p = Path(base) / "python_app"
        if p.exists():
            return p
        return Path(base)
    return Path(__file__).resolve().parents[1]


def assets_dir() -> Path:
    return python_app_dir() / "assets"


def icon_path(icon_name: str) -> str:
    return str((assets_dir() / "icons" / str(icon_name)).resolve())


def lucide_icon_path(icon_name: str) -> str:
    return str((assets_dir() / "icons" / "lucide" / f"{icon_name}.svg").resolve())
