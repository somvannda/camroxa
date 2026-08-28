"""Session management — mirrors sessionStore.ts + authRefresh.ts + bootstrap.ts."""

from __future__ import annotations

import json
import threading
import time
from dataclasses import dataclass
from enum import Enum
from typing import Callable

from pydantic import ValidationError

from shared.lib.desktop_entitlement import (
    DESKTOP_REQUIRES_PAID_PLAN_MESSAGE,
    is_desktop_plan_required_error,
    user_can_use_desktop_studio,
)
from shared.models.auth import AuthTokens, UserMeResponse
from shared.models.local_workspace import LocalWorkspaceContext
from shared.services.account_token_store import list_saved_accounts, load_saved_tokens, remember_account
from shared.services.local_user_scope import (
    activate_local_user_scope,
    deactivate_local_user_scope,
    get_active_workspace_context,
)
from shared.services.platform_api import PlatformApi
from shared.services.platform_client import PlatformApiError
from shared.services.secure_storage import TOKENS_STORAGE_KEY, SecureStorage
from shared.services.workspace_cache import WorkspaceCache
from shared.services.workspace_prefs_sync import pull_workspace_prefs_from_settings


class BootstrapDestination(str, Enum):
    LOGIN = "login"
    ONBOARDING_WELCOME = "onboarding_welcome"
    ONBOARDING_WIZARD = "onboarding_wizard"
    APP_HOME = "app_home"


@dataclass(frozen=True, slots=True)
class BootstrapResult:
    destination: BootstrapDestination
    message: str = ""


@dataclass(frozen=True, slots=True)
class BootstrapProgress:
    label: str
    detail: str
    progress: int


ReportFn = Callable[[BootstrapProgress], None]


class SessionService:
    """Manages auth tokens and session refresh."""

    def __init__(
        self,
        storage: SecureStorage | None = None,
        api: PlatformApi | None = None,
    ) -> None:
        self._storage = storage or SecureStorage()
        self._api = api or PlatformApi()
        self._tokens: AuthTokens | None = None
        self._hydrated = False
        self._current_user: UserMeResponse | None = None
        self.workspace_cache = WorkspaceCache()
        self._refresh_lock = threading.Lock()
        self._refresh_inflight: threading.Event | None = None

        self._api.client.set_session_handlers(
            get_tokens=self.get_tokens,
            refresh_session=self.ensure_fresh_session,
            clear_session=self.clear,
        )

    @property
    def api(self) -> PlatformApi:
        return self._api

    @property
    def current_user(self) -> UserMeResponse | None:
        return self._current_user

    @property
    def local_workspace(self) -> LocalWorkspaceContext | None:
        return get_active_workspace_context()

    def list_saved_accounts(self):
        return list_saved_accounts(self._storage)

    def switch_saved_account(self, user_id: str) -> BootstrapResult:
        tokens_raw = load_saved_tokens(self._storage, user_id)
        if not tokens_raw:
            return BootstrapResult(BootstrapDestination.LOGIN, message="Saved session not found for this account.")
        self.workspace_cache.clear()
        self._current_user = None
        try:
            tokens = AuthTokens.model_validate_json(tokens_raw)
        except ValueError:
            return BootstrapResult(BootstrapDestination.LOGIN, message="Saved session is invalid.")
        self.set_tokens(tokens)
        return self.run_bootstrap()

    def forget_local_workspace(self, user_id: str | None = None) -> None:
        from shared.services.local_user_scope import forget_local_user_data

        target = user_id or (str(self._current_user.id) if self._current_user is not None else None)
        if target:
            forget_local_user_data(target, self._storage)

    def _remember_session_account(self, me: UserMeResponse) -> None:
        tokens = self.get_tokens()
        if tokens is None:
            return
        remember_account(
            self._storage,
            user_id=str(me.id),
            email=me.email,
            display_name=me.display_name,
            tokens_json=tokens.model_dump_json(),
        )

    def _sync_workspace_prefs_from_settings(self, settings_raw: dict | None) -> None:
        if self._current_user is None:
            return
        pull_workspace_prefs_from_settings(str(self._current_user.id), settings_raw)

    def sync_workspace_prefs_from_settings(self, settings_raw: dict | None) -> None:
        """Apply remote settings to local workspace prefs (e.g. after push refresh)."""
        self._sync_workspace_prefs_from_settings(settings_raw)

    def push_workspace_prefs_to_server(self) -> None:
        if self._current_user is None:
            return
        from shared.services.workspace_prefs_sync import build_settings_patch_from_local

        patch = build_settings_patch_from_local(str(self._current_user.id))
        if not patch:
            return
        try:
            self._api.patch_settings(patch)
        except Exception:
            pass

    @property
    def storage(self) -> SecureStorage:
        return self._storage

    def hydrate(self) -> None:
        raw = self._storage.get(TOKENS_STORAGE_KEY)
        self._tokens = _parse_tokens(raw)
        self._hydrated = True

    def get_tokens(self) -> AuthTokens | None:
        if not self._hydrated:
            self.hydrate()
        return self._tokens

    def set_tokens(self, tokens: AuthTokens) -> None:
        self._tokens = tokens
        self._storage.set(TOKENS_STORAGE_KEY, tokens.model_dump_json())
        mark_fresh = getattr(self._api.client, "mark_tokens_fresh", None)
        if callable(mark_fresh):
            mark_fresh()

    def clear(self) -> None:
        self._storage.remove(TOKENS_STORAGE_KEY)
        self._tokens = None
        self._current_user = None
        self.workspace_cache.clear()
        deactivate_local_user_scope()

    def ensure_fresh_session(self, force: bool = False, *, failed_access_token: str = "") -> bool:
        with self._refresh_lock:
            if self._refresh_inflight is not None:
                self._refresh_inflight.wait(timeout=30)

            tokens = self.get_tokens()
            if tokens is None:
                return False

            now_ms = int(time.time() * 1000)
            needs_refresh = now_ms > tokens.expiresAt - 120_000
            failed = (failed_access_token or "").strip()
            if force and failed:
                # 401 on this exact access token: rotate even if expiresAt is still
                # far away (token_version revoke). Skip only if another thread
                # already issued a new access token.
                needs_refresh = tokens.accessToken == failed
            elif force:
                needs_refresh = needs_refresh or now_ms > tokens.expiresAt - 5_000
            if not needs_refresh:
                return True

            if self._refresh_inflight is not None:
                self._refresh_inflight.wait(timeout=30)
                return self.get_tokens() is not None

            event = threading.Event()
            self._refresh_inflight = event
            try:
                tokens = self.get_tokens()
                if tokens is None or not tokens.refreshToken:
                    return False
                refreshed = self._api.refresh(tokens.refreshToken)
                self.set_tokens(AuthTokens.from_token_response(refreshed))
                return True
            except Exception as exc:
                from shared.services.app_logger import log_error, log_warn
                from shared.services.platform_client import PlatformApiError

                if isinstance(exc, PlatformApiError) and exc.status == 401:
                    log_warn(
                        f"Session refresh rejected: {exc}. Sign in again.",
                        category="auth",
                    )
                    self.clear()
                else:
                    log_error("Session token refresh failed", category="auth", exc=exc)
                return False
            finally:
                event.set()
                self._refresh_inflight = None

    def run_bootstrap(self, report: ReportFn | None = None) -> BootstrapResult:
        def _report(label: str, detail: str, progress: int) -> None:
            if report is not None:
                report(BootstrapProgress(label=label, detail=detail, progress=progress))

        _report("Loading session", "Reading saved session tokens.", 15)
        self.hydrate()

        tokens = self.get_tokens()
        if tokens is None:
            self.clear()
            _report("Opening sign in", "No session found.", 100)
            # This is a normal "need to sign in" state for fresh installs / cleared sessions.
            # Keep the login UI clean (no error pill) by returning an empty message.
            return BootstrapResult(BootstrapDestination.LOGIN, message="")

        now_ms = int(time.time() * 1000)
        if now_ms > tokens.expiresAt - 30_000:
            _report("Refreshing session", "Renewing your login session.", 35)
            if not self.ensure_fresh_session(force=True):
                self.clear()
                _report("Opening sign in", "Session expired.", 100)
                return BootstrapResult(BootstrapDestination.LOGIN, message="Session expired. Please sign in again.")

        _report("Validating session", "Checking account session.", 55)
        try:
            me = self._api.get_me()
        except ValidationError:
            self.clear()
            _report("Opening sign in", "Session expired.", 100)
            return BootstrapResult(
                BootstrapDestination.LOGIN,
                message="Unable to read your account profile. Please sign in again.",
            )
        except PlatformApiError as exc:
            self.clear()
            _report("Opening sign in", "Paid plan required." if is_desktop_plan_required_error(exc) else "Session expired.", 100)
            if is_desktop_plan_required_error(exc):
                return BootstrapResult(
                    BootstrapDestination.LOGIN,
                    message=DESKTOP_REQUIRES_PAID_PLAN_MESSAGE,
                )
            return BootstrapResult(
                BootstrapDestination.LOGIN,
                message="Unable to verify your account. Please sign in again.",
            )
        except Exception:
            self.clear()
            _report("Opening sign in", "Session expired.", 100)
            return BootstrapResult(
                BootstrapDestination.LOGIN,
                message="Unable to verify your account. Please sign in again.",
            )

        if not user_can_use_desktop_studio(me):
            self.clear()
            _report("Opening sign in", "Paid plan required.", 100)
            return BootstrapResult(
                BootstrapDestination.LOGIN,
                message=DESKTOP_REQUIRES_PAID_PLAN_MESSAGE,
            )

        self._current_user = me
        activate_local_user_scope(me.id, self._storage)
        self._remember_session_account(me)
        self.workspace_cache.apply_warmup(me=me)

        _report("Loading profiles", "Preparing your workspace.", 80)
        try:
            profiles = self._api.list_profiles()
            self.workspace_cache.apply_warmup(profiles=profiles)
            if not profiles:
                if me.email_confirmed:
                    _report("Resuming onboarding", "Continuing your setup.", 100)
                    return BootstrapResult(BootstrapDestination.ONBOARDING_WIZARD)
                _report("Starting onboarding", "Please confirm your email first.", 100)
                return BootstrapResult(BootstrapDestination.ONBOARDING_WELCOME)
        except Exception:
            # Leave headroom so shell warmup can continue the same progress bar.
            _report("Opening studio", "Continuing with existing session.", 55)
            return BootstrapResult(BootstrapDestination.APP_HOME)

        # Leave headroom so shell warmup can continue the same progress bar.
        _report("Opening studio", "Welcome back.", 55)
        return BootstrapResult(BootstrapDestination.APP_HOME)

    def login(self, email: str, password: str) -> BootstrapResult:
        self.workspace_cache.clear()
        self._current_user = None
        tokens = self._api.login(email, password)
        self.set_tokens(AuthTokens.from_token_response(tokens))
        return self.run_bootstrap()

    def register(self, email: str, password: str, display_name: str) -> None:
        self._api.register(email, password, display_name)
        tokens = self._api.login(email, password)
        self.set_tokens(AuthTokens.from_token_response(tokens))

    def get_api_base_url(self) -> str:
        return self._storage.get_api_base_url()

    def set_api_base_url(self, url: str) -> None:
        self._storage.set_api_base_url(url)

    def fetch_current_user(self) -> UserMeResponse:
        me = self._api.get_me()
        self._current_user = me
        activate_local_user_scope(me.id, self._storage)
        self._remember_session_account(me)
        return me

    def logout(self) -> None:
        try:
            self._api.logout()
        except Exception:
            pass
        self.clear()


def _parse_tokens(raw: str | None) -> AuthTokens | None:
    if not raw:
        return None
    try:
        data = json.loads(raw)
        tokens = AuthTokens.model_validate(data)
        if not tokens.accessToken or not tokens.refreshToken:
            return None
        return tokens
    except (json.JSONDecodeError, ValueError):
        return None
