"""Background workers."""

from __future__ import annotations

from PySide6.QtCore import QThread, Signal

from shared.services.platform_client import PlatformApiError
from shared.services.session_service import (
    BootstrapDestination,
    BootstrapProgress,
    BootstrapResult,
    SessionService,
)


def _paid_plan_result(exc: PlatformApiError) -> BootstrapResult | None:
    """Map the backend's desktop-plan gate to a "stay on login" result."""
    from shared.lib.desktop_entitlement import (
        DESKTOP_REQUIRES_PAID_PLAN_MESSAGE,
        is_desktop_plan_required_error,
    )

    if not is_desktop_plan_required_error(exc):
        return None
    return BootstrapResult(
        BootstrapDestination.LOGIN,
        DESKTOP_REQUIRES_PAID_PLAN_MESSAGE,
    )


class ApiHealthWorker(QThread):
    """Checks platform_api /health off the UI thread."""

    finished_with_status = Signal(bool, str)

    def __init__(self, api_base_url: str, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("ApiHealthWorker")
        self._api_base_url = api_base_url

    def run(self) -> None:
        from shared.services.api_health import check_api_reachable

        ok, message = check_api_reachable(self._api_base_url)
        self.finished_with_status.emit(ok, message)


class BootstrapWorker(QThread):
    """Runs session bootstrap off the UI thread."""

    progress = Signal(str, str, int)
    finished_with_result = Signal(object)

    def __init__(self, session: SessionService, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("BootstrapWorker")
        self._session = session

    def run(self) -> None:
        def report(payload: BootstrapProgress) -> None:
            self.progress.emit(payload.label, payload.detail, payload.progress)

        result = self._session.run_bootstrap(report=report)
        self.finished_with_result.emit(result)


class AuthWorker(QThread):
    """Runs login/register API calls off the UI thread."""

    progress = Signal(str, str, int)
    succeeded = Signal(object)
    failed = Signal(str)

    def __init__(
        self,
        session: SessionService,
        *,
        mode: str,
        email: str,
        password: str,
        display_name: str = "",
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("AuthWorker")
        self._session = session
        self._mode = mode
        self._email = email
        self._password = password
        self._display_name = display_name

    def run(self) -> None:
        try:
            if self._mode == "login":
                self.progress.emit("Signing in", "Checking your credentials.", 30)
                tokens = self._session.api.login(self._email, self._password)
                from shared.models.auth import AuthTokens

                self._session.set_tokens(AuthTokens.from_token_response(tokens))

                def report(payload: BootstrapProgress) -> None:
                    self.progress.emit(payload.label, payload.detail, payload.progress)

                result = self._session.run_bootstrap(report=report)
                self.succeeded.emit(result)
                return
            if self._mode == "register":
                self._session.register(self._email, self._password, self._display_name)
                self.succeeded.emit(BootstrapResult(BootstrapDestination.ONBOARDING_WELCOME))
                return
            self.failed.emit("Unknown auth mode.")
        except PlatformApiError as exc:
            from shared.lib.desktop_entitlement import DESKTOP_REQUIRES_PAID_PLAN_MESSAGE

            if self._mode == "register":
                self.failed.emit(str(exc))
                return
            plan_result = _paid_plan_result(exc)
            if plan_result is not None:
                # Login itself is rejected by v3 before tokens are issued.
                # Treat it as a successful "stay on login" so the plans popup opens.
                self.succeeded.emit(plan_result)
                return
            self.failed.emit(str(exc) or DESKTOP_REQUIRES_PAID_PLAN_MESSAGE)
        except Exception as exc:
            self.failed.emit(str(exc) or "Request failed.")


class GoogleAuthWorker(QThread):
    """Runs the browser + loopback Google sign-in off the UI thread."""

    progress = Signal(str, str, int)
    succeeded = Signal(object)
    failed = Signal(str)

    def __init__(
        self,
        session: SessionService,
        *,
        port: int | None = None,
        timeout: float | None = None,
        browser_open=None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("GoogleAuthWorker")
        self._session = session
        self._port = port
        self._timeout = timeout
        self._browser_open = browser_open

    def _open(self, url: str) -> bool:
        if self._browser_open is not None:
            return bool(self._browser_open(url))
        import webbrowser

        try:
            return bool(webbrowser.open(url))
        except Exception:
            return False

    def run(self) -> None:
        from shared.services.google_desktop_oauth import (
            DEFAULT_WAIT_TIMEOUT_SECONDS,
            GoogleLoopbackServer,
            GoogleSignInError,
        )

        server = GoogleLoopbackServer(self._port)
        try:
            server.start()
            self.progress.emit("Signing in with Google", "Opening your browser…", 20)
            url = self._session.google_authorization_url(desktop_port=server.port)
            if not self._open(url):
                raise GoogleSignInError("Could not open your browser for Google sign-in.")
            self.progress.emit(
                "Signing in with Google",
                "Finish the Google prompt, then return to CAMXORA.",
                35,
            )
            result = server.wait(
                timeout=self._timeout
                if self._timeout is not None
                else DEFAULT_WAIT_TIMEOUT_SECONDS
            )
            self.progress.emit("Signing in with Google", "Checking your Google account.", 55)

            def report(payload: BootstrapProgress) -> None:
                self.progress.emit(payload.label, payload.detail, payload.progress)

            bootstrap = self._session.complete_google_login(result.code, result.state)
            self.succeeded.emit(bootstrap)
        except PlatformApiError as exc:
            plan_result = _paid_plan_result(exc)
            if plan_result is not None:
                self.succeeded.emit(plan_result)
                return
            self.failed.emit(str(exc) or "Google sign-in failed.")
        except Exception as exc:
            self.failed.emit(str(exc) or "Google sign-in failed.")
        finally:
            server.close()

