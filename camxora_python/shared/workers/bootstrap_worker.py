"""Background workers."""

from __future__ import annotations

from PySide6.QtCore import QThread, Signal

from shared.services.platform_client import PlatformApiError
from shared.services.session_service import BootstrapProgress, BootstrapResult, SessionService


class ApiHealthWorker(QThread):
    """Checks platform_api /health off the UI thread."""

    finished_with_status = Signal(bool, str)

    def __init__(self, api_base_url: str, parent=None) -> None:
        super().__init__(parent)
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
                from shared.services.session_service import BootstrapDestination

                self.succeeded.emit(BootstrapResult(BootstrapDestination.ONBOARDING_WELCOME))
                return
            self.failed.emit("Unknown auth mode.")
        except PlatformApiError as exc:
            self.failed.emit(str(exc))
        except Exception as exc:
            self.failed.emit(str(exc) or "Request failed.")
