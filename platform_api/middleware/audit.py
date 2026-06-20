"""Audit logging middleware for the Platform API.

Intercepts state-changing HTTP requests (POST, PUT, PATCH, DELETE) and
automatically creates audit log entries after the response is sent.
Non-mutating methods (GET, HEAD, OPTIONS) are not logged.

The middleware extracts actor information from the request state (set by
the auth middleware), and logs the action after the response completes
so that the outcome (success/failure) can be determined from the status code.

Requirements: 20.1, 20.2, 20.3, 20.4
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Protocol
from uuid import UUID

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

logger = logging.getLogger(__name__)

# HTTP methods that represent state-changing operations
STATE_CHANGING_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


class AuditServicePort(Protocol):
    """Protocol defining the audit service interface needed by the middleware."""

    async def log_event(
        self,
        *,
        actor_id: UUID | str | None = None,
        action_type: str,
        target_resource: str | None = None,
        timestamp: Any = None,
        credit_impact: int = 0,
        outcome: str = "success",
        source_ip: str | None = None,
        client_id: str | None = None,
        endpoint_path: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> UUID:
        """Record an audit log event."""
        ...


def _get_client_ip(request: Request) -> str | None:
    """Extract the client IP address from the request.

    Checks X-Forwarded-For header first (for reverse proxy setups),
    then falls back to the direct client host.

    Args:
        request: The incoming FastAPI request.

    Returns:
        The client IP address string, or None if unavailable.
    """
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        # Take the first IP in the chain (original client)
        return forwarded_for.split(",")[0].strip()
    if request.client:
        return request.client.host
    return None


def _get_client_id(request: Request) -> str | None:
    """Extract the client identifier from the request headers.

    Looks for a custom X-Client-ID header that clients can set
    to identify themselves (e.g., 'desktop-app', 'web-portal').

    Args:
        request: The incoming FastAPI request.

    Returns:
        The client ID string, or None if not provided.
    """
    return request.headers.get("x-client-id")


def _determine_action_type(method: str, path: str) -> str:
    """Determine the action type from the HTTP method and path.

    Maps the request to a categorized action type string based on
    the URL path and HTTP method.

    Args:
        method: The HTTP method (POST, PUT, PATCH, DELETE).
        path: The request URL path.

    Returns:
        A categorized action type string (e.g., 'auth.login', 'profile.create').
    """
    # Normalize path
    normalized = path.lower().strip("/")
    if normalized.startswith("api/v1/"):
        normalized = normalized[7:]

    method_upper = method.upper()

    # Map known paths to action types
    if normalized.startswith("auth/login"):
        return "auth.login"
    elif normalized.startswith("auth/register"):
        return "auth.register"
    elif normalized.startswith("auth/refresh"):
        return "auth.refresh"
    elif normalized.startswith("auth/logout"):
        return "auth.logout"
    elif normalized.startswith("generation/suno"):
        return "generation.suno"
    elif normalized.startswith("generation/image"):
        return "generation.image"
    elif normalized.startswith("generation/draft"):
        return "generation.draft"
    elif normalized.startswith("batches"):
        if method_upper == "POST":
            return "batch.create"
        return f"batch.{method_upper.lower()}"
    elif normalized.startswith("profiles"):
        if method_upper == "POST":
            return "profile.create"
        elif method_upper == "PUT" or method_upper == "PATCH":
            return "profile.update"
        elif method_upper == "DELETE":
            return "profile.delete"
        return f"profile.{method_upper.lower()}"
    elif normalized.startswith("credits/purchase"):
        return "credit.purchase"
    elif normalized.startswith("credits/adjust"):
        return "credit.adjust"
    elif normalized.startswith("credits/pricing"):
        if method_upper == "POST":
            return "credit.pricing.create"
        elif method_upper == "PUT":
            return "credit.pricing.update"
        return f"credit.pricing.{method_upper.lower()}"
    elif normalized.startswith("licenses"):
        if "assign" in normalized:
            return "license.assign"
        elif "revoke" in normalized:
            return "license.revoke"
        elif method_upper == "POST":
            return "license.create"
        return f"license.{method_upper.lower()}"
    elif normalized.startswith("users") and "suspend" in normalized:
        return "user.suspend"
    elif normalized.startswith("users") and "reactivate" in normalized:
        return "user.reactivate"
    elif normalized.startswith("users"):
        if method_upper == "DELETE":
            return "user.delete"
        elif method_upper in ("PUT", "PATCH"):
            return "user.update"
        return f"user.{method_upper.lower()}"
    elif normalized.startswith("settings"):
        return "settings.update"
    elif normalized.startswith("plans"):
        if method_upper == "POST":
            return "plan.create"
        elif method_upper in ("PUT", "PATCH"):
            return "plan.update"
        return f"plan.{method_upper.lower()}"
    elif normalized.startswith("prompts"):
        if method_upper == "POST":
            return "prompt.create"
        elif method_upper in ("PUT", "PATCH"):
            return "prompt.update"
        elif method_upper == "DELETE":
            return "prompt.delete"
        return f"prompt.{method_upper.lower()}"
    elif normalized.startswith("admin/rate-limits"):
        return "admin.rate_limits.update"

    # Generic fallback
    return f"api.{method_upper.lower()}"


def _determine_outcome(status_code: int) -> str:
    """Determine the outcome based on the HTTP response status code.

    Args:
        status_code: The HTTP response status code.

    Returns:
        'success' for 2xx responses, 'failure' for all others.
    """
    if 200 <= status_code < 300:
        return "success"
    return "failure"


def _extract_target_resource(path: str) -> str | None:
    """Extract a target resource identifier from the URL path.

    Looks for UUID-like segments in the path to identify the target resource.

    Args:
        path: The request URL path.

    Returns:
        A resource identifier string, or None if not determinable.
    """
    # Normalize path
    normalized = path.strip("/")
    if normalized.startswith("api/v1/"):
        normalized = normalized[7:]

    parts = normalized.split("/")

    # Look for patterns like /resource/{id}/action
    if len(parts) >= 2:
        resource_type = parts[0]
        # Check if the second part looks like a UUID or ID
        if len(parts) >= 2 and len(parts[1]) > 8:
            return f"{resource_type}:{parts[1]}"

    return None


# ---------------------------------------------------------------------------
# AuditMiddleware class
# ---------------------------------------------------------------------------


class AuditMiddleware(BaseHTTPMiddleware):
    """ASGI middleware that auto-logs state-changing requests.

    Intercepts POST, PUT, PATCH, DELETE requests and creates audit log
    entries after the response is sent. GET, HEAD, and OPTIONS are skipped.

    The middleware runs AFTER the auth middleware, so the authenticated
    user context is available in the request state.

    Args:
        app: The ASGI application.
        audit_service: The audit service instance for logging.
    """

    def __init__(self, app: Any, audit_service: AuditServicePort) -> None:
        super().__init__(app)
        self._audit_service = audit_service

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        """Process the request and log state-changing operations.

        Non-state-changing methods (GET, HEAD, OPTIONS) pass through
        without audit logging. For state-changing methods, the audit
        entry is created after the response is generated.

        Args:
            request: The incoming HTTP request.
            call_next: The next middleware/handler in the chain.

        Returns:
            The HTTP response from the downstream handler.
        """
        try:
            # Skip non-state-changing methods
            if request.method.upper() not in STATE_CHANGING_METHODS:
                return await call_next(request)

            # Process the request
            response = await call_next(request)
        except Exception as exc:
            # BaseHTTPMiddleware swallows exceptions from call_next and returns
            # a bare 500 without CORS headers. Catch here so we can return a
            # proper JSON response that will pass through the CORS middleware.
            import traceback
            logger.error(
                "Unhandled error in request %s %s: %s\n%s",
                request.method,
                request.url.path,
                exc,
                traceback.format_exc(),
            )
            from fastapi.responses import JSONResponse
            return JSONResponse(
                status_code=500,
                content={
                    "error": {
                        "code": "INTERNAL_SERVER_ERROR",
                        "message": "An unexpected error occurred.",
                        "details": str(exc),
                    }
                },
            )

        # Log the audit entry after the response (fire-and-forget style with error handling)
        try:
            await self._log_request(request, response)
        except Exception:
            # Never let audit logging failures affect the response
            logger.exception("Failed to log audit entry for %s %s", request.method, request.url.path)

        return response

    async def _log_request(self, request: Request, response: Response) -> None:
        """Create an audit log entry for a state-changing request.

        Extracts all available context from the request and response to
        populate the audit entry fields.

        Args:
            request: The HTTP request that was processed.
            response: The HTTP response that was generated.
        """
        # Extract actor_id from request state (set by auth middleware)
        actor_id: str | None = None
        if hasattr(request.state, "user_id"):
            actor_id = request.state.user_id
        elif hasattr(request.state, "auth_context"):
            ctx = request.state.auth_context
            if hasattr(ctx, "user_id"):
                actor_id = ctx.user_id

        # Build the audit entry
        path = request.url.path
        action_type = _determine_action_type(request.method, path)
        outcome = _determine_outcome(response.status_code)
        source_ip = _get_client_ip(request)
        client_id = _get_client_id(request)
        target_resource = _extract_target_resource(path)

        metadata: dict[str, Any] = {
            "http_method": request.method,
            "status_code": response.status_code,
        }

        await self._audit_service.log_event(
            actor_id=actor_id,
            action_type=action_type,
            target_resource=target_resource,
            outcome=outcome,
            source_ip=source_ip,
            client_id=client_id,
            endpoint_path=path,
            metadata=metadata,
        )


# ---------------------------------------------------------------------------
# Module-level singleton (configured at startup)
# ---------------------------------------------------------------------------

_audit_middleware_service: AuditServicePort | None = None


def configure_audit_middleware(*, audit_service: AuditServicePort) -> None:
    """Configure the audit middleware with the service instance.

    Call this once during application startup.

    Args:
        audit_service: The AuditService instance to use for logging.
    """
    global _audit_middleware_service
    _audit_middleware_service = audit_service


def get_audit_service() -> AuditServicePort | None:
    """Return the configured audit service for the middleware, or None if not configured."""
    return _audit_middleware_service
