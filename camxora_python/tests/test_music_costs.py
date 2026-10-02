"""Music cost calculation tests."""

from shared.lib.music_costs import (
    format_button_credit_label,
    format_plan_credits,
    get_music_plan_cost_breakdown,
    map_operation_costs,
)
from shared.models.auth import ProfileResponse
from shared.models.platform import OperationCostResponse


def _profile(profile_id: str, name: str) -> ProfileResponse:
    return ProfileResponse(id=profile_id, user_id="u1", name=name)


def _costs() -> dict[str, OperationCostResponse]:
    return map_operation_costs(
        [
            OperationCostResponse(operation_type="lyric", credits_per_operation=3, available=True),
            OperationCostResponse(operation_type="music", credits_per_operation=7, available=True),
            OperationCostResponse(operation_type="background_image", credits_per_operation=5, available=True),
            OperationCostResponse(operation_type="video", credits_per_operation=3, available=True),
            OperationCostResponse(operation_type="video_merge", credits_per_operation=10, available=True),
        ]
    )


def test_default_batch_total_12_credits() -> None:
    costs = _costs()
    breakdown = get_music_plan_cost_breakdown(
        costs.get("lyric"),
        costs.get("music"),
        costs.get("background_image"),
        [_profile("ok", "Primary")],
        [_profile("alt", "Secondary")],
        song_count=4,
        auto_gen_image=False,
        auto_gsuno=False,
        planned_day_count=1,
        image_source_mode="ai",
    )
    assert breakdown is not None
    assert breakdown.total_cost == 12


def test_auto_image_is_per_batch_not_per_song() -> None:
    costs = _costs()
    breakdown = get_music_plan_cost_breakdown(
        costs.get("lyric"),
        costs.get("music"),
        costs.get("background_image"),
        [_profile("ok", "Primary")],
        [_profile("alt", "Secondary")],
        song_count=4,
        auto_gen_image=True,
        auto_gsuno=False,
        planned_day_count=1,
        image_source_mode="ai",
    )
    assert breakdown is not None
    # 1 batch × (2 ok + 2 alt) = 4 album image jobs × 5 credits
    assert breakdown.image_jobs_per_batch == 4
    assert breakdown.image_total_jobs == 4
    assert breakdown.image_total_cost == 20
    assert breakdown.total_cost == 32


def test_four_pairs_image_jobs_scale_by_batch_not_song() -> None:
    costs = _costs()
    primaries = [_profile(f"ok{i}", f"P{i}") for i in range(4)]
    secondaries = [_profile(f"alt{i}", f"S{i}") for i in range(4)]
    breakdown = get_music_plan_cost_breakdown(
        costs.get("lyric"),
        costs.get("music"),
        costs.get("background_image"),
        primaries,
        secondaries,
        song_count=10,
        auto_gen_image=True,
        auto_gsuno=True,
        planned_day_count=1,
        image_source_mode="ai",
    )
    assert breakdown is not None
    assert breakdown.planned_song_count == 40
    assert breakdown.planned_batch_count == 4
    # 4 batches × 4 jobs = 16 (NOT 16×40)
    assert breakdown.image_total_jobs == 16
    assert breakdown.image_total_cost == 80
    assert breakdown.suno_total_cost == 280
    assert breakdown.draft_total_cost == 120
    assert breakdown.total_cost == 480


def test_auto_gsuno_adds_suno_costs() -> None:
    costs = _costs()
    breakdown = get_music_plan_cost_breakdown(
        costs.get("lyric"),
        costs.get("music"),
        costs.get("background_image"),
        [_profile("ok", "Primary")],
        [_profile("alt", "Secondary")],
        song_count=4,
        auto_gen_image=False,
        auto_gsuno=True,
        planned_day_count=1,
        image_source_mode="ai",
    )
    assert breakdown is not None
    assert breakdown.suno_total_cost == 28
    assert breakdown.total_cost == 40


def test_three_day_auto_gsuno_total_120() -> None:
    costs = _costs()
    breakdown = get_music_plan_cost_breakdown(
        costs.get("lyric"),
        costs.get("music"),
        costs.get("background_image"),
        [_profile("ok", "Primary")],
        [_profile("alt", "Secondary")],
        song_count=4,
        auto_gen_image=False,
        auto_gsuno=True,
        planned_day_count=3,
        image_source_mode="ai",
    )
    assert breakdown is not None
    assert breakdown.total_cost == 120


def test_credit_labels_hide_float_noise() -> None:
    assert format_plan_credits(99.40090000000001) == "99.4"
    assert format_button_credit_label("Generate", 99.40090000000001) == "Generate (99.4 credits)"
    assert format_plan_credits(10) == "10"


def test_video_and_merge_added_to_total() -> None:
    costs = _costs()
    breakdown = get_music_plan_cost_breakdown(
        costs.get("lyric"),
        costs.get("music"),
        costs.get("background_image"),
        [_profile("ok", "Primary")],
        [_profile("alt", "Secondary")],
        song_count=4,
        auto_gen_image=False,
        auto_gsuno=True,
        planned_day_count=1,
        image_source_mode="ai",
        video_cost=costs.get("video"),
        merge_cost=costs.get("video_merge"),
        auto_video=True,
        auto_merge=True,
    )
    assert breakdown is not None
    # 4 songs × 2 channels = 8 exports @ 3 credits; 1 batch × 2 channels = 2 merges @ 10.
    assert breakdown.video_ops == 8
    assert breakdown.video_total_cost == 24
    assert breakdown.merge_ops == 2
    assert breakdown.merge_total_cost == 20
    assert breakdown.video_merge_total_cost == 44
    # 12 draft + 28 suno + 44 video/merge = 84
    assert breakdown.total_cost == 84


def test_auto_reel_doubles_video_and_merge() -> None:
    costs = _costs()
    breakdown = get_music_plan_cost_breakdown(
        costs.get("lyric"),
        costs.get("music"),
        costs.get("background_image"),
        [_profile("ok", "Primary")],
        [_profile("alt", "Secondary")],
        song_count=4,
        auto_gen_image=False,
        auto_gsuno=True,
        planned_day_count=1,
        image_source_mode="ai",
        video_cost=costs.get("video"),
        merge_cost=costs.get("video_merge"),
        auto_video=True,
        auto_merge=True,
        auto_reel=True,
    )
    assert breakdown is not None
    assert breakdown.video_ops == 16
    assert breakdown.merge_ops == 4


def test_video_merge_ignored_without_suno() -> None:
    costs = _costs()
    breakdown = get_music_plan_cost_breakdown(
        costs.get("lyric"),
        costs.get("music"),
        costs.get("background_image"),
        [_profile("ok", "Primary")],
        [_profile("alt", "Secondary")],
        song_count=4,
        auto_gen_image=False,
        auto_gsuno=False,
        planned_day_count=1,
        image_source_mode="ai",
        video_cost=costs.get("video"),
        merge_cost=costs.get("video_merge"),
        auto_video=True,
        auto_merge=True,
    )
    assert breakdown is not None
    assert breakdown.video_ops == 0
    assert breakdown.merge_ops == 0
    assert breakdown.total_cost == 12
