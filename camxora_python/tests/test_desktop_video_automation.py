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


def _row() -> ProgressRow:
    return ProgressRow(
        batch="Batch 1",
        run_date="2026-06-29",
        channel="Primary",
        status="Queued",
        music="Ready",
        image="Ready",
        converter="Pending",
        merge="Pending",
        youtube="Pending",
        stage="Converter",
        notes="",
        updated="2026-06-29 12:00:00",
        meta=ProgressRowMeta(
            batch_id="batch-1",
            profile_id="profile-1",
            role="primary",
            run_dir="D:\\Runs\\batch-1\\primary",
            source_mode="ai",
            background_16x9_path="D:\\Runs\\batch-1\\primary\\background-16x9.png",
            background_9x16_path="D:\\Runs\\batch-1\\primary\\background-9x16.png",
            thumbnail_16x9_path="D:\\Runs\\batch-1\\primary\\thumbnail-16x9.png",
            thumbnail_9x16_path="D:\\Runs\\batch-1\\primary\\thumbnail-9x16.png",
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


def test_select_next_auto_video_candidate_returns_long_branch() -> None:
    row = _row()
    key = "batch-1:profile-1:primary"
    candidate = select_next_auto_video_candidate(
        rows=[row],
        profiles=[_profile()],
        settings={"autoVideoAfterSuno": True},
        inspections={key: VideoRunInspection(directory=row.meta.run_dir or "", long_output_paths=(), reel_output_paths=(), merged_long_paths=(), merged_reel_paths=())},
        runtime_by_key={},
        workspace=_workspace(),
    )
    assert candidate is not None
    assert candidate.branch == "long"
    assert candidate.template_id == "video-template-1"
    assert "background-16x9" in candidate.background_path


def test_select_next_auto_video_candidate_disabled_without_toggle() -> None:
    row = _row()
    candidate = select_next_auto_video_candidate(
        rows=[row],
        profiles=[_profile()],
        settings={"autoVideoAfterSuno": False},
        inspections={},
        runtime_by_key={},
        workspace=_workspace(),
    )
    assert candidate is None
