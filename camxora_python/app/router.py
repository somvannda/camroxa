"""Application router — registers shell pages in a QStackedWidget."""

from __future__ import annotations

from PySide6.QtWidgets import QStackedWidget, QWidget

from features.dashboard.views.dashboard_view import DashboardView
from features.profile.views.profile_view import ProfileView
from features.progress.views.progress_view import ProgressView
from features.workflow.views.workflow_view import WorkflowView
from shared.constants.navigation import SHELL_ROUTES, ShellRouteKey, ShellRouteMeta
from shared.services.platform_api import PlatformApi
from shared.services.session_service import SessionService
from shared.services.workspace_cache import WorkspaceCache
from shared.widgets.placeholder_page import PlaceholderPage

# Built on first navigation — keeps app shell startup light.
_LAZY_ROUTE_KEYS: frozenset[ShellRouteKey] = frozenset(
    {
        "profile",
        "workflow",
        "progress",
        "music",
        "image",
        "video",
        "studio",
        "marketplace",
        "settings",
        "log",
    }
)


class _LazyPageStub(QWidget):
    """Placeholder index holder until a heavy page is opened for the first time."""


class AppRouter:
    """Maps shell route keys to stacked widget indices."""

    def __init__(
        self,
        stack: QStackedWidget,
        api: PlatformApi | None = None,
        *,
        cache: WorkspaceCache | None = None,
        session: SessionService | None = None,
    ) -> None:
        self._stack = stack
        self._api = api or PlatformApi()
        self._cache = cache or WorkspaceCache()
        self._session = session
        self._index_by_key: dict[ShellRouteKey, int] = {}
        self._route_by_key: dict[ShellRouteKey, ShellRouteMeta] = {}
        self._page_by_key: dict[ShellRouteKey, QWidget | None] = {}
        self._register_pages()

    def _register_pages(self) -> None:
        for route in SHELL_ROUTES:
            if route.key in _LAZY_ROUTE_KEYS:
                page: QWidget | None = _LazyPageStub()
            elif route.is_placeholder:
                page = PlaceholderPage(route)
            elif route.key == "home":
                page = self._mark_shell_page(DashboardView(self._api, cache=self._cache))
            else:
                page = PlaceholderPage(route)
            index = self._stack.addWidget(page)
            self._index_by_key[route.key] = index
            self._route_by_key[route.key] = route
            self._page_by_key[route.key] = None if route.key in _LAZY_ROUTE_KEYS else page

    def _ensure_page(self, key: ShellRouteKey) -> QWidget:
        existing = self._page_by_key.get(key)
        if existing is not None:
            return existing

        route = self._route_by_key[key]
        page = self._create_page(route)
        index = self._index_by_key[key]
        old_widget = self._stack.widget(index)
        self._stack.removeWidget(old_widget)
        old_widget.deleteLater()
        self._stack.insertWidget(index, page)
        self._page_by_key[key] = page
        return page

    def prewarm_page(self, key: ShellRouteKey) -> bool:
        """Build a lazy page ahead of navigation so first visit is instant."""
        if key not in _LAZY_ROUTE_KEYS or self._page_by_key.get(key) is not None:
            return False
        page = self._ensure_page(key)
        prewarm = getattr(page, "prewarm_from_cache", None)
        if callable(prewarm):
            prewarm()
        return True

    @staticmethod
    def _mark_shell_page(page: QWidget) -> QWidget:
        page.setProperty("shellPage", True)
        return page

    def _create_page(self, route: ShellRouteMeta) -> QWidget:
        if route.key == "home":
            return self._mark_shell_page(DashboardView(self._api, cache=self._cache))
        if route.key == "profile":
            return self._mark_shell_page(ProfileView(self._api, cache=self._cache))
        if route.key == "progress":
            return self._mark_shell_page(ProgressView(self._api, cache=self._cache))
        if route.key == "workflow":
            return self._mark_shell_page(WorkflowView(self._api, cache=self._cache))
        if route.key == "music":
            from features.music.views.music_view import MusicView

            return self._mark_shell_page(MusicView(self._api, cache=self._cache))
        if route.key == "image":
            from features.image.views.image_view import ImageView

            return self._mark_shell_page(ImageView(self._api, cache=self._cache))
        if route.key == "video":
            from features.video.views.video_view import VideoView

            return self._mark_shell_page(VideoView(self._api, cache=self._cache))
        if route.key == "studio":
            from features.studio.views.studio_view import StudioView

            return self._mark_shell_page(StudioView(self._api, cache=self._cache))
        if route.key == "marketplace":
            from features.marketplace.views.marketplace_view import MarketplaceView
            from features.marketplace.views.marketplace_page_controller import MarketplacePageController
            from features.marketplace.coordinator import MarketplaceCoordinator
            from features.video.services.video_local_store import VideoLocalStore

            # Reuse shared PlatformClient so catalog/download get live auth + refresh.
            platform_client = self._api.client
            base = platform_client.base_url()

            view = MarketplaceView(api_base_url=base)

            user_id = ""
            if self._session and self._session.current_user:
                user_id = str(self._session.current_user.id)

            def _on_marketplace_error(msg: str) -> None:
                # UI shows InstallResult.error on the main thread; log here only.
                try:
                    from shared.services.app_logger import log_error

                    log_error(msg, category="marketplace")
                except Exception:
                    pass

            def _on_marketplace_templates_changed() -> None:
                # Invalidate stale Video cache; refresh dropdown without remounting
                # an in-edit draft (runs on the UI thread after install success).
                self._cache.invalidate_video_workspace()
                video_page = self._page_by_key.get("video")
                if video_page is not None:
                    refresh = getattr(video_page, "refresh_templates_from_store", None)
                    if callable(refresh):
                        refresh()
                    else:
                        fallback = getattr(video_page, "refresh_data", None)
                        if callable(fallback):
                            fallback(force=True)
                settings_page = self._page_by_key.get("settings")
                if settings_page is not None:
                    refresh_settings = getattr(settings_page, "refresh_profile_template_options", None)
                    if callable(refresh_settings):
                        refresh_settings()
                try:
                    from shared.services.video_template_catalog import emit_video_template_catalog_changed

                    emit_video_template_catalog_changed()
                except Exception:
                    pass

            coordinator = MarketplaceCoordinator(
                platform_client=platform_client,
                template_store=VideoLocalStore(),
                user_id=user_id,
                on_install_complete=lambda _uid: None,
                on_error=_on_marketplace_error,
            )

            _controller = MarketplacePageController(
                view=view,
                coordinator=coordinator,
                on_templates_changed=_on_marketplace_templates_changed,
            )
            view._controller = _controller  # type: ignore[attr-defined]
            return self._mark_shell_page(view)
        if route.key == "settings":
            from features.settings.views.settings_view import SettingsView

            return self._mark_shell_page(SettingsView(self._api, cache=self._cache, session=self._session))
        if route.key == "log":
            from features.logs.views.log_view import LogView

            return self._mark_shell_page(LogView(self._api))
        return PlaceholderPage(route)

    def navigate(self, key: ShellRouteKey) -> ShellRouteMeta:
        previous = self._stack.currentWidget()
        if key in _LAZY_ROUTE_KEYS:
            self._ensure_page(key)
        index = self._index_by_key.get(key)
        if index is not None:
            self._stack.setCurrentIndex(index)
        current = self._stack.currentWidget()
        self._handle_page_lifecycle(previous, current)
        return self._route_by_key.get(key, SHELL_ROUTES[0])

    def _handle_page_lifecycle(self, previous: QWidget | None, current: QWidget | None) -> None:
        if previous is not current and previous is not None and not isinstance(previous, _LazyPageStub):
            deactivate = getattr(previous, "deactivate_page", None)
            if callable(deactivate):
                deactivate()
        if current is not None and not isinstance(current, _LazyPageStub):
            activate = getattr(current, "activate_page", None)
            if callable(activate):
                activate()

    def current_route(self) -> ShellRouteMeta:
        widget = self._stack.currentWidget()
        if isinstance(widget, PlaceholderPage):
            return widget.route
        index = self._stack.currentIndex()
        for key, idx in self._index_by_key.items():
            if idx == index:
                return self._route_by_key[key]
        return SHELL_ROUTES[0]
