"""Profile page — account, membership, channel profiles, usage, and activity."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QScrollArea, QSizePolicy, QVBoxLayout, QWidget

from features.create.widgets.create_header import CreateHeader
from features.create.widgets.studio_panel import fill_studio_canvas, paint_studio_card
from features.profile.profile_constants import COLUMN_GAP, LEFT_STRETCH, RIGHT_STRETCH
from features.profile.profile_styles import build_profile_page_qss
from features.profile.widgets.account_card import AccountCard
from features.profile.widgets.channel_profiles import ChannelProfilesCard
from features.profile.widgets.membership_card import MembershipCard
from features.profile.widgets.recent_activity import RecentActivityCard
from features.profile.widgets.usage_overview import UsageOverview
from shared.lib.ui_font import ensure_inter_loaded, studio_font
from shared.models.platform import DashboardOverview
from shared.services.action_feedback import notify_action
from shared.services.platform_api import PlatformApi
from shared.services.workspace_cache import WorkspaceCache
from shared.workers.data_workers import DashboardOverviewWorker


class _FramedHeader(CreateHeader):
    """Create header with a painted card frame (QScrollArea QSS cannot reach it)."""

    def paintEvent(self, event) -> None:
        paint_studio_card(self)


class ProfileView(QScrollArea):
    """Signed-in account, plan, credits, allowance, and channel profiles."""

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
        self._last_overview: DashboardOverview | None = None
        self.setObjectName("profile_workspace")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        ensure_inter_loaded()
        self.setStyleSheet(build_profile_page_qss())
        self.setFont(studio_font(12))
        fill_studio_canvas(self.viewport())

        container = QWidget()
        container.setObjectName("profile_workspace")
        container.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        fill_studio_canvas(container)
        container.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        root = QVBoxLayout(container)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(COLUMN_GAP)

        header = _FramedHeader(
            title="Profile",
            subtitle="Signed-in account, plan, credits, allowance, and created channel profiles.",
            meta="",
            eyebrow="WORKSPACE",
        )
        header.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        root.addWidget(header)

        columns = QHBoxLayout()
        columns.setContentsMargins(0, 0, 0, 0)
        columns.setSpacing(COLUMN_GAP)
        columns.setAlignment(Qt.AlignmentFlag.AlignTop)

        left = QVBoxLayout()
        left.setContentsMargins(0, 0, 0, 0)
        left.setSpacing(COLUMN_GAP)
        self._account = AccountCard()
        self._profiles = ChannelProfilesCard(api=api)
        left.addWidget(self._account, 0)
        left.addWidget(self._profiles, 1)
        left_host = QWidget()
        fill_studio_canvas(left_host)
        left_host.setLayout(left)
        left_host.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        columns.addWidget(left_host, LEFT_STRETCH)

        right = QVBoxLayout()
        right.setContentsMargins(0, 0, 0, 0)
        right.setSpacing(COLUMN_GAP)
        self._membership = MembershipCard()
        self._usage = UsageOverview()
        self._activity = RecentActivityCard()
        right.addWidget(self._membership, 0)
        right.addWidget(self._usage, 0)
        right.addWidget(self._activity, 1)
        right_host = QWidget()
        fill_studio_canvas(right_host)
        right_host.setLayout(right)
        right_host.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        right_host.setMinimumWidth(260)
        columns.addWidget(right_host, RIGHT_STRETCH)
        root.addLayout(columns, 1)

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
        notify_action("Refreshing profile…", tone="neutral")
        worker = DashboardOverviewWorker(self._api, self, cache=self._cache)
        worker.succeeded.connect(self._on_loaded)
        worker.failed.connect(self._on_failed)
        worker.finished.connect(lambda: setattr(self, "_worker", None))
        self._worker = worker
        worker.start()

    def _enter_loading_state(self) -> None:
        self._account.show_loading()
        self._membership.show_loading()
        self._profiles.show_loading()
        self._usage.show_loading()
        self._activity.show_loading()

    def _on_failed(self, message: str) -> None:
        if self._last_overview is not None:
            return
        detail = str(message or "").strip() or "Unable to load profile."
        notify_action(detail, tone="error")
        self._account.show_error()
        self._membership.show_loading()
        self._profiles.show_empty()
        self._usage.show_loading()
        self._activity.show_loading()

    def _on_loaded(self, payload: object) -> None:
        if not isinstance(payload, DashboardOverview):
            return
        self._apply_overview(payload)
        notify_action("Profile updated.", tone="success")

    def _apply_overview(self, data: DashboardOverview) -> None:
        self._last_overview = data
        if self._cache is not None:
            self._cache.apply_dashboard(data)
        self._account.apply(data)
        self._membership.apply(data)
        self._profiles.apply(data)
        self._usage.apply(data)
        self._activity.apply(data)
