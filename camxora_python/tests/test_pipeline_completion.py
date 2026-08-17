"""Tests for persisting pipeline_complete when a merge is already known."""

from __future__ import annotations

from unittest.mock import MagicMock

from shared.lib.pipeline_completion import (
    build_pipeline_complete_sync_items,
    clear_pipeline_complete_latch_session,
    persist_discovered_pipeline_complete,
    should_persist_pipeline_complete,
)
from shared.lib.video_runtime_inspection import VideoRunInspection, progress_runtime_key
from shared.models.platform import ProgressRow, ProgressRowMeta


def _row(**overrides: object) -> ProgressRow:
    meta_overrides = dict(overrides.pop("meta", {}) or {})
    meta_defaults = {
        "batch_id": "batch-1",
        "profile_id": "profile-1",
        "role": "OK",
        "run_dir": r"D:\Runs\batch-1\ok",
        "expected": 2,
        "saved": 2,
        "reel_ready": False,
    }
    meta_defaults.update(meta_overrides)
    meta = ProgressRowMeta(**meta_defaults)  # type: ignore[arg-type]
    values = {
        "batch": "Batch 1",
        "run_date": "2026-06-29",
        "channel": "Primary",
        "status": "Completed",
        "music": "Ready",
        "image": "Ready",
        "converter": "Long 2/2",
        "merge": "Long completed",
        "youtube": "Pending",
        "stage": "Merge",
        "notes": "",
        "updated": "2026-06-29 12:00:00",
        "meta": meta,
    }
    values.update(overrides)
    return ProgressRow(**values)  # type: ignore[arg-type]


def _inspection(*, merged_long: bool = False, merged_reel: bool = False) -> VideoRunInspection:
    return VideoRunInspection(
        directory=r"D:\Runs\batch-1\ok",
        long_output_paths=(),
        reel_output_paths=(),
        merged_long_paths=(r"D:\Runs\batch-1\ok\MERGED_OK.mp4",) if merged_long else (),
        merged_reel_paths=(r"D:\Runs\batch-1\ok\MERGED_REEL_OK.mp4",) if merged_reel else (),
    )


def setup_function() -> None:
    clear_pipeline_complete_latch_session()


def test_should_persist_idle_long_completed_without_existing_latch() -> None:
    row = _row()
    assert should_persist_pipeline_complete(row) is True


def test_should_not_persist_when_already_latched() -> None:
    row = _row(meta={"pipeline_complete": True})
    assert should_persist_pipeline_complete(row) is False


def test_should_not_persist_youtube_in_flight() -> None:
    row = _row(stage="YouTube", status="In Progress")
    assert should_persist_pipeline_complete(row) is False


def test_should_persist_when_merged_long_seen_and_reel_not_in_run() -> None:
    row = _row(merge="Pending", stage="Export", status="Pending")
    assert should_persist_pipeline_complete(row) is False
    assert should_persist_pipeline_complete(row, _inspection(merged_long=True)) is True


def test_should_not_persist_merged_long_while_reel_still_pending() -> None:
    row = _row(
        merge="Long completed · Reel pending",
        stage="Merge",
        status="In Progress",
        meta={"reel_ready": True},
    )
    assert should_persist_pipeline_complete(row, _inspection(merged_long=True)) is False
    assert should_persist_pipeline_complete(row, _inspection(merged_long=True, merged_reel=True)) is True


def test_build_and_persist_sync_items_once_per_session() -> None:
    row = _row()
    key = progress_runtime_key(row.meta.batch_id, row.meta.profile_id, row.meta.role)
    items = build_pipeline_complete_sync_items([row], {key: _inspection(merged_long=True)})
    assert len(items) == 1
    assert items[0].pipeline_complete is True

    api = MagicMock()
    assert persist_discovered_pipeline_complete(api, [row]) == 1
    api.sync_local_progress.assert_called_once()
    assert persist_discovered_pipeline_complete(api, [row]) == 0
    assert api.sync_local_progress.call_count == 1
