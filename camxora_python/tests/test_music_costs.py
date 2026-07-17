"""Music cost calculation tests."""

from shared.lib.music_costs import get_music_plan_cost_breakdown, map_operation_costs
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


def test_auto_image_adds_image_costs() -> None:
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
    assert breakdown.image_total_cost == 80
    assert breakdown.total_cost == 92


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
