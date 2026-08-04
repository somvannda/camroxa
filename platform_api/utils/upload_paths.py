"""Safe resolution of channel-profile upload paths under the repo uploads root."""

from __future__ import annotations

import os
from pathlib import Path


def project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def uploads_root() -> Path:
    return (project_root() / "uploads").resolve()


def resolve_upload_path(value: str | None) -> Path | None:
    """Resolve a stored upload path and reject anything outside ``uploads/``."""
    raw = str(value or "").strip()
    if not raw:
        return None
    p = Path(raw)
    candidate = (p if p.is_absolute() else (project_root() / p)).resolve()
    root = uploads_root()
    root_str = str(root)
    cand_str = str(candidate)
    if cand_str == root_str or not cand_str.startswith(root_str + os.sep):
        return None
    return candidate


def upload_path_exists(value: str | None) -> bool:
    path = resolve_upload_path(value)
    return path is not None and path.is_file()
