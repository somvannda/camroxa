"""Remember media we already pushed to storage so a retry does not re-upload.

Each click of "Upload to YouTube" used to start a fresh multipart upload of the
whole original (2.8 GB in the reported case). The signed media URL stays valid
for days, so cache it per file (path + size + mtime) and reuse it.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

CACHE_FILE_NAME = "publish_asset_cache.json"
CACHE_TTL_SECONDS = 6 * 24 * 60 * 60  # signed URLs live 7 days; keep a day of slack
MIN_REMAINING_SECONDS = 6 * 60 * 60


def cache_path() -> Path:
    override = os.environ.get("CAMXORA_PUBLISH_CACHE_PATH", "").strip()
    if override:
        return Path(override)
    root = os.environ.get("LOCALAPPDATA") or os.environ.get("XDG_CACHE_HOME")
    base = Path(root) if root else Path.home() / ".cache"
    return base / "Camxora" / CACHE_FILE_NAME


def _key(path: str) -> str:
    return str(path or "").strip().replace("\\", "/").lower()


def _load_raw() -> dict[str, dict]:
    try:
        data = json.loads(cache_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _save_raw(data: dict[str, dict]) -> None:
    try:
        target = cache_path()
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(data), encoding="utf-8")
    except OSError:
        pass


def lookup_media_url(path: str, *, size_bytes: int, mtime: float, now: float) -> str | None:
    """Return a still-valid media URL for this exact file version, if cached."""
    entry = _load_raw().get(_key(path))
    if not isinstance(entry, dict):
        return None
    try:
        if int(entry.get("size_bytes") or -1) != int(size_bytes):
            return None
        if abs(float(entry.get("mtime") or 0) - float(mtime)) > 1:
            return None
        expires_at = float(entry.get("expires_at") or 0)
    except (TypeError, ValueError):
        return None
    if expires_at - now < MIN_REMAINING_SECONDS:
        return None
    url = str(entry.get("media_url") or "").strip()
    return url or None


def store_media_url(
    path: str,
    *,
    size_bytes: int,
    mtime: float,
    media_url: str,
    now: float,
) -> None:
    url = str(media_url or "").strip()
    if not url:
        return
    data = _load_raw()
    data[_key(path)] = {
        "size_bytes": int(size_bytes),
        "mtime": float(mtime),
        "media_url": url,
        "expires_at": float(now) + CACHE_TTL_SECONDS,
    }
    _save_raw(data)


def forget_media_url(path: str) -> None:
    data = _load_raw()
    if data.pop(_key(path), None) is not None:
        _save_raw(data)
