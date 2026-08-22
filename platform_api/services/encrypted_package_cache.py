"""Short-lived in-process cache of CXA1 ciphertext packages.

Segment requests used to download the whole object from storage for every chunk.
The cache is ciphertext only. It never stores a content key or plaintext MP3.
"""

from __future__ import annotations

import asyncio
import time
from collections import OrderedDict
from collections.abc import Awaitable, Callable

_TTL_SECONDS = 90.0
_MAX_PACKAGES = 8
_lock = asyncio.Lock()
_cache: OrderedDict[str, tuple[float, bytes]] = OrderedDict()


def clear_packaged_blob_cache() -> None:
    _cache.clear()


def packaged_blob_cache_stats() -> dict[str, int]:
    return {"size": len(_cache), "max": _MAX_PACKAGES}


async def get_packaged_blob(
    storage_key: str,
    loader: Callable[[], Awaitable[bytes | None]],
) -> bytes | None:
    key = (storage_key or "").strip()
    if not key:
        return await loader()
    now = time.monotonic()
    async with _lock:
        hit = _cache.get(key)
        if hit is not None and hit[0] > now:
            _cache.move_to_end(key)
            return hit[1]
        if hit is not None:
            _cache.pop(key, None)
    blob = await loader()
    if not blob:
        return blob
    async with _lock:
        _cache[key] = (time.monotonic() + _TTL_SECONDS, blob)
        _cache.move_to_end(key)
        while len(_cache) > _MAX_PACKAGES:
            _cache.popitem(last=False)
    return blob
