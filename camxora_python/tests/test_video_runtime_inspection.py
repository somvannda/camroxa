"""Tests for desktop video runtime inspection."""

from __future__ import annotations

from shared.lib.video_runtime_inspection import (
    inspect_video_run_entries,
    resolve_progress_runtime_presentation,
)
from shared.models.desktop import VideoExportState, VideoWorkspaceState
from shared.services.video_workspace_service import get_video_workspace_service
from shared.models.platform import ProgressRow, ProgressRowMeta
from shared.services.file_service import DirectoryEntry


def _base_row(**meta_overrides: object) -> ProgressRow:
    meta = ProgressRowMeta(
        batch_id="batch-1",
        profile_id="profile-1",
        role="primary",
        run_dir=r"D:\Runs\batch-1\primary",
        expected=2,
        saved=2,
        long_ready=True,
        reel_ready=True,
        **meta_overrides,
    )
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
        notes="Desktop-only progress",
        updated="2026-06-29 12:00:00",
        meta=meta,
    )


def test_inspect_video_run_entries_classifies_mp4_outputs() -> None:
    inspection = inspect_video_run_entries(
        r"D:\Runs\batch-1\primary",
        [
            DirectoryEntry(name="track_01.mp4", is_directory=False),
            DirectoryEntry(name="track_01_reel.mp4", is_directory=False),
            DirectoryEntry(name="merged_batch.mp4", is_directory=False),
            DirectoryEntry(name="merged_reel_batch.mp4", is_directory=False),
            DirectoryEntry(name="notes.txt", is_directory=False),
        ],
    )
    assert len(inspection.long_output_paths) == 1
    assert len(inspection.reel_output_paths) == 1
    assert len(inspection.merged_long_paths) == 1
    assert len(inspection.merged_reel_paths) == 1


def test_resolve_runtime_marks_converter_partial_from_incomplete_local_outputs() -> None:
    row = _base_row()
    inspection = inspect_video_run_entries(
        row.meta.run_dir or "",
        [DirectoryEntry(name="track_01.mp4", is_directory=False)],
    )
    runtime = resolve_progress_runtime_presentation(row, inspection, None)
    assert runtime.stage == "Converter"
    assert runtime.status == "Partial"
    assert runtime.converter_percent > 0


def test_resolve_runtime_marks_converter_completed_when_both_branches_ready() -> None:
    row = _base_row()
    inspection = inspect_video_run_entries(
        row.meta.run_dir or "",
        [
            DirectoryEntry(name="track_01.mp4", is_directory=False),
            DirectoryEntry(name="track_02.mp4", is_directory=False),
            DirectoryEntry(name="track_01_reel.mp4", is_directory=False),
            DirectoryEntry(name="track_02_reel.mp4", is_directory=False),
        ],
    )
    runtime = resolve_progress_runtime_presentation(row, inspection, None)
    assert runtime.stage == "Converter"
    assert runtime.status == "Completed"
    assert runtime.converter_percent == 100


def test_resolve_runtime_honors_active_export_workspace() -> None:
    row = _base_row()
    workspace = VideoWorkspaceState(
        mp3_directory=r"D:\Runs\batch-1\primary",
        export=VideoExportState(
            running=True,
            merge_running=False,
            output_dir=r"D:\Runs\batch-1\primary",
            total_jobs=4,
            completed_jobs=2,
            current_status="Exporting long 2/4",
        ),
    )
    runtime = resolve_progress_runtime_presentation(row, None, workspace)
    assert runtime.stage == "Converter"
    assert runtime.status == "Converting"
    assert "Exporting long 2/4" in runtime.notes


def test_video_workspace_service_registry() -> None:
    service = get_video_workspace_service()
    service.set_workspace_state(
        VideoWorkspaceState(
            export=VideoExportState(running=True, output_dir=r"D:\Runs\batch-1\primary"),
        )
    )
    assert service.export_is_active()
    service.set_workspace_state(None)
    assert not service.export_is_active()
