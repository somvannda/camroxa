"""Dashboard page — 100% parity with HomePage.tsx."""

from __future__ import annotations

from PySide6.QtWidgets import QFrame, QHBoxLayout, QScrollArea, QSizePolicy, QVBoxLayout, QWidget

from features.dashboard.widgets.daily_channel_quota_card import DailyChannelQuotaCard
from features.dashboard.widgets.error_banner import DashboardErrorBanner
from features.dashboard.widgets.kpi_card import KpiCard
from features.dashboard.widgets.recent_activity_card import RecentActivityCard
from features.dashboard.widgets.remaining_month_card import RemainingMonthCard
from features.dashboard.widgets.weekly_usage_card import WeeklyUsageCard
from shared.lib.formatting import format_compact_number, format_short_date
from shared.models.platform import DashboardOverview
from shared.services.platform_api import PlatformApi
from shared.services.workspace_cache import WorkspaceCache
from shared.workers.data_workers import DashboardOverviewWorker

from shared.icons.material_symbols import KPI_ICONS

KPI_CONFIG = (
    ("Credits Spent", "credits", lambda s: s.credits_spent),
    ("Songs Generated", "music", lambda s: s.songs_generated),
    ("Images Generated", "image", lambda s: s.images_generated),
    ("Videos Generated", "video", lambda s: s.videos_generated),
    ("YouTube Uploaded", "youtube", lambda s: s.videos_generated),
)


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
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self._api = api
        self._cache = cache
        self._worker: DashboardOverviewWorker | None = None
        self._loading = False
        self._last_overview: DashboardOverview | None = None

        container = QWidget()
        root = QVBoxLayout(container)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(24)

        self._error_banner = DashboardErrorBanner()
        self._error_banner.hide()
        root.addWidget(self._error_banner)

        kpi_row = QHBoxLayout()
        kpi_row.setSpacing(8)
        self._kpi_cards: list[KpiCard] = []
        for title, icon_key, _ in KPI_CONFIG:
            symbol, accent = KPI_ICONS[icon_key]
            card = KpiCard(title, symbol=symbol, accent=accent)
            self._kpi_cards.append(card)
            kpi_row.addWidget(card, stretch=1)
        root.addLayout(kpi_row)

        middle = QHBoxLayout()
        middle.setSpacing(24)
        self._weekly = WeeklyUsageCard()
        self._weekly.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._remaining = RemainingMonthCard()
        self._remaining.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        middle.addWidget(self._weekly, stretch=59)
        middle.addWidget(self._remaining, stretch=41)
        root.addLayout(middle)

        self._daily_channels = DailyChannelQuotaCard()
        root.addWidget(self._daily_channels)

        self._activity = RecentActivityCard()
        root.addWidget(self._activity)

        self.setWidget(container)
        self._enter_loading_state()

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
        worker.finished.connect(lambda: setattr(self, "_worker", None))
        self._worker = worker
        worker.start()

    def _enter_loading_state(self) -> None:
        self._loading = True
        self._error_banner.hide()
        for card in self._kpi_cards:
            card.set_value("--")
        self._activity.show_loading()

    def _on_failed(self, _message: str) -> None:
        self._loading = False
        if self._last_overview is not None:
            return
        self._error_banner.show()
        for card in self._kpi_cards:
            card.set_value("--")
        self._daily_channels.apply_quota(None)
        self._activity.show_empty()

    def _on_loaded(self, payload: object) -> None:
        if not isinstance(payload, DashboardOverview):
            return
        self._loading = False
        self._error_banner.hide()
        self._apply_overview(payload)

    def _apply_overview(self, data: DashboardOverview) -> None:
        self._loading = False
        self._last_overview = data
        if self._cache is not None:
            self._cache.apply_dashboard(data)
        stats = data.stats
        for card, (_, _, getter) in zip(self._kpi_cards, KPI_CONFIG, strict=True):
            card.set_value(format_compact_number(getter(stats)))

        plan = data.license.plan_type if data.license else data.me.plan_name or "No plan"
        if data.license and data.license.expiration_date is not None:
            expiry = f"Expires {format_short_date(data.license.expiration_date)}"
        else:
            expiry = "Expiration not provided"
        self._weekly.set_plan(plan, expiry)
        self._weekly.set_usage(stats.usage_by_day)

        self._remaining.apply_overview(data)
        self._daily_channels.apply_overview(data)
        self._activity.apply_overview(data)
