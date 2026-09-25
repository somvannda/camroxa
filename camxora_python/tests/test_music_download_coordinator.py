"""Music download coordinator must not block the UI thread."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest
from PySide6.QtCore import QCoreApplication
from PySide6.QtWidgets import QApplication

from shared.models.platform import (
    MusicDownloadSyncItem,
    PendingMusicDownloadItem,
    PendingMusicDownloadTarget,
    PendingMusicDownloadsResponse,
)
from shared.services.music_download_coordinator import MusicDownloadCoordinator
from shared.services.platform_client import PlatformApiError
from shared.workers.data_workers import MusicDownloadSyncResult, MusicDownloadSyncWorker


@pytest.fixture(scope="session")
def qapp() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def _pump() -> None:
    QCoreApplication.processEvents()


def test_sync_worker_remaps_foreign_output_dir_then_downloads(
    qapp: QApplication, tmp_path, monkeypatch
) -> None:
    """Pending items planned under another PC's path must still land locally."""
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.setattr("shared.lib.app_paths.get_user_data_dir", lambda: tmp_path)
    monkeypatch.setattr("shared.services.local_user_scope.get_user_data_dir", lambda: tmp_path)

    from shared.services.local_user_scope import activate_local_user_scope, deactivate_local_user_scope
    from shared.services.secure_storage import SecureStorage

    class _MemoryStorage(SecureStorage):
        def __init__(self) -> None:
            super().__init__(store_path=Path("memory-only") / "store.json")
            self._data = {}

        def _load(self) -> None:
            return

        def _save(self) -> None:
            return

    activate_local_user_scope("user-a", _MemoryStorage())
    local_suno = tmp_path / "Suno"
    local_suno.mkdir()
    from shared.lib.device_workspace_paths import persist_device_paths_from_settings

    persist_device_paths_from_settings({"sunoOutputDir": str(local_suno)})

    foreign_dir = r"C:\Users\OtherPC\AppData\Local\Camxora\Media\Suno\ch\2026-08-03_album"
    api = MagicMock()
    api.list_pending_music_downloads.return_value = PendingMusicDownloadsResponse(
        items=[
            PendingMusicDownloadItem(
                task_id="task-1",
                primary=PendingMusicDownloadTarget(
                    download_url="https://example.test/a.mp3",
                    downloaded=False,
                    output_dir=foreign_dir,
                    target_path=foreign_dir + r"\track_OK.mp3",
                ),
            )
        ]
    )

    def fake_download(_url: str, path: str) -> bool:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_bytes(b"mp3")
        return True

    monkeypatch.setattr(MusicDownloadSyncWorker, "_download_file", staticmethod(fake_download))
    monkeypatch.setattr(
        "shared.lib.path_locality.is_foreign_windows_profile_path",
        lambda path: "OtherPC" in str(path),
    )

    results: list[MusicDownloadSyncResult] = []
    worker = MusicDownloadSyncWorker(api, limit=24)
    worker.succeeded.connect(results.append)
    worker.start()
    assert worker.wait(5_000)
    _pump()

    assert results == [MusicDownloadSyncResult(pending_count=1, synced_count=1)]
    synced = api.sync_music_downloads.call_args.args[0]
    assert synced[0].downloaded_primary is True
    assert synced[0].output_dir_primary == str(local_suno / "ch" / "2026-08-03_album")
    assert (local_suno / "ch" / "2026-08-03_album" / "track_OK.mp3").is_file()
    deactivate_local_user_scope()


def test_sync_worker_empty_pending(qapp: QApplication) -> None:
    api = MagicMock()
    api.list_pending_music_downloads.return_value = PendingMusicDownloadsResponse(items=[])

    results: list[MusicDownloadSyncResult] = []
    errors: list[str] = []
    worker = MusicDownloadSyncWorker(api, limit=24)
    worker.succeeded.connect(results.append)
    worker.failed.connect(errors.append)
    worker.start()
    assert worker.wait(5_000)
    _pump()

    assert errors == []
    assert results == [MusicDownloadSyncResult(pending_count=0, synced_count=0)]
    api.sync_music_downloads.assert_not_called()


def test_sync_worker_downloads_and_syncs(qapp: QApplication, tmp_path, monkeypatch) -> None:
    target = tmp_path / "track.mp3"
    api = MagicMock()
    api.list_pending_music_downloads.return_value = PendingMusicDownloadsResponse(
        items=[
            PendingMusicDownloadItem(
                task_id="task-1",
                primary=PendingMusicDownloadTarget(
                    download_url="https://example.test/a.mp3",
                    downloaded=False,
                    output_dir=str(tmp_path),
                    target_path=str(target),
                ),
            )
        ]
    )

    def fake_download(_url: str, path: str) -> bool:
        Path(path).write_bytes(b"mp3")
        return True

    monkeypatch.setattr(MusicDownloadSyncWorker, "_download_file", staticmethod(fake_download))

    results: list[MusicDownloadSyncResult] = []
    worker = MusicDownloadSyncWorker(api, limit=24)
    worker.succeeded.connect(results.append)
    worker.start()
    assert worker.wait(5_000)
    _pump()

    assert results == [MusicDownloadSyncResult(pending_count=1, synced_count=1)]
    api.sync_music_downloads.assert_called_once()
    synced = api.sync_music_downloads.call_args.args[0]
    assert isinstance(synced[0], MusicDownloadSyncItem)
    assert synced[0].task_id == "task-1"
    assert synced[0].downloaded_primary is True


def test_sync_worker_skips_item_with_unwritable_output_dir_but_syncs_others(
    qapp: QApplication, tmp_path, monkeypatch
) -> None:
    # One pending item pointing at a bad/cross-machine output_dir must not
    # abort the whole sync cycle — every other pending download this cycle
    # should still succeed.
    blocker = tmp_path / "blocked"
    blocker.write_text("not a directory", encoding="utf-8")
    bad_dir = blocker / "nested"

    good_target = tmp_path / "good" / "track.mp3"
    api = MagicMock()
    api.list_pending_music_downloads.return_value = PendingMusicDownloadsResponse(
        items=[
            PendingMusicDownloadItem(
                task_id="task-bad",
                primary=PendingMusicDownloadTarget(
                    download_url="https://example.test/bad.mp3",
                    downloaded=False,
                    output_dir=str(bad_dir),
                    target_path=str(bad_dir / "bad.mp3"),
                ),
            ),
            PendingMusicDownloadItem(
                task_id="task-good",
                primary=PendingMusicDownloadTarget(
                    download_url="https://example.test/good.mp3",
                    downloaded=False,
                    output_dir=str(tmp_path / "good"),
                    target_path=str(good_target),
                ),
            ),
        ]
    )

    def fake_download(url: str, path: str) -> bool:
        if "bad" in url:
            raise RuntimeError("simulated download-side failure")
        Path(path).write_bytes(b"mp3")
        return True

    monkeypatch.setattr(MusicDownloadSyncWorker, "_download_file", staticmethod(fake_download))

    results: list[MusicDownloadSyncResult] = []
    worker = MusicDownloadSyncWorker(api, limit=24)
    worker.succeeded.connect(results.append)
    worker.start()
    assert worker.wait(5_000)
    _pump()

    assert results == [MusicDownloadSyncResult(pending_count=2, synced_count=1)]
    synced = api.sync_music_downloads.call_args.args[0]
    assert len(synced) == 1
    assert synced[0].task_id == "task-good"


def test_download_file_rejects_empty_response_body(tmp_path, monkeypatch) -> None:
    class _FakeResponse:
        content = b""

        def raise_for_status(self) -> None:
            return None

    class _FakeClient:
        def __init__(self, *args, **kwargs) -> None:
            pass

        def __enter__(self) -> "_FakeClient":
            return self

        def __exit__(self, *args) -> None:
            return None

        def get(self, _url: str) -> _FakeResponse:
            return _FakeResponse()

    monkeypatch.setattr("httpx.Client", _FakeClient)

    target = tmp_path / "empty.mp3"
    ok = MusicDownloadSyncWorker._download_file("https://example.test/empty.mp3", str(target))

    assert ok is False
    assert not target.exists()


def test_download_file_rewrites_suno_m4a_and_saves_mpeg(tmp_path, monkeypatch) -> None:
    mpeg = b"ID3" + b"\x00" * 300
    m4a = b"\x00\x00\x00\x20ftypisom" + b"\x00" * 300
    requested: list[str] = []

    class _FakeResponse:
        def __init__(self, content: bytes) -> None:
            self.content = content

        def raise_for_status(self) -> None:
            return None

    class _FakeClient:
        def __init__(self, *args, **kwargs) -> None:
            pass

        def __enter__(self) -> "_FakeClient":
            return self

        def __exit__(self, *args) -> None:
            return None

        def get(self, url: str) -> _FakeResponse:
            requested.append(url)
            if url.endswith(".mp3"):
                return _FakeResponse(mpeg)
            return _FakeResponse(m4a)

    monkeypatch.setattr("httpx.Client", _FakeClient)

    target = tmp_path / "track_OK.mp3"
    ok = MusicDownloadSyncWorker._download_file(
        "https://cdn1.suno.ai/441cb4bf-f013-4c88-8ea1-9d17499b1762.m4a",
        str(target),
    )

    assert ok is True
    assert requested == ["https://cdn1.suno.ai/441cb4bf-f013-4c88-8ea1-9d17499b1762.mp3"]
    assert target.read_bytes() == mpeg


def test_download_file_rejects_opus_mp4_payload(tmp_path, monkeypatch) -> None:
    class _FakeResponse:
        content = b"\x00\x00\x00\x20ftypisom" + b"\x00" * 300

        def raise_for_status(self) -> None:
            return None

    class _FakeClient:
        def __init__(self, *args, **kwargs) -> None:
            pass

        def __enter__(self) -> "_FakeClient":
            return self

        def __exit__(self, *args) -> None:
            return None

        def get(self, _url: str) -> _FakeResponse:
            return _FakeResponse()

    monkeypatch.setattr("httpx.Client", _FakeClient)

    target = tmp_path / "opus.mp3"
    ok = MusicDownloadSyncWorker._download_file("https://example.test/clip.mp3", str(target))

    assert ok is False
    assert not target.exists()


def test_download_file_rejects_when_disk_has_too_little_space(tmp_path, monkeypatch) -> None:
    import shared.workers.data_workers as data_workers_module

    monkeypatch.setattr(data_workers_module, "has_sufficient_free_space", lambda *_a, **_k: False)

    target = tmp_path / "track.mp3"
    ok = MusicDownloadSyncWorker._download_file("https://example.test/track.mp3", str(target))

    assert ok is False
    assert not target.exists()


def test_sync_worker_api_error_emits_failed(qapp: QApplication) -> None:
    api = MagicMock()
    api.list_pending_music_downloads.side_effect = PlatformApiError(0, "Cannot connect")

    errors: list[str] = []
    worker = MusicDownloadSyncWorker(api, limit=24)
    worker.failed.connect(errors.append)
    worker.start()
    assert worker.wait(5_000)
    _pump()

    assert errors == ["Cannot connect"]


def test_coordinator_poll_uses_worker_not_blocking_api(qapp: QApplication) -> None:
    api = MagicMock()
    api.list_pending_music_downloads.return_value = PendingMusicDownloadsResponse(items=[])

    coordinator = MusicDownloadCoordinator(api)
    coordinator.start()
    assert coordinator._worker is not None
    assert coordinator._worker.wait(5_000)
    _pump()

    assert coordinator._timer.interval() == 12_000
    api.list_pending_music_downloads.assert_called()
    coordinator.stop()


def test_coordinator_pauses_poll_while_preview_playing(qapp: QApplication) -> None:
    api = MagicMock()
    api.list_pending_music_downloads.return_value = PendingMusicDownloadsResponse(items=[])

    coordinator = MusicDownloadCoordinator(api)
    coordinator.start()
    assert coordinator._worker is not None
    assert coordinator._worker.wait(5_000)
    _pump()
    api.reset_mock()

    coordinator.set_preview_playing(True)
    assert not coordinator._timer.isActive()

    # Success path must not re-arm the 4s pending cadence over a live preview.
    coordinator._had_pending = True
    coordinator._on_sync_succeeded(
        MusicDownloadSyncResult(pending_count=3, synced_count=0)
    )
    assert not coordinator._timer.isActive()

    coordinator._poll()
    assert coordinator._worker is None
    api.list_pending_music_downloads.assert_not_called()

    coordinator.set_preview_playing(False)
    assert coordinator._timer.isActive()
    assert coordinator._timer.interval() == 4_000
    coordinator.stop()


def test_sync_worker_downloads_targets_concurrently(
    qapp: QApplication, tmp_path, monkeypatch
) -> None:
    """A slow target must not serialize the rest of the batch."""
    import threading

    barrier = threading.Barrier(2, timeout=2)

    def fake_download(_url: str, path: str) -> bool:
        barrier.wait()
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_bytes(b"mp3")
        return True

    monkeypatch.setattr(MusicDownloadSyncWorker, "_download_file", staticmethod(fake_download))

    api = MagicMock()
    api.list_pending_music_downloads.return_value = PendingMusicDownloadsResponse(
        items=[
            PendingMusicDownloadItem(
                task_id=f"task-{index}",
                primary=PendingMusicDownloadTarget(
                    download_url=f"https://example.test/{index}.mp3",
                    downloaded=False,
                    output_dir=str(tmp_path),
                    target_path=str(tmp_path / f"{index}.mp3"),
                ),
            )
            for index in (1, 2)
        ]
    )

    results: list[MusicDownloadSyncResult] = []
    worker = MusicDownloadSyncWorker(api, limit=24)
    worker.succeeded.connect(results.append)
    worker.start()
    assert worker.wait(15_000)
    _pump()

    assert results == [MusicDownloadSyncResult(pending_count=2, synced_count=2)]


def test_download_many_preserves_outcomes_and_falls_back(monkeypatch) -> None:
    import shared.workers.data_workers as data_workers_module

    calls: list[str] = []

    def fake_download(url: str, path: str) -> bool:
        calls.append(url)
        return url.endswith("b.mp3")

    monkeypatch.setattr(MusicDownloadSyncWorker, "_download_file", staticmethod(fake_download))

    outcomes = data_workers_module._download_many(
        [
            ("https://example.test/a.mp3", "", "/tmp/a.mp3"),
            ("https://example.test/dead.mp3", "https://example.test/b.mp3", "/tmp/b.mp3"),
        ]
    )

    assert [outcome.ok for outcome in outcomes] == [False, True]
    assert "https://example.test/b.mp3" in calls


def test_duration_header_backfill_runs_off_hot_path(monkeypatch) -> None:
    import threading

    import shared.workers.data_workers as data_workers_module

    done = threading.Event()
    seen: list[str] = []

    def fake_ensure(path: str) -> bool:
        seen.append(str(path))
        done.set()
        return True

    monkeypatch.setattr(
        "shared.lib.suno_mp3_download.ensure_mp3_duration_header", fake_ensure
    )

    data_workers_module._schedule_mp3_duration_header_backfill(["/tmp/track.mp3"])

    assert done.wait(2.0)
    assert seen == ["/tmp/track.mp3"]
