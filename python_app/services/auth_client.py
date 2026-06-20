"""HTTP client for Platform API authentication endpoints.

Implements the AuthClientPort protocol using httpx.Client (sync) with
configurable base URL and 15-second default timeout. All methods are
designed to be called from worker threads (not the Qt main thread).

HTTP status codes are mapped to typed exceptions:
    401 → AuthenticationError / TokenExpiredError
    403 → AccountLockedError
    409 → DuplicateEmailError
    422 → ValidationError
    network errors → NetworkError
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import httpx

from python_app.services.api_errors import (
    AccountLockedError,
    AuthenticationError,
    DuplicateEmailError,
    NetworkError,
    TokenExpiredError,
    ValidationError,
)

_DEFAULT_TIMEOUT = 15.0  # seconds


@dataclass(frozen=True)
class AuthTokens:
    """Token pair returned from auth endpoints."""

    access_token: str
    refresh_token: str
    expires_in: int  # seconds


class AuthClientPort(Protocol):
    """Protocol for authentication operations."""

    def login(self, email: str, password: str) -> AuthTokens:
        """Authenticate with email/password."""
        ...

    def register(self, email: str, password: str, display_name: str) -> None:
        """Register a new account."""
        ...

    def refresh(self, refresh_token: str) -> AuthTokens:
        """Obtain new tokens using a refresh token."""
        ...

    def logout(self, access_token: str, refresh_token: str) -> None:
        """Revoke refresh token server-side. Best-effort."""
        ...

    def validate(self, access_token: str) -> bool:
        """Check if access token is still valid. Returns True if 200, False on 401."""
        ...


class AuthClient:
    """HTTP client for Platform API authentication endpoints.

    Satisfies the AuthClientPort protocol. Uses a shared httpx.Client
    instance for connection pooling (thread-safe).

    Args:
        base_url: Platform API base URL (e.g. "http://localhost:8000/api/v1").
        timeout: Request timeout in seconds. Defaults to 15s.
    """

    def __init__(
        self,
        base_url: str = "http://localhost:8000/api/v1",
        timeout: float = _DEFAULT_TIMEOUT,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._client = httpx.Client(
            base_url=self._base_url,
            timeout=timeout,
        )

    # ------------------------------------------------------------------
    # Public API (AuthClientPort)
    # ------------------------------------------------------------------

    def login(self, email: str, password: str) -> AuthTokens:
        """Authenticate with email/password.

        Raises:
            AuthenticationError: On 401 (invalid credentials).
            AccountLockedError: On 403 (account locked).
            NetworkError: On connection failure or timeout.
        """
        response = self._post(
            "/auth/login",
            json={"email": email, "password": password},
        )

        if response.status_code == 200:
            data = response.json()
            return AuthTokens(
                access_token=data["access_token"],
                refresh_token=data["refresh_token"],
                expires_in=data["expires_in"],
            )

        if response.status_code == 401:
            msg = self._extract_message(response, "Invalid email or password")
            raise AuthenticationError(msg, status_code=401)

        if response.status_code == 403:
            msg = self._extract_message(response, "Account temporarily locked")
            raise AccountLockedError(msg, status_code=403)

        # Unexpected status — raise generic authentication error
        msg = self._extract_message(response, "Login failed")
        raise AuthenticationError(msg, status_code=response.status_code)

    def register(self, email: str, password: str, display_name: str) -> None:
        """Register a new account.

        Raises:
            DuplicateEmailError: On 409 (email already exists).
            ValidationError: On 422 (field validation errors).
            NetworkError: On connection failure or timeout.
        """
        response = self._post(
            "/auth/register",
            json={
                "email": email,
                "password": password,
                "display_name": display_name,
            },
        )

        if response.status_code == 201:
            return

        if response.status_code == 409:
            msg = self._extract_message(response, "Email already registered")
            raise DuplicateEmailError(msg, status_code=409)

        if response.status_code == 422:
            msg, field_errors = self._extract_validation_errors(response)
            raise ValidationError(msg, field_errors=field_errors)

        # Unexpected status
        msg = self._extract_message(response, "Registration failed")
        raise AuthenticationError(msg, status_code=response.status_code)

    def refresh(self, refresh_token: str) -> AuthTokens:
        """Obtain new tokens using a refresh token.

        Raises:
            TokenExpiredError: On 401 (refresh token invalid/expired).
            NetworkError: On connection failure or timeout.
        """
        response = self._post(
            "/auth/refresh",
            json={"refresh_token": refresh_token},
        )

        if response.status_code == 200:
            data = response.json()
            return AuthTokens(
                access_token=data["access_token"],
                refresh_token=data["refresh_token"],
                expires_in=data["expires_in"],
            )

        if response.status_code == 401:
            msg = self._extract_message(response, "Refresh token expired")
            raise TokenExpiredError(msg, status_code=401)

        # Unexpected status
        msg = self._extract_message(response, "Token refresh failed")
        raise TokenExpiredError(msg, status_code=response.status_code)

    def logout(self, access_token: str, refresh_token: str) -> None:
        """Revoke refresh token server-side. Best-effort (ignores errors)."""
        try:
            self._client.post(
                "/auth/logout",
                json={
                    "access_token": access_token,
                    "refresh_token": refresh_token,
                },
            )
        except Exception:  # noqa: BLE001 — best-effort, suppress all errors
            pass

    def validate(self, access_token: str) -> bool:
        """Check if access token is still valid (GET /users/me).

        Returns True if 200, False on 401.

        Raises:
            NetworkError: On connection failure or timeout.
        """
        try:
            response = self._client.get(
                "/users/me",
                headers={"Authorization": f"Bearer {access_token}"},
            )
        except (httpx.ConnectError, httpx.TimeoutException, httpx.NetworkError) as exc:
            raise NetworkError(
                f"Connection failed while validating token: {exc}",
                status_code=None,
            ) from exc

        if response.status_code == 200:
            return True
        if response.status_code == 401:
            return False

        # Unexpected status — treat as invalid
        return False

    def check_profiles(self, access_token: str) -> dict:
        """Check if user has completed channel onboarding (GET /channel-setup/profiles-status).

        Returns dict with 'has_profiles' bool and 'profile_count' int.
        """
        try:
            response = self._client.get(
                "/channel-setup/profiles-status",
                headers={"Authorization": f"Bearer {access_token}"},
            )
            if response.status_code == 200:
                return response.json()
        except Exception:  # noqa: BLE001
            pass
        return {"has_profiles": False, "profile_count": 0}

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _post(self, path: str, json: dict) -> httpx.Response:  # type: ignore[type-arg]
        """Send a POST request, translating network errors."""
        try:
            return self._client.post(path, json=json)
        except (httpx.ConnectError, httpx.TimeoutException, httpx.NetworkError) as exc:
            raise NetworkError(
                f"Connection failed: {exc}",
                status_code=None,
            ) from exc

    @staticmethod
    def _extract_message(response: httpx.Response, default: str) -> str:
        """Extract error message from JSON response body, or use default."""
        try:
            body = response.json()
            return body.get("message", body.get("detail", default))
        except Exception:  # noqa: BLE001
            return default

    @staticmethod
    def _extract_validation_errors(
        response: httpx.Response,
    ) -> tuple[str, dict[str, str]]:
        """Extract field-level validation errors from a 422 response.

        Supports three response shapes:
        1. PlatformAPIError: {"error": {"message": "...", "details": {"fields": [...]}}}
        2. FastAPI Pydantic: {"detail": [{"loc": [...], "msg": "..."}]}
        3. Simple: {"message": "...", "field_errors": {"field": "msg"}}

        Returns (summary_message, field_errors_dict).
        """
        field_errors: dict[str, str] = {}
        message = "Validation failed"
        try:
            body = response.json()

            # Unwrap {"error": {...}} envelope from PlatformAPIError handler
            if "error" in body and isinstance(body["error"], dict):
                err = body["error"]
                message = err.get("message", message)
                details = err.get("details", {})
                # details may be {"fields": [...]} or a plain dict
                if isinstance(details, dict) and "fields" in details:
                    field_list = details["fields"]
                    if isinstance(field_list, list):
                        for item in field_list:
                            if isinstance(item, dict):
                                field_errors[str(item.get("field", "unknown"))] = item.get("message", "Invalid value")
                    elif isinstance(field_list, dict):
                        field_errors = {k: str(v) for k, v in field_list.items()}
                elif isinstance(details, dict):
                    field_errors = {k: str(v) for k, v in details.items() if k != "fields"}
            else:
                message = body.get("message", message)

            # FastAPI Pydantic-style detail list
            if not field_errors:
                details = body.get("detail", body.get("field_errors", []))
                if isinstance(details, list):
                    for item in details:
                        if isinstance(item, dict):
                            loc = item.get("loc", [])
                            field_name = loc[-1] if loc else item.get("field", "unknown")
                            msg = item.get("msg", "Invalid value")
                            field_errors[str(field_name)] = msg
                elif isinstance(details, dict):
                    field_errors = {k: str(v) for k, v in details.items()}

        except Exception:  # noqa: BLE001
            pass

        return message, field_errors

    def close(self) -> None:
        """Close the underlying httpx client and release connections."""
        self._client.close()

    def __enter__(self) -> AuthClient:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()
