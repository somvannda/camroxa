"""Helpers for Progress missing-MP3 recovery."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from shared.lib.missing_mp3 import (
    count_missing_role_mp3s,
    count_missing_role_mp3s_from_meta,
    filter_missing_redownload_items,
    resolve_row_local_run_dir,
    target_path_is_present,
)
from shared.models.platform import ProgressRow, ProgressRowMeta


def _row(*, run_dir: str, role: str = "OK", download_ready: int = 2, expected: int = 2) -> ProgressRow:
    meta = ProgressRowMeta(
        batch_id="batch-1",
        profile_id="profile-1",
        role=role,
        run_dir=run_dir,
        expected=expected,
        saved=0,
        download_ready=download_ready,
        download_pending=download_ready,
    )
    return ProgressRow(
        batch="batch-1",
        run_date="2026-08-06",
        channel="Demo",
        status="Preparing",
        music=f"0/{expected}",
        image="—",
        converter="—",
        merge="—",
        youtube="—",
        stage="Music",
        notes="",
        updated="10:00:00",
        meta=meta,
    )


def test_count_missing_role_mp3s_disk_first(tmp_path: Path, monkeypatch) -> None:
    local_root = tmp_path / "Suno"
    run = local_root / "Bass-Gravity" / "2026-08-06_Marble"
    run.mkdir(parents=True)
    (run / "1. Track_Alt.mp3").write_bytes(b"mp3")
    monkeypatch.setattr(
        "shared.lib.device_workspace_paths.resolve_local_suno_output_dir",
        lambda *_a, **_k: str(local_root),
    )
    foreign = r"C:\Users\Other\AppData\Local\Camxora\Media\Suno\Bass-Gravity\2026-08-06_Marble"
    row = _row(run_dir=foreign, role="ALT", download_ready=2, expected=2)
    assert resolve_row_local_run_dir(row) == str(run)
    assert count_missing_role_mp3s(row) == 1


def test_count_missing_when_folder_absent(tmp_path: Path, monkeypatch) -> None:
    local_root = tmp_path / "Suno"
    local_root.mkdir()
    monkeypatch.setattr(
        "shared.lib.device_workspace_paths.resolve_local_suno_output_dir",
        lambda *_a, **_k: str(local_root),
    )
    row = _row(
        run_dir=str(local_root / "Chan" / "2026-08-06_Album"),
        download_ready=3,
        expected=3,
    )
    assert count_missing_role_mp3s(row) == 3


def test_count_missing_uses_expected_when_api_url_count_matches_disk(tmp_path: Path) -> None:
    """9 files + 9 Suno URLs + expected 10 → still offer Download missing (1)."""
    run = tmp_path / "run"
    run.mkdir()
    for i in range(1, 10):
        (run / f"{i}. Track_Alt.mp3").write_bytes(b"x")
    row = _row(run_dir=str(run), role="ALT", download_ready=9, expected=10)
    assert count_missing_role_mp3s(row) == 1


def test_filter_missing_redownload_items(tmp_path: Path) -> None:
    present = tmp_path / "1. A_OK.mp3"
    present.write_bytes(b"ID3" + b"\x00" * 300)
    missing = tmp_path / "2. B_OK.mp3"
    opus = tmp_path / "3. C_OK.mp3"
    opus.write_bytes(b"\x00\x00\x00\x20ftypisom" + b"\x00" * 300)
    items = [
        SimpleNamespace(target_path=str(present), task_id="t1"),
        SimpleNamespace(target_path=str(missing), task_id="t2"),
        SimpleNamespace(target_path="", task_id="t3"),
        SimpleNamespace(target_path=str(opus), task_id="t4"),
    ]
    filtered = filter_missing_redownload_items(items)
    assert [i.task_id for i in filtered] == ["t2", "t3", "t4"]
    assert target_path_is_present(str(present)) is True
    assert target_path_is_present(str(missing)) is False
    assert target_path_is_present(str(opus)) is False


def test_count_missing_from_meta_uses_saved_not_disk() -> None:
    row = _row(run_dir=r"D:\missing-on-purpose", expected=15, download_ready=15)
    row = row.model_copy(update={"meta": row.meta.model_copy(update={"saved": 15})})
    assert count_missing_role_mp3s_from_meta(row) == 0
    row = row.model_copy(update={"meta": row.meta.model_copy(update={"saved": 12})})
    assert count_missing_role_mp3s_from_meta(row) == 3
