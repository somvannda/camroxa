"""Tests for video run directory inspection."""

from __future__ import annotations

from pathlib import Path

from platform_api.services.video_run_inspection import (
    build_video_run_presentation,
    inspect_video_run_directory,
)


def test_inspect_video_run_directory_classifies_mp4_outputs(tmp_path: Path) -> None:
    (tmp_path / "song-01.mp4").write_bytes(b"mp4")
    (tmp_path / "song-01_reel.mp4").write_bytes(b"mp4")
    (tmp_path / "MERGED_song-01.mp4").write_bytes(b"mp4")
    (tmp_path / "MERGED_REEL_song-01.mp4").write_bytes(b"mp4")

    inspection = inspect_video_run_directory(str(tmp_path))
    assert inspection is not None
    assert len(inspection.long_output_paths) == 1
    assert len(inspection.reel_output_paths) == 1
    assert len(inspection.merged_long_paths) == 1
    assert len(inspection.merged_reel_paths) == 1


def test_build_video_run_presentation_marks_merger_complete(tmp_path: Path) -> None:
    (tmp_path / "MERGED_batch.mp4").write_bytes(b"mp4")

    presentation = build_video_run_presentation(
        inspection=inspect_video_run_directory(str(tmp_path)),
        expected=2,
        assets_ready=True,
    )
    assert presentation.stage == "Merger"
    assert presentation.status == "Completed"
    assert "Long merged" in presentation.merge


def test_build_video_run_presentation_without_exports_waits_for_assets() -> None:
    presentation = build_video_run_presentation(
        inspection=None,
        expected=2,
        assets_ready=False,
    )
    assert presentation.converter == "Waiting for image assets"
    assert presentation.merge == "—"
