"""Regression tests for ProfileMediaCacheWorker (background profile logo/cover download).

Selecting a profile in Settings used to download the logo/cover
synchronously on the UI thread — a real, multi-megabyte network call that
froze the whole app on every profile switch whenever the file wasn't cached
yet, and hung hard on a slow or unreliable connection to the API (matches
"peer closed connection ... received 2178801 bytes, expected 2447760" seen
in the wild). This worker moves that download off the UI thread.
"""

from __future__ import annotations

from pathlib import Path

from shared.services.platform_client import PlatformApiError
from shared.workers.data_workers import ProfileMediaCacheResult, ProfileMediaCacheWorker


def test_download_writes_file_on_success(tmp_path: Path) -> None:
    destination = tmp_path / "logo.png"
    result = ProfileMediaCacheWorker._download(lambda: b"fake-bytes", destination)
    assert result == str(destination)
    assert destination.read_bytes() == b"fake-bytes"


def test_download_returns_none_on_empty_bytes(tmp_path: Path) -> None:
    destination = tmp_path / "logo.png"
    result = ProfileMediaCacheWorker._download(lambda: b"", destination)
    assert result is None
    assert not destination.exists()


def test_download_returns_none_on_api_error(tmp_path: Path) -> None:
    destination = tmp_path / "cover.png"

    def _raise():
        raise PlatformApiError(0, "Network error: peer closed connection without sending complete message body")

    result = ProfileMediaCacheWorker._download(_raise, destination)
    assert result is None
    assert not destination.exists()


def test_run_downloads_only_requested_media(tmp_path: Path) -> None:
    class _FakeApi:
        def __init__(self) -> None:
            self.logo_calls = 0
            self.cover_calls = 0

        def download_profile_logo(self, _profile_id: str) -> bytes:
            self.logo_calls += 1
            return b"logo-bytes"

        def download_profile_cover(self, _profile_id: str, _index: int = 0) -> bytes:
            self.cover_calls += 1
            return b"cover-bytes"

    api = _FakeApi()
    cache_dir = tmp_path / "profile-1"
    worker = ProfileMediaCacheWorker(
        api,
        profile_id="profile-1",
        cache_dir=cache_dir,
        need_logo=True,
        need_cover=False,
    )

    captured: list[ProfileMediaCacheResult] = []
    worker.succeeded.connect(captured.append)
    worker.run()

    assert api.logo_calls == 1
    assert api.cover_calls == 0
    assert len(captured) == 1
    assert captured[0].logo_path == str(cache_dir / "logo.png")
    assert captured[0].cover_path is None
    assert (cache_dir / "logo.png").read_bytes() == b"logo-bytes"
