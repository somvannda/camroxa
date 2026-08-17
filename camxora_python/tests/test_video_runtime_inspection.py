"""Tests for desktop video runtime inspection."""

from __future__ import annotations

from shared.lib.video_runtime_inspection import (
    STATUS_COMPLETED,
    STATUS_IN_PROGRESS,
    STAGE_EXPORT,
    STAGE_MERGE,
    build_video_run_inspection_map,
    inspect_video_run_entries,
    progress_runtime_key,
    resolve_progress_runtime_presentation,
    row_is_idle_progress_row,
    row_skip_disk_scan,
    run_includes_reel,
)
from shared.models.desktop import VideoExportState, VideoWorkspaceState
from shared.services.video_workspace_service import get_video_workspace_service
from shared.models.platform import ProgressRow, ProgressRowMeta
from shared.services.file_service import DirectoryEntry


def _base_row(**meta_overrides: object) -> ProgressRow:
    meta_defaults = {
        "batch_id": "batch-1",
        "profile_id": "profile-1",
        "role": "primary",
        "run_dir": r"D:\Runs\batch-1\primary",
        "expected": 2,
        "saved": 2,
        "long_ready": True,
        "reel_ready": True,
    }
    meta_defaults.update(meta_overrides)
    meta = ProgressRowMeta(**meta_defaults)  # type: ignore[arg-type]
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
            DirectoryEntry(name="MERGED_PRIMARY_batch.mp4", is_directory=False),
            DirectoryEntry(name="MERGED_REEL_PRIMARY_batch.mp4", is_directory=False),
            DirectoryEntry(name="notes.txt", is_directory=False),
        ],
    )
    assert len(inspection.long_output_paths) == 1
    assert len(inspection.reel_output_paths) == 1
    assert len(inspection.merged_long_paths) == 1
    assert len(inspection.merged_reel_paths) == 1
    assert inspection.mp3_paths == ()


def test_inspect_skips_tiny_on_disk_mp4s(tmp_path) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "stub.mp4").write_bytes(b"x" * 20)
    (run_dir / "good.mp4").write_bytes(b"x" * 60_000)
    inspection = inspect_video_run_entries(
        str(run_dir),
        [
            DirectoryEntry(name="stub.mp4", is_directory=False),
            DirectoryEntry(name="good.mp4", is_directory=False),
        ],
    )
    assert len(inspection.long_output_paths) == 1
    assert inspection.long_output_paths[0].endswith("good.mp4")


def test_resolve_runtime_marks_export_in_progress_from_incomplete_local_outputs() -> None:
    row = _base_row()
    inspection = inspect_video_run_entries(
        row.meta.run_dir or "",
        [DirectoryEntry(name="track_01.mp4", is_directory=False)],
    )
    runtime = resolve_progress_runtime_presentation(row, inspection, None)
    assert runtime.stage == STAGE_EXPORT
    assert runtime.status == STATUS_IN_PROGRESS
    assert runtime.converter_percent > 0


def test_resolve_runtime_marks_export_completed_when_both_branches_ready() -> None:
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
    assert runtime.stage == STAGE_EXPORT
    assert runtime.status == STATUS_COMPLETED
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
    assert runtime.stage == STAGE_EXPORT
    assert runtime.status == STATUS_IN_PROGRESS
    assert "Exporting long 2/4" in runtime.notes


def test_resolve_runtime_promotes_merge_when_merged_file_exists_during_export() -> None:
    row = _base_row()
    inspection = inspect_video_run_entries(
        row.meta.run_dir or "",
        [
            DirectoryEntry(name="track_01.mp4", is_directory=False),
            DirectoryEntry(name="track_02.mp4", is_directory=False),
            DirectoryEntry(name="track_03.mp4", is_directory=False),
            DirectoryEntry(name="MERGED_PRIMARY_batch-2026-07-08-1-2.mp4", is_directory=False),
        ],
    )
    workspace = VideoWorkspaceState(
        mp3_directory=row.meta.run_dir or "",
        export=VideoExportState(
            running=True,
            merge_running=False,
            output_dir=row.meta.run_dir or "",
            total_jobs=6,
            completed_jobs=3,
            current_status="Exporting reel 0/3",
            branch="reel",
        ),
    )
    runtime = resolve_progress_runtime_presentation(row, inspection, workspace)
    assert runtime.stage == STAGE_MERGE
    assert runtime.status == STATUS_IN_PROGRESS
    assert "Long completed" in runtime.merge


def test_beattok_long_only_merge_completed_without_reel_branch() -> None:
    row = _base_row(
        expected=3,
        long_ready=True,
        reel_ready=False,
        run_dir=r"D:\Runs\beattok\inside-the-outlaw-restless-broadcast-broadcast",
    )
    row = row.model_copy(update={"channel": "beattok", "stage": "Export", "status": "Pending"})
    inspection = inspect_video_run_entries(
        row.meta.run_dir or "",
        [
            DirectoryEntry(name="01 Track.mp4", is_directory=False),
            DirectoryEntry(name="02 Track.mp4", is_directory=False),
            DirectoryEntry(name="03 Track.mp4", is_directory=False),
            DirectoryEntry(name="MERGED_PRIMARY_batch-2026-07-08-1-2.mp4", is_directory=False),
            DirectoryEntry(name="MERGE_ORDER_20260708120000.txt", is_directory=False),
        ],
    )
    assert run_includes_reel(row) is False
    runtime = resolve_progress_runtime_presentation(row, inspection, None)
    assert runtime.stage == STATUS_COMPLETED
    assert runtime.status == STATUS_COMPLETED
    assert runtime.converter == "Long 3/3"
    assert runtime.converter_percent == 100
    assert runtime.merge_percent == 100
    assert runtime.merge == "Long completed"


def test_beattok_partial_merge_promotes_merge_stage_not_export() -> None:
    row = _base_row(
        expected=3,
        long_ready=True,
        reel_ready=True,
        background_9x16_path=r"D:\Runs\beattok\background-9x16.png",
        thumbnail_9x16_path=r"D:\Runs\beattok\thumbnail-9x16.png",
    )
    inspection = inspect_video_run_entries(
        row.meta.run_dir or "",
        [
            DirectoryEntry(name="01 Track.mp4", is_directory=False),
            DirectoryEntry(name="02 Track.mp4", is_directory=False),
            DirectoryEntry(name="03 Track.mp4", is_directory=False),
            DirectoryEntry(name="MERGED_PRIMARY_batch.mp4", is_directory=False),
        ],
    )
    runtime = resolve_progress_runtime_presentation(row, inspection, None)
    assert runtime.stage == STAGE_MERGE
    assert runtime.status == STATUS_IN_PROGRESS
    assert runtime.merge == "Long completed · Reel pending"
    assert runtime.converter_percent == 50


def test_inspect_collects_mp3_names_from_listing() -> None:
    inspection = inspect_video_run_entries(
        r"D:\Runs\batch-1\primary",
        [
            DirectoryEntry(name="1. Track_OK.mp3", is_directory=False),
            DirectoryEntry(name="2. Track_OK.mp3", is_directory=False),
            DirectoryEntry(name="1. Track_OK.mp4", is_directory=False),
        ],
    )
    assert [path.replace("/", "\\") for path in inspection.mp3_paths] == [
        r"D:\Runs\batch-1\primary\1. Track_OK.mp3",
        r"D:\Runs\batch-1\primary\2. Track_OK.mp3",
    ]


def test_row_skip_disk_scan_for_long_completed_without_reel() -> None:
    row = _base_row(reel_ready=False, background_9x16_path=None, thumbnail_9x16_path=None)
    row = row.model_copy(update={"merge": "Long completed", "stage": "Merge", "status": "Completed"})
    assert row_skip_disk_scan(row) is True


def test_row_skip_disk_scan_false_for_unfinished_export() -> None:
    row = _base_row(reel_ready=False)
    row = row.model_copy(update={"merge": "Pending", "stage": "Export", "status": "Pending"})
    assert row_skip_disk_scan(row) is False


def test_row_is_idle_hides_long_completed_keeps_youtube_and_reel_pending() -> None:
    idle = _base_row(reel_ready=False, background_9x16_path=None, thumbnail_9x16_path=None)
    idle = idle.model_copy(update={"merge": "Long completed", "stage": "Merge", "status": "Completed"})
    assert row_is_idle_progress_row(idle) is True

    youtube = idle.model_copy(update={"stage": "YouTube", "status": "In Progress"})
    assert row_is_idle_progress_row(youtube) is False

    pending = _base_row(reel_ready=True).model_copy(
        update={"merge": "Long completed · Reel pending", "stage": "Merge", "status": "In Progress"}
    )
    assert row_is_idle_progress_row(pending) is False


def test_inspection_map_does_not_list_idle_long_completed_folder(monkeypatch, tmp_path) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "track.mp4").write_bytes(b"x" * 60_000)
    called: list[str] = []

    def _list(directory: str, *, max_results: int = 500):
        called.append(directory)
        raise AssertionError("idle Long completed rows must not list the run folder")

    monkeypatch.setattr("shared.lib.video_runtime_inspection.list_directory_entries", _list)
    row = _base_row(
        run_dir=str(run_dir),
        reel_ready=False,
        background_9x16_path=None,
        thumbnail_9x16_path=None,
    ).model_copy(update={"merge": "Long completed", "stage": "Merge", "status": "Completed"})
    inspections = build_video_run_inspection_map([row])
    assert called == []
    key = progress_runtime_key(row.meta.batch_id, row.meta.profile_id, row.meta.role)
    assert key in inspections


def test_inspection_map_reuses_listing_when_directory_mtime_unchanged(tmp_path, monkeypatch) -> None:
    from shared.lib import video_runtime_inspection as inspection_mod

    inspection_mod._inspection_mtime_cache.clear()
    run_dir = tmp_path / "active-run"
    run_dir.mkdir()
    (run_dir / "track.mp4").write_bytes(b"x" * 60_000)
    called: list[str] = []
    real_list = inspection_mod.list_directory_entries

    def _list(directory: str, *, max_results: int = 500):
        called.append(directory)
        return real_list(directory, max_results=max_results)

    monkeypatch.setattr(inspection_mod, "list_directory_entries", _list)
    row = _base_row(run_dir=str(run_dir), reel_ready=False).model_copy(
        update={"merge": "Pending", "stage": "Export", "status": "Pending"}
    )
    first = build_video_run_inspection_map([row])
    second = build_video_run_inspection_map([row])
    assert len(called) == 1
    key = progress_runtime_key(row.meta.batch_id, row.meta.profile_id, row.meta.role)
    assert first[key] == second[key]
    inspection_mod._inspection_mtime_cache.clear()


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
