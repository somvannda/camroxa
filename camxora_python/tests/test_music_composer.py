"""Music composer helper tests."""

from shared.lib.manual_asset_paths import build_run_folder_label, plan_manual_asset_run_directories
from shared.lib.music_composer import (
    get_inclusive_date_list,
    get_inclusive_day_span,
    matches_history_filters,
    matches_history_date_range,
    normalize_history_date_range,
    HistoryFiltersState,
    song_matches_history_status_filter,
)
from shared.models.platform import MusicHistoryBatch


def test_normalize_history_date_range_swaps_inverted() -> None:
    assert normalize_history_date_range("2026-07-27", "2026-07-26") == (
        "2026-07-26",
        "2026-07-27",
    )
    assert normalize_history_date_range("2027-07-26", "2026-07-26") == (
        "2026-07-26",
        "2027-07-26",
    )


def test_inclusive_day_span_invalid_when_inverted() -> None:
    assert get_inclusive_day_span("2026-06-27", "2026-06-25") is None


def test_inclusive_date_list_three_days() -> None:
    assert get_inclusive_date_list("2026-06-25", "2026-06-27") == [
        "2026-06-25",
        "2026-06-26",
        "2026-06-27",
    ]


def test_build_run_folder_label_uses_date_first() -> None:
    assert build_run_folder_label(run_date="2026-06-25", album="Neon Nights") == "2026-06-25_Neon-Nights"


def test_plan_manual_asset_run_directories() -> None:
    planned = plan_manual_asset_run_directories(
        base_dir="D:/Music",
        ok_profile_folder="Primary",
        alt_profile_folder="Secondary",
        run_label=build_run_folder_label(run_date="2026-06-25", album="Neon Nights"),
        existing_ok_entries=["2026-06-25_Neon-Nights"],
        existing_alt_entries=["2026-06-25_Neon-Nights"],
    )
    assert planned.run_folder_name == "2026-06-25_Neon-Nights_02"
    assert planned.ok_run_dir.endswith("2026-06-25_Neon-Nights_02")


def test_last_batch_only_filter() -> None:
    batches = [
        MusicHistoryBatch(batch_id="b1", from_date="2026-06-25", to_date="2026-06-25", created_at="2026-06-25T10:00:00Z", updated_at="2026-06-25T10:00:00Z"),
        MusicHistoryBatch(batch_id="b2", from_date="2026-06-24", to_date="2026-06-24", created_at="2026-06-24T10:00:00Z", updated_at="2026-06-24T10:00:00Z"),
    ]
    assert matches_history_filters(batches[0], HistoryFiltersState(last_batch_only=True), 0)
    assert not matches_history_filters(batches[1], HistoryFiltersState(last_batch_only=True), 1)


def test_date_filter_includes_created_day_for_future_planned_run() -> None:
    batch = MusicHistoryBatch(
        batch_id="b-future",
        from_date="2026-07-22",
        to_date="2026-07-22",
        created_at="2026-07-20T15:00:00Z",
        updated_at="2026-07-20T15:30:00Z",
    )
    assert matches_history_date_range(batch, from_date="2026-07-20", to_date="2026-07-20")
    assert matches_history_date_range(batch, from_date="2026-07-22", to_date="2026-07-22")
    assert not matches_history_date_range(batch, from_date="2026-07-18", to_date="2026-07-19")


def test_date_filter_swaps_inverted_from_to() -> None:
    batch = MusicHistoryBatch(
        batch_id="b-day",
        from_date="2026-07-26",
        to_date="2026-07-26",
        created_at="2026-07-25T15:00:00Z",
        updated_at="2026-07-25T15:00:00Z",
    )
    # From 2027 / To 2026 (screenshot bug) must still match after normalize.
    assert matches_history_date_range(batch, from_date="2026-07-27", to_date="2026-07-26")
    assert matches_history_date_range(batch, from_date="2027-07-26", to_date="2026-07-26")


def test_last_batch_ignores_date_filter() -> None:
    batch = MusicHistoryBatch(
        batch_id="b-latest",
        from_date="2026-07-25",
        to_date="2026-07-25",
        created_at="2026-07-25T10:00:00Z",
        updated_at="2026-07-25T10:00:00Z",
    )
    assert matches_history_filters(
        batch,
        HistoryFiltersState(
            last_batch_only=True,
            from_date="2026-07-26",
            to_date="2026-07-27",
        ),
        0,
    )
    assert not matches_history_filters(
        batch,
        HistoryFiltersState(
            from_date="2026-07-26",
            to_date="2026-07-27",
        ),
        0,
    )


def test_date_filter_rejects_mid_gap_between_created_and_planned() -> None:
    batch = MusicHistoryBatch(
        batch_id="b-gap",
        from_date="2026-07-22",
        to_date="2026-07-22",
        created_at="2026-07-20T15:00:00Z",
        updated_at="2026-07-21T12:00:00Z",
    )
    assert not matches_history_date_range(batch, from_date="2026-07-21", to_date="2026-07-21")


def test_date_filter_ignores_updated_at_only() -> None:
    batch = MusicHistoryBatch(
        batch_id="b-old",
        from_date="2026-07-01",
        to_date="2026-07-01",
        created_at="2026-07-01T09:00:00Z",
        updated_at="2026-07-25T16:00:00Z",
    )
    assert not matches_history_date_range(batch, from_date="2026-07-25", to_date="2026-07-25")
    assert matches_history_date_range(batch, from_date="2026-07-01", to_date="2026-07-01")


def test_date_filter_multi_day_planned_window_overlap() -> None:
    batch = MusicHistoryBatch(
        batch_id="b-span",
        from_date="2026-07-20",
        to_date="2026-07-22",
        created_at="2026-07-19T10:00:00Z",
        updated_at="2026-07-19T10:00:00Z",
    )
    assert matches_history_date_range(batch, from_date="2026-07-21", to_date="2026-07-21")
    assert matches_history_date_range(batch, from_date="2026-07-18", to_date="2026-07-20")
    assert not matches_history_date_range(batch, from_date="2026-07-23", to_date="2026-07-24")


def test_batch_id_filter() -> None:
    batch = MusicHistoryBatch(
        batch_id="batch-a",
        from_date="2026-07-20",
        to_date="2026-07-20",
        created_at="2026-07-20T10:00:00Z",
        updated_at="2026-07-20T10:00:00Z",
    )
    assert matches_history_filters(batch, HistoryFiltersState(batch_id="batch-a"), 0)
    assert not matches_history_filters(batch, HistoryFiltersState(batch_id="batch-b"), 0)


def test_song_status_filter_buckets() -> None:
    assert song_matches_history_status_filter(
        status="suno_success", suno_status="success", status_filter="success"
    )
    assert song_matches_history_status_filter(
        status="suno_failed", suno_status="failed", status_filter="failed"
    )
    assert song_matches_history_status_filter(
        status="pending", suno_status=None, status_filter="pending"
    )
    assert not song_matches_history_status_filter(
        status="suno_success", suno_status="success", status_filter="failed"
    )
    assert song_matches_history_status_filter(
        status="suno_success",
        suno_status="success",
        status_filter=("success", "failed"),
    )
    assert song_matches_history_status_filter(
        status="suno_failed",
        suno_status="failed",
        status_filter=["failed", "pending"],
    )
    assert not song_matches_history_status_filter(
        status="pending",
        suno_status=None,
        status_filter=("success", "failed"),
    )
    assert song_matches_history_status_filter(
        status="pending", suno_status=None, status_filter=()
    )
