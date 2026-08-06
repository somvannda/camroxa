"""Progress presentation helper tests."""

from __future__ import annotations

from shared.lib.progress_presentation import (
    compute_stage_progress_percent,
    format_export_compact,
    format_images_compact,
    format_merge_compact,
    format_album_label,
    format_pipeline_step_text,
    format_run_date_label,
    format_video_compact,
    format_youtube_compact,
    resolve_progress_error_message,
)
from shared.models.platform import ProgressRow, ProgressRowMeta


def _row(**meta_overrides: object) -> ProgressRow:
    meta = ProgressRowMeta(
        batch_id="batch-1",
        profile_id="profile-1",
        role="OK",
        expected=2,
        saved=2,
        bg_ready=2,
        bg_total=2,
        th_ready=1,
        th_total=2,
        bg_status="READY",
        th_status="PENDING",
        youtube_pending=1,
        **meta_overrides,
    )
    return ProgressRow(
        batch="abc123",
        run_date="2026-07-07",
        channel="Bass Drive",
        status="Uploading",
        music="2/2",
        image="",
        converter="Long 2/2 · Reel 2/2",
        merge="Long merged · Reel pending",
        youtube="Uploading",
        stage="YouTube",
        notes="",
        updated="14:00:00",
        meta=meta,
    )


def test_format_images_compact_uses_status_badges() -> None:
    text = format_images_compact(_row().meta)
    assert "BG 2/2 ✓" in text
    assert "TH 1/2 …" in text


def test_format_video_compact_joins_converter_and_merge() -> None:
    text = format_video_compact("Long 1/2 · Reel 0/2", "Pending · waiting for branch exports")
    assert "Long 1/2" in text
    assert "Pending · waiting for branch exports" in text


def test_format_youtube_compact_uses_meta_counts() -> None:
    row = _row()
    row.youtube = "—"
    row.meta.youtube_pending = 0
    row.meta.youtube_success = 1
    assert format_youtube_compact(row) == "Completed ✓"


def test_compute_stage_progress_percent_for_music_and_merger() -> None:
    row = _row()
    row.meta.saved = 1
    row.meta.expected = 2
    assert compute_stage_progress_percent(
        row,
        effective_stage="Music",
        effective_status="Downloading",
    ) == "50%"
    # Pending downloads must not inflate % beyond files already landed.
    row.meta.download_ready = 2
    row.meta.download_pending = 1
    assert compute_stage_progress_percent(
        row,
        effective_stage="Music",
        effective_status="Downloading",
    ) == "50%"
    assert compute_stage_progress_percent(
        row,
        effective_stage="Merge",
        effective_status="In Progress",
        merge_percent=40,
    ) == "40%"


def test_format_run_date_label_uses_start_date_only() -> None:
    assert format_run_date_label("2026-07-07 → 2026-07-08") == "2026-07-07"
    assert format_run_date_label("2026-07-07") == "2026-07-07"


def test_format_album_label() -> None:
    assert format_album_label("Veins of the Lost Highway") == "Veins of the Lost Highway"
    assert format_album_label(None) == "—"


def test_format_export_and_merge_compact_shorten_long_text() -> None:
    assert format_export_compact("Waiting for image assets") == "Not started"
    assert format_export_compact("Long 2/2 · Reel 0/2") == "L 2/2 · R 0/2"
    assert format_merge_compact("Pending · waiting for branch exports") == "Pending"
    assert format_merge_compact("Long completed · Reel pending") == "Long completed"


def test_resolve_progress_error_message_collects_notes_and_failures() -> None:
    row = _row()
    row.stage = "Error"
    row.notes = "Image job failed: timeout"
    row.meta.bg_status = "FAILED"
    message = resolve_progress_error_message(
        row,
        effective_stage="Error",
        effective_status="Failed",
        effective_notes="Image job failed: timeout",
    )
    assert message is not None
    assert "Image job failed: timeout" in message
    assert "Background image generation failed." in message
