"""Progress router helper tests."""

from __future__ import annotations

from datetime import date, datetime, timezone

from platform_api.routers.progress import (
    _batch_run_from_date,
    _batch_run_to_date,
    _format_batch_run_date,
)


def test_format_batch_run_date_uses_planned_dates() -> None:
    batch = {
        "planned_from_date": date(2026, 7, 12),
        "planned_to_date": date(2026, 7, 12),
        "created_at": datetime(2026, 7, 11, 20, 0, tzinfo=timezone.utc),
    }
    assert _format_batch_run_date(batch) == "2026-07-12"


def test_format_batch_run_date_shows_planned_range() -> None:
    batch = {
        "planned_from_date": date(2026, 7, 11),
        "planned_to_date": date(2026, 7, 12),
        "created_at": datetime(2026, 7, 10, 12, 0, tzinfo=timezone.utc),
    }
    assert _format_batch_run_date(batch) == "2026-07-11 → 2026-07-12"


def test_coerce_uuid_list_normalizes_postgres_arrays() -> None:
    from platform_api.routers.progress import _coerce_uuid_list
    from uuid import uuid4

    first = uuid4()
    second = uuid4()
    assert _coerce_uuid_list([first, second]) == [str(first), str(second)]
    assert _coerce_uuid_list(None) == []


def test_batch_run_dates_fallback_to_utc_created_at() -> None:
    created = datetime(2026, 7, 11, 20, 0, tzinfo=timezone.utc)
    batch = {"created_at": created}
    assert _batch_run_from_date(batch) == date(2026, 7, 11)
    assert _batch_run_to_date(batch) == date(2026, 7, 11)


def test_progress_batch_fetch_limit_widens_for_active_only() -> None:
    from platform_api.routers.progress import _progress_batch_fetch_limit

    assert _progress_batch_fetch_limit(limit=10, active_only=False) == 20
    assert _progress_batch_fetch_limit(limit=10, active_only=True) == 100
    assert _progress_batch_fetch_limit(limit=80, active_only=False) == 100


def _progress_row(
    *,
    bg_ready: int,
    bg_total: int,
    long_ready: bool,
    saved: int = 10,
    th_ready: int = 1,
    th_total: int = 1,
    th_status: str = "success",
    song_failed: int = 0,
    pipeline_complete: bool = False,
    youtube_success: int = 0,
    background_path: str | None = None,
):
    from platform_api.routers.progress import _build_row

    profile_id = "9ea905e6-f706-458b-9d93-03d2239cd86c"
    batch_id = "b0bc9079-fd14-49c9-b0e8-b669cee50002"
    return _build_row(
        batch={
            "id": batch_id,
            "status": "completed",
            "song_count": 10,
            "ok_run_dir": r"neon-kicks\2026-09-02_Mercury-Heartline-Stories",
            "alt_run_dir": "",
            "ok_album": "Mercury Heartline Stories",
        },
        role="OK",
        profile_id=profile_id,
        profile_name="Neon Kicks",
        song_stats={"draft_failed": song_failed, "suno_failed": 0},
        suno_stats={"downloaded_ok": saved, "ready_ok": saved, "pending": 0},
        image_groups={
            (batch_id, profile_id, "OK"): {
                "background": {
                    "ready": bg_ready,
                    "total": bg_total,
                    "failed": 0,
                    "latest_status": "success" if bg_ready >= bg_total and bg_total else "pending",
                },
                "thumbnail": {
                    "ready": th_ready,
                    "total": th_total,
                    "failed": 1 if th_status == "failed" else 0,
                    "latest_status": th_status,
                },
            }
        },
        channel_assets={
            (batch_id, profile_id, "OK"): {
                "long_ready": long_ready,
                "reel_ready": False,
                "pipeline_complete": pipeline_complete,
                "background_16x9_path": background_path,
            }
        },
        youtube_groups={
            (batch_id, profile_id, "OK"): {"success": youtube_success, "pending": 0, "failed": 0, "latest_status": "SUCCESS" if youtube_success else ""}
        }
        if youtube_success
        else {},
        youtube_batch_groups={},
    )


def test_progress_leaves_image_stage_when_background_jobs_succeed_without_local_files() -> None:
    row = _progress_row(bg_ready=1, bg_total=1, long_ready=False)
    assert row.stage != "Image"
    assert "still in progress" not in (row.notes or "").lower()
    assert row.meta.bg_status == "READY"
    assert row.meta.long_ready is False
    assert row.meta.background_16x9_path is None
    assert "Waiting for image assets" in (row.converter or "")
    assert row.stage != "Merger"
    assert row.stage != "Done"


def test_progress_stays_on_image_when_background_jobs_incomplete() -> None:
    row = _progress_row(bg_ready=0, bg_total=1, long_ready=False)
    assert row.stage == "Image"
    assert "still in progress" in (row.notes or "").lower()


def test_progress_does_not_fake_export_ready_from_synthetic_path() -> None:
    from platform_api.routers.progress import _export_assets_verified

    assert _export_assets_verified(
        long_ready=True,
        reel_ready=False,
        paths=("server://image-job-ready/background-16x9", None, None, None),
    ) is False
    assert _export_assets_verified(
        long_ready=True,
        reel_ready=False,
        paths=(r"D:\SUNO\album\background-16x9.png", None, None, None),
    ) is True


def test_progress_keeps_music_stage_when_downloads_incomplete() -> None:
    row = _progress_row(bg_ready=1, bg_total=1, long_ready=False, saved=3)
    assert row.stage == "Music"


def test_progress_keeps_error_when_thumbnail_failed() -> None:
    row = _progress_row(
        bg_ready=1,
        bg_total=1,
        long_ready=False,
        th_ready=0,
        th_total=1,
        th_status="failed",
    )
    assert row.stage == "Error"


def test_progress_keeps_done_when_youtube_succeeded() -> None:
    row = _progress_row(bg_ready=1, bg_total=1, long_ready=False, youtube_success=1)
    assert row.stage == "Done"


def test_progress_keeps_completed_when_pipeline_complete() -> None:
    row = _progress_row(bg_ready=1, bg_total=1, long_ready=False, pipeline_complete=True)
    assert row.stage == "Completed"


def test_progress_music_count_clamps_retry_duplicates() -> None:
    # Extra suno_tasks rows from a retry must never render e.g. 16/15.
    row = _progress_row(bg_ready=1, bg_total=1, long_ready=False, saved=16)
    assert row.music == "10/10"
    assert row.meta.saved == 10
    assert row.meta.download_ready == 10
    assert row.meta.download_pending == 0
