"""Delivery summary layered on a completed media pipeline."""

from __future__ import annotations

from types import SimpleNamespace

from features.workflow.lib.workflow_steps import format_delivery_summary


def _row(**meta_overrides):
    values: dict[str, object] = {
        "youtube_pending": 0,
        "youtube_success": 0,
        "youtube_failed": 0,
        "youtube_url": None,
        "youtube_status": "",
    }
    values.update(meta_overrides)
    return SimpleNamespace(meta=SimpleNamespace(**values), youtube="")


def test_no_uploads_tracked_returns_none() -> None:
    assert format_delivery_summary(_row()) is None
    assert format_delivery_summary(SimpleNamespace(meta=None)) is None


def test_uploading_reports_progress() -> None:
    assert format_delivery_summary(_row(youtube_pending=1, youtube_success=1)) == "uploading 1/2"
    assert format_delivery_summary(_row(youtube_pending=2, youtube_success=0)) == "uploading 0/2"
    assert (
        format_delivery_summary(_row(youtube_status="queued", youtube_pending=1))
        == "uploading 0/1"
    )


def test_uploaded_reports_total() -> None:
    assert (
        format_delivery_summary(_row(youtube_success=2, youtube_url="https://y/1"))
        == "uploaded 2/2"
    )
    assert format_delivery_summary(_row(youtube_url="https://y/1")) == "uploaded 1/1"


def test_failures_are_actionable() -> None:
    assert (
        format_delivery_summary(_row(youtube_failed=1, youtube_success=1))
        == "upload failed · retry (1)"
    )
    assert (
        format_delivery_summary(_row(youtube_status="blocked", youtube_pending=1))
        == "upload blocked"
    )


def test_ready_state_is_explicit() -> None:
    assert format_delivery_summary(_row(youtube_status="ready")) == "upload ready"
