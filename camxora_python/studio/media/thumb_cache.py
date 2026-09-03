"""Persistent on-disk cache for timeline filmstrips and thumbnails."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

_FILMSTRIP_META_VERSION = 1


def persistent_cache_dir() -> Path:
    if os.name == "nt":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")) / "camxora_studio"
    else:
        base = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "camxora_studio"
    (base / "filmstrips").mkdir(parents=True, exist_ok=True)
    (base / "thumbs").mkdir(parents=True, exist_ok=True)
    return base


def media_cache_key(path: Path) -> str:
    resolved = str(path.resolve())
    try:
        stat = path.stat()
        payload = f"{resolved}:{stat.st_mtime_ns}:{stat.st_size}"
    except OSError:
        payload = resolved
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


def _filmstrip_meta_path(cache_key: str) -> Path:
    return persistent_cache_dir() / "filmstrips" / f"{cache_key}.json"


def load_cached_filmstrip(
    path: Path,
    *,
    frames: int,
    size: tuple[int, int],
) -> list[str] | None:
    cache_key = media_cache_key(path)
    meta_path = _filmstrip_meta_path(cache_key)
    if not meta_path.exists():
        return None
    try:
        data = json.loads(meta_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if data.get("version") != _FILMSTRIP_META_VERSION:
        return None
    if data.get("frames") != frames or tuple(data.get("size", [])) != size:
        return None
    paths = [str(p) for p in data.get("paths", [])]
    if not paths or not all(Path(p).exists() for p in paths):
        return None
    return paths


def save_cached_filmstrip(
    path: Path,
    *,
    frames: int,
    size: tuple[int, int],
    thumb_paths: list[str],
) -> None:
    if not thumb_paths:
        return
    cache_key = media_cache_key(path)
    meta_path = _filmstrip_meta_path(cache_key)
    meta_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": _FILMSTRIP_META_VERSION,
        "source": str(path.resolve()),
        "frames": frames,
        "size": list(size),
        "paths": thumb_paths,
    }
    meta_path.write_text(json.dumps(payload, indent=0), encoding="utf-8")
