"""YouTube upload credits in the music plan estimate (and preference safety)."""

from __future__ import annotations

import pytest
from PySide6.QtWidgets import QApplication

from features.music.widgets.automation_card import AutomationCard
from shared.lib.music_costs import (
    get_music_plan_cost_breakdown,
    map_operation_costs,
    upload_ops_for_plan,
)
from shared.models.auth import ProfileResponse
from shared.models.platform import OperationCostResponse


@pytest.fixture
def qapp() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def _profile(profile_id: str, name: str) -> ProfileResponse:
    return ProfileResponse(id=profile_id, user_id="u1", name=name)


def _costs(publish: float = 5) -> dict[str, OperationCostResponse]:
    return map_operation_costs(
        [
            OperationCostResponse(operation_type="lyric", credits_per_operation=2, available=True),
            OperationCostResponse(operation_type="music", credits_per_operation=10, available=True),
            OperationCostResponse(
                operation_type="background_image", credits_per_operation=6, available=True
            ),
            OperationCostResponse(operation_type="video", credits_per_operation=2, available=True),
            OperationCostResponse(
                operation_type="video_merge", credits_per_operation=2, available=True
            ),
            OperationCostResponse(
                operation_type="publish", credits_per_operation=publish, available=True
            ),
        ]
    )


def _breakdown(costs, *, auto_upload: bool):
    return get_music_plan_cost_breakdown(
        costs.get("lyric"),
        costs.get("music"),
        costs.get("background_image"),
        [_profile("ok", "Primary")],
        [_profile("alt", "Secondary")],
        song_count=2,
        auto_gen_image=False,
        auto_gsuno=True,
        planned_day_count=1,
        image_source_mode="auto",
        video_cost=costs.get("video"),
        merge_cost=costs.get("video_merge"),
        auto_video=True,
        auto_merge=True,
        publish_cost=costs.get("publish"),
        auto_upload=auto_upload,
    )


def test_upload_ops_follow_merges() -> None:
    assert upload_ops_for_plan(0, auto_upload=True) == 0
    assert upload_ops_for_plan(10, auto_upload=False) == 0
    assert upload_ops_for_plan(10, auto_upload=True) == 10


def test_uploads_are_charged_per_merged_video() -> None:
    costs = _costs(publish=5)
    without = _breakdown(costs, auto_upload=False)
    with_uploads = _breakdown(costs, auto_upload=True)

    assert without is not None and with_uploads is not None
    assert without.upload_ops == 0
    assert without.publish_total_cost == 0.0
    assert with_uploads.upload_ops == with_uploads.merge_ops
    assert with_uploads.publish_total_cost == pytest.approx(with_uploads.merge_ops * 5)
    assert with_uploads.total_cost == pytest.approx(
        (without.total_cost or 0) + (with_uploads.publish_total_cost or 0)
    )


def test_missing_publish_price_makes_the_total_unknown() -> None:
    costs = map_operation_costs(
        [
            OperationCostResponse(operation_type="lyric", credits_per_operation=2, available=True),
            OperationCostResponse(operation_type="music", credits_per_operation=10, available=True),
        ]
    )
    breakdown = _breakdown(costs, auto_upload=True)

    assert breakdown is not None
    assert breakdown.publish_unit_cost is None
    assert breakdown.total_cost is None


def test_disabling_the_toggle_keeps_the_saved_preference(qapp: QApplication) -> None:
    card = AutomationCard()
    card.apply_automation_flags(
        auto_gen_image=False,
        auto_gsuno=False,
        auto_video_after_suno=False,
        auto_merge_after_video=False,
        auto_reel_after_video=False,
        auto_upload_youtube=True,
    )

    card.set_auto_upload_enabled(False)

    assert card.automation_values()["auto_upload_youtube"] is True
    assert card._auto_upload.isChecked() is True
    assert card._auto_upload.isEnabled() is False
