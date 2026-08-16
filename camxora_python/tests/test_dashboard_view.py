"""Dashboard view tests — requirements T-1 through T-6."""

from __future__ import annotations

from datetime import datetime

import pytest
from PySide6.QtWidgets import QApplication, QPushButton

from features.dashboard.views.dashboard_view import DashboardView
from features.dashboard.widgets.error_banner import ERROR_MESSAGE
from features.dashboard.widgets.progress_summary_row import ProgressSummaryRow
from features.dashboard.widgets.recent_activity_card import EMPTY_MESSAGE, LOADING_MESSAGE
from shared.models.auth import UserMeResponse
from shared.models.platform import (
    ChannelDailyQuota,
    DailyUsage,
    DashboardOverview,
    DashboardStatsResponse,
    QuotaStatusResponse,
    RecentActivity,
    ValidateLicenseResponse,
)
from shared.services.platform_api import PlatformApi


@pytest.fixture(scope="session")
def qapp() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def _sample_overview() -> DashboardOverview:
    return DashboardOverview(
        me=UserMeResponse(
            id="user-1",
            email="user@example.com",
            email_confirmed=True,
            display_name="User",
            credit_balance=100,
            plan_name="Pro",
        ),
        license=ValidateLicenseResponse(
            plan_type="monthly",
            profile_allowance=2,
            monthly_song_quota=40,
            songs_remaining=30,
            wallet_balance=100,
        ),
        stats=DashboardStatsResponse(
            credits_spent=25,
            credits_remaining=75,
            credits_total=100,
            songs_generated=8,
            songs_remaining=30,
            songs_quota=40,
            images_generated=3,
            studio_exports=0,
            manual_exports=2,
            videos_generated=2,
            usage_by_day=[
                DailyUsage(date="2026-07-01", songs=1, images=0, videos=0),
                DailyUsage(date="2026-07-02", songs=2, images=1, videos=0),
            ],
            recent_activity=[
                RecentActivity(
                    timestamp=datetime(2026, 7, 7, 14, 30),
                    kind="Song",
                    detail="Track A",
                    status="success",
                )
            ],
        ),
        quota=QuotaStatusResponse(
            songs_remaining=30,
            songs_quota=40,
            channels=[
                ChannelDailyQuota(
                    profile_id="profile-1",
                    profile_name="Primary",
                    daily_songs_used=1,
                    daily_songs_limit=7,
                    daily_songs_remaining=6,
                    daily_images_used=0,
                    daily_images_limit=7,
                    daily_images_remaining=7,
                )
            ],
        ),
    )


def test_loading_placeholders(qapp: QApplication) -> None:
    view = DashboardView(PlatformApi())
    view.show()
    assert view._weekly.isVisible()
    assert view._remaining.isVisible()
    assert all(card._value.text() == "--" for card in view._kpi_cards)
    assert view._activity._table.item(0, 0).text() == LOADING_MESSAGE
    buttons = view.findChildren(QPushButton)
    assert not any("refresh" in btn.text().lower() for btn in buttons)


def test_error_banner(qapp: QApplication) -> None:
    from PySide6.QtWidgets import QLabel

    view = DashboardView(PlatformApi())
    view._on_failed("network")
    assert not view._error_banner.isHidden()
    label = view._error_banner.findChild(QLabel)
    assert label is not None
    assert "unable to load dashboard statistics right now" in label.text().lower()


def test_success_bind_kpis(qapp: QApplication) -> None:
    view = DashboardView(PlatformApi())
    view._apply_overview(_sample_overview())
    values = [card._value.text() for card in view._kpi_cards]
    assert values[0] == "25"
    assert values[1] == "8"
    assert values[4] == "2"


def test_daily_channel_quota_card(qapp: QApplication) -> None:
    view = DashboardView(PlatformApi())
    view.show()
    view._apply_overview(_sample_overview())
    assert view._daily_channels._empty.isHidden()
    assert view._daily_channels._rows.count() == 1


def test_songs_bar_value_total_format(qapp: QApplication) -> None:
    row = ProgressSummaryRow("Songs", bar_color="sky")
    row.set_amounts(30, 40)
    assert row._amount.text() == "30 / 40"
    assert row._percent.text() == "75%"


def test_remaining_card_shows_used_over_quota(qapp: QApplication) -> None:
    view = DashboardView(PlatformApi())
    view._apply_overview(_sample_overview())
    # 40 quota, 30 remaining → 10 used
    assert view._remaining._songs._amount.text() == "10 / 40"
    assert view._remaining._songs._percent.text() == "25%"
    assert view._remaining._song_quota._value.text() == "10 of 40 used"
    assert view._remaining._credits._amount.text() == "25 / 100"


def test_remaining_card_uses_scaled_quota_not_base_plan(qapp: QApplication) -> None:
    overview = _sample_overview()
    overview.license.monthly_song_quota = 300
    overview.license.songs_remaining = 467
    overview.license.monthly_image_quota = 120
    overview.license.images_remaining = 189
    overview.quota.songs_quota = 1500
    overview.quota.songs_remaining = 467
    overview.quota.images_quota = 600
    overview.quota.images_remaining = 189
    overview.quota.drafts_quota = 6300
    overview.quota.drafts_remaining = 4086
    overview.stats.songs_quota = 1500
    overview.stats.songs_remaining = 467

    view = DashboardView(PlatformApi())
    view._apply_overview(overview)
    assert view._remaining._songs._amount.text() == "1,033 / 1,500"
    assert view._remaining._images._amount.text() == "411 / 600"
    assert view._remaining._drafts._amount.text() == "2,214 / 6,300"
    assert view._remaining._song_quota._value.text() == "1,033 of 1,500 used"


def test_remaining_card_exhausted_quota_reads_as_used(qapp: QApplication) -> None:
    overview = _sample_overview()
    overview.license.monthly_song_quota = 300
    overview.license.songs_remaining = 0
    overview.quota.songs_quota = 300
    overview.quota.songs_remaining = 0
    overview.stats.songs_quota = 300
    overview.stats.songs_remaining = 0

    view = DashboardView(PlatformApi())
    view._apply_overview(overview)
    assert view._remaining._songs._amount.text() == "300 / 300"
    assert view._remaining._songs._percent.text() == "100%"
    assert view._remaining._song_quota._value.text() == "300 of 300 used"


def test_activity_loading_and_empty(qapp: QApplication) -> None:
    view = DashboardView(PlatformApi())
    view._enter_loading_state()
    assert view._activity._table.item(0, 0).text() == LOADING_MESSAGE
    view._activity.show_empty()
    assert view._activity._table.item(0, 0).text() == EMPTY_MESSAGE


def test_activity_rows_with_overview(qapp: QApplication) -> None:
    view = DashboardView(PlatformApi())
    view._apply_overview(_sample_overview())
    assert view._activity._table.rowCount() == 1
    assert view._activity._table.item(0, 1).text() == "Song"
    assert view._activity._table.cellWidget(0, 4) is not None


def test_dashboard_skips_refresh_when_cache_fresh(qapp: QApplication, monkeypatch) -> None:
    from shared.services.workspace_cache import WorkspaceCache
    from shared.workers import data_workers

    cache = WorkspaceCache()
    overview = _sample_overview()
    cache.apply_dashboard(overview)
    view = DashboardView(PlatformApi(), cache=cache)
    view._apply_overview(overview)
    started: list[int] = []

    def _track_start(self) -> None:  # noqa: ANN001
        started.append(1)

    monkeypatch.setattr(data_workers.DashboardOverviewWorker, "start", _track_start)
    view.refresh_data()
    assert started == []
