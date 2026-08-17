"""Tests for desktop → API progress sync payload building."""

from __future__ import annotations

from shared.lib.progress_local_sync import build_local_progress_sync_items, local_mp3_files_ready
from shared.models.platform import ProgressRow, ProgressRowMeta


def _row(*, run_dir: str, saved: int = 0, long_ready: bool = False) -> ProgressRow:
    return ProgressRow(
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
            run_dir=run_dir,
            expected=1,
            saved=saved,
            download_ready=1,
            download_pending=1,
            long_ready=long_ready,
            reel_ready=False,
        ),
    )


def test_build_local_progress_sync_items_when_assets_ready_but_api_stale(tmp_path) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "background-16x9.png").write_bytes(b"bg")
    (run_dir / "thumbnail-16x9.png").write_bytes(b"th")
    (run_dir / "1. Track_OK.mp3").write_bytes(b"mp3")

    items = build_local_progress_sync_items([_row(run_dir=str(run_dir), saved=0, long_ready=False)])
    assert len(items) == 1
    assert items[0].long_ready is True
    assert items[0].local_mp3_count == 1


def test_build_local_progress_sync_items_latches_idle_long_completed_without_disk(tmp_path, monkeypatch) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "1. Track_OK.mp3").write_bytes(b"mp3")

    def _boom(*_args, **_kwargs):
        raise AssertionError("idle Long completed rows must not walk the run folder")

    monkeypatch.setattr("shared.lib.progress_local_sync.count_channel_mp3_files", _boom)
    monkeypatch.setattr("shared.lib.progress_local_sync.resolve_local_channel_asset_paths", _boom)
    row = _row(run_dir=str(run_dir), saved=2, long_ready=True).model_copy(
        update={"stage": "Merge", "status": "Completed", "merge": "Long completed"}
    )
    items = build_local_progress_sync_items([row])
    assert len(items) == 1
    assert items[0].pipeline_complete is True


def test_build_local_progress_sync_items_skips_already_latched_idle_row(tmp_path, monkeypatch) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()

    def _boom(*_args, **_kwargs):
        raise AssertionError("already-latched idle rows must not walk the run folder")

    monkeypatch.setattr("shared.lib.progress_local_sync.count_channel_mp3_files", _boom)
    row = _row(run_dir=str(run_dir), saved=2, long_ready=True)
    row = row.model_copy(
        update={
            "stage": "Merge",
            "status": "Completed",
            "merge": "Long completed",
            "meta": row.meta.model_copy(update={"pipeline_complete": True}),
        }
    )
    assert build_local_progress_sync_items([row]) == []


def test_local_mp3_files_ready_ignores_stale_api_counters(tmp_path) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "1. Track_OK.mp3").write_bytes(b"mp3")
    row = _row(run_dir=str(run_dir), saved=0)
    assert local_mp3_files_ready(row) is True
