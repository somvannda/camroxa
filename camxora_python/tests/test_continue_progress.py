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
    long_ready: bool = True,
    run_dir: str = r"E:\runs\demo",
    converter: str = "pending",
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
            long_ready=long_ready,
            reel_ready=False,
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


def test_continue_starts_merge_on_merge_stage() -> None:
    plan = resolve_continue_progress(
        _entry(stage="merge", converter="long 10/10 completed", long_ready=True)
    )
    assert plan.action == "start_merge"


def test_continue_starts_merge_when_exports_complete(tmp_path) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    for i in range(3):
        path = run_dir / f"{i}. track_OK.mp4"
        path.write_bytes(b"0" * 60_000)
    plan = resolve_continue_progress(
        _entry(
            stage="export",
            status="pending",
            converter="long 3/3 completed",
            run_dir=str(run_dir),
            long_ready=True,
        )
    )
    assert plan.action == "start_merge"


def test_continue_none_when_done() -> None:
    plan = resolve_continue_progress(_entry(stage="done", long_ready=True))
    assert plan.action == "none"
