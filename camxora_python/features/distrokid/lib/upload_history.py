"""Local DistroKid upload history cache (+ fingerprint helpers)."""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def _default_history_path() -> Path:
    from shared.lib.app_paths import get_user_data_dir

    return get_user_data_dir() / "distrokid" / "upload_history.json"


def sha256_file(path: Path, *, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(chunk_size)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


class UploadHistory:
    """Machine-local cache of DistroKid uploads (platform_api is source of truth when online)."""

    def __init__(self, history_file: Path | None = None) -> None:
        self.history_file = history_file or _default_history_path()
        self._history: list[dict[str, Any]] = []
        self._load()

    def _load(self) -> None:
        if not self.history_file.exists():
            self._history = []
            return
        try:
            raw = json.loads(self.history_file.read_text(encoding="utf-8"))
            self._history = raw if isinstance(raw, list) else []
        except (OSError, json.JSONDecodeError) as exc:
            logger.error("Error loading DistroKid upload history: %s", exc)
            self._history = []

    def _save(self) -> None:
        try:
            self.history_file.parent.mkdir(parents=True, exist_ok=True)
            self.history_file.write_text(
                json.dumps(self._history, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        except OSError as exc:
            logger.error("Error saving DistroKid upload history: %s", exc)

    def record_success(
        self,
        *,
        directory_path: str,
        album_name: str,
        track_count: int = 0,
        tracks: list[dict[str, Any]] | None = None,
        batch_id: str = "",
    ) -> None:
        entry: dict[str, Any] = {
            "directory": directory_path,
            "album_name": album_name,
            "track_count": track_count,
            "batch_id": batch_id,
            "tracks": tracks or [],
            "uploaded_at": datetime.now().isoformat(),
            "status": "success",
        }
        self._history.append(entry)
        self._save()

    def is_uploaded(self, directory_path: str) -> bool:
        try:
            normalized = str(Path(directory_path).resolve())
        except OSError:
            normalized = str(directory_path)
        for entry in self._history:
            if entry.get("status") != "success":
                continue
            try:
                existing = str(Path(str(entry.get("directory") or "")).resolve())
            except OSError:
                existing = str(entry.get("directory") or "")
            if existing == normalized:
                return True
        return False

    def find_duplicate(
        self,
        *,
        album_name: str,
        track_title: str,
        wav_byte_size: int | None = None,
        wav_sha256: str | None = None,
    ) -> dict[str, Any] | None:
        album_key = album_name.strip().lower()
        title_key = track_title.strip().lower()
        for entry in reversed(self._history):
            if entry.get("status") != "success":
                continue
            if str(entry.get("album_name") or "").strip().lower() != album_key:
                continue
            for track in entry.get("tracks") or []:
                if not isinstance(track, dict):
                    continue
                if str(track.get("title") or "").strip().lower() != title_key:
                    continue
                if wav_sha256 and track.get("wav_sha256") == wav_sha256:
                    return entry
                if wav_byte_size is not None and int(track.get("wav_byte_size") or -1) == int(wav_byte_size):
                    return entry
                if wav_sha256 is None and wav_byte_size is None:
                    return entry
        return None

    def get_upload_date(self, directory_path: str) -> str | None:
        try:
            normalized = str(Path(directory_path).resolve())
        except OSError:
            normalized = str(directory_path)
        for entry in reversed(self._history):
            if entry.get("status") != "success":
                continue
            try:
                existing = str(Path(str(entry.get("directory") or "")).resolve())
            except OSError:
                existing = str(entry.get("directory") or "")
            if existing == normalized:
                value = entry.get("uploaded_at")
                return str(value) if value else None
        return None

    def get_all(self) -> list[dict[str, Any]]:
        return list(self._history)

    def get_successful(self) -> list[dict[str, Any]]:
        return [e for e in self._history if e.get("status") == "success"]

    def clear(self) -> None:
        self._history = []
        self._save()
