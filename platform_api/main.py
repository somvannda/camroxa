"""FastAPI application factory for the Platform API."""

import logging
import os
import sys
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# Configure root logging so startup diagnostics appear in terminal
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    stream=sys.stdout,
)


from platform_api.config import Settings, get_settings
from platform_api.exceptions import PlatformAPIError

logger = logging.getLogger(__name__)

# Status codes that trigger security audit logging.
_SECURITY_AUDIT_CODES = {401, 403}


async def _platform_error_handler(request: Request, exc: PlatformAPIError) -> JSONResponse:
    """Handle PlatformAPIError subclasses and return the standard JSON error envelope."""
    # Audit log for security-sensitive responses (401/403).
    if exc.status_code in _SECURITY_AUDIT_CODES:
        logger.warning(
            "SECURITY_AUDIT: status=%d code=%s path=%s method=%s client=%s message=%s",
            exc.status_code,
            exc.error_code,
            request.url.path,
            request.method,
            request.client.host if request.client else "unknown",
            exc.message,
        )

    content: dict = {
        "error": {
            "code": exc.error_code,
            "message": exc.message,
        }
    }
    if exc.details is not None:
        content["error"]["details"] = exc.details

    return JSONResponse(status_code=exc.status_code, content=content)


async def _global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Return structured JSON error responses for unhandled exceptions."""
    # Always log the full traceback for debugging
    import traceback
    logger.error(
        "Unhandled exception on %s %s: %s\n%s",
        request.method,
        request.url.path,
        str(exc),
        traceback.format_exc(),
    )
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": "An unexpected error occurred.",
                "details": str(exc) if get_settings().debug else None,
            }
        },
    )


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Manage application startup and shutdown lifecycle.

    Startup:
      - Create asyncpg connection pool
      - Create Redis connection
      - Configure auth middleware dependencies
      - Configure rate limiter
      - Configure audit middleware

    Shutdown:
      - Close Redis connection
      - Close asyncpg pool
      - Clear dependency singletons
    """
    from platform_api.dependencies import (
        clear_connections,
        get_audit_service,
        get_auth_service,
        get_credit_repo,
        get_license_repo,
        get_rate_limit_config_repo,
        get_user_repo,
        set_db_pool,
        set_redis,
    )
    from platform_api.middleware.auth import configure_auth_dependencies
    from platform_api.middleware.audit import configure_audit_middleware
    from platform_api.middleware.rate_limit import configure_rate_limiter

    settings = get_settings()
    db_pool = None
    redis_conn = None

    # --- Startup diagnostics ---
    logger.info("=" * 60)
    logger.info("PLATFORM API STARTUP DIAGNOSTICS")
    logger.info("=" * 60)
    logger.info("Working directory: %s", os.getcwd())
    logger.info("Database URL: %s", settings.database_url.replace(settings.database_url.split("@")[0].split("//")[1] if "@" in settings.database_url else "", "***"))
    logger.info("Redis URL: %s", settings.redis_url)
    logger.info("Debug mode: %s", settings.debug)
    logger.info("CORS origins: %s", settings.cors_origins)
    logger.info("Encryption master key set: %s", "YES" if settings.encryption_master_key else "NO")
    logger.info("=" * 60)

    try:
        # --- Create asyncpg connection pool ---
        import asyncpg

        # Parse the database URL for asyncpg (strip the driver prefix if present)
        dsn = settings.database_url
        if dsn.startswith("postgresql+asyncpg://"):
            dsn = dsn.replace("postgresql+asyncpg://", "postgresql://", 1)

        db_pool = await asyncpg.create_pool(dsn, min_size=2, max_size=10)
        set_db_pool(db_pool)
        logger.info("Database connection pool created.")

        # Verify DB connectivity
        try:
            async with db_pool.acquire() as conn:
                result = await conn.fetchval("SELECT 1")
                logger.info("Database connectivity verified: SELECT 1 = %s", result)

                # Check if key pool tables exist
                kp_exists = await conn.fetchval(
                    "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'api_key_entries')"
                )
                logger.info("Key pool tables exist: %s", kp_exists)
        except Exception as db_check_exc:
            logger.error("Database connectivity check FAILED: %s", db_check_exc)

        # --- Create Redis connection ---
        import redis.asyncio as aioredis

        redis_conn = aioredis.from_url(
            settings.redis_url,
            decode_responses=True,
        )
        set_redis(redis_conn)
        logger.info("Redis connection established.")

        # Verify Redis connectivity
        try:
            pong = await redis_conn.ping()
            logger.info("Redis connectivity verified: PING = %s", pong)
        except Exception as redis_check_exc:
            logger.error("Redis connectivity check FAILED: %s", redis_check_exc)

        # --- Configure auth middleware dependencies ---
        configure_auth_dependencies(
            auth_service=get_auth_service(),
            user_repo=get_user_repo(),
            license_repo=get_license_repo(),
            credit_repo=get_credit_repo(),
        )
        logger.info("Auth middleware configured.")

        # --- Configure rate limiter ---
        configure_rate_limiter(
            redis=redis_conn,
            config_repo=get_rate_limit_config_repo(),
        )
        logger.info("Rate limiter configured.")

        # --- Configure audit middleware ---
        configure_audit_middleware(audit_service=get_audit_service())
        logger.info("Audit middleware configured.")

        # --- Warm Key Pool Redis cache ---
        logger.info(
            "Key pool encryption key configured: %s",
            "YES" if settings.encryption_master_key else "NO (key pool disabled)",
        )
        if settings.encryption_master_key:
            try:
                from platform_api.services.key_pool_service import KeyPoolService
                from platform_api.repositories.key_pool_repo import KeyPoolRepository
                from platform_api.services.key_encryption import KeyEncryption

                key_pool_repo = KeyPoolRepository(pool=db_pool)
                key_encryption = KeyEncryption(master_key=settings.encryption_master_key)
                key_pool_service = KeyPoolService(
                    repository=key_pool_repo,
                    encryption=key_encryption,
                    redis=redis_conn,
                )
                await key_pool_service.load_all_caches()
                logger.info("Key pool Redis cache warmed on startup.")
            except Exception as exc:
                logger.warning(
                    "Failed to warm key pool cache on startup (non-fatal): %s", exc
                )
        else:
            logger.warning(
                "ENCRYPTION_MASTER_KEY not set — key pool cache not loaded. "
                "Set PLATFORM_ENCRYPTION_MASTER_KEY to enable the API key pool."
            )

    except Exception as exc:
        logger.error("Failed to initialize application resources: %s", exc)
        # Still yield so the app can serve error responses / health degraded
        # In production, you'd likely want to fail hard here.

    yield

    # --- Shutdown: cleanup resources ---
    if redis_conn is not None:
        try:
            await redis_conn.aclose()
            logger.info("Redis connection closed.")
        except Exception as exc:
            logger.warning("Error closing Redis connection: %s", exc)

    if db_pool is not None:
        try:
            await db_pool.close()
            logger.info("Database connection pool closed.")
        except Exception as exc:
            logger.warning("Error closing database pool: %s", exc)

    clear_connections()


def create_app(settings: Settings | None = None) -> FastAPI:
    """Create and configure the FastAPI application.

    Args:
        settings: Optional settings override (useful for testing).

    Returns:
        Configured FastAPI application instance.
    """
    if settings is None:
        settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        docs_url=f"{settings.api_v1_prefix}/docs",
        redoc_url=f"{settings.api_v1_prefix}/redoc",
        openapi_url=f"{settings.api_v1_prefix}/openapi.json",
        lifespan=_lifespan,
    )

    # --- Middleware Stack ---
    # Middleware is applied in reverse order (last added = first to run).
    # Desired execution order: Rate Limiting → Auth → Audit
    # So we add: Audit first (innermost), then CORS (outermost after rate limit).

    # Audit middleware (BaseHTTPMiddleware — innermost of our custom stack)
    from platform_api.middleware.audit import AuditMiddleware, get_audit_service

    # We use a lazy audit service that defers to the configured singleton.
    # The middleware is added here but the actual service is wired in lifespan.
    app.add_middleware(AuditMiddleware, audit_service=_LazyAuditService())

    # CORS Middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Note: Rate limiting is implemented as a FastAPI Depends() in route handlers
    # (via RateLimiter.check()), not as ASGI middleware. The auth middleware is also
    # implemented as Depends(get_current_user). This allows fine-grained control
    # per endpoint rather than blanket middleware on all requests.

    # --- Global Exception Handlers ---
    app.add_exception_handler(PlatformAPIError, _platform_error_handler)  # type: ignore[arg-type]
    app.add_exception_handler(Exception, _global_exception_handler)

    # --- Router Registration ---
    from platform_api.routers import (
        admin,
        auth,
        batch,
        callbacks,
        credits,
        generation,
        health,
        key_pool,
        licenses,
        plans,
        profiles,
        prompts,
        settings_router,
        stats,
        users,
        ws,
    )

    # --- Wire ALL router dependencies ---
    from platform_api.wire_dependencies import wire_all_dependencies
    wire_all_dependencies(app)

    # Health check at root (no auth, no API prefix).
    app.include_router(health.router)

    app.include_router(auth.router, prefix=settings.api_v1_prefix)
    app.include_router(users.router, prefix=settings.api_v1_prefix)
    app.include_router(licenses.router, prefix=settings.api_v1_prefix)
    app.include_router(plans.router, prefix=settings.api_v1_prefix)
    app.include_router(credits.router, prefix=settings.api_v1_prefix)
    app.include_router(profiles.router, prefix=settings.api_v1_prefix)
    app.include_router(prompts.router, prefix=settings.api_v1_prefix)
    app.include_router(generation.router, prefix=settings.api_v1_prefix)
    app.include_router(batch.router, prefix=settings.api_v1_prefix)
    app.include_router(callbacks.router, prefix=settings.api_v1_prefix)
    app.include_router(ws.router, prefix=settings.api_v1_prefix)
    app.include_router(settings_router.router, prefix=settings.api_v1_prefix)
    app.include_router(stats.router, prefix=settings.api_v1_prefix)
    app.include_router(admin.router, prefix=settings.api_v1_prefix)
    app.include_router(key_pool.router, prefix=settings.api_v1_prefix)

    from platform_api.routers import channel_setup
    app.include_router(channel_setup.router, prefix=settings.api_v1_prefix)

    from platform_api.routers import channel_prompts
    app.include_router(channel_prompts.router, prefix=settings.api_v1_prefix)

    return app


# ---------------------------------------------------------------------------
# Lazy audit service proxy (allows adding middleware before lifespan runs)
# ---------------------------------------------------------------------------


class _LazyAuditService:
    """Proxy that delegates to the configured audit service singleton.

    The AuditMiddleware requires an audit_service at construction time,
    but the actual service isn't configured until the lifespan runs.
    This proxy defers the call so that audit logging works once the
    lifespan has initialized, and silently no-ops before that.
    """

    async def log_event(self, **kwargs) -> None:
        """Forward to the real audit service if configured."""
        from platform_api.middleware.audit import get_audit_service

        service = get_audit_service()
        if service is not None:
            await service.log_event(**kwargs)


# Default app instance used by uvicorn (e.g., `uvicorn platform_api.main:app`)
app = create_app()
