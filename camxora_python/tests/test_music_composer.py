"""Music composer helper tests."""

from shared.lib.manual_asset_paths import build_run_folder_label, plan_manual_asset_run_directories
from shared.lib.music_composer import get_inclusive_date_list, get_inclusive_day_span, matches_history_filters, HistoryFiltersState
from shared.models.platform import MusicHistoryBatch


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
