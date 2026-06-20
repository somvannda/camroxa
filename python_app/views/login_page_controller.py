"""Login Page Controller — orchestrates login/registration logic.

Connects LoginView signals to AuthClient operations, running auth calls on
worker threads to keep the UI responsive.  Uses a Qt signal to safely marshal
results back onto the main thread for UI updates.

Dependencies (constructor-injected):
    auth_client: AuthClientPort
    token_store: TokenStorePort
    license_gate: LicenseGatePort
    on_authenticated: Callable[[], None]  — navigate to main window
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from typing import TYPE_CHECKING

from PyQt6.QtCore import QObject, pyqtSignal

from python_app.services.api_errors import (
    AccountLockedError,
    AuthenticationError,
    DuplicateEmailError,
    NetworkError,
    TokenExpiredError,
    ValidationError,
)

if TYPE_CHECKING:
    from python_app.services.auth_client import AuthClientPort
    from python_app.services.license_gate import LicenseGate, LicenseStatus
    from python_app.services.token_store import TokenStorePort
    from python_app.views.login_view import LoginView

logger = logging.getLogger(__name__)


class _UiInvoker(QObject):
    """Helper QObject that emits a signal to invoke a callable on the UI thread."""

    invoke = pyqtSignal(object)


class _BusAdapter:
    """Adapts _UiInvoker to match the bus.ui_invoke.emit() interface."""

    def __init__(self, invoker: _UiInvoker):
        self.ui_invoke = invoker.invoke


class LoginPageController:
    """Orchestrates login/registration logic between view and auth client.

    All network operations run on daemon threads. UI updates are marshalled
    back to the main thread via a Qt signal to prevent cross-thread access.
    """

    def __init__(
        self,
        *,
        auth_client: "AuthClientPort",
        token_store: "TokenStorePort",
        license_gate: "LicenseGate",
        on_authenticated: Callable[[], None],
    ) -> None:
        self._auth_client = auth_client
        self._token_store = token_store
        self._license_gate = license_gate
        self._on_authenticated = on_authenticated
        self._view: LoginView | None = None
        self._login_email: str = ""

        # Signal-based UI invoker for thread-safe updates
        self._invoker = _UiInvoker()
        self._invoker.invoke.connect(self._execute_on_ui)

    # ------------------------------------------------------------------
    # View binding
    # ------------------------------------------------------------------

    def set_view(self, view: "LoginView") -> None:
        """Bind the controller to a LoginView and connect signals."""
        self._view = view
        view.login_requested.connect(self.handle_login)
        view.register_requested.connect(self.handle_register)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def handle_login(self, email: str, password: str) -> None:
        """Spawn worker thread: login → save tokens → license check → navigate.

        Called when the LoginView emits ``login_requested``.
        """
        logger.info("Login attempt for email: %s", email)
        self._set_loading(True)

        def work() -> None:
            try:
                logger.info("Connecting to auth server...")
                tokens = self._auth_client.login(email, password)
                logger.info("Auth successful, saving tokens...")
                self._token_store.save(tokens.access_token, tokens.refresh_token)

                # Check license (non-blocking for login success)
                try:
                    self._license_gate.validate(tokens.access_token)
                except Exception:
                    # License check failure shouldn't block login
                    logger.warning("License check failed during login", exc_info=True)

                # Check if user has completed onboarding (channel profiles)
                profiles = self._auth_client.check_profiles(tokens.access_token)
                has_profiles = profiles.get("has_profiles", False)

                if has_profiles:
                    self._ui_invoke(self._on_login_success)
                else:
                    # User hasn't completed onboarding — redirect there
                    self._login_email = email
                    self._ui_invoke(lambda: self._open_onboarding_with_token(email, tokens.access_token))

            except AuthenticationError:
                logger.warning("Login failed: invalid credentials")
                self._ui_invoke(
                    lambda: self._show_error("Invalid email or password")
                )
            except AccountLockedError:
                logger.warning("Login failed: account locked")
                self._ui_invoke(
                    lambda: self._show_error(
                        "Account temporarily locked. Please try again later."
                    )
                )
            except NetworkError as exc:
                logger.error("Login failed: network error: %s", exc)
                self._ui_invoke(
                    lambda: self._show_error(
                        "Connection failed. Please check your internet connection."
                    )
                )
            except Exception as exc:
                logger.error("Unexpected login error", exc_info=True)
                self._ui_invoke(
                    lambda: self._show_error(f"Login failed: {exc}")
                )
            finally:
                self._ui_invoke(lambda: self._set_loading(False))

        threading.Thread(target=work, daemon=True).start()

    def handle_register(self, email: str, password: str, display_name: str) -> None:
        """Spawn worker thread: register → show success → switch to login.

        Called when the LoginView emits ``register_requested``.
        """
        self._set_loading(True)

        def work() -> None:
            try:
                self._auth_client.register(email, password, display_name)
                self._ui_invoke(self._on_register_success)

            except DuplicateEmailError:
                # Email already registered AND confirmed. The user likely just
                # needs to log in (e.g. a confirmed account with no channel
                # profiles → onboarding). Try logging them in with the entered
                # credentials and route by profile status; if the password is
                # wrong, send them to the login tab.
                self._login_after_duplicate(email, password)
            except ValidationError as exc:
                field_errors = exc.field_errors
                self._ui_invoke(
                    lambda: self._show_field_errors(field_errors)
                )
            except NetworkError:
                self._ui_invoke(
                    lambda: self._show_error(
                        "Connection failed. Please check your internet connection."
                    )
                )
            except Exception as exc:
                logger.error("Unexpected registration error", exc_info=True)
                self._ui_invoke(
                    lambda: self._show_error(f"Registration failed: {exc}")
                )
            finally:
                self._ui_invoke(lambda: self._set_loading(False))

        threading.Thread(target=work, daemon=True).start()

    def attempt_auto_login(self) -> None:
        """Called at startup: validate stored tokens or refresh them.

        Flow:
            1. Check if token_store has tokens
            2. If yes: try auth_client.validate(access_token)
            3. If valid: check license → call on_authenticated()
            4. If 401: try auth_client.refresh(refresh_token)
               → save new tokens → check license → on_authenticated()
            5. If refresh fails: clear token_store, show login view
            6. If no tokens: do nothing (login view stays visible)
        """
        if not self._token_store.has_tokens():
            return

        def work() -> None:
            try:
                stored = self._token_store.load()
                if stored is None:
                    return

                access_token = stored.access_token
                refresh_token = stored.refresh_token

                # Step 2: validate access token
                is_valid = self._auth_client.validate(access_token)

                if is_valid:
                    # Step 3: token is valid — check license and profiles
                    try:
                        self._license_gate.validate(access_token)
                    except Exception:
                        logger.warning(
                            "License check failed during auto-login",
                            exc_info=True,
                        )
                    profiles = self._auth_client.check_profiles(access_token)
                    if profiles.get("has_profiles", False):
                        self._ui_invoke(self._on_login_success)
                    else:
                        self._ui_invoke(lambda: self._open_onboarding_with_token("", access_token))
                    return

                # Step 4: access token invalid — try refresh
                try:
                    new_tokens = self._auth_client.refresh(refresh_token)
                    self._token_store.save(
                        new_tokens.access_token, new_tokens.refresh_token
                    )

                    # Check license with new token
                    try:
                        self._license_gate.validate(new_tokens.access_token)
                    except Exception:
                        logger.warning(
                            "License check failed after token refresh",
                            exc_info=True,
                        )
                    profiles = self._auth_client.check_profiles(new_tokens.access_token)
                    if profiles.get("has_profiles", False):
                        self._ui_invoke(self._on_login_success)
                    else:
                        self._ui_invoke(lambda: self._open_onboarding_with_token("", new_tokens.access_token))

                except (TokenExpiredError, AuthenticationError):
                    # Step 5: refresh failed — clear and show login
                    self._token_store.clear()
                    logger.info("Auto-login failed: refresh token expired")

            except NetworkError:
                # Network error during auto-login: log and stay on login view
                logger.warning("Network error during auto-login", exc_info=True)

            except Exception:
                # Unexpected error: clear tokens and stay on login view
                logger.error("Unexpected error during auto-login", exc_info=True)
                self._token_store.clear()

        threading.Thread(target=work, daemon=True).start()

    # ------------------------------------------------------------------
    # Internal UI helpers (called on main thread)
    # ------------------------------------------------------------------

    def _ui_invoke(self, fn: Callable[[], None]) -> None:
        """Marshal a callable onto the UI thread via Qt signal."""
        self._invoker.invoke.emit(fn)

    @staticmethod
    def _execute_on_ui(fn: object) -> None:
        """Slot that executes the marshalled callable on the UI thread."""
        if callable(fn):
            fn()

    def _set_loading(self, is_loading: bool) -> None:
        """Set loading state on the view (must be called on UI thread)."""
        if self._view is not None:
            self._view.set_loading(is_loading)

    def _show_error(self, message: str) -> None:
        """Show an error message on the view (must be called on UI thread)."""
        if self._view is not None:
            self._view.show_error(message)

    def _show_field_errors(self, errors: dict[str, str]) -> None:
        """Show field-level errors on the view (must be called on UI thread)."""
        if self._view is not None:
            self._view.show_field_errors(errors)

    def _on_login_success(self) -> None:
        """Handle successful login: navigate to main window (UI thread)."""
        self._set_loading(False)
        self._on_authenticated()

    def _on_register_success(self) -> None:
        """Handle successful registration: start onboarding within login view."""
        self._open_onboarding()

    def _login_after_duplicate(self, email: str, password: str) -> None:
        """Register returned 409 (email already confirmed). Try to log the user
        in with the entered credentials and route by profile status. Runs on the
        register worker thread; marshals UI updates to the UI thread.
        """
        try:
            tokens = self._auth_client.login(email, password)
            self._token_store.save(tokens.access_token, tokens.refresh_token)
            try:
                self._license_gate.validate(tokens.access_token)
            except Exception:
                logger.warning("License check failed after register->login", exc_info=True)

            profiles = self._auth_client.check_profiles(tokens.access_token)
            if profiles.get("has_profiles", False):
                # Flow 2: confirmed + has profile → dashboard
                self._ui_invoke(self._on_login_success)
            else:
                # Flow 5: confirmed + no profile → onboarding
                self._login_email = email
                self._ui_invoke(lambda: self._open_onboarding_with_token(email, tokens.access_token))

        except (AuthenticationError, DuplicateEmailError):
            # Email exists but the entered password doesn't match — guide them
            # to the login tab instead of dead-ending on the register form.
            self._ui_invoke(lambda: self._prompt_login_existing_email(email))
        except NetworkError:
            self._ui_invoke(
                lambda: self._show_error(
                    "Connection failed. Please check your internet connection."
                )
            )
        except Exception:
            logger.error("Login after duplicate registration failed", exc_info=True)
            self._ui_invoke(
                lambda: self._show_error("This email is already registered. Please log in.")
            )

    def _prompt_login_existing_email(self, email: str) -> None:
        """Switch the view to the login tab, prefill the email, and explain why
        (the email is already registered). Must run on the UI thread.
        """
        self._set_loading(False)
        view = self._view
        if view is None:
            return
        try:
            if hasattr(view, "_on_login_tab_clicked"):
                view._on_login_tab_clicked()
            login_input = getattr(view, "login_email_input", None)
            if login_input is not None and email:
                login_input.setText(email)
        except Exception:
            logger.debug("Could not switch to login tab", exc_info=True)
        self._show_error("This email is already registered. Please log in.")

    def _open_onboarding(self) -> None:
        """Start onboarding inside the login view (no popup)."""
        from python_app.views.onboarding_controller import OnboardingController

        # Get the email from the register form
        email = ""
        if self._view is not None:
            register_email = getattr(self._view, '_register_email', None)
            if isinstance(register_email, dict):
                email_input = register_email.get("input")
                if email_input is not None:
                    email = email_input.text().strip()

        def on_onboarding_complete():
            self._on_authenticated()

        self._onboarding_controller = OnboardingController(
            login_view=self._view,
            token_store=self._token_store,
            on_complete=on_onboarding_complete,
            bus=_BusAdapter(self._invoker),
        )

        self._onboarding_controller.start(email, "")

    def _open_onboarding_with_token(self, email: str, access_token: str) -> None:
        """Start onboarding after login for users without channel profiles."""
        from python_app.views.onboarding_controller import OnboardingController

        def on_onboarding_complete():
            self._on_authenticated()

        self._onboarding_controller = OnboardingController(
            login_view=self._view,
            token_store=self._token_store,
            on_complete=on_onboarding_complete,
            bus=_BusAdapter(self._invoker),
        )

        self._onboarding_controller.start(email, access_token, skip_verification=True)
