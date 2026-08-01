"""RunFolderRecoveryWorker must move a run folder and resume without re-drafting."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest
from PySide6.QtCore import QCoreApplication
from PySide6.QtWidgets import QApplication

from shared.models.platform import (
    BatchRedownloadItem,
    BatchRedownloadPlanResponse,
    ImageJobListItem,
    ImageJobsListResponse,
    ProgressLocalSyncResponse,
)
from shared.workers.data_workers import RunFolderRecoveryResult, RunFolderRecoveryWorker


@pytest.fixture(scope="session")
def qapp() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def _pump() -> None:
    QCoreApplication.processEvents()


def test_recovery_worker_rejects_low_disk_space(qapp: QApplication, tmp_path, monkeypatch) -> None:
    import shared.workers.data_workers as data_workers_module

    monkeypatch.setattr(data_workers_module, "has_sufficient_free_space", lambda *_a, **_k: False)

    api = MagicMock()
    errors: list[str] = []
    worker = RunFolderRecoveryWorker(
        api,
        batch_id="batch-1",
        profile_id="profile-1",
        role="OK",
        new_run_dir=str(tmp_path / "new"),
    )
    worker.failed.connect(errors.append)
    worker.start()
    assert worker.wait(5_000)
    _pump()

    assert len(errors) == 1
    assert "enough free space" in errors[0]
    api.sync_local_progress.assert_not_called()


def test_recovery_worker_repoints_run_dir_and_redownloads(qapp: QApplication, tmp_path, monkeypatch) -> None:
    new_dir = tmp_path / "new_run"
    api = MagicMock()
    api.sync_local_progress.return_value = ProgressLocalSyncResponse(updated=1)
    api.get_batch_redownload_plan.return_value = BatchRedownloadPlanResponse(
        items=[
            BatchRedownloadItem(
                task_id="task-1",
                title="Shadow Rebels",
                track_number=1,
                download_url="https://example.test/shadow-rebels.mp3",
                target_path=str(new_dir / "1. Shadow Rebels_OK.mp3"),
            )
        ]
    )
    api.list_image_jobs.return_value = ImageJobsListResponse(
        items=[
            ImageJobListItem(
                id="job-1",
                batch_id="batch-1",
                kind="background",
                channel_role="OK",
                status="success",
                output_image_path=str(tmp_path / "old_run" / "background-16x9-ok.png"),
            ),
            ImageJobListItem(
                id="job-2",
                batch_id="batch-1",
                kind="background",
                channel_role="ALT",
                status="success",
                output_image_path=str(tmp_path / "old_run" / "background-16x9-alt.png"),
            ),
        ]
    )

    def fake_download(_url: str, path: str) -> bool:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_bytes(b"mp3")
        return True

    monkeypatch.setattr(
        "shared.workers.data_workers.MusicDownloadSyncWorker._download_file",
        staticmethod(fake_download),
    )

    def fake_ensure_image_output_local(_api, path, _job_id):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_bytes(b"png")
        return path

    monkeypatch.setattr(
        "shared.lib.image_output_utils.ensure_image_output_local",
        fake_ensure_image_output_local,
    )

    results: list[RunFolderRecoveryResult] = []
    errors: list[str] = []
    worker = RunFolderRecoveryWorker(
        api,
        batch_id="batch-1",
        profile_id="profile-1",
        role="OK",
        new_run_dir=str(new_dir),
    )
    worker.succeeded.connect(results.append)
    worker.failed.connect(errors.append)
    worker.start()
    assert worker.wait(5_000)
    _pump()

    assert errors == []
    assert len(results) == 1
    result = results[0]
    assert result.mp3_total == 1
    assert result.mp3_downloaded == 1
    assert result.mp3_failed == 0
    # Only the OK-role image job should be considered — the ALT job must be skipped.
    assert result.images_total == 1
    assert result.images_downloaded == 1
    assert result.images_failed == 0
    assert not result.had_any_failure

    api.sync_local_progress.assert_called_once()
    sync_items = api.sync_local_progress.call_args.args[0]
    assert sync_items[0].batch_id == "batch-1"
    assert sync_items[0].profile_id == "profile-1"
    assert sync_items[0].role == "OK"
    assert sync_items[0].run_dir == str(new_dir)

    api.get_batch_redownload_plan.assert_called_once_with(
        batch_id="batch-1", role="OK", run_dir=str(new_dir)
    )
    assert (new_dir / "1. Shadow Rebels_OK.mp3").is_file()
    assert (new_dir / "background-16x9-ok.png").is_file()


def test_recovery_worker_falls_back_to_backblaze_when_suno_url_dead(
    qapp: QApplication, tmp_path, monkeypatch
) -> None:
    """Suno URL (primary) failing must trigger exactly one retry against
    `fallback_download_url` (our Backblaze copy) before counting as failed."""
    new_dir = tmp_path / "new_run"
    api = MagicMock()
    api.sync_local_progress.return_value = ProgressLocalSyncResponse(updated=1)
    api.get_batch_redownload_plan.return_value = BatchRedownloadPlanResponse(
        items=[
            BatchRedownloadItem(
                task_id="task-1",
                title="Shadow Rebels",
                download_url="https://suno.cdn.example.com/expired.mp3",
                fallback_download_url="https://b2.example.com/signed/shadow-rebels.mp3",
                target_path=str(new_dir / "1. Shadow Rebels_OK.mp3"),
            )
        ]
    )
    api.list_image_jobs.return_value = ImageJobsListResponse(items=[])

    attempted_urls: list[str] = []

    def fake_download(url: str, path: str) -> bool:
        attempted_urls.append(url)
        if "suno.cdn" in url:
            return False  # Primary (Suno) URL is dead.
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_bytes(b"mp3")
        return True

    monkeypatch.setattr(
        "shared.workers.data_workers.MusicDownloadSyncWorker._download_file",
        staticmethod(fake_download),
    )

    results: list[RunFolderRecoveryResult] = []
    worker = RunFolderRecoveryWorker(
        api,
        batch_id="batch-1",
        profile_id="profile-1",
        role="OK",
        new_run_dir=str(new_dir),
    )
    worker.succeeded.connect(results.append)
    worker.start()
    assert worker.wait(5_000)
    _pump()

    assert attempted_urls == [
        "https://suno.cdn.example.com/expired.mp3",
        "https://b2.example.com/signed/shadow-rebels.mp3",
    ]
    assert len(results) == 1
    result = results[0]
    assert result.mp3_total == 1
    assert result.mp3_downloaded == 1
    assert result.mp3_failed == 0
    assert not result.had_any_failure
    assert (new_dir / "1. Shadow Rebels_OK.mp3").is_file()


def test_recovery_worker_counts_partial_failures(qapp: QApplication, tmp_path, monkeypatch) -> None:
    new_dir = tmp_path / "new_run"
    api = MagicMock()
    api.sync_local_progress.return_value = ProgressLocalSyncResponse(updated=1)
    api.get_batch_redownload_plan.return_value = BatchRedownloadPlanResponse(
        items=[
            BatchRedownloadItem(
                task_id="task-1",
                title="Good Track",
                download_url="https://example.test/good.mp3",
                target_path=str(new_dir / "good.mp3"),
            ),
            BatchRedownloadItem(
                task_id="task-2",
                title="Bad Track",
                download_url="https://example.test/bad.mp3",
                target_path=str(new_dir / "bad.mp3"),
            ),
        ]
    )
    api.list_image_jobs.return_value = ImageJobsListResponse(items=[])

    def fake_download(url: str, path: str) -> bool:
        if "bad" in url:
            return False
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_bytes(b"mp3")
        return True

    monkeypatch.setattr(
        "shared.workers.data_workers.MusicDownloadSyncWorker._download_file",
        staticmethod(fake_download),
    )

    results: list[RunFolderRecoveryResult] = []
    worker = RunFolderRecoveryWorker(
        api,
        batch_id="batch-1",
        profile_id="profile-1",
        role="OK",
        new_run_dir=str(new_dir),
    )
    worker.succeeded.connect(results.append)
    worker.start()
    assert worker.wait(5_000)
    _pump()

    assert len(results) == 1
    result = results[0]
    assert result.mp3_total == 2
    assert result.mp3_downloaded == 1
    assert result.mp3_failed == 1
    assert result.had_any_failure
