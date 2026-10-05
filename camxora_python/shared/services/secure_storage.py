"""Encrypted local key-value store — mirrors Electron secureStorage IPC."""

from __future__ import annotations

import json
import os
from pathlib import Path

from shared.services.build_config import get_bundled_api_base_url, is_api_url_locked
from shared.services.dpapi import dpapi_decrypt_from_base64, dpapi_encrypt_to_base64

TOKENS_STORAGE_KEY = "camxora.auth.tokens"
API_BASE_URL_KEY = "camxora.apiBaseUrl"
LAST_USER_ID_KEY = "camxora.auth.lastUserId"
DEFAULT_API_BASE_URL = "http://localhost:8000/api/v3"


class SecureStorage:
    """DPAPI-backed secure store persisted as encrypted JSON entries."""

    def __init__(self, store_path: Path | None = None) -> None:
        if store_path is None:
            base = Path(os.environ.get("LOCALAPPDATA", Path.home()))
            store_path = base / "Camxora" / "camxora-secure-store.json"
        self._path = store_path
        self._data: dict[str, str] = {}
        self._load()

    @property
    def path(self) -> Path:
        return self._path

    def get(self, key: str) -> str | None:
        return self._data.get(key)

    def set(self, key: str, value: str) -> None:
        self._data[key] = value
        self._save()

    def remove(self, key: str) -> None:
        if key in self._data:
            del self._data[key]
            self._save()

    def clear(self) -> None:
        self._data.clear()
        self._save()

    def get_api_base_url(self) -> str:
        bundled = get_bundled_api_base_url()
        if bundled:
            return bundled
        value = self.get(API_BASE_URL_KEY)
        if value and value.strip():
            return value.strip().rstrip("/")
        return DEFAULT_API_BASE_URL

    def set_api_base_url(self, url: str) -> None:
        if is_api_url_locked():
            return
        cleaned = url.strip().rstrip("/")
        if cleaned:
            self._data[API_BASE_URL_KEY] = cleaned
            self._save()

    def is_api_url_locked(self) -> bool:
        return is_api_url_locked()

    def _load(self) -> None:
        if not self._path.is_file():
            return
        try:
            encrypted = self._path.read_text(encoding="utf-8").strip()
            if not encrypted:
                return
            raw = dpapi_decrypt_from_base64(encrypted)
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                self._data = {str(k): str(v) for k, v in parsed.items()}
            else:
                self._quarantine("store is not a JSON object")
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            # Never silently discard saved credentials: keep the unreadable file
            # (renamed) so it can be recovered, and start empty in memory. A later
            # save writes a fresh file instead of overwriting the original.
            self._quarantine(str(exc))

    def _quarantine(self, reason: str) -> None:
        import time

        try:
            target = self._path.with_name(f"{self._path.name}.corrupt-{int(time.time())}")
            self._path.replace(target)
            print(
                f"[secure_storage] unreadable store moved to {target}: {reason}",
                flush=True,
            )
        except OSError:
            # If we cannot move it, keep no data in memory but leave the file
            # untouched so a manual recovery is still possible.
            pass
        self._data = {}

    def _save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(self._data, separators=(",", ":"))
        encrypted = dpapi_encrypt_to_base64(payload)
        tmp = self._path.with_suffix(".tmp")
        tmp.write_text(encrypted, encoding="utf-8")
        tmp.replace(self._path)
