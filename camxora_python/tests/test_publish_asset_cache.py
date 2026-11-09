"""Upload cache: reuse a still-valid media URL for the same file version."""

from __future__ import annotations

import pytest

from shared.lib.publish_asset_cache import (
    CACHE_TTL_SECONDS,
    forget_media_url,
    lookup_media_url,
    store_media_url,
)


@pytest.fixture(autouse=True)
def isolated_cache(tmp_path, monkeypatch):
    monkeypatch.setenv("CAMXORA_PUBLISH_CACHE_PATH", str(tmp_path / "cache.json"))
    yield


def test_round_trip_returns_the_url() -> None:
    store_media_url(
        "C:/media/a.mp4", size_bytes=10, mtime=1000.0, media_url="https://x/a", now=500.0
    )

    assert (
        lookup_media_url("c:\\media\\A.MP4", size_bytes=10, mtime=1000.0, now=1000.0)
        == "https://x/a"
    )


def test_size_or_mtime_mismatch_is_a_miss() -> None:
    store_media_url(
        "C:/media/a.mp4", size_bytes=10, mtime=1000.0, media_url="https://x/a", now=500.0
    )

    assert lookup_media_url("C:/media/a.mp4", size_bytes=11, mtime=1000.0, now=1000.0) is None
    assert lookup_media_url("C:/media/a.mp4", size_bytes=10, mtime=2000.0, now=1000.0) is None


def test_near_expiry_is_treated_as_a_miss() -> None:
    store_media_url(
        "C:/media/a.mp4", size_bytes=10, mtime=1000.0, media_url="https://x/a", now=0.0
    )

    almost_expired = CACHE_TTL_SECONDS - 60
    assert (
        lookup_media_url("C:/media/a.mp4", size_bytes=10, mtime=1000.0, now=almost_expired)
        is None
    )


def test_forget_removes_the_entry() -> None:
    store_media_url(
        "C:/media/a.mp4", size_bytes=10, mtime=1000.0, media_url="https://x/a", now=0.0
    )
    forget_media_url("C:/media/a.mp4")

    assert lookup_media_url("C:/media/a.mp4", size_bytes=10, mtime=1000.0, now=1.0) is None


def test_missing_cache_file_is_a_miss() -> None:
    assert lookup_media_url("C:/media/none.mp4", size_bytes=1, mtime=1.0, now=1.0) is None
