"""Shared marketplace preview image loader with cache and bounded concurrency.

Prevents N+1 serial fetches from template cards, keeps work off the UI thread,
and drops stale completions after filter/page changes.
"""

from __future__ import annotations

import hashlib
import threading
from concurrent.futures import Future, ThreadPoolExecutor
from pathlib import Path
import httpx
from PySide6.QtCore import QObject, Signal

from shared.lib.app_paths import get_user_data_dir


_MAX_WORKERS = 4
_MEMORY_CACHE_LIMIT = 64
_REQUEST_TIMEOUT = 10.0


def get_marketplace_preview_cache_dir() -> Path:
    path = get_user_data_dir() / "marketplace-previews"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _cache_key(url: str) -> str:
    return hashlib.sha256(url.encode("utf-8")).hexdigest()


class MarketplacePreviewLoader(QObject):
    """Loads preview bytes with memory+disk cache and a shared worker pool.

    Signals:
        loaded(item_id, data, generation): Preview bytes ready for a request gen.
        failed(item_id, generation): Load failed for a request gen.
    """

    loaded = Signal(str, bytes, int)
    failed = Signal(str, int)

    def __init__(
        self,
        *,
        cache_dir: Path | None = None,
        max_workers: int = _MAX_WORKERS,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._cache_dir = cache_dir or get_marketplace_preview_cache_dir()
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        self._memory: dict[str, bytes] = {}
        self._memory_order: list[str] = []
        self._lock = threading.Lock()
        self._generation = 0
        self._inflight: dict[str, Future[bytes | None]] = {}
        self._executor = ThreadPoolExecutor(
            max_workers=max(1, max_workers),
            thread_name_prefix="mkt-preview",
        )

    @property
    def generation(self) -> int:
        return self._generation

    def begin_generation(self) -> int:
        """Bump generation so in-flight completions for old pages are ignored."""
        with self._lock:
            self._generation += 1
            return self._generation

    def shutdown(self) -> None:
        self.begin_generation()
        self._executor.shutdown(wait=False, cancel_futures=True)

    def request(self, item_id: str, url: str, generation: int) -> None:
        """Request preview bytes for ``item_id`` at ``url`` for ``generation``."""
        candidate = (url or "").strip()
        if not candidate:
            self.failed.emit(item_id, generation)
            return

        cached = self._get_memory(candidate)
        if cached is not None:
            self.loaded.emit(item_id, cached, generation)
            return

        disk = self._read_disk(candidate)
        if disk is not None:
            self._put_memory(candidate, disk)
            self.loaded.emit(item_id, disk, generation)
            return

        with self._lock:
            if generation != self._generation:
                return
            existing = self._inflight.get(candidate)
            if existing is not None and not existing.done():
                existing.add_done_callback(
                    lambda fut, iid=item_id, gen=generation, u=candidate: self._on_future_done(
                        fut, iid, u, gen
                    )
                )
                return
            future = self._executor.submit(self._fetch_url, candidate)
            self._inflight[candidate] = future

        future.add_done_callback(
            lambda fut, iid=item_id, gen=generation, u=candidate: self._on_future_done(
                fut, iid, u, gen
            )
        )

    def _on_future_done(
        self,
        future: Future[bytes | None],
        item_id: str,
        url: str,
        generation: int,
    ) -> None:
        with self._lock:
            self._inflight.pop(url, None)
            current_gen = self._generation
        if generation != current_gen:
            return
        try:
            data = future.result()
        except Exception:
            data = None
        if data:
            self._put_memory(url, data)
            self._write_disk(url, data)
            self.loaded.emit(item_id, data, generation)
        else:
            self.failed.emit(item_id, generation)

    def _fetch_url(self, url: str) -> bytes | None:
        try:
            resp = httpx.get(url, timeout=_REQUEST_TIMEOUT)
            if resp.status_code == 200 and resp.content:
                return bytes(resp.content)
        except Exception:
            return None
        return None

    def _get_memory(self, url: str) -> bytes | None:
        key = _cache_key(url)
        with self._lock:
            data = self._memory.get(key)
            if data is None:
                return None
            if key in self._memory_order:
                self._memory_order.remove(key)
            self._memory_order.append(key)
            return data

    def _put_memory(self, url: str, data: bytes) -> None:
        key = _cache_key(url)
        with self._lock:
            self._memory[key] = data
            if key in self._memory_order:
                self._memory_order.remove(key)
            self._memory_order.append(key)
            while len(self._memory_order) > _MEMORY_CACHE_LIMIT:
                old = self._memory_order.pop(0)
                self._memory.pop(old, None)

    def _disk_path(self, url: str) -> Path:
        return self._cache_dir / f"{_cache_key(url)}.bin"

    def _read_disk(self, url: str) -> bytes | None:
        path = self._disk_path(url)
        try:
            if path.is_file():
                data = path.read_bytes()
                return data if data else None
        except OSError:
            return None
        return None

    def _write_disk(self, url: str, data: bytes) -> None:
        path = self._disk_path(url)
        try:
            path.write_bytes(data)
        except OSError:
            pass


def close_loader(loader: MarketplacePreviewLoader | None) -> None:
    if loader is not None:
        loader.shutdown()
