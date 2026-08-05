"""Image workspace lib tests."""

from __future__ import annotations

from shared.lib.image_workspace import (
    batch_date_label,
    batch_is_within_range,
    build_footer_detail,
    build_queue_rows,
    build_queue_status_summary,
    filter_batches_by_date,
    format_queue_role_status,
    normalize_image_prompt_settings,
    pick_preferred_image_job,
)
from shared.models.auth import ProfileResponse
from shared.models.platform import ImageJobListItem, MusicHistoryBatch, MusicHistorySong


def _batch(**overrides) -> MusicHistoryBatch:
    defaults = {
        "batch_id": "batch-1",
        "from_date": "2026-06-28",
        "to_date": "2026-06-28",
        "created_at": "2026-06-28T00:00:00Z",
        "updated_at": "2026-06-28T00:00:00Z",
        "songs": [
            MusicHistorySong(
                song_id="song-1",
                batch_index=0,
                title="Track One",
                album="Neon Nights",
            ),
            MusicHistorySong(
                song_id="song-2",
                batch_index=1,
                title="Track Two",
                album="Neon Nights",
            ),
        ],
    }
    defaults.update(overrides)
    return MusicHistoryBatch(**defaults)


def test_normalize_image_prompt_settings_legacy_fallback() -> None:
    settings = normalize_image_prompt_settings({"imagePrompt": "Legacy prompt"})
    assert settings.image_background_prompt == "Legacy prompt"
    assert settings.image_thumbnail_prompt == ""


def test_batch_is_within_range() -> None:
    batch = _batch(from_date="2026-06-25", to_date="2026-06-27")
    assert batch_is_within_range(batch, "2026-06-26", "2026-06-26")
    assert not batch_is_within_range(batch, "2026-06-28", "2026-06-28")


def test_build_queue_rows_groups_background_and_thumbnail() -> None:
    jobs = [
        ImageJobListItem(
            id="bg-1",
            batch_id="batch-1",
            song_id="song-1",
            profile_id="profile-ok",
            kind="background",
            channel_role="ok",
            status="success",
        ),
        ImageJobListItem(
            id="th-1",
            batch_id="batch-1",
            song_id="song-1",
            profile_id="profile-ok",
            kind="thumbnail",
            channel_role="ok",
            status="pending",
        ),
    ]
    rows = build_queue_rows(
        jobs,
        [_batch()],
        [ProfileResponse(id="profile-ok", user_id="u1", name="OK Channel")],
    )
    assert len(rows) == 1
    assert rows[0].bg_job is not None
    assert rows[0].th_job is not None
    assert rows[0].profile_name == "OK Channel"
    assert rows[0].album_label == "Neon Nights"
    assert rows[0].track_count == 2


def test_build_queue_rows_uses_role_specific_album_labels() -> None:
    batch = _batch(
        ok_profile_id="profile-ok",
        alt_profile_id="profile-alt",
        ok_album="Primary Album",
        alt_album="Secondary Album",
    )
    jobs = [
        ImageJobListItem(
            id="bg-ok",
            batch_id="batch-1",
            song_id="song-1",
            profile_id="profile-ok",
            kind="background",
            channel_role="ok",
            status="success",
        ),
        ImageJobListItem(
            id="bg-alt",
            batch_id="batch-1",
            song_id="song-1",
            profile_id="profile-alt",
            kind="background",
            channel_role="alt",
            status="success",
        ),
    ]
    rows = build_queue_rows(
        jobs,
        [batch],
        [
            ProfileResponse(id="profile-ok", user_id="u1", name="Primary"),
            ProfileResponse(id="profile-alt", user_id="u1", name="Secondary"),
        ],
    )
    ok_row = next(row for row in rows if row.role == "ok")
    alt_row = next(row for row in rows if row.role == "alt")
    assert ok_row.album_label == "Primary Album"
    assert alt_row.album_label == "Secondary Album"


def test_build_queue_rows_groups_by_batch_and_role_not_song() -> None:
    jobs = [
        ImageJobListItem(
            id="bg-1",
            batch_id="batch-1",
            song_id="song-1",
            profile_id="profile-ok",
            kind="background",
            channel_role="ok",
            status="success",
        ),
        ImageJobListItem(
            id="bg-2",
            batch_id="batch-1",
            song_id="song-2",
            profile_id="profile-ok",
            kind="background",
            channel_role="ok",
            status="failed",
        ),
        ImageJobListItem(
            id="bg-3",
            batch_id="batch-1",
            song_id="song-1",
            profile_id="profile-alt",
            kind="background",
            channel_role="alt",
            status="success",
        ),
    ]
    rows = build_queue_rows(
        jobs,
        [_batch()],
        [
            ProfileResponse(id="profile-ok", user_id="u1", name="OK Channel"),
            ProfileResponse(id="profile-alt", user_id="u1", name="ALT Channel"),
        ],
    )
    assert len(rows) == 2
    ok_row = next(row for row in rows if row.role == "ok")
    alt_row = next(row for row in rows if row.role == "alt")
    assert len(ok_row.bg_jobs) == 2
    assert ok_row.bg_job is not None and ok_row.bg_job.status == "success"
    assert format_queue_role_status(ok_row.bg_jobs) == "1 fail"
    assert alt_row.album_label == "Neon Nights"


def test_pick_preferred_image_job_prefers_success_over_failed() -> None:
    failed = ImageJobListItem(
        id="bg-failed",
        batch_id="batch-1",
        song_id="song-1",
        profile_id="profile-ok",
        kind="background",
        channel_role="ok",
        status="failed",
        updated_at="2026-06-28T02:00:00Z",
    )
    success = ImageJobListItem(
        id="bg-success",
        batch_id="batch-1",
        song_id="song-1",
        profile_id="profile-ok",
        kind="background",
        channel_role="ok",
        status="success",
        updated_at="2026-06-28T01:00:00Z",
    )
    assert pick_preferred_image_job(failed, success).id == "bg-success"
    assert pick_preferred_image_job(success, failed).id == "bg-success"


def test_build_queue_status_summary_empty_batches() -> None:
    summary = build_queue_status_summary(grouped_row_count=0, filtered_batch_count=0, rows=[])
    assert summary == "No batches found in the selected date range."


def test_build_footer_detail_includes_errors() -> None:
    rows = build_queue_rows(
        [
            ImageJobListItem(
                id="bg-1",
                batch_id="batch-1",
                song_id="song-1",
                profile_id="profile-ok",
                kind="background",
                channel_role="ok",
                status="failed",
                error="Generation failed",
                input_image_path="C:/samples/bg.png",
            )
        ],
        [_batch()],
        [ProfileResponse(id="profile-ok", user_id="u1", name="OK Channel")],
    )
    detail = build_footer_detail(rows[0])
    assert "BG error: Generation failed" in detail
    assert "BG sample: bg.png" in detail
    assert "2 tracks in batch" in detail


def test_batch_date_label_range() -> None:
    assert batch_date_label(_batch(from_date="2026-06-25", to_date="2026-06-27")) == "2026-06-25 → 2026-06-27"


def test_filter_batches_by_date() -> None:
    batches = [
        _batch(batch_id="b1", from_date="2026-06-28", to_date="2026-06-28"),
        _batch(batch_id="b2", from_date="2026-06-20", to_date="2026-06-20"),
    ]
    filtered = filter_batches_by_date(batches, "2026-06-28", "2026-06-28")
    assert [batch.batch_id for batch in filtered] == ["b1"]


def test_build_queue_rows_manual_image_album_label() -> None:
    batch = _batch(
        batch_id="manual-1",
        status="manual_image",
        ok_album="Not available",
        from_date="2026-08-05",
        to_date="2026-08-05",
        songs=[],
    )
    rows = build_queue_rows(
        [
            ImageJobListItem(
                id="job-bg",
                batch_id="manual-1",
                profile_id="profile-ok",
                kind="background",
                channel_role="ok",
                status="pending",
            )
        ],
        [batch],
        [ProfileResponse(id="profile-ok", user_id="u1", name="OK Channel")],
    )
    assert len(rows) == 1
    assert rows[0].album_label == "Not available"
    assert rows[0].profile_name == "Not available"
    assert rows[0].role == "n/a"
