"""Admin pipeline board stage promotion — catalog archive vs live errors."""

from __future__ import annotations

from platform_api.services.admin_pipeline_service import _promote_admin_stage


def test_streaming_failures_do_not_mark_completed_music_as_error() -> None:
    stage, status, notes = _promote_admin_stage(
        stage="Converter",
        status="Queued",
        notes="Waiting for desktop video export and merge.",
        stream_group={"total": 10, "success": 8, "pending": 0, "failed": 2, "error": "403"},
        music_done=True,
        image_done=True,
    )
    assert stage == "Done"
    assert status == "Done"
    assert "streaming archive" in notes.lower()


def test_all_streaming_success_still_promotes_to_done() -> None:
    stage, status, notes = _promote_admin_stage(
        stage="Converter",
        status="Queued",
        notes="Waiting for desktop video export and merge.",
        stream_group={"total": 10, "success": 10, "pending": 0, "failed": 0},
        music_done=True,
        image_done=True,
    )
    assert stage == "Done"
    assert status == "Done"
    assert "streaming uploads are complete" in notes.lower()


def test_pending_streaming_stays_streaming() -> None:
    stage, status, notes = _promote_admin_stage(
        stage="Converter",
        status="Queued",
        notes="Waiting for desktop video export and merge.",
        stream_group={"total": 10, "success": 3, "pending": 5, "failed": 2},
        music_done=True,
        image_done=True,
    )
    assert stage == "Streaming"
    assert status == "Uploading"
    assert "in progress" in notes.lower()


def test_generation_error_is_not_overridden_by_streaming() -> None:
    stage, status, notes = _promote_admin_stage(
        stage="Error",
        status="Failed",
        notes="One or more generation steps failed. Right-click this row for recovery actions.",
        stream_group={"total": 10, "success": 8, "pending": 0, "failed": 2},
        music_done=False,
        image_done=False,
    )
    assert stage == "Error"
    assert status == "Failed"
    assert "generation steps failed" in notes.lower()
