"""Desktop Google sign-in: loopback listener and the auth worker."""

from __future__ import annotations

import httpx
import pytest
from PySide6.QtWidgets import QApplication

from shared.services.google_desktop_oauth import (
    CALLBACK_PATH,
    DEFAULT_LOOPBACK_PORT,
    GoogleLoopbackServer,
    GoogleSignInError,
    desktop_port_from_state,
    loopback_port_from_env,
)
from shared.services.platform_api import PlatformApi
from shared.services.secure_storage import SecureStorage
from shared.services.session_service import (
    BootstrapDestination,
    BootstrapResult,
    SessionService,
)
from shared.workers.bootstrap_worker import GoogleAuthWorker


@pytest.fixture
def qapp() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_loopback_server_captures_code_and_state() -> None:
    server = GoogleLoopbackServer(port=0)
    try:
        redirect_uri = server.start()
        assert redirect_uri.endswith(CALLBACK_PATH)
        assert redirect_uri.startswith("http://127.0.0.1:")

        response = httpx.get(f"{redirect_uri}?code=abc123&state=state-xyz", timeout=5.0)

        assert response.status_code == 200
        assert "signed in" in response.text.lower()
        result = server.wait(timeout=5.0)
        assert result.code == "abc123"
        assert result.state == "state-xyz"
    finally:
        server.close()


def test_loopback_server_reports_cancelled_consent() -> None:
    server = GoogleLoopbackServer(port=0)
    try:
        redirect_uri = server.start()
        httpx.get(f"{redirect_uri}?error=access_denied", timeout=5.0)

        with pytest.raises(GoogleSignInError, match="cancelled"):
            server.wait(timeout=5.0)
    finally:
        server.close()


def test_loopback_server_ignores_other_paths() -> None:
    server = GoogleLoopbackServer(port=0)
    try:
        redirect_uri = server.start()
        base = redirect_uri.rsplit(CALLBACK_PATH, 1)[0]
        response = httpx.get(f"{base}/favicon.ico", timeout=5.0)

        assert response.status_code == 404
        with pytest.raises(GoogleSignInError, match="timed out"):
            server.wait(timeout=0.2)
    finally:
        server.close()


def test_loopback_server_times_out() -> None:
    server = GoogleLoopbackServer(port=0)
    try:
        server.start()

        with pytest.raises(GoogleSignInError, match="timed out"):
            server.wait(timeout=0.1)
    finally:
        server.close()


def test_loopback_server_reports_busy_port() -> None:
    first = GoogleLoopbackServer(port=0)
    second = GoogleLoopbackServer(port=0)
    try:
        redirect_uri = first.start()
        second._port = int(redirect_uri.rsplit(":", 1)[1].split("/", 1)[0])

        with pytest.raises(GoogleSignInError, match="busy"):
            second.start()
    finally:
        second.close()
        first.close()


def test_loopback_port_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CAMXORA_OAUTH_LOOPBACK_PORT", "45999")
    assert loopback_port_from_env() == 45999

    monkeypatch.setenv("CAMXORA_OAUTH_LOOPBACK_PORT", "not-a-port")
    assert loopback_port_from_env() == DEFAULT_LOOPBACK_PORT

    monkeypatch.delenv("CAMXORA_OAUTH_LOOPBACK_PORT", raising=False)
    assert loopback_port_from_env() == DEFAULT_LOOPBACK_PORT


class _FakeSession:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.desktop_port = 0
        self.completed: tuple[str, str] | None = None

    def google_authorization_url(self, *, desktop_port: int) -> str:
        if self.fail:
            raise RuntimeError("Google sign-in is unavailable right now.")
        self.desktop_port = desktop_port
        # The API keeps the registered https redirect; the port only travels in
        # the signed state.
        return "https://accounts.google.com/o/oauth2/v2/auth?client_id=fake"

    def complete_google_login(self, code: str, state: str) -> BootstrapResult:
        self.completed = (code, state)
        return BootstrapResult(BootstrapDestination.APP_HOME)


def test_google_auth_worker_completes_signin(qapp: QApplication) -> None:
    session = _FakeSession()
    captured: dict[str, object] = {}

    def open_browser(url: str) -> bool:
        # Simulate the browser finishing consent while the worker waits: the
        # website's /auth/callback forwards the browser to the loopback listener.
        assert url.startswith("https://accounts.google.com/")
        redirect_uri = f"http://127.0.0.1:{session.desktop_port}{CALLBACK_PATH}"
        httpx.get(f"{redirect_uri}?code=desktop-code&state=desktop-state", timeout=5.0)
        return True

    worker = GoogleAuthWorker(session, port=0, timeout=10.0, browser_open=open_browser)
    worker.succeeded.connect(lambda result: captured.setdefault("result", result))
    worker.failed.connect(lambda message: captured.setdefault("error", message))

    worker.run()

    assert "error" not in captured
    assert isinstance(captured["result"], BootstrapResult)
    assert captured["result"].destination is BootstrapDestination.APP_HOME
    assert session.completed == ("desktop-code", "desktop-state")


def test_google_auth_worker_reports_missing_browser(qapp: QApplication) -> None:
    session = _FakeSession()
    captured: dict[str, object] = {}
    worker = GoogleAuthWorker(session, port=0, timeout=2.0, browser_open=lambda _url: False)
    worker.failed.connect(lambda message: captured.setdefault("error", message))

    worker.run()

    assert "browser" in str(captured.get("error", "")).lower()


def test_google_auth_worker_reports_api_failure(qapp: QApplication) -> None:
    session = _FakeSession(fail=True)
    captured: dict[str, object] = {}
    worker = GoogleAuthWorker(
        session,
        port=0,
        timeout=2.0,
        browser_open=lambda _url: True,
    )
    worker.failed.connect(lambda message: captured.setdefault("error", message))

    worker.run()

    assert "unavailable" in str(captured.get("error", "")).lower()


# ---------------------------------------------------------------------------
# Old-server guard: a platform_api that ignores `desktop_port` must fail fast
# instead of leaving the window waiting for a hand-off that never arrives.
# ---------------------------------------------------------------------------


def _state_with(desktop_port: int | None) -> str:
    import base64
    import json

    payload: dict[str, object] = {"type": "google_oauth_state"}
    if desktop_port is not None:
        payload["desktop_port"] = desktop_port
    body = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
    return f"header.{body}.signature"


def test_desktop_port_from_state() -> None:
    assert desktop_port_from_state(_state_with(41580)) == 41580
    assert desktop_port_from_state(_state_with(None)) is None
    assert desktop_port_from_state(_state_with(0)) is None
    assert desktop_port_from_state(_state_with(70000)) is None
    assert desktop_port_from_state("") is None
    assert desktop_port_from_state("garbage") is None
    assert desktop_port_from_state("a.%%%.c") is None


class _NoopClient:
    def set_session_handlers(self, **_kwargs) -> None:
        return


class _MemoryStorage(SecureStorage):
    def __init__(self) -> None:
        self._data: dict[str, str] = {}
        self._api_base_url = "https://api.camxora.com/api/v3"

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


class _StubApi(PlatformApi):
    def __init__(self, state: str) -> None:
        self._client = _NoopClient()
        self._state = state
        self.requested_port: int | None = None

    def google_auth_url(self, desktop_port: int) -> dict[str, object]:
        self.requested_port = desktop_port
        return {"url": "https://accounts.google.com/o/oauth2/v2/auth?x=1", "state": self._state}


def _service(state: str) -> tuple[SessionService, _StubApi]:
    api = _StubApi(state)
    return SessionService(storage=_MemoryStorage(), api=api), api


def test_google_authorization_url_accepts_matching_state() -> None:
    service, api = _service(_state_with(41580))

    url = service.google_authorization_url(desktop_port=41580)

    assert url.startswith("https://accounts.google.com/")
    assert api.requested_port == 41580


def test_google_authorization_url_rejects_old_server() -> None:
    service, _api = _service(_state_with(None))

    with pytest.raises(RuntimeError, match="newer CAMXORA server"):
        service.google_authorization_url(desktop_port=41580)
