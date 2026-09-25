"""Tests for auto-video candidate selection."""

from __future__ import annotations

from features.video.lib.desktop_video_automation import (
    branch_is_conclusively_complete,
    build_merge_candidate_from_row,
    select_next_auto_video_candidate,
)
from shared.lib.video_runtime_inspection import ProgressRuntimePresentation, VideoRunInspection
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


def _row(*, run_dir: str, batch_id: str = "batch-1") -> ProgressRow:
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
            batch_id=batch_id,
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


def test_select_logs_skip_reason_when_background_missing(tmp_path, caplog) -> None:
    run_dir = tmp_path / "primary"
    run_dir.mkdir(parents=True, exist_ok=True)
    # Audio present (gate passes) but no background image on disk.
    (run_dir / "1. Track_OK.mp3").write_bytes(b"mp3")
    (run_dir / "2. Track_OK.mp3").write_bytes(b"mp3")
    row = _row(run_dir=str(run_dir))
    key = "batch-1:profile-1:OK"
    with caplog.at_level("INFO"):
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
    assert candidate is None
    assert "not exportable" in caplog.text


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


def _empty_inspection(run_dir: str) -> VideoRunInspection:
    return VideoRunInspection(
        directory=run_dir,
        long_output_paths=(),
        reel_output_paths=(),
        merged_long_paths=(),
        merged_reel_paths=(),
    )


def _runtime(*, merge: str, stage: str = "Merge", status: str = "Completed") -> ProgressRuntimePresentation:
    return ProgressRuntimePresentation(
        converter="Long 0/2",
        merge=merge,
        stage=stage,
        status=status,
        notes="",
        converter_percent=0,
        merge_percent=100,
    )


def test_select_skips_when_pipeline_complete_even_if_track_mp4s_missing(tmp_path) -> None:
    run_dir = tmp_path / "primary"
    _seed_run_folder(run_dir)
    row = _row(run_dir=str(run_dir))
    row = row.model_copy(update={"meta": row.meta.model_copy(update={"pipeline_complete": True})})
    key = "batch-1:profile-1:OK"
    candidate = select_next_auto_video_candidate(
        rows=[row],
        profiles=[_profile()],
        settings={"autoVideoAfterSuno": True, "autoReelAfterVideo": True},
        inspections={key: _empty_inspection(str(run_dir))},
        runtime_by_key={},
        workspace=_workspace(),
    )
    assert candidate is None


def test_select_skips_when_long_completed_label_and_track_mp4s_missing(tmp_path) -> None:
    run_dir = tmp_path / "primary"
    _seed_run_folder(run_dir)
    row = _row(run_dir=str(run_dir)).model_copy(update={"stage": "Merge", "merge": "Long completed"})
    key = "batch-1:profile-1:OK"
    candidate = select_next_auto_video_candidate(
        rows=[row],
        profiles=[_profile()],
        settings={"autoVideoAfterSuno": True},
        inspections={key: _empty_inspection(str(run_dir))},
        runtime_by_key={key: _runtime(merge="Long completed")},
        workspace=_workspace(),
    )
    assert candidate is None


def test_select_skips_when_merged_file_exists_but_track_mp4s_deleted(tmp_path) -> None:
    run_dir = tmp_path / "primary"
    _seed_run_folder(run_dir)
    row = _row(run_dir=str(run_dir)).model_copy(update={"stage": "Merge", "merge": "Long completed"})
    key = "batch-1:profile-1:OK"
    inspection = VideoRunInspection(
        directory=str(run_dir),
        long_output_paths=(),
        reel_output_paths=(),
        merged_long_paths=(f"{run_dir}\\MERGED_PRIMARY_batch.mp4",),
        merged_reel_paths=(),
    )
    candidate = select_next_auto_video_candidate(
        rows=[row],
        profiles=[_profile()],
        settings={"autoVideoAfterSuno": True},
        inspections={key: inspection},
        runtime_by_key={},
        workspace=_workspace(),
    )
    assert candidate is None


def test_select_allows_reel_after_long_completed_when_reel_pending(tmp_path) -> None:
    run_dir = tmp_path / "primary"
    _seed_run_folder(run_dir)
    row = _row(run_dir=str(run_dir)).model_copy(
        update={"stage": "Merge", "status": "In Progress", "merge": "Long completed · Reel pending"}
    )
    key = "batch-1:profile-1:OK"
    candidate = select_next_auto_video_candidate(
        rows=[row],
        profiles=[_profile()],
        settings={"autoVideoAfterSuno": True, "autoReelAfterVideo": True},
        inspections={key: _empty_inspection(str(run_dir))},
        runtime_by_key={
            key: _runtime(merge="Long completed · Reel pending", status="In Progress"),
        },
        workspace=_workspace(),
    )
    assert candidate is not None
    assert candidate.branch == "reel"


def test_branch_is_conclusively_complete_from_merge_label() -> None:
    row = _row(run_dir=r"D:\Runs\demo")
    runtime = _runtime(merge="Long completed")
    assert branch_is_conclusively_complete(row, "long", runtime=runtime) is True
    assert branch_is_conclusively_complete(row, "reel", runtime=runtime) is False


def test_build_merge_candidate_does_not_require_background(tmp_path) -> None:
    """Merge Continue must work even when BG uses non-canonical names (export-only)."""
    run_dir = tmp_path / "alt"
    run_dir.mkdir(parents=True)
    (run_dir / "background-1-left.jpg").write_bytes(b"bg")
    (run_dir / "1. Track_Alt.mp3").write_bytes(b"mp3")
    (run_dir / "1. Track_Alt.mp4").write_bytes(b"0" * 60_000)
    row = _row(run_dir=str(run_dir)).model_copy(
        update={
            "meta": ProgressRowMeta(
                batch_id="batch-1",
                profile_id="profile-1",
                role="ALT",
                run_dir=str(run_dir),
                source_mode="ai",
                long_ready=False,
                reel_ready=False,
                expected=1,
                saved=1,
                download_ready=1,
                download_pending=0,
            )
        }
    )
    candidate, reason = build_merge_candidate_from_row(row, _profile(), "long")
    assert reason is None
    assert candidate is not None
    assert candidate.run_dir == str(run_dir)
    assert candidate.role == "ALT"


def test_select_next_auto_video_candidate_skips_deferred_run(tmp_path) -> None:
    first = tmp_path / "first"
    second = tmp_path / "second"
    _seed_run_folder(first)
    _seed_run_folder(second)
    row_a = _row(run_dir=str(first), batch_id="batch-1")
    row_b = _row(run_dir=str(second), batch_id="batch-2")
    candidate = select_next_auto_video_candidate(
        rows=[row_a, row_b],
        profiles=[_profile()],
        settings={"autoVideoAfterSuno": True},
        inspections={
            "batch-1:profile-1:OK": VideoRunInspection(
                directory=str(first),
                long_output_paths=(),
                reel_output_paths=(),
                merged_long_paths=(),
                merged_reel_paths=(),
            ),
            "batch-2:profile-1:OK": VideoRunInspection(
                directory=str(second),
                long_output_paths=(),
                reel_output_paths=(),
                merged_long_paths=(),
                merged_reel_paths=(),
            ),
        },
        runtime_by_key={},
        workspace=_workspace(),
        skip_keys={"batch-1:profile-1:OK"},
    )
    assert candidate is not None
    assert candidate.batch_id == "batch-2"
    assert candidate.run_dir == str(second)
