"""Tests for the exception hierarchy and global error handler."""

import pytest
from httpx import ASGITransport, AsyncClient

from platform_api.exceptions import (
    AccountLockedError,
    AuthenticationError,
    DuplicateError,
    ExternalServiceError,
    ForbiddenError,
    InsufficientCreditsError,
    LicenseExpiredError,
    NotFoundError,
    PlatformAPIError,
    QuotaExceededError,
    ValidationError,
)
from platform_api.main import create_app


# ---------------------------------------------------------------------------
# Exception class unit tests
# ---------------------------------------------------------------------------


class TestExceptionHierarchy:
    """All custom exceptions inherit from PlatformAPIError."""

    def test_base_exception_defaults(self) -> None:
        exc = PlatformAPIError()
        assert exc.status_code == 500
        assert exc.error_code == "INTERNAL_ERROR"
        assert exc.message == "An unexpected error occurred."
        assert exc.details is None

    def test_base_exception_custom(self) -> None:
        exc = PlatformAPIError("custom msg", details={"key": "val"})
        assert exc.message == "custom msg"
        assert exc.details == {"key": "val"}

    @pytest.mark.parametrize(
        "exc_cls,expected_status,expected_code",
        [
            (AuthenticationError, 401, "AUTHENTICATION_ERROR"),
            (AccountLockedError, 403, "ACCOUNT_LOCKED"),
            (ForbiddenError, 403, "FORBIDDEN"),
            (LicenseExpiredError, 403, "LICENSE_EXPIRED"),
            (InsufficientCreditsError, 402, "INSUFFICIENT_CREDITS"),
            (QuotaExceededError, 429, "QUOTA_EXCEEDED"),
            (ExternalServiceError, 502, "EXTERNAL_SERVICE_ERROR"),
            (ValidationError, 422, "VALIDATION_ERROR"),
            (DuplicateError, 409, "DUPLICATE_ERROR"),
            (NotFoundError, 404, "NOT_FOUND"),
        ],
    )
    def test_subclass_status_and_code(
        self, exc_cls: type[PlatformAPIError], expected_status: int, expected_code: str
    ) -> None:
        exc = exc_cls()
        assert isinstance(exc, PlatformAPIError)
        assert exc.status_code == expected_status
        assert exc.error_code == expected_code

    def test_validation_error_with_field_details(self) -> None:
        details = {"fields": {"email": "invalid format", "password": "too short"}}
        exc = ValidationError("Validation failed.", details=details)
        assert exc.details == details
        assert exc.status_code == 422


# ---------------------------------------------------------------------------
# Global error handler integration tests
# ---------------------------------------------------------------------------


class TestGlobalErrorHandler:
    """The app should return structured JSON for PlatformAPIError subclasses."""

    @pytest.fixture
    def app(self):
        """Create app with test routes that raise various exceptions."""
        from fastapi import FastAPI

        application = create_app()

        @application.get("/test/auth-error")
        async def _raise_auth():
            raise AuthenticationError("Bad creds")

        @application.get("/test/locked")
        async def _raise_locked():
            raise AccountLockedError()

        @application.get("/test/forbidden")
        async def _raise_forbidden():
            raise ForbiddenError("Admins only")

        @application.get("/test/license-expired")
        async def _raise_license():
            raise LicenseExpiredError()

        @application.get("/test/credits")
        async def _raise_credits():
            raise InsufficientCreditsError(
                "Need 14 credits, have 3.",
                details={"required": 14, "balance": 3},
            )

        @application.get("/test/quota")
        async def _raise_quota():
            raise QuotaExceededError(
                "Daily limit reached.",
                details={"limit": 7, "used": 7, "reset_at": "2024-01-02T00:00:00Z"},
            )

        @application.get("/test/external")
        async def _raise_external():
            raise ExternalServiceError("Suno API timeout")

        @application.get("/test/validation")
        async def _raise_validation():
            raise ValidationError(
                "Validation failed.",
                details={"fields": {"email": "invalid format"}},
            )

        @application.get("/test/duplicate")
        async def _raise_duplicate():
            raise DuplicateError("Email already exists.")

        @application.get("/test/not-found")
        async def _raise_not_found():
            raise NotFoundError("User not found.")

        @application.get("/test/unhandled")
        async def _raise_unhandled():
            raise RuntimeError("unexpected kaboom")

        return application

    @pytest.fixture
    async def client(self, app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            yield c

    async def test_auth_error_response(self, client: AsyncClient) -> None:
        resp = await client.get("/test/auth-error")
        assert resp.status_code == 401
        body = resp.json()
        assert body["error"]["code"] == "AUTHENTICATION_ERROR"
        assert body["error"]["message"] == "Bad creds"
        assert "details" not in body["error"]

    async def test_locked_error_response(self, client: AsyncClient) -> None:
        resp = await client.get("/test/locked")
        assert resp.status_code == 403
        body = resp.json()
        assert body["error"]["code"] == "ACCOUNT_LOCKED"

    async def test_forbidden_error_response(self, client: AsyncClient) -> None:
        resp = await client.get("/test/forbidden")
        assert resp.status_code == 403
        body = resp.json()
        assert body["error"]["code"] == "FORBIDDEN"
        assert body["error"]["message"] == "Admins only"

    async def test_license_expired_response(self, client: AsyncClient) -> None:
        resp = await client.get("/test/license-expired")
        assert resp.status_code == 403
        body = resp.json()
        assert body["error"]["code"] == "LICENSE_EXPIRED"

    async def test_insufficient_credits_with_details(self, client: AsyncClient) -> None:
        resp = await client.get("/test/credits")
        assert resp.status_code == 402
        body = resp.json()
        assert body["error"]["code"] == "INSUFFICIENT_CREDITS"
        assert body["error"]["details"]["required"] == 14
        assert body["error"]["details"]["balance"] == 3

    async def test_quota_exceeded_with_details(self, client: AsyncClient) -> None:
        resp = await client.get("/test/quota")
        assert resp.status_code == 429
        body = resp.json()
        assert body["error"]["code"] == "QUOTA_EXCEEDED"
        assert body["error"]["details"]["limit"] == 7

    async def test_external_service_error(self, client: AsyncClient) -> None:
        resp = await client.get("/test/external")
        assert resp.status_code == 502
        body = resp.json()
        assert body["error"]["code"] == "EXTERNAL_SERVICE_ERROR"

    async def test_validation_error_with_fields(self, client: AsyncClient) -> None:
        resp = await client.get("/test/validation")
        assert resp.status_code == 422
        body = resp.json()
        assert body["error"]["code"] == "VALIDATION_ERROR"
        assert body["error"]["details"]["fields"]["email"] == "invalid format"

    async def test_duplicate_error(self, client: AsyncClient) -> None:
        resp = await client.get("/test/duplicate")
        assert resp.status_code == 409
        body = resp.json()
        assert body["error"]["code"] == "DUPLICATE_ERROR"

    async def test_not_found_error(self, client: AsyncClient) -> None:
        resp = await client.get("/test/not-found")
        assert resp.status_code == 404
        body = resp.json()
        assert body["error"]["code"] == "NOT_FOUND"

    async def test_unhandled_exception_returns_500(self, client: AsyncClient) -> None:
        # Under ASGI transport, unhandled exceptions propagate through Starlette's
        # ServerErrorMiddleware. We verify the handler is registered and would
        # produce 500 in production by testing through raise_server_exceptions=False.
        transport = ASGITransport(app=client._transport.app, raise_app_exceptions=False)  # type: ignore[attr-defined]
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            resp = await c.get("/test/unhandled")
        assert resp.status_code == 500
        body = resp.json()
        assert body["error"]["code"] == "INTERNAL_SERVER_ERROR"

    async def test_no_details_when_none(self, client: AsyncClient) -> None:
        """details key should be absent when no details are provided."""
        resp = await client.get("/test/auth-error")
        body = resp.json()
        assert "details" not in body["error"]

    async def test_security_audit_logged_for_401(
        self, client: AsyncClient, caplog: pytest.LogCaptureFixture
    ) -> None:
        """401 responses should trigger an audit log."""
        import logging

        with caplog.at_level(logging.WARNING, logger="platform_api.main"):
            await client.get("/test/auth-error")
        assert any("SECURITY_AUDIT" in record.message for record in caplog.records)

    async def test_security_audit_logged_for_403(
        self, client: AsyncClient, caplog: pytest.LogCaptureFixture
    ) -> None:
        """403 responses should trigger an audit log."""
        import logging

        with caplog.at_level(logging.WARNING, logger="platform_api.main"):
            await client.get("/test/forbidden")
        assert any("SECURITY_AUDIT" in record.message for record in caplog.records)
