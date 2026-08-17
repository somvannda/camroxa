"""Tests for desktop progress local overlay."""

from __future__ import annotations

from shared.lib.progress_local_overlay import apply_local_progress_overlays
from shared.models.platform import ProgressRow, ProgressRowMeta


def _row(**meta_overrides: object) -> ProgressRow:
    base = dict(
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
    )
    base.update(meta_overrides)
    meta = ProgressRowMeta(**base)
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


def test_overlay_preserves_completed_music_when_folder_moved(tmp_path) -> None:
    """Moved/archived run folder must not rewind API download counters."""
    run_dir = tmp_path / "missing-run"
    # Intentionally do not create the directory.

    rows = apply_local_progress_overlays([_row(run_dir=str(run_dir))])
    row = rows[0]

    assert row.meta.saved == 1
    assert row.meta.download_pending == 0
    assert row.stage in {"Converter", "Export"}
    assert row.meta.long_ready is True
    # Must not reopen Music work after the folder was moved.
    assert row.stage.lower() != "music"


def test_overlay_preserves_pipeline_complete_flag(tmp_path) -> None:
    run_dir = tmp_path / "gone"
    source = _row(run_dir=str(run_dir), pipeline_complete=True).model_copy(
        update={"stage": "Completed", "status": "Completed", "notes": "Desktop pipeline completed."},
    )
    row = apply_local_progress_overlays([source])[0]
    assert row.stage == "Completed"
    assert row.meta.saved == 1


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


def test_overlay_downgrades_music_when_download_still_pending(tmp_path) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "background-16x9.png").write_bytes(b"bg")
    (run_dir / "thumbnail-16x9.png").write_bytes(b"th")

    source = _row(
        run_dir=str(run_dir),
        saved=0,
        download_ready=1,
        download_pending=1,
        long_ready=False,
    ).model_copy(update={"stage": "Music", "status": "Downloading", "music": "0/1 ↓"})
    rows = apply_local_progress_overlays([source])
    row = rows[0]

    assert row.meta.saved == 0
    assert row.stage == "Music"


def test_overlay_downgrades_converter_when_images_missing_but_folder_present(tmp_path) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "1. Track_OK.mp3").write_bytes(b"mp3")

    source = _row(run_dir=str(run_dir), long_ready=False, bg_ready=0, th_ready=0)
    rows = apply_local_progress_overlays([source])
    row = rows[0]

    assert row.stage == "Image"
    assert row.meta.long_ready is False


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
    assert row.status == "Pending"
    assert "Pending · no exports yet" in row.converter


def test_overlay_promotes_image_stage_when_background_only(tmp_path) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "background-16x9.png").write_bytes(b"bg")
    (run_dir / "1. Track_OK.mp3").write_bytes(b"mp3")

    source = _row(run_dir=str(run_dir), long_ready=False, th_ready=0, th_total=1).model_copy(
        update={"stage": "Image", "converter": "Waiting for image assets"},
    )
    row = apply_local_progress_overlays([source])[0]

    assert row.stage == "Export"
    assert row.meta.long_ready is True
    assert row.meta.thumbnail_16x9_path in (None, "")


def test_overlay_maps_queued_converter_to_export_pending(tmp_path) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "background-16x9.png").write_bytes(b"bg")
    (run_dir / "thumbnail-16x9.png").write_bytes(b"th")
    (run_dir / "1. Track_OK.mp3").write_bytes(b"mp3")

    source = _row(run_dir=str(run_dir)).model_copy(
        update={"stage": "Converter", "status": "Queued", "converter": "Assets ready · no exports yet"},
    )
    row = apply_local_progress_overlays([source])[0]

    assert row.stage == "Export"
    assert row.status == "Pending"


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


def test_overlay_remaps_foreign_run_dir_onto_local_suno(tmp_path, monkeypatch) -> None:
    local_root = tmp_path / "Suno"
    album = local_root / "Bass-Gravity" / "2026-08-06_Marble"
    album.mkdir(parents=True)
    (album / "1. Track_OK.mp3").write_bytes(b"mp3")
    (album / "background-16x9.png").write_bytes(b"bg")
    monkeypatch.setattr(
        "shared.lib.device_workspace_paths.resolve_local_suno_output_dir",
        lambda *_a, **_k: str(local_root),
    )
    foreign = r"C:\Users\Other\AppData\Local\Camxora\Media\Suno\Bass-Gravity\2026-08-06_Marble"
    row = apply_local_progress_overlays([_row(run_dir=foreign)])[0]
    assert row.meta.run_dir == str(album)
    assert row.meta.saved == 1


def test_overlay_uses_disk_mp3_count_even_when_api_downloaded_flags_complete(tmp_path) -> None:
    """Premature downloaded_* flags must not inflate Music saved / Progress %."""
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "1. Track_Alt.mp3").write_bytes(b"a")
    (run_dir / "2. Track_Alt.mp3").write_bytes(b"b")
    # Only 2 of 3 Alt files on disk; API claims all 3 downloaded.
    source = _row(
        run_dir=str(run_dir),
        role="ALT",
        expected=3,
        saved=3,
        download_ready=3,
        download_pending=0,
        long_ready=False,
        bg_ready=0,
        bg_total=0,
        th_ready=0,
        th_total=0,
    ).model_copy(update={"stage": "Image", "status": "Rendering", "music": "3/3 ✓"})
    row = apply_local_progress_overlays([source])[0]

    assert row.meta.saved == 2
    assert row.meta.download_pending == 1
    assert row.stage == "Music"
    assert "2/3" in row.music


def test_overlay_bumps_saved_when_disk_ahead_of_api_flags(tmp_path) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "1. Track_OK.mp3").write_bytes(b"a")
    (run_dir / "2. Track_OK.mp3").write_bytes(b"b")
    source = _row(
        run_dir=str(run_dir),
        expected=2,
        saved=0,
        download_ready=2,
        download_pending=2,
        long_ready=False,
        bg_ready=0,
        bg_total=0,
        th_ready=0,
        th_total=0,
    ).model_copy(update={"stage": "Music", "status": "Downloading", "music": "0/2 ↓"})
    row = apply_local_progress_overlays([source])[0]

    assert row.meta.saved == 2
    assert row.meta.download_pending == 0
    assert "2/2" in row.music


def test_overlay_does_not_count_mp3s_on_long_completed_folder(tmp_path, monkeypatch) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "1. Track_OK.mp3").write_bytes(b"mp3")
    (run_dir / "background-16x9.png").write_bytes(b"bg")

    def _boom(*_args, **_kwargs):
        raise AssertionError("idle Long completed rows must not count MP3s")

    monkeypatch.setattr("shared.lib.progress_local_overlay.count_channel_mp3_files", _boom)
    source = _row(run_dir=str(run_dir)).model_copy(
        update={"stage": "Merge", "status": "Completed", "merge": "Long completed"}
    )
    row = apply_local_progress_overlays([source])[0]
    assert row.meta.saved == 1
    assert row.merge == "Long completed"
