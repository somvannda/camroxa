"""Persist last-used directories for QFileDialog."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSettings

_SETTINGS_PATH = Path.home() / ".camxora" / "settings.ini"


def _settings() -> QSettings:
    _SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    return QSettings(str(_SETTINGS_PATH), QSettings.Format.IniFormat)


def last_open_dir(key: str) -> str:
    """Return a validated directory for dialog start paths, or empty string."""
    raw = _settings().value(f"file_dialog/{key}", "")
    if not raw:
        return ""
    path = Path(str(raw))
    return str(path) if path.is_dir() else ""


def set_last_open_dir(key: str, selected_paths: list[str] | str) -> None:
    """Remember the folder containing the first selected file or directory."""
    if isinstance(selected_paths, str):
        paths = [selected_paths] if selected_paths else []
    else:
        paths = selected_paths
    if not paths:
        return
    first = Path(paths[0])
    directory = first if first.is_dir() else first.parent
    if directory.is_dir():
        _settings().setValue(f"file_dialog/{key}", str(directory))
