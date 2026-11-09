"""Persist multipart upload state so an interrupted transfer resumes.

A crash or a closed app used to restart the whole file from part 1. We already
know which parts landed (ETags), so store them per file version and skip those
on the next attempt.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path

STATE_FILE_NAME = "publish_upload_state.json"
MIN_REMAINING_SECONDS = 6 * 60 * 60
# B2 keeps an unfinished multipart upload for days; a day is long enough to
# resume after a crash without keeping state for uploads the user abandoned.
UPLOAD_STATE_TTL_SECONDS = 24 * 60 * 60


@dataclass(frozen=True, slots=True)
class UploadState:
    key: str
    upload_id: str
    part_size: int
    part_count: int
    parts: dict[int, str] = field(default_factory=dict)
    expires_at: float = 0.0

    def missing_parts(self) -> list[int]:
        return [n for n in range(1, self.part_count + 1) if n not in self.parts]

    def next_batch(self, size: int) -> list[int]:
        missing = self.missing_parts()
        return missing[: max(1, int(size))]


def state_path() -> Path:
    override = os.environ.get("CAMXORA_UPLOAD_STATE_PATH", "").strip()
    if override:
        return Path(override)
    root = os.environ.get("LOCALAPPDATA") or os.environ.get("XDG_CACHE_HOME")
    base = Path(root) if root else Path.home() / ".cache"
    return base / "Camxora" / STATE_FILE_NAME


def _key(path: str) -> str:
    return str(path or "").strip().replace("\\", "/").lower()


def _load_raw() -> dict[str, dict]:
    try:
        data = json.loads(state_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _save_raw(data: dict[str, dict]) -> None:
    try:
        target = state_path()
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(data), encoding="utf-8")
    except OSError:
        pass


def load_state(path: str, *, size_bytes: int, mtime: float, now: float) -> UploadState | None:
    entry = _load_raw().get(_key(path))
    if not isinstance(entry, dict):
        return None
    try:
        if int(entry.get("size_bytes") or -1) != int(size_bytes):
            return None
        if abs(float(entry.get("mtime") or 0) - float(mtime)) > 1:
            return None
        expires_at = float(entry.get("expires_at") or 0)
        parts = {
            int(number): str(etag)
            for number, etag in (entry.get("parts") or {}).items()
            if str(etag).strip()
        }
        state = UploadState(
            key=str(entry.get("key") or ""),
            upload_id=str(entry.get("upload_id") or ""),
            part_size=int(entry.get("part_size") or 0),
            part_count=int(entry.get("part_count") or 0),
            parts=parts,
            expires_at=expires_at,
        )
    except (TypeError, ValueError):
        return None
    if not state.key or not state.upload_id or state.part_size <= 0 or state.part_count <= 0:
        return None
    if expires_at - now < MIN_REMAINING_SECONDS:
        return None
    return state


def save_state(
    path: str,
    *,
    size_bytes: int,
    mtime: float,
    state: UploadState,
    now: float,
    ttl_seconds: int,
) -> None:
    data = _load_raw()
    data[_key(path)] = {
        "size_bytes": int(size_bytes),
        "mtime": float(mtime),
        "key": state.key,
        "upload_id": state.upload_id,
        "part_size": int(state.part_size),
        "part_count": int(state.part_count),
        "parts": {str(number): etag for number, etag in state.parts.items()},
        "expires_at": float(now) + int(ttl_seconds),
    }
    _save_raw(data)


def clear_state(path: str) -> None:
    data = _load_raw()
    if data.pop(_key(path), None) is not None:
        _save_raw(data)
