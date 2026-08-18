"""Tests for Continue Progress action resolution."""

from __future__ import annotations

from features.progress.lib.continue_progress import resolve_continue_progress
from features.progress.widgets.operational_rows_card import EffectiveProgressRow
from shared.models.platform import ProgressRow, ProgressRowMeta


def _entry(
    *,
    stage: str = "export",
    status: str = "pending",
    music: str = "READY",
    draft_ids: list[str] | None = None,
    suno_ids: list[str] | None = None,
    bg_total: int = 2,
    th_total: int = 2,
    bg_status: str = "",
    th_status: str = "",
    long_ready: bool = True,
    run_dir: str = r"E:\runs\demo",
    converter: str = "pending",
    expected: int = 0,
) -> EffectiveProgressRow:
    row = ProgressRow(
        run_date="2026-07-20",
        channel="Bass Drive",
        album="Demo",
        stage=stage,
        status=status,
        music=music,
        image="ok",
        converter=converter,
        merge="",
        youtube="",
        notes="",
        updated="2026-07-20T00:00:00Z",
        batch="batch-1",
        meta=ProgressRowMeta(
            batch_id="batch-1",
            profile_id="profile-1",
            role="primary",
            run_dir=run_dir,
            draft_failed_song_ids=draft_ids or [],
            suno_failed_song_ids=suno_ids or [],
            bg_total=bg_total,
            th_total=th_total,
            bg_status=bg_status,
            th_status=th_status,
            long_ready=long_ready,
            reel_ready=False,
            expected=expected,
        ),
    )
    return EffectiveProgressRow(
        row=row,
        effective_status=status,
        effective_converter=converter,
        effective_merge="",
        effective_stage=stage,
        effective_notes="",
    )


def test_continue_prefers_failed_drafts() -> None:
    plan = resolve_continue_progress(_entry(draft_ids=["s1", "s2"]))
    assert plan.action == "retry_drafts"
    assert plan.song_ids == ["s1", "s2"]


def test_continue_prefers_failed_suno() -> None:
    plan = resolve_continue_progress(_entry(suno_ids=["s9"]))
    assert plan.action == "retry_suno"
    assert plan.song_ids == ["s9"]


def test_continue_enqueues_images_when_music_ready() -> None:
    plan = resolve_continue_progress(
        _entry(stage="music", bg_total=0, th_total=0, long_ready=False)
    )
    assert plan.action == "enqueue_images"


def test_continue_starts_export_on_export_stage() -> None:
    plan = resolve_continue_progress(_entry(stage="export", status="pending"))
    assert plan.action == "start_export"


def test_continue_retries_images_while_jobs_pending() -> None:
    plan = resolve_continue_progress(
        _entry(stage="image", bg_status="PENDING", long_ready=False)
    )
    assert plan.action == "retry_images"


def test_continue_does_not_retry_when_image_jobs_already_ready() -> None:
    plan = resolve_continue_progress(
        _entry(stage="image", bg_status="READY", long_ready=True)
    )
    assert plan.action != "retry_images"
    assert plan.action == "start_export"


def test_continue_does_not_export_converter_without_local_assets() -> None:
    plan = resolve_continue_progress(
        _entry(stage="converter", bg_status="READY", long_ready=False)
    )
    assert plan.action != "start_export"


def test_continue_starts_merge_on_merge_stage() -> None:
    plan = resolve_continue_progress(
        _entry(stage="merge", converter="long 10/10 completed", long_ready=True)
    )
    assert plan.action == "start_merge"


def test_continue_starts_merge_when_exports_complete(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(
        "features.video.lib.export_output_validity.resolve_ffprobe_path",
        lambda *_args, **_kwargs: "",
    )
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    for i in range(3):
        (run_dir / f"{i}. track_OK.mp3").write_bytes(b"id3")
        (run_dir / f"{i}. track_OK.mp4").write_bytes(b"0" * 60_000)
    plan = resolve_continue_progress(
        _entry(
            stage="export",
            status="pending",
            converter="long 3/3 completed",
            run_dir=str(run_dir),
            long_ready=True,
            expected=3,
        )
    )
    assert plan.action == "start_merge"


def test_continue_none_when_done() -> None:
    plan = resolve_continue_progress(_entry(stage="done", long_ready=True))
    assert plan.action == "none"


def _album_with_gap(tmp_path, *, missing_last: bool = True, tiny_last: bool = False):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    for index in range(1, 4):
        mp3 = run_dir / f"{index}. Track_OK.mp3"
        mp3.write_bytes(b"id3")
        if index == 3 and missing_last:
            continue
        size = 20 if (tiny_last and index == 3) else 60_000
        (run_dir / f"{index}. Track_OK.mp4").write_bytes(b"0" * size)
    return run_dir


def test_continue_repairs_missing_mp4_instead_of_merging(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(
        "features.video.lib.export_output_validity.resolve_ffprobe_path",
        lambda *_args, **_kwargs: "",
    )
    run_dir = _album_with_gap(tmp_path)
    plan = resolve_continue_progress(
        _entry(
            stage="export",
            converter="long 2/3 completed",
            run_dir=str(run_dir),
            long_ready=True,
            expected=3,
        )
    )
    assert plan.action == "start_export"
    assert "Regenerate missing/broken" in plan.label


def test_continue_repairs_tiny_mp4_on_merge_stage(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(
        "features.video.lib.export_output_validity.resolve_ffprobe_path",
        lambda *_args, **_kwargs: "",
    )
    run_dir = _album_with_gap(tmp_path, missing_last=False, tiny_last=True)
    plan = resolve_continue_progress(
        _entry(
            stage="merge",
            converter="long 3/3 completed",
            run_dir=str(run_dir),
            long_ready=True,
            expected=3,
        )
    )
    assert plan.action == "start_export"
    assert "Regenerate missing/broken" in plan.label


def test_continue_merges_when_all_mp4s_usable(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(
        "features.video.lib.export_output_validity.resolve_ffprobe_path",
        lambda *_args, **_kwargs: "",
    )
    run_dir = _album_with_gap(tmp_path, missing_last=False)
    plan = resolve_continue_progress(
        _entry(
            stage="merge",
            converter="long 3/3 completed",
            run_dir=str(run_dir),
            long_ready=True,
            expected=3,
        )
    )
    assert plan.action == "start_merge"


def test_continue_asks_to_download_when_album_is_short_of_expected(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(
        "features.video.lib.export_output_validity.resolve_ffprobe_path",
        lambda *_args, **_kwargs: "",
    )
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    for index in range(1, 3):
        (run_dir / f"{index}. Track_OK.mp3").write_bytes(b"id3")
        (run_dir / f"{index}. Track_OK.mp4").write_bytes(b"0" * 60_000)
    plan = resolve_continue_progress(
        _entry(
            stage="merge",
            converter="long 2/3 completed",
            run_dir=str(run_dir),
            long_ready=True,
            expected=3,
        )
    )
    assert plan.action == "none"
    assert "Download missing MP3s" in plan.label
