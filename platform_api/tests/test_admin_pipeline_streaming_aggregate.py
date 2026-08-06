"""Tests for Pipeline Ops streaming aggregation (any-success-wins)."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from platform_api.services.admin_pipeline_service import (
    _aggregate_streaming_groups,
    _format_streaming_chip,
    _promote_admin_stage,
)


def _row(
    *,
    batch_id: str,
    kind: str,
    status: str,
    song_id: str | None = None,
    suno_task_id: str | None = None,
    error: str | None = None,
    updated_at: datetime | None = None,
    job_id: str | None = None,
) -> dict:
    return {
        "id": job_id or str(uuid4()),
        "batch_id": batch_id,
        "song_id": song_id,
        "suno_task_id": suno_task_id,
        "kind": kind,
        "status": status,
        "error": error,
        "updated_at": updated_at or datetime.now(timezone.utc),
    }


def test_aggregate_streaming_any_success_wins_over_earlier_fail() -> None:
    batch = str(uuid4())
    task = str(uuid4())
    t0 = datetime(2026, 8, 6, 10, 0, tzinfo=timezone.utc)
    t1 = datetime(2026, 8, 6, 10, 2, tzinfo=timezone.utc)
    rows = [
        _row(
            batch_id=batch,
            kind="mp3_ok",
            status="failed",
            suno_task_id=task,
            error="403 Forbidden",
            updated_at=t0,
        ),
        _row(
            batch_id=batch,
            kind="mp3_ok",
            status="success",
            suno_task_id=task,
            updated_at=t1,
        ),
    ]
    groups = _aggregate_streaming_groups(rows)
    group = groups[(batch, "OK")]
    assert group["total"] == 1
    assert group["success"] == 1
    assert group["failed"] == 0
    assert _format_streaming_chip(group) == "Done 1/1"
    stage, status, notes = _promote_admin_stage(
        stage="Converter",
        status="Queued",
        notes="waiting",
        stream_group=group,
        music_done=True,
        image_done=True,
    )
    assert (stage, status) == ("Done", "Done")
    assert "complete" in notes.lower()


def test_aggregate_streaming_fail_only_still_failed() -> None:
    batch = str(uuid4())
    task = str(uuid4())
    rows = [
        _row(
            batch_id=batch,
            kind="mp3_alt",
            status="failed",
            suno_task_id=task,
            error="403 Forbidden",
        ),
    ]
    groups = _aggregate_streaming_groups(rows)
    group = groups[(batch, "ALT")]
    assert group["failed"] == 1
    assert group["success"] == 0
    stage, status, _notes = _promote_admin_stage(
        stage="Image",
        status="Queued",
        notes="",
        stream_group=group,
        music_done=True,
        image_done=True,
    )
    assert (stage, status) == ("Error", "Failed")
