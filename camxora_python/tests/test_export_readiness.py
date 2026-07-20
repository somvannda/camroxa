"""Tests for consolidated export readiness validation."""

from __future__ import annotations

from features.video.lib.export_readiness import evaluate_video_export_readiness
from shared.models.auth import ProfileResponse
from shared.models.desktop import (
    PreviewAspectRatio,
    VideoExportState,
    VideoPlaybackState,
    VideoTemplateSummary,
    VideoWorkspaceState,
    VideoWorkspaceUiState,
)
from shared.models.platform import ProgressRow, ProgressRowMeta


def _workspace() -> VideoWorkspaceState:
    return VideoWorkspaceState(
        template={},
        template_id="video-template-1",
        template_name="Template",
        templates=[VideoTemplateSummary(id="video-template-1", name="Long Template")],
        output_resolution="1920x1080",
        preview_aspect_ratio=PreviewAspectRatio(width=16, height=9),
        background_path="",
        logo_path="",
        selected_mp3_path="",
        mp3_directory="",
        mp3_list=[],
        playback=VideoPlaybackState(),
        export=VideoExportState(),
        ui=VideoWorkspaceUiState(preview_title="Preview", notes=[]),
    )


def _profile() -> ProfileResponse:
    return ProfileResponse(
        id="profile-1",
        user_id="user-1",
        name="Primary",
        folder_name="Primary",
        run_prefix="PRI",
        video_template_id="video-template-1",
        reel_template_id="reel-template-1",
    )


def test_evaluate_video_export_readiness_reports_missing_assets_and_mp3s(tmp_path) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    row = ProgressRow(
        batch="Batch 1",
        run_date="2026-06-29",
        channel="Primary",
        status="Pending",
        music="0/1",
        image="Missing",
        converter="Pending",
        merge="Pending",
        youtube="Pending",
        stage="Export",
        notes="",
        updated="2026-06-29 12:00:00",
        meta=ProgressRowMeta(
            batch_id="batch-1",
            profile_id="profile-1",
            role="OK",
            run_dir=str(run_dir),
            expected=1,
            saved=0,
        ),
    )

    readiness = evaluate_video_export_readiness(
        row,
        _profile(),
        workspace=_workspace(),
        progress_load_error="connection refused",
    )
    assert readiness.ready is False
    assert any("/progress failed" in issue for issue in readiness.issues)
    assert any("background-16x9.png" in issue for issue in readiness.issues)
    assert any("_OK.mp3" in issue for issue in readiness.issues)


def test_evaluate_video_export_readiness_passes_when_run_folder_complete(tmp_path) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "background-16x9.png").write_bytes(b"bg")
    (run_dir / "thumbnail-16x9.png").write_bytes(b"th")
    (run_dir / "1. Track_OK.mp3").write_bytes(b"mp3")
    row = ProgressRow(
        batch="Batch 1",
        run_date="2026-06-29",
        channel="Primary",
        status="Pending",
        music="1/1",
        image="Ready",
        converter="Pending",
        merge="Pending",
        youtube="Pending",
        stage="Export",
        notes="",
        updated="2026-06-29 12:00:00",
        meta=ProgressRowMeta(
            batch_id="batch-1",
            profile_id="profile-1",
            role="OK",
            run_dir=str(run_dir),
            expected=1,
            saved=1,
            long_ready=True,
            reel_ready=False,
        ),
    )

    readiness = evaluate_video_export_readiness(row, _profile(), workspace=_workspace())
    assert readiness.ready is True
    assert readiness.issues == ()
