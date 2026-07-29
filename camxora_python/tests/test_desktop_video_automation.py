"""Tests for auto-video candidate selection."""

from __future__ import annotations

from features.video.lib.desktop_video_automation import select_next_auto_video_candidate
from shared.lib.video_runtime_inspection import VideoRunInspection
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
        templates=[
            VideoTemplateSummary(id="video-template-1", name="Long Template"),
            VideoTemplateSummary(id="reel-template-1", name="Reel Template"),
        ],
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


def _row(*, run_dir: str) -> ProgressRow:
    return ProgressRow(
        batch="Batch 1",
        run_date="2026-06-29",
        channel="Primary",
        status="Pending",
        music="Ready",
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
            run_dir=run_dir,
            source_mode="ai",
            background_16x9_path=f"{run_dir}/background-16x9.png",
            background_9x16_path=f"{run_dir}/background-9x16.png",
            thumbnail_16x9_path=f"{run_dir}/thumbnail-16x9.png",
            thumbnail_9x16_path=f"{run_dir}/thumbnail-9x16.png",
            long_ready=True,
            reel_ready=True,
            expected=2,
            saved=2,
            download_ready=2,
            download_pending=0,
        ),
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
        output_resolution="1920x1080",
    )


def _seed_run_folder(run_dir) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "background-16x9.png").write_bytes(b"bg")
    (run_dir / "background-9x16.png").write_bytes(b"bg9")
    (run_dir / "thumbnail-16x9.png").write_bytes(b"th")
    (run_dir / "thumbnail-9x16.png").write_bytes(b"th9")
    (run_dir / "1. Track_OK.mp3").write_bytes(b"mp3")
    (run_dir / "2. Track_OK.mp3").write_bytes(b"mp3")


def test_select_next_auto_video_candidate_returns_long_branch(tmp_path) -> None:
    run_dir = tmp_path / "primary"
    _seed_run_folder(run_dir)
    row = _row(run_dir=str(run_dir))
    key = "batch-1:profile-1:OK"
    candidate = select_next_auto_video_candidate(
        rows=[row],
        profiles=[_profile()],
        settings={"autoVideoAfterSuno": True},
        inspections={key: VideoRunInspection(directory=str(run_dir), long_output_paths=(), reel_output_paths=(), merged_long_paths=(), merged_reel_paths=())},
        runtime_by_key={},
        workspace=_workspace(),
    )
    assert candidate is not None
    assert candidate.branch == "long"
    assert candidate.template_id == "video-template-1"
    assert "background-16x9" in candidate.background_path


def test_select_next_auto_video_candidate_with_background_only(tmp_path) -> None:
    run_dir = tmp_path / "primary"
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "background-16x9.png").write_bytes(b"bg")
    (run_dir / "1. Track_OK.mp3").write_bytes(b"mp3")
    (run_dir / "2. Track_OK.mp3").write_bytes(b"mp3")
    row = _row(run_dir=str(run_dir))
    key = "batch-1:profile-1:OK"
    candidate = select_next_auto_video_candidate(
        rows=[row],
        profiles=[_profile()],
        settings={"autoVideoAfterSuno": True},
        inspections={
            key: VideoRunInspection(
                directory=str(run_dir),
                long_output_paths=(),
                reel_output_paths=(),
                merged_long_paths=(),
                merged_reel_paths=(),
            )
        },
        runtime_by_key={},
        workspace=_workspace(),
    )
    assert candidate is not None
    assert candidate.branch == "long"
    assert "background-16x9" in candidate.background_path


def test_select_next_auto_video_candidate_disabled_without_toggle(tmp_path) -> None:
    run_dir = tmp_path / "primary"
    _seed_run_folder(run_dir)
    row = _row(run_dir=str(run_dir))
    candidate = select_next_auto_video_candidate(
        rows=[row],
        profiles=[_profile()],
        settings={"autoVideoAfterSuno": False},
        inspections={},
        runtime_by_key={},
        workspace=_workspace(),
    )
    assert candidate is None


def test_select_next_auto_video_candidate_skips_without_local_mp3s(tmp_path) -> None:
    run_dir = tmp_path / "primary"
    run_dir.mkdir()
    (run_dir / "background-16x9.png").write_bytes(b"bg")
    (run_dir / "thumbnail-16x9.png").write_bytes(b"th")
    row = _row(run_dir=str(run_dir))
    candidate = select_next_auto_video_candidate(
        rows=[row],
        profiles=[_profile()],
        settings={"autoVideoAfterSuno": True},
        inspections={},
        runtime_by_key={},
        workspace=_workspace(),
    )
    assert candidate is None


def test_select_next_auto_video_candidate_accepts_export_pending_stage(tmp_path) -> None:
    run_dir = tmp_path / "primary"
    _seed_run_folder(run_dir)
    row = _row(run_dir=str(run_dir)).model_copy(update={"stage": "Export", "status": "Pending"})
    key = "batch-1:profile-1:OK"
    candidate = select_next_auto_video_candidate(
        rows=[row],
        profiles=[_profile()],
        settings={"autoVideoAfterSuno": True},
        inspections={key: VideoRunInspection(directory=str(run_dir), long_output_paths=(), reel_output_paths=(), merged_long_paths=(), merged_reel_paths=())},
        runtime_by_key={},
        workspace=_workspace(),
    )
    assert candidate is not None
