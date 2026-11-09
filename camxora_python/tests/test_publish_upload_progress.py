"""Upload progress must survive files larger than 2 GiB."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from PySide6.QtWidgets import QApplication

from shared.models.publishing import PublishJob
from shared.workers.data_workers import PublishUploadWorker


@pytest.fixture
def qapp() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_progress_signal_accepts_more_than_int32(qapp: QApplication) -> None:
    worker = PublishUploadWorker(api=None)  # never started; signals only
    captured: list[tuple[int, int]] = []
    worker.progress.connect(lambda sent, total: captured.append((sent, total)))

    # A 4 GiB merged video: Qt `int` (32-bit) used to raise OverflowError here,
    # which aborted the upload before a single byte was sent.
    worker.progress.emit(3_000_000_000, 4_000_000_000)

    assert captured == [(3_000_000_000, 4_000_000_000)]


class _ExistingJobApi:
    """Server says this slot already has a job: nothing may be re-sent."""

    def __init__(self) -> None:
        self.completed_calls = 0
        self.puts: list[str] = []

    def create_publish_job(self, _request):
        return SimpleNamespace(
            job_uid="job-1",
            status="processing",
            upload_url=None,
            thumbnail_upload_url=None,
            existing=True,
        )

    def get_publish_job(self, job_uid: str) -> PublishJob:
        return PublishJob(job_uid=job_uid, status="processing")

    def complete_publish_job(self, *_args, **_kwargs):
        self.completed_calls += 1
        raise AssertionError("an existing job must not be finalised again")


def test_an_existing_job_is_not_uploaded_or_finalised_again(qapp: QApplication, tmp_path) -> None:
    api = _ExistingJobApi()
    worker = PublishUploadWorker(api=api)
    statuses: list[str] = []
    jobs: list[object] = []
    worker.status_changed.connect(statuses.append)
    worker.succeeded.connect(jobs.append)

    media = tmp_path / "merged.mp4"
    media.write_bytes(b"x" * 16)
    request = SimpleNamespace(
        file_path=str(media),
        file_checksum=None,
        thumbnail_path=None,
        file_name="merged.mp4",
    )

    worker._create_job_with_retries(request, str(media), "create job", 1)

    assert api.completed_calls == 0
    assert jobs and jobs[0].status == "processing"
    assert any("already uploading" in text for text in statuses)


class _ReuseApi:
    def __init__(self, media_url: str | None) -> None:
        self.media_url = media_url
        self.lookups = 0

    def find_publish_media(self, **_kwargs):
        self.lookups += 1
        return {"media_url": self.media_url} if self.media_url else {}


def test_a_retry_reuses_the_media_the_server_already_hosts(qapp: QApplication) -> None:
    """Local cache misses after a re-merge or reinstall; the server still has it."""
    from types import SimpleNamespace

    api = _ReuseApi("https://cdn.example/merged.mp4")
    worker = PublishUploadWorker(api=api)
    request = SimpleNamespace(batch_id="batch-1", role="ok")

    assert worker._reuse_server_media(request, 2_600_000_000) == "https://cdn.example/merged.mp4"
    assert api.lookups == 1


def test_no_server_copy_means_a_real_upload_is_allowed(qapp: QApplication) -> None:
    from types import SimpleNamespace

    api = _ReuseApi(None)
    worker = PublishUploadWorker(api=api)

    assert worker._reuse_server_media(SimpleNamespace(batch_id="batch-1", role="OK"), 10) == ""
    # No batch id means no way to match a slot, so never guess.
    assert worker._reuse_server_media(SimpleNamespace(batch_id="", role="OK"), 10) == ""
