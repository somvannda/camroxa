"""Per-track MP4 health + repair-export targeting."""

from __future__ import annotations

from pathlib import Path

from features.video.lib.export_track_health import (
    decide_merge_prep,
    inspect_run_export_health,
    list_run_mp3_paths,
    manual_pipeline_start_kwargs,
    select_export_mp3_paths,
    summarize_export_health,
    tracks_missing_mp3,
    tracks_needing_export,
    unlink_track_export,
)
from features.video.lib.render_scene_request import MIN_VALID_EXPORT_BYTES


def _write_mp3(run_dir: Path, name: str) -> Path:
    path = run_dir / name
    path.write_bytes(b"id3")
    return path


def _write_mp4(run_dir: Path, stem: str, *, size: int) -> Path:
    path = run_dir / f"{stem}.mp4"
    path.write_bytes(b"x" * size)
    return path


def test_list_run_mp3_paths_sorts_numeric_prefix(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    _write_mp3(run_dir, "10. Z_OK.mp3")
    _write_mp3(run_dir, "2. A_OK.mp3")
    _write_mp3(run_dir, "1. B_OK.mp3")
    names = [Path(path).name for path in list_run_mp3_paths(str(run_dir))]
    assert names == ["1. B_OK.mp3", "2. A_OK.mp3", "10. Z_OK.mp3"]


def test_inspect_missing_mp4(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    _write_mp3(run_dir, "1. Track_OK.mp3")
    health = inspect_run_export_health(str(run_dir), "long")
    assert [item.status for item in health] == ["missing_mp4"]
    assert tracks_needing_export(health) == [str(run_dir / "1. Track_OK.mp3")]


def test_inspect_tiny_stub_mp4(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    mp3 = _write_mp3(run_dir, "1. Track_OK.mp3")
    _write_mp4(run_dir, mp3.stem, size=12)
    health = inspect_run_export_health(str(run_dir), "long")
    assert health[0].status == "tiny"
    assert health[0].needs_export is True


def test_inspect_ok_when_size_valid_without_ffprobe(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(
        "features.video.lib.export_output_validity.resolve_ffprobe_path",
        lambda *_args, **_kwargs: "",
    )
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    mp3 = _write_mp3(run_dir, "1. Track_OK.mp3")
    _write_mp4(run_dir, mp3.stem, size=MIN_VALID_EXPORT_BYTES + 8)
    health = inspect_run_export_health(str(run_dir), "long")
    assert health[0].status == "ok"
    assert tracks_needing_export(health) == []


def test_inspect_corrupt_when_unusable_but_large(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(
        "features.video.lib.export_track_health.is_usable_export_output",
        lambda *_args, **_kwargs: False,
    )
    monkeypatch.setattr(
        "features.video.lib.export_track_health.is_valid_export_output",
        lambda *_args, **_kwargs: False,
    )
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    mp3 = _write_mp3(run_dir, "1. Track_OK.mp3")
    _write_mp4(run_dir, mp3.stem, size=MIN_VALID_EXPORT_BYTES + 8)
    health = inspect_run_export_health(str(run_dir), "long")
    assert health[0].status == "corrupt"


def test_inspect_truncated_when_valid_size_but_media_incomplete(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(
        "features.video.lib.export_track_health.is_usable_export_output",
        lambda *_args, **_kwargs: False,
    )
    monkeypatch.setattr(
        "features.video.lib.export_track_health.is_valid_export_output",
        lambda *_args, **_kwargs: True,
    )
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    mp3 = _write_mp3(run_dir, "1. Track_OK.mp3")
    _write_mp4(run_dir, mp3.stem, size=MIN_VALID_EXPORT_BYTES + 8)
    health = inspect_run_export_health(str(run_dir), "long")
    assert health[0].status == "truncated"


def test_inspect_spec_mismatch(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(
        "features.video.lib.export_track_health.is_usable_export_output",
        lambda *_args, **_kwargs: True,
    )
    monkeypatch.setattr(
        "features.video.lib.export_track_health.export_matches_batch_specs",
        lambda *_args, **_kwargs: False,
    )
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    mp3 = _write_mp3(run_dir, "1. Track_OK.mp3")
    _write_mp4(run_dir, mp3.stem, size=MIN_VALID_EXPORT_BYTES + 8)
    health = inspect_run_export_health(
        str(run_dir),
        "long",
        expected_width=1920,
        expected_height=1080,
        expected_fps=24,
    )
    assert health[0].status == "spec_mismatch"
    assert tracks_needing_export(health) == [str(mp3)]


def test_inspect_missing_mp3_when_path_passed(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    ghost = str(run_dir / "1. Ghost_OK.mp3")
    health = inspect_run_export_health(str(run_dir), "long", mp3_paths=[ghost])
    assert health[0].status == "missing_mp3"
    assert tracks_needing_export(health) == []
    assert tracks_missing_mp3(health) == [ghost]


def test_inspect_mixed_album_only_flags_broken_tracks(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(
        "features.video.lib.export_output_validity.resolve_ffprobe_path",
        lambda *_args, **_kwargs: "",
    )
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    ok = _write_mp3(run_dir, "1. Good_OK.mp3")
    _write_mp4(run_dir, ok.stem, size=MIN_VALID_EXPORT_BYTES + 8)
    missing = _write_mp3(run_dir, "2. Missing_OK.mp3")
    tiny = _write_mp3(run_dir, "3. Tiny_OK.mp3")
    _write_mp4(run_dir, tiny.stem, size=20)
    health = inspect_run_export_health(str(run_dir), "long")
    assert [item.status for item in health] == ["ok", "missing_mp4", "tiny"]
    assert tracks_needing_export(health) == [str(missing), str(tiny)]
    summary = summarize_export_health(health)
    assert "1 usable" in summary
    assert "2 need re-export" in summary


def test_reel_branch_uses_reel_filename(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    mp3 = _write_mp3(run_dir, "1. Track_OK.mp3")
    health = inspect_run_export_health(str(run_dir), "reel")
    assert health[0].mp4_path.endswith("_REEL.mp4")
    assert Path(health[0].mp4_path).parent == run_dir
    assert str(mp3) == health[0].mp3_path


def test_empty_run_dir_is_empty_health(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    assert inspect_run_export_health(str(run_dir), "long") == []
    assert list_run_mp3_paths(str(tmp_path / "missing")) == []


def test_select_export_mp3_paths_keeps_album_order_and_matches_filename(tmp_path: Path) -> None:
    available = [
        str(tmp_path / "1. A_OK.mp3"),
        str(tmp_path / "2. B_OK.mp3"),
        str(tmp_path / "3. C_OK.mp3"),
    ]
    selected = select_export_mp3_paths(available, requested=[str(tmp_path / "other" / "3. C_OK.mp3")])
    assert selected == [available[2]]
    assert select_export_mp3_paths(available, requested=None) == available
    assert select_export_mp3_paths(available, requested=["missing.mp3"]) == []


def test_unlink_track_export_removes_long_and_reel(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    mp3 = _write_mp3(run_dir, "1. Track_OK.mp3")
    long_mp4 = _write_mp4(run_dir, mp3.stem, size=80_000)
    reel_mp4 = run_dir / f"{mp3.stem}_REEL.mp4"
    reel_mp4.write_bytes(b"x" * 80_000)
    assert Path(unlink_track_export(str(run_dir), str(mp3), "long")) == long_mp4
    assert not long_mp4.exists()
    assert reel_mp4.exists()
    unlink_track_export(str(run_dir), str(mp3), "reel")
    assert not reel_mp4.exists()


def test_manual_pipeline_start_kwargs_for_repair_force_and_rebuild() -> None:
    repair = manual_pipeline_start_kwargs("repair_export")
    assert repair["repair_unhealthy"] is True
    assert repair["force_regenerate"] is False
    assert repair["mp3_paths"] is None

    one = manual_pipeline_start_kwargs("force_export", ["D:/a.mp3"])
    assert one["force_regenerate"] is True
    assert one["force_selected"] is True
    assert one["mp3_paths"] == ["D:/a.mp3"]

    wipe = manual_pipeline_start_kwargs("force_export")
    assert wipe["force_regenerate"] is True
    assert wipe["force_selected"] is False
    assert wipe["mp3_paths"] is None

    rebuild = manual_pipeline_start_kwargs("rebuild_export")
    assert rebuild["repair_unhealthy"] is False
    assert rebuild["force_regenerate"] is False


def test_decide_merge_prep_repairs_broken_then_merges_healthy(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(
        "features.video.lib.export_output_validity.resolve_ffprobe_path",
        lambda *_args, **_kwargs: "",
    )
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    ok = _write_mp3(run_dir, "1. Good_OK.mp3")
    _write_mp4(run_dir, ok.stem, size=MIN_VALID_EXPORT_BYTES + 8)
    _write_mp3(run_dir, "2. Missing_OK.mp3")
    health = inspect_run_export_health(str(run_dir), "long")
    assert decide_merge_prep(health) == "repair"
    assert decide_merge_prep(health, skip_repair=True) == "merge"

    healthy_only = inspect_run_export_health(str(run_dir), "long", mp3_paths=[str(ok)])
    assert decide_merge_prep(healthy_only) == "merge"

    ghost = inspect_run_export_health(str(run_dir), "long", mp3_paths=[str(run_dir / "ghost.mp3")])
    assert decide_merge_prep(ghost) == "missing_audio"
    assert decide_merge_prep([]) == "no_mp4"
