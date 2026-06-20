"""Platform API exception hierarchy.

All domain exceptions inherit from PlatformAPIError and carry an HTTP status code,
a machine-readable error code, and a human-readable message. The global exception
handler in main.py converts these into the standard JSON error envelope.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


class PlatformAPIError(Exception):
    """Base exception for all Platform API domain errors.

    Attributes:
        status_code: HTTP status code to return.
        error_code: Machine-readable error identifier (e.g. "AUTHENTICATION_ERROR").
        message: Human-readable description of the error.
        details: Optional dict with additional context (e.g. field validation errors).
    """

    status_code: int = 500
    error_code: str = "INTERNAL_ERROR"

    def __init__(
        self,
        message: str = "An unexpected error occurred.",
        *,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.message = message
        self.details = details
        super().__init__(message)


class AuthenticationError(PlatformAPIError):
    """Invalid or missing credentials (401)."""

    status_code = 401
    error_code = "AUTHENTICATION_ERROR"

    def __init__(
        self,
        message: str = "Invalid credentials.",
        *,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, details=details)


class AccountLockedError(PlatformAPIError):
    """Account locked due to repeated failed login attempts (403)."""

    status_code = 403
    error_code = "ACCOUNT_LOCKED"

    def __init__(
        self,
        message: str = "Account locked for 15 minutes due to repeated failed login attempts.",
        *,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, details=details)


class ForbiddenError(PlatformAPIError):
    """Non-admin access to admin-only endpoints (403)."""

    status_code = 403
    error_code = "FORBIDDEN"

    def __init__(
        self,
        message: str = "You do not have permission to perform this action.",
        *,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, details=details)


class LicenseExpiredError(PlatformAPIError):
    """License expired — generation requests rejected (403)."""

    status_code = 403
    error_code = "LICENSE_EXPIRED"

    def __init__(
        self,
        message: str = "Your license has expired. Please renew to continue.",
        *,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, details=details)


class InsufficientCreditsError(PlatformAPIError):
    """Wallet balance too low for the requested operation (402)."""

    status_code = 402
    error_code = "INSUFFICIENT_CREDITS"

    def __init__(
        self,
        message: str = "Insufficient credits for this operation.",
        *,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, details=details)


class QuotaExceededError(PlatformAPIError):
    """Daily or monthly generation quota exceeded (429)."""

    status_code = 429
    error_code = "QUOTA_EXCEEDED"

    def __init__(
        self,
        message: str = "Generation quota exceeded.",
        *,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, details=details)


class ExternalServiceError(PlatformAPIError):
    """Upstream AI service returned an error or is unreachable (502).

    Attributes:
        is_retryable: Whether the caller should retry the request.
            True for timeouts, rate limits (429), and 5xx server errors.
            False for 4xx client errors (except 429).
    """

    status_code = 502
    error_code = "EXTERNAL_SERVICE_ERROR"

    def __init__(
        self,
        message: str = "An external service error occurred.",
        *,
        is_retryable: bool = False,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.is_retryable = is_retryable
        super().__init__(message, details=details)


class ValidationError(PlatformAPIError):
    """Request validation failed — details lists which fields failed (422)."""

    status_code = 422
    error_code = "VALIDATION_ERROR"

    def __init__(
        self,
        message: str = "Validation failed.",
        *,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, details=details)


class DuplicateError(PlatformAPIError):
    """Conflict — resource already exists (409)."""

    status_code = 409
    error_code = "DUPLICATE_ERROR"

    def __init__(
        self,
        message: str = "Resource already exists.",
        *,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, details=details)


class NotFoundError(PlatformAPIError):
    """Requested resource does not exist (404)."""

    status_code = 404
    error_code = "NOT_FOUND"

    def __init__(
        self,
        message: str = "Resource not found.",
        *,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, details=details)


class NoAvailableKeysError(PlatformAPIError):
    """Raised when no active keys exist for a provider (503)."""

    status_code = 503
    error_code = "NO_AVAILABLE_KEYS"

    def __init__(self, provider: str, status_counts: dict[str, int]) -> None:
        super().__init__(
            f"No available API keys for provider '{provider}'.",
            details={"provider": provider, "status_counts": status_counts},
        )


class DuplicateKeyLabelError(PlatformAPIError):
    """Raised when a duplicate label is used within the same provider (409)."""

    status_code = 409
    error_code = "DUPLICATE_KEY_LABEL"

    def __init__(self, provider: str, label: str) -> None:
        super().__init__(
            f"Label '{label}' already exists for provider '{provider}'.",
            details={"provider": provider, "label": label},
        )
