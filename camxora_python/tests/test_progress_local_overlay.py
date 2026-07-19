"""Tests for desktop progress local overlay."""

from __future__ import annotations

from shared.lib.progress_local_overlay import apply_local_progress_overlays
from shared.models.platform import ProgressRow, ProgressRowMeta


def _row(**meta_overrides: object) -> ProgressRow:
    meta = ProgressRowMeta(
        batch_id="batch-1",
        profile_id="profile-1",
        role="OK",
        expected=1,
        saved=1,
        download_ready=1,
        download_pending=0,
        bg_ready=1,
        bg_total=1,
        th_ready=1,
        th_total=1,
        bg_status="READY",
        th_status="READY",
        long_ready=True,
        reel_ready=False,
        **meta_overrides,
    )
    return ProgressRow(
        batch="batch-1",
        run_date="2026-07-07",
        channel="Demo",
        status="Queued",
        music="1/1 ✓",
        image="BG 1/1 ✓ · TH 1/1 ✓",
        converter="Long Ready · Reel Missing",
        merge="Waiting for branch exports",
        youtube="—",
        stage="Converter",
        notes="Waiting for desktop video export and merge.",
        updated="14:00:00",
        meta=meta,
    )


def test_overlay_downgrades_ready_assets_when_files_missing(tmp_path) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()

    rows = apply_local_progress_overlays([_row(run_dir=str(run_dir))])
    row = rows[0]

    assert row.meta.long_ready is False
    assert row.meta.bg_status == "SYNC"
    assert row.stage == "Music"
    assert "mp3" in row.notes.lower() or "download" in row.notes.lower()


def test_overlay_keeps_ready_assets_when_files_exist(tmp_path) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "background-16x9.png").write_bytes(b"bg")
    (run_dir / "thumbnail-16x9.png").write_bytes(b"th")
    (run_dir / "1. Track_OK.mp3").write_bytes(b"mp3")

    rows = apply_local_progress_overlays([_row(run_dir=str(run_dir))])
    row = rows[0]

    assert row.meta.long_ready is True
    assert row.meta.bg_status == "READY"
    assert row.stage == "Export"


def test_overlay_downgrades_music_when_mp3s_missing(tmp_path) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "background-16x9.png").write_bytes(b"bg")
    (run_dir / "thumbnail-16x9.png").write_bytes(b"th")

    rows = apply_local_progress_overlays([_row(run_dir=str(run_dir))])
    row = rows[0]

    assert row.meta.saved == 0
    assert row.meta.download_pending == 1
    assert row.stage == "Music"


def test_overlay_downgrades_converter_when_images_missing_but_music_local(tmp_path) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "1. Track_OK.mp3").write_bytes(b"mp3")

    rows = apply_local_progress_overlays([_row(run_dir=str(run_dir))])
    row = rows[0]

    assert row.stage == "Image"
    assert row.meta.long_ready is False
    assert row.meta.bg_status == "SYNC"


def test_overlay_promotes_image_stage_when_assets_exist(tmp_path) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "background-16x9.png").write_bytes(b"bg")
    (run_dir / "thumbnail-16x9.png").write_bytes(b"th")
    (run_dir / "1. Track_OK.mp3").write_bytes(b"mp3")

    source = _row(run_dir=str(run_dir)).model_copy(
        update={"stage": "Image", "converter": "Waiting for image assets"},
    )
    row = apply_local_progress_overlays([source])[0]

    assert row.stage == "Export"
    assert "Pending · no exports yet" in row.converter


def test_overlay_resolves_role_specific_asset_names(tmp_path) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "background-16x9-alt.png").write_bytes(b"bg")
    (run_dir / "thumbnail-16x9-alt.png").write_bytes(b"th")
    (run_dir / "1. Track_Alt.mp3").write_bytes(b"mp3")

    source = _row(run_dir=str(run_dir)).model_copy(
        update={"stage": "Image", "converter": "Waiting for image assets"},
    )
    source.meta = source.meta.model_copy(update={"role": "Alt"})
    row = apply_local_progress_overlays([source])[0]

    assert row.meta.long_ready is True
    assert row.stage == "Export"
