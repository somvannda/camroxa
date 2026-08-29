"""Dashboard view tests — studio chrome plus live overview bind."""

from __future__ import annotations

from datetime import datetime

import pytest
from PySide6.QtCore import QDate
from PySide6.QtWidgets import QApplication, QPushButton

from features.create.widgets.create_header import CreateHeader
from features.dashboard.views.dashboard_view import DashboardView
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
                DailyUsage(date="2026-07-01", songs=1, images=0, videos=0, manual_exports=0),
                DailyUsage(date="2026-07-02", songs=2, images=1, videos=0, manual_exports=2),
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
    assert view._daily_channels.isVisible()
    assert all(card._value.text() == "--" for card in view._kpi_cards)
    assert view._activity._table.item(0, 0).text() == LOADING_MESSAGE
    buttons = view.findChildren(QPushButton)
    assert any(btn.text().lower() == "refresh" for btn in buttons)
    header = view.widget().findChild(CreateHeader)
    assert header is not None
    assert header.objectName() == "CreateHeader"


def test_error_banner(qapp: QApplication) -> None:
    from PySide6.QtWidgets import QLabel

    view = DashboardView(PlatformApi())
    view._on_failed("network")
    assert not view._error_banner.isHidden()
    label = view._error_banner.findChild(QLabel)
    assert label is not None
    assert "unable to load dashboard statistics right now" in label.text().lower()


def _apply_in_range(view: DashboardView, overview: DashboardOverview | None = None) -> None:
    view._from_date.blockSignals(True)
    view._to_date.blockSignals(True)
    view._from_date.setDate(QDate(2026, 7, 1))
    view._to_date.setDate(QDate(2026, 7, 7))
    view._from_date.blockSignals(False)
    view._to_date.blockSignals(False)
    view._apply_overview(overview or _sample_overview())


def test_success_bind_kpis(qapp: QApplication) -> None:
    view = DashboardView(PlatformApi())
    _apply_in_range(view)
    values = [card._value.text() for card in view._kpi_cards]
    assert values[0] == "25 / 100"
    assert values[1] == "3"
    assert values[4] == "2"
    assert view._kpi_cards[0]._delta.text() == "25% this period"
    assert view._weekly._plan_value.text() == "Monthly"


def test_songs_bar_value_total_format(qapp: QApplication) -> None:
    row = ProgressSummaryRow("Songs", bar_color="sky")
    row.set_amounts(30, 40)
    assert row._amount.text() == "30 / 40"
    assert row._percent.text() == "75%"


def test_remaining_card_shows_wallet_and_meters(qapp: QApplication) -> None:
    view = DashboardView(PlatformApi())
    _apply_in_range(view)
    assert view._remaining._wallet._value.text() == "100"
    assert view._remaining._spent._value.text() == "25"
    assert view._remaining._songs._amount.text() == "10 / 40"
    assert view._daily_channels._model.rowCount() >= 1
    assert view._daily_channels._model.data(view._daily_channels._model.index(1, 0)) == "Primary"


def test_remaining_card_zero_wallet_still_shows_number(qapp: QApplication) -> None:
    overview = _sample_overview()
    overview.license.wallet_balance = 0
    overview.me.credit_balance = 0
    overview.stats.credits_spent = 0
    view = DashboardView(PlatformApi())
    view._apply_overview(overview)
    assert view._remaining._wallet._value.text() == "0"
    assert view._remaining._spent._value.text() == "0"


def test_activity_loading_and_empty(qapp: QApplication) -> None:
    view = DashboardView(PlatformApi())
    view._enter_loading_state()
    assert view._activity._table.item(0, 0).text() == LOADING_MESSAGE
    view._activity.show_empty()
    assert view._activity._table.item(0, 0).text() == EMPTY_MESSAGE


def test_activity_rows_with_overview(qapp: QApplication) -> None:
    view = DashboardView(PlatformApi())
    _apply_in_range(view)
    assert view._activity._table.rowCount() == 1
    assert view._activity._table.item(0, 1).text() == "Song"
    assert view._activity._table.item(0, 4).text() == "--"
    assert view._activity._table.cellWidget(0, 6) is not None


def test_plan_slug_is_humanized(qapp: QApplication) -> None:
    overview = _sample_overview()
    overview.license.plan_type = "starter_monthly"
    view = DashboardView(PlatformApi())
    _apply_in_range(view, overview)
    assert view._weekly._plan_value.text() == "Starter (Monthly)"
    assert view._activity._plan_line.text() == "Starter (Monthly)"


def test_date_range_filters_activity_and_chart(qapp: QApplication) -> None:
    view = DashboardView(PlatformApi())
    view._apply_overview(_sample_overview())
    view._from_date.setDate(QDate(2026, 8, 1))
    view._to_date.setDate(QDate(2026, 8, 8))
    assert view._activity._table.item(0, 0).text() == EMPTY_MESSAGE
    assert view._kpi_cards[1]._value.text() == "0"


def test_refresh_disables_button_while_worker_runs(qapp: QApplication, monkeypatch) -> None:
    from shared.workers import data_workers

    view = DashboardView(PlatformApi())
    started: list[int] = []

    def _track_start(self) -> None:  # noqa: ANN001
        started.append(1)

    monkeypatch.setattr(data_workers.DashboardOverviewWorker, "start", _track_start)
    view._on_refresh()
    assert started == [1]
    assert view._refresh_btn.text() == "Refreshing…"
    assert not view._refresh_btn.isEnabled()
    view._on_worker_finished()
    assert view._refresh_btn.isEnabled()
    assert view._refresh_btn.text() == "Refresh"


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


def test_dashboard_table_selection_uses_studio_purple() -> None:
    from features.dashboard.dashboard_styles import build_dashboard_page_qss

    qss = build_dashboard_page_qss()
    assert "QTableView#ChannelTable::item:selected" in qss
    assert "QTableWidget#ActivityTable::item:selected" in qss
    assert "background-color: #6335D9" in qss
