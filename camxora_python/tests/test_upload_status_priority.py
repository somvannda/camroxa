"""Delivery status must follow the newest attempt, not an older failure."""

from __future__ import annotations

from features.workflow.lib.workflow_steps import format_upload_status
from shared.models.platform import ProgressRow, ProgressRowMeta


def _row(**meta: object) -> ProgressRow:
    return ProgressRow(
        batch="Batch",
        run_date="2026-11-07",
        channel="Channel",
        album="Album",
        status="Completed",
        music="10/10",
        image="BG 1/1",
        converter="Completed",
        merge="Completed",
        youtube="",
        stage="Completed",
        notes="",
        updated="2026-11-07 10:00",
        meta=ProgressRowMeta(batch_id="b", profile_id="p", role="OK", **meta),
    )


def test_a_later_success_wins_over_an_earlier_failure() -> None:
    # Production showed "Video published to YouTube." immediately followed by
    # "YouTube: Failed" because the old failed job still counted.
    row = _row(youtube_success=1, youtube_failed=1, youtube_url="https://youtu.be/x")

    assert format_upload_status(row) == "Uploaded"


def test_failure_is_reported_when_nothing_succeeded() -> None:
    assert format_upload_status(_row(youtube_failed=1)) == "Failed"


def test_pending_is_reported_when_nothing_settled() -> None:
    assert format_upload_status(_row(youtube_pending=1)) == "Uploading"
