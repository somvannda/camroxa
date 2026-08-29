"""Smoke test for main window."""

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QHBoxLayout, QStackedWidget, QVBoxLayout, QWidget

from app.application import AppShellWidget
from app.root_window import RootWindow
from app.router import AppRouter
from shared.services.secure_storage import SecureStorage
from shared.widgets.window_title_bar import WindowTitleBar


class _MemoryStorage(SecureStorage):
    """In-memory storage for tests — avoids DPAPI from background threads."""

    def __init__(self) -> None:
        self._data: dict[str, str] = {}
        self._api_base_url = "http://localhost:8000/api/v3"

    def get(self, key: str) -> str | None:
        return self._data.get(key)

    def set(self, key: str, value: str) -> None:
        self._data[key] = value

    def remove(self, key: str) -> None:
        self._data.pop(key, None)

    def get_api_base_url(self) -> str:
        return self._api_base_url

    def set_api_base_url(self, url: str) -> None:
        self._api_base_url = url


@pytest.fixture(scope="session")
def qapp() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


@pytest.fixture
def memory_session():
    from shared.services.session_service import SessionService

    session = SessionService(storage=_MemoryStorage())
    session.hydrate()
    return session


def test_app_shell_creates(qapp: QApplication, memory_session) -> None:
    shell = AppShellWidget(session=memory_session)
    assert shell is not None


def test_footer_spans_full_shell_width(qapp: QApplication, memory_session) -> None:
    shell = AppShellWidget(session=memory_session)
    root = shell.layout()
    assert isinstance(root, QVBoxLayout)
    assert root.itemAt(root.count() - 1).widget() is shell._status_bar
    assert shell._status_bar.parentWidget() is shell

    body = shell.findChild(QWidget, "shell_body")
    assert body is not None
    body_layout = body.layout()
    assert isinstance(body_layout, QHBoxLayout)
    assert body_layout.contentsMargins().left() == 10
    assert body_layout.spacing() == 10
    assert shell._sidebar.parentWidget() is body


def test_profile_hides_generic_shell_page_header(qapp: QApplication, memory_session) -> None:
    shell = AppShellWidget(session=memory_session)
    shell._navigate("music")
    assert shell._page_header.isHidden()
    shell._navigate("profile")
    assert shell._page_header.isHidden()
    shell._navigate("create")
    assert shell._page_header.isHidden()
    shell._navigate("home")
    assert shell._page_header.isHidden()
    shell._navigate("workflow")
    assert shell._page_header.isHidden()
    shell._navigate("progress")
    assert shell._page_header.isHidden()
    shell._navigate("image")
    assert shell._page_header.isHidden()
    shell._navigate("marketplace")
    assert shell._page_header.isHidden()
    shell._navigate("settings")
    assert not shell._page_header.isHidden()


def test_router_navigates_all_routes(qapp: QApplication, memory_session) -> None:
    stack = QStackedWidget()
    router = AppRouter(stack, memory_session.api)
    for route in router._route_by_key.values():
        meta = router.navigate(route.key)
        assert meta.key == route.key


def test_router_prewarm_builds_video_page_once(qapp: QApplication, memory_session) -> None:
    stack = QStackedWidget()
    router = AppRouter(stack, memory_session.api)
    assert router._page_by_key["video"] is None
    assert router.prewarm_page("video") is True
    page = router._page_by_key["video"]
    assert page is not None
    # Already built — second prewarm and navigation reuse the same instance.
    assert router.prewarm_page("video") is False
    router.navigate("video")
    assert router._page_by_key["video"] is page


def test_shell_prewarms_all_heavy_pages_before_show(qapp: QApplication, memory_session) -> None:
    shell = AppShellWidget(session=memory_session)
    # Root window drains this during the startup screen, one page per call.
    built: list[str] = []
    while True:
        key = shell.prewarm_pending_page()
        if key is None:
            break
        built.append(key)
    assert built == list(AppShellWidget._PREWARM_ROUTE_KEYS)
    for key in AppShellWidget._PREWARM_ROUTE_KEYS:
        assert shell._router._page_by_key[key] is not None
    assert shell.prewarm_pending_page() is None


def test_root_window_uses_custom_title_bar(
    qapp: QApplication,
    memory_session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(RootWindow, "_start_bootstrap", lambda self: None)
    window = RootWindow(session=memory_session)

    title_bar = window.centralWidget().findChild(WindowTitleBar)
    assert title_bar is not None
    assert window.windowFlags() & Qt.WindowType.FramelessWindowHint
