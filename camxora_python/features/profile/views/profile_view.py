"""Profile page — mirrors ProfilePage.tsx."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QScrollArea, QVBoxLayout, QWidget

from features.profile.widgets.profile_cards import (
    AccountCard,
    ActivityCard,
    ChannelProfilesCard,
    MembershipCard,
)
from shared.models.platform import DashboardOverview
from shared.services.action_feedback import notify_action
from shared.services.platform_api import PlatformApi
from shared.services.workspace_cache import WorkspaceCache
from shared.workers.data_workers import DashboardOverviewWorker


class ProfileView(QScrollArea):
    """Account, membership, channel profiles, and activity summary."""

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
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)

        container = QWidget()
        root = QVBoxLayout(container)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(20)

        top = QHBoxLayout()
        top.setSpacing(20)
        top.setAlignment(Qt.AlignmentFlag.AlignTop)
        self._account = AccountCard()
        self._membership = MembershipCard()
        top.addWidget(self._account, stretch=12, alignment=Qt.AlignmentFlag.AlignTop)
        top.addWidget(self._membership, stretch=8, alignment=Qt.AlignmentFlag.AlignTop)
        root.addLayout(top)

        bottom = QHBoxLayout()
        bottom.setSpacing(20)
        self._profiles = ChannelProfilesCard()
        self._activity = ActivityCard()
        bottom.addWidget(self._profiles, stretch=155)
        bottom.addWidget(self._activity, stretch=75)
        root.addLayout(bottom)

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
        self._activity.show_loading()

    def _on_failed(self, message: str) -> None:
        if self._last_overview is not None:
            return
        detail = str(message or "").strip() or "Unable to load profile."
        notify_action(detail, tone="error")
        self._account.show_error()
        self._membership.show_loading()
        self._profiles.show_empty()
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
        self._activity.apply(data)
