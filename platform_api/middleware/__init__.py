"""Middleware components for the Platform API."""

from platform_api.middleware.auth import (
    AuthContext,
    check_credit_balance,
    configure_auth_dependencies,
    get_current_user,
    require_active_license,
    require_admin,
    require_generation_access,
    require_sufficient_credits,
)
from platform_api.middleware.rate_limit import (
    RateLimitConfig,
    RateLimiter,
    check_rate_limit,
    configure_rate_limiter,
    get_rate_limiter,
    resolve_endpoint_type,
)

__all__ = [
    "AuthContext",
    "RateLimitConfig",
    "RateLimiter",
    "check_credit_balance",
    "check_rate_limit",
    "configure_auth_dependencies",
    "configure_rate_limiter",
    "get_current_user",
    "get_rate_limiter",
    "require_active_license",
    "require_admin",
    "require_generation_access",
    "require_sufficient_credits",
    "resolve_endpoint_type",
]
