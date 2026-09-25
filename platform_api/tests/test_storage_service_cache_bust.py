"""Tests for CDN cache-busting in StorageService.get_signed_get_url."""

from __future__ import annotations

from platform_api.services.storage_service import StorageService
from platform_api.services.streaming_config_service import StreamingStorageConfig


def _config(*, cdn: str = "https://cdn.example.com") -> StreamingStorageConfig:
    return StreamingStorageConfig(
        key_id="key",
        application_key="secret",
        bucket="bucket",
        region="us-west-004",
        endpoint="https://s3.us-west-004.backblazeb2.com",
        cdn_base_url=cdn,
        stream_url_ttl_seconds=3600,
        secret_source="database",
        configured=True,
    )


async def test_cdn_url_plain(monkeypatch) -> None:
    service = StorageService(_config())

    async def _fail(_key: str) -> str:  # pragma: no cover - must not be called
        raise AssertionError("_object_version should not run without cache_bust")

    monkeypatch.setattr(service, "_object_version", _fail)
    assert await service.get_signed_get_url("user/album/song-ok.mp3") == (
        "https://cdn.example.com/user/album/song-ok.mp3"
    )


async def test_cdn_url_cache_bust_appends_version(monkeypatch) -> None:
    service = StorageService(_config())

    async def _version(_key: str) -> str:
        return "e85bbd867bab704b630ef0f9bc3ba81f7aaec6d0"

    monkeypatch.setattr(service, "_object_version", _version)
    url = await service.get_signed_get_url("user/album/song-ok.mp3", cache_bust=True)
    assert url == (
        "https://cdn.example.com/user/album/song-ok.mp3"
        "?v=e85bbd867bab704b630ef0f9bc3ba81f7aaec6d0"
    )


async def test_cdn_url_cache_bust_without_version_is_plain(monkeypatch) -> None:
    service = StorageService(_config())

    async def _no_version(_key: str) -> str:
        return ""

    monkeypatch.setattr(service, "_object_version", _no_version)
    url = await service.get_signed_get_url("user/album/song-ok.mp3", cache_bust=True)
    assert url == "https://cdn.example.com/user/album/song-ok.mp3"


async def test_leading_slash_stripped() -> None:
    service = StorageService(_config())
    assert await service.get_signed_get_url("/user/song.mp3") == (
        "https://cdn.example.com/user/song.mp3"
    )
