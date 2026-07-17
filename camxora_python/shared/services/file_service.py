"""Local filesystem helpers for desktop runtime inspection."""

from __future__ import annotations

import os
import webbrowser
from dataclasses import dataclass
from pathlib import Path

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}


@dataclass(frozen=True, slots=True)
class DirectoryEntry:
    name: str
    is_directory: bool


def list_directory_entries(directory_path: str, *, max_results: int = 500) -> list[DirectoryEntry]:
    directory = Path(directory_path.strip())
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
    directory = Path(directory_path.strip())
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
    normalized = str(target_path or "").strip()
    if not normalized:
        return
    if os.name == "nt":
        os.startfile(normalized)  # type: ignore[attr-defined]
        return
    from shared.lib.subprocess_utils import run_hidden

    run_hidden(["xdg-open", normalized], check=False)


def read_file_bytes(target_path: str) -> bytes | None:
    normalized = str(target_path or "").strip()
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
