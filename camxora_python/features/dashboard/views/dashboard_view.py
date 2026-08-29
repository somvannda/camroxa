"""Dashboard page — Create studio chrome with dashboard information architecture."""

from __future__ import annotations

from datetime import date, datetime, timedelta

from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from features.account.views.upgrade_plans_dialog import format_plan_display_name
from features.create.widgets.create_header import CreateHeader
from features.create.widgets.studio_controls import StudioDateEdit
from features.create.widgets.studio_panel import fill_studio_canvas, paint_studio_card
from features.dashboard.dashboard_styles import build_dashboard_page_qss
from features.dashboard.widgets.daily_channel_quota_card import DailyChannelQuotaCard
from features.dashboard.widgets.error_banner import DashboardErrorBanner
from features.dashboard.widgets.kpi_card import KpiCard
from features.dashboard.widgets.recent_activity_card import RecentActivityCard
from features.dashboard.widgets.remaining_month_card import RemainingMonthCard
from features.dashboard.widgets.weekly_usage_card import WeeklyUsageCard
from shared.lib.formatting import format_compact_number, format_short_date, percent_of
from shared.lib.ui_font import ensure_inter_loaded, studio_font
from shared.models.platform import DailyUsage, DashboardOverview, DashboardStatsResponse, RecentActivity
from shared.services.platform_api import PlatformApi
from shared.services.workspace_cache import WorkspaceCache
from shared.workers.data_workers import DashboardOverviewWorker

KPI_CONFIG = (
    ("Credits Spent", "sparkles"),
    ("Songs Generated", "music-4"),
    ("Images Generated", "image"),
    ("Studio Exports", "video"),
    ("Manual Exports", "download"),
    ("YouTube Uploads", "youtube"),
)
PAGE_GAP = 10


class _FramedHeader(CreateHeader):
    """Create header with a painted card frame (QScrollArea QSS cannot reach it)."""

    def paintEvent(self, event) -> None:  # noqa: N802
        paint_studio_card(self)


class DashboardView(QScrollArea):
    """Dashboard with KPI cards, usage chart, quotas, and recent activity."""

    def __init__(
        self,
        api: PlatformApi,
        parent: QWidget | None = None,
        *,
        cache: WorkspaceCache | None = None,
    ) -> None:
        super().__init__(parent)
        self._api = api
        self._cache = cache
        self._worker: DashboardOverviewWorker | None = None
        self._loading = False
        self._last_overview: DashboardOverview | None = None
        self._range_dirty = False
        self.setObjectName("dashboard_workspace")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        ensure_inter_loaded()
        self.setStyleSheet(build_dashboard_page_qss())
        self.setFont(studio_font(12))
        fill_studio_canvas(self.viewport())

        container = QWidget()
        container.setObjectName("dashboard_workspace")
        container.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        fill_studio_canvas(container)
        container.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        root = QVBoxLayout(container)
        root.setContentsMargins(PAGE_GAP, PAGE_GAP, PAGE_GAP, PAGE_GAP)
        root.setSpacing(PAGE_GAP)

        trailing = QWidget()
        trailing_row = QHBoxLayout(trailing)
        trailing_row.setContentsMargins(0, 0, 0, 0)
        trailing_row.setSpacing(8)
        today = date.today()
        start = today - timedelta(days=7)
        self._from_date = StudioDateEdit()
        self._from_date.setDate(QDate(start.year, start.month, start.day))
        self._from_date.setFixedWidth(132)
        self._to_date = StudioDateEdit()
        self._to_date.setDate(QDate(today.year, today.month, today.day))
        self._to_date.setFixedWidth(132)
        arrow = QLabel("→")
        arrow.setObjectName("FieldLabel")
        self._refresh_btn = QPushButton("Refresh")
        self._refresh_btn.setObjectName("SecondaryButton")
        self._refresh_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._refresh_btn.setFixedHeight(28)
        self._refresh_btn.clicked.connect(self._on_refresh)
        trailing_row.addWidget(self._from_date)
        trailing_row.addWidget(arrow)
        trailing_row.addWidget(self._to_date)
        trailing_row.addWidget(self._refresh_btn)
        self._from_date.dateChanged.connect(self._on_range_changed)
        self._to_date.dateChanged.connect(self._on_range_changed)

        header = _FramedHeader(
            title="Dashboard",
            subtitle="Overview of the current CAMXORA account, profile readiness, and studio status.",
            meta="",
            eyebrow="WORKSPACE",
            trailing=trailing,
        )
        header.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        root.addWidget(header)

        self._error_banner = DashboardErrorBanner()
        self._error_banner.hide()
        root.addWidget(self._error_banner)

        kpi_row = QHBoxLayout()
        kpi_row.setSpacing(PAGE_GAP)
        self._kpi_cards: list[KpiCard] = []
        for title, icon_name in KPI_CONFIG:
            card = KpiCard(title, symbol=icon_name)
            self._kpi_cards.append(card)
            kpi_row.addWidget(card, stretch=1)
        root.addLayout(kpi_row)

        self._splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter = self._splitter
        splitter.setChildrenCollapsible(False)
        splitter.setHandleWidth(10)

        left_host = QWidget()
        fill_studio_canvas(left_host)
        left = QVBoxLayout(left_host)
        left.setContentsMargins(0, 0, 0, 0)
        left.setSpacing(PAGE_GAP)
        self._weekly = WeeklyUsageCard()
        self._weekly.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._daily_channels = DailyChannelQuotaCard()
        self._daily_channels.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        left.addWidget(self._weekly, 1)
        left.addWidget(self._daily_channels, 0)
        splitter.addWidget(left_host)

        self._remaining = RemainingMonthCard()
        self._remaining.setMinimumWidth(320)
        self._remaining.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        splitter.addWidget(self._remaining)
        splitter.setStretchFactor(0, 59)
        splitter.setStretchFactor(1, 41)
        root.addWidget(splitter, 1)

        self._activity = RecentActivityCard()
        root.addWidget(self._activity)

        self.setWidget(container)
        self._splitter_sized = False
        self._enter_loading_state()

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        if self._splitter_sized:
            return
        width = max(self.viewport().width() - (PAGE_GAP * 2), 400)
        self._splitter.setSizes([int(width * 0.59), int(width * 0.41)])
        self._splitter_sized = True

    def activate_page(self) -> None:
        self.refresh_data()

    def refresh_data(self, *, force: bool = False) -> None:
        if self._worker is not None and self._worker.isRunning():
            return
        if not force and self._cache is not None and self._cache.is_dashboard_fresh():
            cached = self._cache.snapshot_dashboard()
            if cached is not None:
                self._apply_overview(cached)
                return
        if self._last_overview is None:
            cached = self._cache.snapshot_dashboard() if self._cache is not None else None
            if cached is not None:
                self._apply_overview(cached)
            else:
                self._enter_loading_state()
        worker = DashboardOverviewWorker(self._api, self, cache=self._cache)
        worker.succeeded.connect(self._on_loaded)
        worker.failed.connect(self._on_failed)
        worker.finished.connect(self._on_worker_finished)
        self._worker = worker
        self._set_refreshing(True)
        worker.start()

    def _on_refresh(self) -> None:
        if self._worker is not None and self._worker.isRunning():
            return
        self.refresh_data(force=True)

    def _on_range_changed(self, *_args) -> None:
        self._range_dirty = True
        if self._last_overview is not None:
            self._bind_filtered(self._last_overview)

    def _enter_loading_state(self) -> None:
        self._loading = True
        self._error_banner.hide()
        for card in self._kpi_cards:
            card.set_value("--")
            card.set_delta("—", tone="flat")
        self._activity.show_loading()

    def _on_failed(self, _message: str) -> None:
        self._loading = False
        if self._last_overview is not None:
            return
        self._error_banner.show()
        for card in self._kpi_cards:
            card.set_value("--")
            card.set_delta("—", tone="flat")
        self._activity.show_empty()

    def _on_loaded(self, payload: object) -> None:
        if not isinstance(payload, DashboardOverview):
            return
        self._loading = False
        self._error_banner.hide()
        self._apply_overview(payload)

    def _on_worker_finished(self) -> None:
        self._worker = None
        self._set_refreshing(False)

    def _set_refreshing(self, busy: bool) -> None:
        self._refresh_btn.setEnabled(not busy)
        self._refresh_btn.setText("Refreshing…" if busy else "Refresh")

    def _selected_range(self) -> tuple[date, date]:
        start = _from_qdate(self._from_date.date())
        end = _from_qdate(self._to_date.date())
        if start > end:
            start, end = end, start
        return start, end

    def _apply_overview(self, data: DashboardOverview) -> None:
        self._loading = False
        self._last_overview = data
        if self._cache is not None:
            self._cache.apply_dashboard(data)
        self._bind_filtered(data)

    def _bind_filtered(self, data: DashboardOverview) -> None:
        stats = data.stats
        start, end = self._selected_range()
        days = _filter_days(stats.usage_by_day, start, end)
        activities = _filter_activities(stats.recent_activity, start, end)

        values, deltas = _kpi_payload(
            stats,
            days,
            previous=_previous_window(stats.usage_by_day, start, end),
            window_days=max((end - start).days, 0) + 1,
        )
        for card, value, (delta_text, tone) in zip(self._kpi_cards, values, deltas, strict=True):
            card.set_value(value)
            card.set_delta(delta_text, tone=tone)

        plan = _plan_label(data)
        if data.license and data.license.expiration_date is not None:
            expiry = f"Expires {format_short_date(data.license.expiration_date)}"
        else:
            expiry = "Expiration not provided"
        self._weekly.set_plan(plan, expiry)
        self._weekly.set_usage(days)

        self._remaining.apply_overview(data)
        self._daily_channels.apply_overview(data)
        self._activity.set_header_plan(plan, f"Expires: {expiry.replace('Expires ', '')}")
        self._activity.set_activities(activities)


def _plan_label(data: DashboardOverview) -> str:
    raw = ""
    if data.license and data.license.plan_type:
        raw = str(data.license.plan_type)
    elif data.me.plan_name:
        raw = str(data.me.plan_name)
    if not raw or raw.strip().lower() in {"no plan", "none", "free"}:
        return "No plan"
    return format_plan_display_name(raw)


def _from_qdate(value: QDate) -> date:
    return date(value.year(), value.month(), value.day())


def _usage_date(value: str) -> date | None:
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None


def _activity_date(activity: RecentActivity) -> date | None:
    stamp = activity.timestamp
    if isinstance(stamp, datetime):
        return stamp.date()
    return None


def _filter_days(entries: list[DailyUsage], start: date, end: date) -> list[DailyUsage]:
    matched: list[DailyUsage] = []
    for entry in entries:
        parsed = _usage_date(entry.date)
        if parsed is None or start <= parsed <= end:
            matched.append(entry)
    return matched


def _filter_activities(entries: list[RecentActivity], start: date, end: date) -> list[RecentActivity]:
    matched: list[RecentActivity] = []
    for entry in entries:
        parsed = _activity_date(entry)
        if parsed is None or start <= parsed <= end:
            matched.append(entry)
    return matched


def _previous_window(entries: list[DailyUsage], start: date, end: date) -> list[DailyUsage]:
    span = max((end - start).days, 0) + 1
    prev_end = start - timedelta(days=1)
    prev_start = prev_end - timedelta(days=span - 1)
    return _filter_days(entries, prev_start, prev_end)


def _sum_days(entries: list[DailyUsage], attr: str) -> int:
    total = 0
    for entry in entries:
        if attr == "studio_exports":
            studio = entry.studio_exports if (entry.studio_exports or entry.manual_exports) else entry.videos
            total += int(studio or 0)
        else:
            total += int(getattr(entry, attr, 0) or 0)
    return total


def _delta_vs_previous(current: int, previous: int, *, window_days: int) -> tuple[str, str]:
    if previous <= 0:
        return "—", "flat"
    change = round(((current - previous) / previous) * 100)
    label = f"vs prev {window_days} days"
    if change > 0:
        return f"+{change}% {label}", "up"
    if change < 0:
        return f"{change}% {label}", "down"
    return f"0% {label}", "flat"


def _kpi_payload(
    stats: DashboardStatsResponse,
    days: list[DailyUsage],
    *,
    previous: list[DailyUsage],
    window_days: int,
) -> tuple[list[str], list[tuple[str, str]]]:
    credit_total = stats.credits_total or (stats.credits_spent + stats.credits_remaining)
    credit_spent = stats.credits_spent
    credits_value = (
        f"{format_compact_number(credit_spent)} / {format_compact_number(credit_total)}"
        if credit_total
        else format_compact_number(credit_spent)
    )
    credits_pct = percent_of(int(credit_spent), int(credit_total)) if credit_total else 0
    credits_delta = (f"{credits_pct}% this period", "flat") if credit_total else ("—", "flat")

    songs_n = _sum_days(days, "songs")
    images_n = _sum_days(days, "images")
    studio_n = _sum_days(days, "studio_exports")
    manual_n = _sum_days(days, "manual_exports")
    youtube_n = _sum_days(days, "youtube_uploads")

    values = [
        credits_value,
        format_compact_number(songs_n),
        format_compact_number(images_n),
        format_compact_number(studio_n),
        format_compact_number(manual_n),
        format_compact_number(youtube_n),
    ]
    deltas = [
        credits_delta,
        _delta_vs_previous(songs_n, _sum_days(previous, "songs"), window_days=window_days),
        _delta_vs_previous(images_n, _sum_days(previous, "images"), window_days=window_days),
        _delta_vs_previous(studio_n, _sum_days(previous, "studio_exports"), window_days=window_days),
        _delta_vs_previous(manual_n, _sum_days(previous, "manual_exports"), window_days=window_days),
        _delta_vs_previous(youtube_n, _sum_days(previous, "youtube_uploads"), window_days=window_days),
    ]
    return values, deltas
