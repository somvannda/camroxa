"""Short-lived in-process cache of server-decrypted MP3 for licensed play streams."""

from __future__ import annotations

import time
from threading import Lock

_TTL_SECONDS = 90
_MAX_ENTRIES = 8
_cache: dict[str, tuple[float, bytes]] = {}
_lock = Lock()


def get_decrypted(cache_key: str) -> bytes | None:
    now = time.monotonic()
    with _lock:
        row = _cache.get(cache_key)
        if row is None:
            return None
        expires_at, data = row
        if expires_at <= now:
            _cache.pop(cache_key, None)
            return None
        return data


def put_decrypted(cache_key: str, data: bytes) -> None:
    now = time.monotonic()
    with _lock:
        if len(_cache) >= _MAX_ENTRIES:
            oldest = min(_cache.items(), key=lambda item: item[1][0])[0]
            _cache.pop(oldest, None)
        _cache[cache_key] = (now + _TTL_SECONDS, data)


def clear_decrypted_cache() -> None:
    with _lock:
        _cache.clear()
