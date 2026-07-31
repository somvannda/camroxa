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
