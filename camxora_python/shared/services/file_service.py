"""Local filesystem helpers for desktop runtime inspection."""

from __future__ import annotations

import os
import webbrowser
from dataclasses import dataclass
from pathlib import Path

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}


def sanitize_local_path(target_path: str) -> str:
    """Fix paths polluted with a Linux server cwd prefix on Windows clients."""
    text = str(target_path or "").strip()
    if not text:
        return text
    if os.name == "nt" and text.startswith("/") and ":\\" in text.replace("/", "\\"):
        normalized = text.replace("/", "\\")
        marker = ":\\"
        idx = normalized.find(marker)
        if idx > 1:
            return normalized[idx - 1 :]
    return text


@dataclass(frozen=True, slots=True)
class DirectoryEntry:
    name: str
    is_directory: bool


def list_directory_entries(directory_path: str, *, max_results: int = 500) -> list[DirectoryEntry]:
    directory = Path(sanitize_local_path(directory_path.strip()))
    if not directory.is_dir():
        return []

    entries: list[DirectoryEntry] = []
    try:
        for index, child in enumerate(directory.iterdir()):
            if index >= max_results:
                break
            entries.append(DirectoryEntry(name=child.name, is_directory=child.is_dir()))
    except OSError:
        return []
    return entries


def list_directory_image_paths(directory_path: str, *, max_results: int = 50) -> list[str]:
    directory = Path(sanitize_local_path(directory_path.strip()))
    if not directory.is_dir():
        return []

    files: list[str] = []
    try:
        for index, child in enumerate(directory.iterdir()):
            if index >= max_results:
                break
            if child.is_file() and child.suffix.lower() in IMAGE_EXTENSIONS:
                files.append(str(child))
    except OSError:
        return []
    return files


def ensure_directory(directory_path: str) -> None:
    Path(directory_path.strip()).mkdir(parents=True, exist_ok=True)


def open_path(target_path: str) -> None:
    normalized = sanitize_local_path(str(target_path or "").strip())
    if not normalized:
        return
    path = Path(normalized)
    if not path.exists():
        from shared.services.app_logger import log_warn
        from shared.services.shell_status import emit_shell_status

        log_warn(f"Cannot open missing path: {normalized}", category="filesystem")
        emit_shell_status(f"File not found: {path.name}", tone="warning")
        return
    if os.name == "nt":
        os.startfile(normalized)  # type: ignore[attr-defined]
        return
    from shared.lib.subprocess_utils import run_hidden

    run_hidden(["xdg-open", normalized], check=False)


def read_file_bytes(target_path: str) -> bytes | None:
    normalized = sanitize_local_path(str(target_path or "").strip())
    if not normalized:
        return None
    path = Path(normalized)
    if not path.is_file():
        return None
    try:
        return path.read_bytes()
    except OSError:
        return None


def open_external_url(url: str) -> None:
    normalized = str(url or "").strip()
    if normalized:
        webbrowser.open(normalized)
