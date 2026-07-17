"""Resolve packaged resource files for development and frozen builds."""

from __future__ import annotations

import sys
from pathlib import Path


def get_package_root() -> Path:
    """Return the camxora_python package root (or PyInstaller extract root)."""
    if getattr(sys, "frozen", False):
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            return Path(meipass)
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[2]


def _resource_candidate_roots() -> list[Path]:
    """Roots that may contain a ``resources/`` directory."""
    roots: list[Path] = [get_package_root()]
    if getattr(sys, "frozen", False):
        install_dir = Path(sys.executable).resolve().parent
        roots.extend(
            [
                install_dir / "_internal",
                install_dir,
            ]
        )
    # Preserve order, drop duplicates
    seen: set[Path] = set()
    unique: list[Path] = []
    for root in roots:
        resolved = root.resolve()
        if resolved not in seen:
            seen.add(resolved)
            unique.append(resolved)
    return unique


def get_resource_path(*parts: str) -> Path:
    """Return the first existing resource path, else the primary expected path."""
    relative = Path("resources", *parts)
    primary = get_package_root() / relative
    for root in _resource_candidate_roots():
        candidate = root / relative
        if candidate.is_file() or candidate.is_dir():
            return candidate
    return primary
