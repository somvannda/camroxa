"""Regression tests: the pending-download poll must stay off the 30s hot path.

Heavy per-poll work (Suno reconcile, image-job healing, per-object B2 HEADs)
previously ran inline and pushed ``GET /music/downloads/pending`` past the
desktop client's 30s timeout, so clients stopped retrying failed MP3 downloads.
"""

from __future__ import annotations

import asyncio
import time
from uuid import uuid4

import pytest

from platform_api.services.batch_service import BatchService


class _PendingRepo:
    def __init__(self, rows):
        self._rows = rows

    async def list_pending_suno_downloads(self, *, user_id, limit, max_age_days):
        return list(self._rows)


def _service(repo) -> BatchService:
    return BatchService(
        batch_repo=repo,
        credit_service=None,  # type: ignore[arg-type]
        pricing_service=None,  # type: ignore[arg-type]
        generation_service=None,  # type: ignore[arg-type]
        profile_repo=None,  # type: ignore[arg-type]
        ai_routing_service=None,
    )


def _row(task_id, batch_id):
    return {
        "id": task_id,
        "song_id": uuid4(),
        "batch_id": batch_id,
        "batch_index": 0,
        "title": "Test Track",
        "ok_run_dir": "D:/Music/Primary",
        "alt_run_dir": "D:/Music/Secondary",
        "ok_run_dir_alt": "",
        "output_dir_ok": None,
        "output_dir_alt": None,
        "alt_profile_folder": None,
        "alt_profile_name": None,
        "audio_url_ok": "https://cdn.example.com/ok.mp3",
        "audio_id_ok": "clip-ok",
        "audio_url_alt": "https://cdn.example.com/alt.mp3",
        "audio_id_alt": "clip-alt",
        "downloaded_ok": False,
        "downloaded_alt": False,
    }


@pytest.mark.asyncio
async def test_pending_downloads_offload_reconcile_and_image_jobs(monkeypatch) -> None:
    task_id = uuid4()
    batch_id = uuid4()
    user_id = str(uuid4())
    service = _service(_PendingRepo([_row(task_id, batch_id)]))
    scheduled: dict[str, dict] = {}

    monkeypatch.setattr(
        service, "_schedule_pending_reconcile", lambda **kw: scheduled.setdefault("reconcile", kw)
    )
    monkeypatch.setattr(
        service, "_schedule_pending_image_jobs", lambda **kw: scheduled.setdefault("images", kw)
    )
    monkeypatch.setattr(
        service, "_schedule_dead_download_probe", lambda **kw: scheduled.setdefault("probe", kw)
    )

    async def _no_b2(rows):
        return {}

    monkeypatch.setattr(service, "_resolve_pending_b2_urls", _no_b2)

    # If either ever runs inline again, these explode and the test fails.
    async def _inline_reconcile(**_kw):
        raise AssertionError("reconcile must not run on the request path")

    async def _inline_images(**_kw):
        raise AssertionError("image-job ensure must not run on the request path")

    monkeypatch.setattr(service, "reconcile_pending_suno_tasks", _inline_reconcile)
    monkeypatch.setattr(service, "ensure_batch_image_jobs", _inline_images)

    items = await service.list_pending_suno_downloads(user_id=user_id, limit=24)

    assert len(items) == 1
    assert scheduled["reconcile"] == {"user_id": user_id, "limit": 24}
    assert scheduled["images"] == {"user_id": user_id, "batch_ids": {batch_id}}
    assert scheduled["probe"] == {"user_id": user_id}


@pytest.mark.asyncio
async def test_pending_b2_resolution_times_out_without_blocking(monkeypatch) -> None:
    task_id = uuid4()
    service = _service(_PendingRepo([]))
    service._PENDING_B2_RESOLVE_TIMEOUT_S = 0.05

    _patch_streaming(monkeypatch, task_id, storage=_SlowStorage())

    start = time.monotonic()
    result = await service._resolve_pending_b2_urls([{"id": task_id}])
    elapsed = time.monotonic() - start

    assert result == {}
    assert elapsed < 0.9


@pytest.mark.asyncio
async def test_pending_b2_resolution_returns_urls(monkeypatch) -> None:
    task_id = uuid4()
    service = _service(_PendingRepo([]))
    _patch_streaming(monkeypatch, task_id, storage=_FastStorage())

    result = await service._resolve_pending_b2_urls([{"id": task_id}])

    assert result == {
        (str(task_id), "ok"): "https://cdn.test/k1",
        (str(task_id), "alt"): "https://cdn.test/k2",
    }


class _SlowStorage:
    @staticmethod
    def from_config(_config):
        return _SlowStorage()

    async def get_signed_get_url(self, key, *, cache_bust=False):
        await asyncio.sleep(1.0)
        return f"https://cdn.test/{key}"


class _FastStorage:
    @staticmethod
    def from_config(_config):
        return _FastStorage()

    async def get_signed_get_url(self, key, *, cache_bust=False):
        return f"https://cdn.test/{key}"


def _patch_streaming(monkeypatch, task_id, *, storage) -> None:
    class _Config:
        configured = True

    async def _resolve_config(_pool):
        return _Config()

    class _StreamingRepo:
        def __init__(self, _pool):
            pass

        async def get_track_storage_keys_for_suno_tasks(self, _ids):
            return {(task_id, "ok"): "k1", (task_id, "alt"): "k2"}

    monkeypatch.setattr(
        "platform_api.services.streaming_config_service.resolve_streaming_storage_config",
        _resolve_config,
    )
    monkeypatch.setattr(
        "platform_api.repositories.streaming_repo.StreamingRepository", _StreamingRepo
    )
    monkeypatch.setattr(
        "platform_api.services.storage_service.StorageService", type(storage)
    )
    monkeypatch.setattr("platform_api.dependencies.get_db_pool", lambda: object())
