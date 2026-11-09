"""Hosted publish media must not accumulate in the bucket forever."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import pytest

from platform_api.services import publish_service as module
from platform_api.services.publish_service import MEDIA_RETENTION_DAYS, PublishService


class _Repo:
    async def list_jobs(self, *_args: Any, **_kwargs: Any) -> list[Any]:
        return []

    async def expire_pending_uploads(self) -> int:
        return 0


class _Storage:
    def __init__(self, objects: list[dict[str, Any]]) -> None:
        self.objects = objects
        self.deleted: list[str] = []
        self.list_calls = 0

    async def list_objects(self, prefix: str) -> list[dict[str, Any]]:
        self.list_calls += 1
        assert prefix == "publish/"
        return list(self.objects)

    async def delete_object(self, key: str) -> None:
        self.deleted.append(key)


class _Config:
    configured = True


def _service() -> PublishService:
    return PublishService(
        db=object(),
        repo=_Repo(),  # type: ignore[arg-type]
        client=object(),
        billing=object(),
        enabled=True,
    )


def _patch_storage(monkeypatch, storage: _Storage) -> None:
    async def fake_config(_db: Any) -> _Config:
        return _Config()

    monkeypatch.setattr(
        "platform_api.services.streaming_config_service.resolve_streaming_storage_config",
        fake_config,
    )
    monkeypatch.setattr(
        "platform_api.services.storage_service.StorageService.from_config",
        staticmethod(lambda _config: storage),
    )
    monkeypatch.setattr(module, "_last_media_purge", 0.0)


@pytest.mark.asyncio
async def test_only_expired_originals_are_deleted(monkeypatch) -> None:
    now = datetime.now(timezone.utc)
    storage = _Storage(
        [
            {"key": "publish/u/old.mp4", "size": 10, "last_modified": now - timedelta(days=MEDIA_RETENTION_DAYS + 1)},
            {"key": "publish/u/fresh.mp4", "size": 10, "last_modified": now - timedelta(hours=1)},
            {"key": "publish/u/unknown.mp4", "size": 10, "last_modified": None},
        ]
    )
    _patch_storage(monkeypatch, storage)

    await _service()._purge_stale_media()

    assert storage.deleted == ["publish/u/old.mp4"]
    assert storage.list_calls == 1


@pytest.mark.asyncio
async def test_the_sweep_runs_at_most_once_per_interval(monkeypatch) -> None:
    storage = _Storage([])
    _patch_storage(monkeypatch, storage)
    service = _service()

    await service._purge_stale_media()
    await service._purge_stale_media()

    assert storage.list_calls == 1


@pytest.mark.asyncio
async def test_a_listing_failure_does_not_break_listing_jobs(monkeypatch) -> None:
    class _Broken(_Storage):
        async def list_objects(self, prefix: str) -> list[dict[str, Any]]:
            raise RuntimeError("bucket unreachable")

    storage = _Broken([])
    _patch_storage(monkeypatch, storage)

    jobs = await _service().list_jobs("user-1")

    assert jobs == []
