"""License validation and feature gating via Platform API.

Implements the LicenseGatePort protocol. Calls GET /api/v1/licenses/validate
with a Bearer token to check whether the user holds an active license.

Results are cached in memory for UI gating so that repeated
`is_generation_allowed()` calls do not trigger network requests.

Fail-safe behavior:
    - On network error during validation: use cached status if available,
      otherwise return LicenseStatus(is_active=False).
    - `is_generation_allowed()` returns False when no status has been
      checked yet.
"""

from __future__ import annotations

from dataclasses import dataclass
from threading import Lock

import httpx

from python_app.services.api_errors import NetworkError

_DEFAULT_TIMEOUT = 15.0  # seconds


@dataclass(frozen=True)
class LicenseStatus:
    """License validation result.

    Attributes:
        is_active: Whether the user has a valid, non-expired license.
        plan_name: License plan type — "monthly", "yearly", or "lifetime".
            None when no license is present.
        expires_at: ISO-8601 datetime string for when the license expires.
            None for lifetime plans or when no license is present.
        wallet_balance: User's current credit balance.
    """

    is_active: bool
    plan_name: str | None = None
    expires_at: str | None = None
    wallet_balance: int | None = None


class LicenseGate:
    """Checks user license status and controls feature availability.

    Satisfies the LicenseGatePort protocol. Uses a shared httpx.Client
    instance for connection pooling (thread-safe). The cached license
    status is protected by a threading lock.

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
        self._cached_status: LicenseStatus | None = None
        self._lock = Lock()

    # ------------------------------------------------------------------
    # Public API (LicenseGatePort)
    # ------------------------------------------------------------------

    def validate(self, access_token: str) -> LicenseStatus:
        """Check license status via Platform API.

        Calls GET /api/v1/licenses/validate with the provided Bearer token.
        On success, caches and returns the resulting LicenseStatus.

        On network error: returns cached status if available, otherwise
        returns LicenseStatus(is_active=False) as a fail-safe.

        Args:
            access_token: JWT access token for Authorization header.

        Returns:
            LicenseStatus reflecting the current license state.
        """
        try:
            response = self._client.get(
                "/licenses/validate",
                headers={"Authorization": f"Bearer {access_token}"},
            )
        except (httpx.ConnectError, httpx.TimeoutException, httpx.NetworkError) as exc:
            # Fail-safe: use cached status or inactive
            return self._handle_network_error(exc)

        if response.status_code == 200:
            data = response.json()
            status = LicenseStatus(
                is_active=True,
                plan_name=data.get("plan_name") or data.get("plan_type"),
                expires_at=data.get("expires_at") or data.get("expiration_date"),
                wallet_balance=data.get("wallet_balance"),
            )
            self.update_status(status)
            return status

        # Non-200 responses (e.g. 401, 403, 404) → treat as inactive
        status = LicenseStatus(is_active=False)
        self.update_status(status)
        return status

    def is_generation_allowed(self) -> bool:
        """Check cached license status (no network call).

        Used by UI to enable/disable generation controls.

        Returns:
            True if a cached status exists and is_active is True.
            False when no status has been checked yet (fail-safe)
            or the cached license is inactive.
        """
        with self._lock:
            if self._cached_status is None:
                return False
            return self._cached_status.is_active

    def update_status(self, status: LicenseStatus) -> None:
        """Update the cached license status.

        Typically called after a successful validation, but can also be
        called externally (e.g., after token refresh triggers a re-check).

        Args:
            status: The new LicenseStatus to cache.
        """
        with self._lock:
            self._cached_status = status

    def get_cached_status(self) -> LicenseStatus | None:
        """Return the last known license status or None if not checked.

        Returns:
            The most recently cached LicenseStatus, or None if validate()
            has never been called successfully.
        """
        with self._lock:
            return self._cached_status

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _handle_network_error(self, exc: Exception) -> LicenseStatus:
        """Handle network errors during validation with fail-safe logic.

        If a cached status exists, returns it (stale data is better than
        blocking the user). Otherwise, returns inactive status.
        """
        with self._lock:
            if self._cached_status is not None:
                return self._cached_status

        return LicenseStatus(is_active=False)

    def close(self) -> None:
        """Close the underlying httpx client and release connections."""
        self._client.close()

    def __enter__(self) -> LicenseGate:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()
