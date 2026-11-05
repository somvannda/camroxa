"""Upload progress must survive files larger than 2 GiB."""

from __future__ import annotations

import pytest
from PySide6.QtWidgets import QApplication

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
