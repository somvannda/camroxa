"""Structured error hierarchy for Platform API integration failures.

Each error class stores a `status_code` (int | None) and `message` (str).
`ValidationError` additionally stores `field_errors: dict[str, str]` for
per-field validation messages returned by the API (422 responses).
"""

from __future__ import annotations


class PlatformAPIError(Exception):
    """Base error for all Platform API communication failures."""

    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class NetworkError(PlatformAPIError):
    """Connection failure, timeout, or DNS resolution error."""

    pass


class AuthenticationError(PlatformAPIError):
    """Invalid credentials (401)."""

    pass


class AccountLockedError(PlatformAPIError):
    """Account temporarily locked (403 with lockout reason)."""

    pass


class TokenExpiredError(PlatformAPIError):
    """Both access and refresh tokens are invalid (401 on refresh)."""

    pass


class DuplicateEmailError(PlatformAPIError):
    """Email already registered (409)."""

    pass


class ValidationError(PlatformAPIError):
    """Field validation errors from API (422).

    Attributes:
        field_errors: Mapping of field names to their error messages.
    """

    def __init__(
        self, message: str, field_errors: dict[str, str] | None = None
    ) -> None:
        super().__init__(message, 422)
        self.field_errors: dict[str, str] = field_errors or {}


class InsufficientCreditsError(PlatformAPIError):
    """Not enough credits for the operation (402)."""

    pass


class LicenseExpiredError(PlatformAPIError):
    """License expired or not active (403 with license reason)."""

    pass


class GenerationError(PlatformAPIError):
    """Generation request failed (5xx or unexpected error)."""

    pass
