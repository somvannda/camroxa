"""Main application shell — mirrors camxora AppShellLayout.tsx."""

from __future__ import annotations

from PySide6.QtCore import QTimer, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from app.router import AppRouter
from shared.constants.navigation import ShellRouteKey
from shared.services.build_config import footer_environment_badge, footer_version_badge
from shared.services.image_output_sync_coordinator import ImageOutputSyncCoordinator
from shared.services.progress_local_sync_coordinator import (
    ProgressLocalSyncCoordinator,
    bind_progress_local_sync_coordinator,
)
from shared.services.music_download_coordinator import MusicDownloadCoordinator
from shared.services.session_service import SessionService
from shared.services.setup_readiness_service import refresh_setup_readiness
from shared.services.shell_status import ShellStatusBus
from shared.services.video_pipeline_coordinator import VideoPipelineCoordinator, bind_video_pipeline_coordinator
from shared.widgets.flash_status_footer import FlashStatusFooter
from shared.widgets.shell_footer_bar import ShellFooterBar
from shared.widgets.page_header import PageHeader
from shared.widgets.sidebar_nav import SidebarNav


class AppShellWidget(QWidget):
    """Workspace shell with sidebar navigation and stacked pages."""

    logout_requested = Signal()

    # Heavy lazy pages built while the startup screen is still visible, so the
    # shell never stutters after it appears and every first visit is instant.
    _PREWARM_ROUTE_KEYS: tuple[ShellRouteKey, ...] = ("video", "music", "image", "settings", "profile")

    def __init__(self, session: SessionService | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._session = session or SessionService()
        self._session.hydrate()
        self._api = self._session.api
        self._prewarm_queue: list[ShellRouteKey] = list(self._PREWARM_ROUTE_KEYS)
        self._build_ui()
        self._connect_signals()

    def show_home(self) -> None:
        """Navigate to dashboard and load data — call when shell becomes visible."""
        self._navigate("home")

    def prewarm_pending_page(self) -> ShellRouteKey | None:
        """Build the next heavy page; returns its key, or None when done."""
        while self._prewarm_queue:
            key = self._prewarm_queue.pop(0)
            try:
                self._router.prewarm_page(key)
            except Exception:
                pass  # Page falls back to on-demand build during navigation.
            return key
        return None

    def _build_ui(self) -> None:
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self._sidebar = SidebarNav()
        root.addWidget(self._sidebar)

        content = QWidget()
        content.setObjectName("shell_content_host")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)

        content_inner = QWidget()
        content_inner.setObjectName("shell_content_inner")
        content_inner_layout = QVBoxLayout(content_inner)
        content_inner_layout.setContentsMargins(12, 12, 12, 12)
        content_inner_layout.setSpacing(8)

        self._page_header = PageHeader()
        content_inner_layout.addWidget(self._page_header)

        self._stack = QStackedWidget()
        self._stack.setObjectName("shell_page_stack")
        content_inner_layout.addWidget(self._stack, stretch=1)

        self._action_flash = FlashStatusFooter(content_inner)

        content_layout.addWidget(content_inner, stretch=1)

        self._status_bar = ShellFooterBar()
        self._route_ready_message = "Ready"
        self._status_bar.set_message(self._route_ready_message)
        env_label, env_tooltip = footer_environment_badge()
        self._status_bar.set_environment_badge(env_label, tooltip=env_tooltip)
        version_label, version_tooltip = footer_version_badge()
        self._status_bar.set_version_badge(version_label, tooltip=version_tooltip)
        content_layout.addWidget(self._status_bar)

        root.addWidget(content, stretch=1)
        self._router = AppRouter(self._stack, self._api, cache=self._session.workspace_cache, session=self._session)
        from shared.services.workspace_prefs_push import bind_session

        bind_session(self._session)
        self._music_downloads = MusicDownloadCoordinator(self._api, self)
        self._music_downloads.start()
        self._image_outputs = ImageOutputSyncCoordinator(self._api, self)
        self._image_outputs.start()
        self._progress_local_sync = ProgressLocalSyncCoordinator(self._api, self)
        bind_progress_local_sync_coordinator(self._progress_local_sync)
        self._progress_local_sync.start()
        self._video_pipeline = VideoPipelineCoordinator(self._api, self)
        bind_video_pipeline_coordinator(self._video_pipeline)
        self._video_pipeline.start()

        self._session_keepalive = QTimer(self)
        self._session_keepalive.setInterval(60_000)
        self._session_keepalive.timeout.connect(self._session.ensure_fresh_session)
        self._session_keepalive.start()

        bus = ShellStatusBus.instance()
        bus.show_message.connect(self._status_bar.set_message)
        bus.restore_default.connect(self._restore_status_message)
        bus.flash_action.connect(self._on_action_flash)

    def _on_action_flash(self, message: str, tone: str, duration_ms: int) -> None:
        self._action_flash.flash(message, tone=tone, duration_ms=duration_ms)

    def _connect_signals(self) -> None:
        self._sidebar.route_selected.connect(self._on_route_selected)
        self._sidebar.logout_clicked.connect(self.logout_requested.emit)

    def refresh_account_summary(self) -> None:
        user = self._session.current_user
        if user is None:
            try:
                user = self._session.fetch_current_user()
            except Exception:
                self._sidebar.set_account_summary("Guest User", None, "Credits: --")
                self._status_bar.set_summary(credits="Credits: --", allowance="Profiles: --")
                return

        display_name = user.display_name.strip() or user.email.strip() or "User"
        credits = f"{user.credit_balance:,} credits"
        self._sidebar.set_account_summary(display_name, user.plan_name, credits)
        profile_count = user.channel_profile_count
        allowance = (
            f"{profile_count} / {user.profile_allowance} profiles"
            if user.profile_allowance is not None
            else f"{profile_count} profiles"
        )
        self._status_bar.set_summary(credits=credits, allowance=allowance)

    def prepare_app_quit(self) -> None:
        """Cancel video exports and prevent batch chaining during window close."""
        page = None
        try:
            page = self._router._page_by_key.get("video")  # noqa: SLF001 — quit path only
        except Exception:
            page = None
        prepare = getattr(page, "prepare_app_quit", None)
        if callable(prepare):
            try:
                prepare()
            except Exception:
                pass

    def shutdown_background_workers(self) -> None:
        """Stop polling coordinators before the shell/window is destroyed."""
        try:
            self._session_keepalive.stop()
        except Exception:
            pass
        for attr in (
            "_music_downloads",
            "_image_outputs",
            "_progress_local_sync",
            "_video_pipeline",
        ):
            coordinator = getattr(self, attr, None)
            if coordinator is None:
                continue
            stop = getattr(coordinator, "stop", None)
            if callable(stop):
                try:
                    stop()
                except Exception:
                    pass

    def _restore_status_message(self) -> None:
        self._status_bar.set_message(self._route_ready_message)

    def _on_route_selected(self, key: str) -> None:
        self._navigate(key)  # type: ignore[arg-type]

    def _navigate(self, key: ShellRouteKey) -> None:
        route = self._router.navigate(key)
        self._sidebar.select_route(key)

        is_video = key == "video"
        self._page_header.setVisible(not is_video)
        if not is_video:
            self._page_header.set_route(route)

        self._route_ready_message = f"Ready: {route.label}"
        self._status_bar.set_message(self._route_ready_message)
        refresh_setup_readiness(
            api=self._api,
            cache=self._session.workspace_cache,
            parent=self,
            force_network=key == "settings",
        )


# Backward-compatible alias used in tests
CamxoraApplication = AppShellWidget
