"""An interrupted upload must resume at the first missing part, not at zero."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from PySide6.QtWidgets import QApplication

from shared.lib.upload_resume import (
    UPLOAD_STATE_TTL_SECONDS,
    UploadState,
    clear_state,
    load_state,
    save_state,
)
from shared.workers.data_workers import PublishUploadWorker

PART_SIZE = 10


@pytest.fixture(autouse=True)
def isolated_state(tmp_path, monkeypatch):
    monkeypatch.setenv("CAMXORA_UPLOAD_STATE_PATH", str(tmp_path / "state.json"))
    monkeypatch.setenv("CAMXORA_PUBLISH_CACHE_PATH", str(tmp_path / "cache.json"))
    yield


@pytest.fixture
def qapp() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def _state(parts: dict[int, str] | None = None, *, expires_at: float = 10_000.0) -> UploadState:
    return UploadState(
        key="publish/user/abc.mp4",
        upload_id="upload-1",
        part_size=PART_SIZE,
        part_count=3,
        parts=dict(parts or {}),
        expires_at=expires_at,
    )


# ---------------------------------------------------------------------------
# state store
# ---------------------------------------------------------------------------


def test_state_round_trip() -> None:
    save_state(
        "C:/media/a.mp4",
        size_bytes=25,
        mtime=1000.0,
        state=_state({1: "etag-1", 2: "etag-2"}),
        now=100.0,
        ttl_seconds=UPLOAD_STATE_TTL_SECONDS,
    )

    loaded = load_state("c:\\media\\A.MP4", size_bytes=25, mtime=1000.0, now=200.0)

    assert loaded is not None
    assert loaded.upload_id == "upload-1"
    assert loaded.part_size == PART_SIZE
    assert loaded.part_count == 3
    assert loaded.parts == {1: "etag-1", 2: "etag-2"}
    assert loaded.missing_parts() == [3]


def test_size_or_mtime_mismatch_is_ignored() -> None:
    save_state(
        "C:/media/a.mp4",
        size_bytes=25,
        mtime=1000.0,
        state=_state({1: "etag-1"}),
        now=100.0,
        ttl_seconds=UPLOAD_STATE_TTL_SECONDS,
    )

    assert load_state("C:/media/a.mp4", size_bytes=26, mtime=1000.0, now=200.0) is None
    assert load_state("C:/media/a.mp4", size_bytes=25, mtime=2000.0, now=200.0) is None


def test_near_expiry_is_ignored() -> None:
    save_state(
        "C:/media/a.mp4",
        size_bytes=25,
        mtime=1000.0,
        state=_state({1: "etag-1"}),
        now=0.0,
        ttl_seconds=UPLOAD_STATE_TTL_SECONDS,
    )

    almost = UPLOAD_STATE_TTL_SECONDS - 60
    assert load_state("C:/media/a.mp4", size_bytes=25, mtime=1000.0, now=almost) is None


def test_clear_state_removes_the_entry() -> None:
    save_state(
        "C:/media/a.mp4",
        size_bytes=25,
        mtime=1000.0,
        state=_state({1: "etag-1"}),
        now=0.0,
        ttl_seconds=UPLOAD_STATE_TTL_SECONDS,
    )
    clear_state("C:/media/a.mp4")

    assert load_state("C:/media/a.mp4", size_bytes=25, mtime=1000.0, now=1.0) is None


def test_missing_parts_batches_in_order() -> None:
    state = UploadState(
        key="k",
        upload_id="u",
        part_size=PART_SIZE,
        part_count=25,
        parts={1: "a", 3: "c"},
        expires_at=10.0,
    )

    assert state.missing_parts() == [2] + list(range(4, 26))
    assert state.next_batch(10) == [2, 4, 5, 6, 7, 8, 9, 10, 11, 12]


def test_corrupt_state_file_is_a_miss(tmp_path, monkeypatch) -> None:
    target = tmp_path / "broken.json"
    target.write_text("{not json", encoding="utf-8")
    monkeypatch.setenv("CAMXORA_UPLOAD_STATE_PATH", str(target))

    assert load_state("C:/media/a.mp4", size_bytes=25, mtime=1000.0, now=1.0) is None


def test_saved_json_is_readable(tmp_path, monkeypatch) -> None:
    target = tmp_path / "state.json"
    monkeypatch.setenv("CAMXORA_UPLOAD_STATE_PATH", str(target))
    save_state(
        "C:/media/a.mp4",
        size_bytes=25,
        mtime=1000.0,
        state=_state({1: "etag-1"}),
        now=0.0,
        ttl_seconds=60,
    )

    payload = json.loads(target.read_text(encoding="utf-8"))

    assert list(payload.values())[0]["parts"] == {"1": "etag-1"}


# ---------------------------------------------------------------------------
# worker
# ---------------------------------------------------------------------------


class _FakeApi:
    def __init__(self, *, part_count: int = 3) -> None:
        self.part_count = part_count
        self.create_calls = 0
        self.signed: list[list[int]] = []
        self.completed: list[dict[str, Any]] = []
        self.aborted = False

    def create_publish_upload(self, **_kwargs: Any) -> dict[str, Any]:
        self.create_calls += 1
        return {
            "key": "publish/user/new.mp4",
            "upload_id": "upload-new",
            "part_size": PART_SIZE,
            "part_count": self.part_count,
            "parts": [
                {"part_number": number, "url": f"https://put/{number}"}
                for number in range(1, self.part_count + 1)
            ],
        }

    def sign_publish_upload_parts(
        self, *, key: str, upload_id: str, part_numbers: list[int]
    ) -> list[dict[str, Any]]:
        self.signed.append(list(part_numbers))
        return [{"part_number": n, "url": f"https://put/{n}"} for n in part_numbers]

    def complete_publish_upload(
        self, *, key: str, upload_id: str, parts: list[dict[str, Any]]
    ) -> str:
        self.completed = list(parts)
        return "https://media/merged.mp4"

    def abort_publish_upload(self, **_kwargs: Any) -> None:
        self.aborted = True


class _Request:
    file_name = "merged.mp4"


def _media_file(tmp_path: Path, size: int = 25) -> Path:
    target = tmp_path / "merged.mp4"
    target.write_bytes(b"x" * size)
    return target


def _worker(api: _FakeApi, qapp: QApplication) -> tuple[PublishUploadWorker, list[tuple[int, int]]]:
    worker = PublishUploadWorker(api=api)
    progress: list[tuple[int, int]] = []
    worker.progress.connect(lambda sent, total: progress.append((sent, total)))
    return worker, progress


def test_worker_resumes_by_skipping_completed_parts(tmp_path, qapp) -> None:
    api = _FakeApi()
    file_path = _media_file(tmp_path)
    stat = file_path.stat()
    state = UploadState(
        key="publish/user/old.mp4",
        upload_id="upload-old",
        part_size=PART_SIZE,
        part_count=3,
        parts={1: "etag-1"},
        expires_at=0.0,
    )
    sent_parts: list[int] = []

    worker, progress = _worker(api, qapp)
    worker._put_part = (  # type: ignore[method-assign]
        lambda url, path, offset, length: sent_parts.append(int(url.rsplit("/", 1)[1])) or f"etag-{url[-1]}"
    )

    media_url = worker._stream_parts(_Request(), str(file_path), 25, stat, state)

    assert media_url == "https://media/merged.mp4"
    assert sent_parts == [2, 3]
    assert api.create_calls == 0
    assert api.completed == [
        {"part_number": 1, "etag": "etag-1"},
        {"part_number": 2, "etag": "etag-2"},
        {"part_number": 3, "etag": "etag-3"},
    ]
    # Progress starts from the bytes already on the server.
    assert progress[0] == (10, 25)
    assert progress[-1] == (25, 25)
    # A finished upload leaves nothing to resume.
    assert load_state(str(file_path), size_bytes=25, mtime=stat.st_mtime, now=0.0) is None


def test_worker_persists_progress_after_each_part(tmp_path, qapp) -> None:
    api = _FakeApi()
    file_path = _media_file(tmp_path)
    stat = file_path.stat()

    def failing_put(url: str, path: str, offset: int, length: int) -> str:
        if url.endswith("/3"):
            raise RuntimeError("connection reset")
        return f"etag-{url[-1]}"

    worker, _progress = _worker(api, qapp)
    worker._put_part = failing_put  # type: ignore[method-assign]

    with pytest.raises(RuntimeError):
        worker._stream_parts(_Request(), str(file_path), 25, stat, None)

    resumed = load_state(str(file_path), size_bytes=25, mtime=stat.st_mtime, now=0.0)

    assert resumed is not None
    assert resumed.parts == {1: "etag-1", 2: "etag-2"}
    assert resumed.missing_parts() == [3]


def test_stale_state_falls_back_to_a_fresh_upload(tmp_path, qapp) -> None:
    api = _FakeApi()
    file_path = _media_file(tmp_path)
    stat = file_path.stat()
    save_state(
        str(file_path),
        size_bytes=25,
        mtime=stat.st_mtime,
        state=UploadState(
            key="publish/user/gone.mp4",
            upload_id="upload-gone",
            part_size=PART_SIZE,
            part_count=3,
            parts={1: "etag-1"},
            expires_at=0.0,
        ),
        now=__import__("time").time(),
        ttl_seconds=UPLOAD_STATE_TTL_SECONDS,
    )
    attempts = {"count": 0}

    def flaky_put(url: str, path: str, offset: int, length: int) -> str:
        attempts["count"] += 1
        # The resumed multipart upload no longer exists on storage.
        if attempts["count"] == 1:
            raise RuntimeError("404 Not Found")
        return f"etag-{url[-1]}"

    worker, _progress = _worker(api, qapp)
    worker._put_part = flaky_put  # type: ignore[method-assign]

    media_url = worker._upload_via_storage(_Request(), str(file_path), 25)

    assert media_url == "https://media/merged.mp4"
    assert api.create_calls == 1
    assert api.completed == [
        {"part_number": 1, "etag": "etag-1"},
        {"part_number": 2, "etag": "etag-2"},
        {"part_number": 3, "etag": "etag-3"},
    ]


def test_cancel_aborts_and_clears_resume_state(tmp_path, qapp) -> None:
    api = _FakeApi()
    file_path = _media_file(tmp_path)
    stat = file_path.stat()
    worker, _progress = _worker(api, qapp)
    sent: list[int] = []
    worker.isInterruptionRequested = lambda: True  # type: ignore[method-assign]
    worker._put_part = (  # type: ignore[method-assign]
        lambda url, path, offset, length: sent.append(1) or "etag"
    )

    with pytest.raises(RuntimeError, match="cancelled"):
        worker._stream_parts(_Request(), str(file_path), 25, stat, None)

    assert sent == []
    assert api.aborted is True
    assert load_state(str(file_path), size_bytes=25, mtime=stat.st_mtime, now=0.0) is None
