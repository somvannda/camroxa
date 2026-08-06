"""MissingMp3DownloadWorker downloads only absent role tracks."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest
from PySide6.QtCore import QCoreApplication
from PySide6.QtWidgets import QApplication

from shared.models.platform import (
    BatchRedownloadItem,
    BatchRedownloadPlanResponse,
    ProgressLocalSyncResponse,
)
from shared.workers.data_workers import MissingMp3DownloadResult, MissingMp3DownloadWorker


@pytest.fixture(scope="session")
def qapp() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def _pump() -> None:
    QCoreApplication.processEvents()


def test_missing_mp3_worker_skips_present_and_downloads_missing(
    qapp: QApplication, tmp_path: Path, monkeypatch
) -> None:
    import shared.workers.data_workers as data_workers_module

    monkeypatch.setattr(data_workers_module, "has_sufficient_free_space", lambda *_a, **_k: True)
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    present = run_dir / "1. Present_OK.mp3"
    present.write_bytes(b"already")
    missing = run_dir / "2. Missing_OK.mp3"

    api = MagicMock()
    api.sync_local_progress.return_value = ProgressLocalSyncResponse(updated=1)
    api.get_batch_redownload_plan.return_value = BatchRedownloadPlanResponse(
        items=[
            BatchRedownloadItem(
                task_id="task-1",
                title="Present",
                track_number=1,
                download_url="https://example.test/1.mp3",
                target_path=str(present),
            ),
            BatchRedownloadItem(
                task_id="task-2",
                title="Missing",
                track_number=2,
                download_url="https://example.test/2.mp3",
                target_path=str(missing),
            ),
        ]
    )

    def _fake_download(url: str, target: str) -> bool:
        Path(target).write_bytes(b"dl")
        return True

    monkeypatch.setattr(
        "shared.workers.data_workers.MusicDownloadSyncWorker._download_file",
        staticmethod(_fake_download),
    )

    results: list[MissingMp3DownloadResult] = []
    worker = MissingMp3DownloadWorker(
        api,
        batch_id="batch-1",
        profile_id="profile-1",
        role="OK",
        run_dir=str(run_dir),
    )
    worker.succeeded.connect(results.append)
    worker.start()
    assert worker.wait(5_000)
    _pump()

    assert len(results) == 1
    result = results[0]
    assert result.downloaded == 1
    assert result.skipped == 1
    assert result.failed == 0
    assert missing.is_file()
    api.sync_local_progress.assert_called_once()
    sync_item = api.sync_local_progress.call_args.args[0][0]
    assert sync_item.persist_batch_run_dir is False
    api.sync_music_downloads.assert_called_once()
    synced = api.sync_music_downloads.call_args[0][0]
    assert len(synced) == 1
    assert synced[0].task_id == "task-2"
    assert synced[0].downloaded_primary is True


def test_missing_mp3_worker_uses_fallback_url(
    qapp: QApplication, tmp_path: Path, monkeypatch
) -> None:
    import shared.workers.data_workers as data_workers_module

    monkeypatch.setattr(data_workers_module, "has_sufficient_free_space", lambda *_a, **_k: True)
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    target = run_dir / "1. Track_Alt.mp3"

    api = MagicMock()
    api.sync_local_progress.return_value = ProgressLocalSyncResponse(updated=1)
    api.get_batch_redownload_plan.return_value = BatchRedownloadPlanResponse(
        items=[
            BatchRedownloadItem(
                task_id="task-alt",
                title="Track",
                track_number=1,
                download_url="https://example.test/dead.mp3",
                fallback_download_url="https://example.test/b2.mp3",
                target_path=str(target),
            )
        ]
    )

    calls: list[str] = []

    def _fake_download(url: str, path: str) -> bool:
        calls.append(url)
        if "dead" in url:
            return False
        Path(path).write_bytes(b"ok")
        return True

    monkeypatch.setattr(
        "shared.workers.data_workers.MusicDownloadSyncWorker._download_file",
        staticmethod(_fake_download),
    )

    results: list[MissingMp3DownloadResult] = []
    worker = MissingMp3DownloadWorker(
        api,
        batch_id="batch-1",
        profile_id="profile-1",
        role="ALT",
        run_dir=str(run_dir),
    )
    worker.succeeded.connect(results.append)
    worker.start()
    assert worker.wait(5_000)
    _pump()

    assert results[0].downloaded == 1
    assert calls == [
        "https://example.test/dead.mp3",
        "https://example.test/b2.mp3",
    ]
    synced = api.sync_music_downloads.call_args[0][0]
    assert synced[0].downloaded_secondary is True
    assert synced[0].downloaded_primary is None
