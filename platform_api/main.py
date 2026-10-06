"""FastAPI application factory for the Platform API."""

import asyncio
import logging
import os
import sys
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

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

    headers: dict[str, str] = {}
    retry_after = getattr(exc, "retry_after", None)
    if retry_after is not None:
        try:
            headers["Retry-After"] = str(int(retry_after))
        except (TypeError, ValueError):
            pass

    return JSONResponse(status_code=exc.status_code, content=content, headers=headers)


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
        get_notification_service,
        get_rate_limit_config_repo,
        get_usage_tracking_repo,
        get_user_repo,
        set_db_pool,
        set_redis,
    )
    from platform_api.middleware.auth import configure_auth_dependencies
    from platform_api.middleware.audit import configure_audit_middleware
    from platform_api.middleware.rate_limit import configure_rate_limiter
    from platform_api.logging_setup import configure_api_logging
    from platform_api.services.slai_image_config_service import load_slai_image_provider_config
    from platform_api.routers.ws import configure_ws_dependencies

    settings = get_settings()
    db_pool = None
    redis_conn = None
    pipeline_stuck_task: asyncio.Task | None = None
    subscription_maintenance_task: asyncio.Task | None = None
    b2_backfill_task: asyncio.Task | None = None

    configure_api_logging()
    logger.info("API logging ready — batch/music, image, and credit progress appear in this terminal.")
    logger.info("=" * 60)
    logger.info("PLATFORM API STARTUP DIAGNOSTICS")
    logger.info("=" * 60)
    logger.info("Working directory: %s", os.getcwd())
    logger.info("Environment: %s", settings.environment)
    logger.info("Database URL: %s", settings.database_url.replace(settings.database_url.split("@")[0].split("//")[1] if "@" in settings.database_url else "", "***"))
    logger.info("Redis URL: %s", settings.redis_url)
    logger.info("Debug mode: %s", settings.debug)
    logger.info("CORS origins: %s", settings.cors_origins)
    logger.info("Encryption master key set: %s", "YES" if settings.encryption_master_key else "NO")
    logger.info("=" * 60)

    from platform_api.config import validate_production_settings

    validate_production_settings(settings)

    try:
        from platform_api.migrations.runner import run_pending_migrations

        await run_pending_migrations()

        # --- Create asyncpg connection pool ---
        import asyncpg

        # Parse the database URL for asyncpg (strip the driver prefix if present)
        dsn = settings.database_url
        if dsn.startswith("postgresql+asyncpg://"):
            dsn = dsn.replace("postgresql+asyncpg://", "postgresql://", 1)

        db_pool = await asyncpg.create_pool(dsn, min_size=4, max_size=8)
        set_db_pool(db_pool)
        logger.info("Database connection pool created.")

        from platform_api.dependencies import get_settings_repo

        await load_slai_image_provider_config(get_settings_repo())
        logger.info("SLAI image provider configuration loaded from system settings.")

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
            plan_repo=get_license_repo(),
            usage_repo=get_usage_tracking_repo(),
        )
        logger.info("Auth middleware configured.")

        # --- Configure rate limiter ---
        configure_rate_limiter(
            redis=redis_conn,
            config_repo=get_rate_limit_config_repo(),
        )
        logger.info("Rate limiter configured.")

        from platform_api.middleware.abuse_detection import configure_abuse_detection

        configure_abuse_detection(redis_conn)
        logger.info("Signup/generation abuse detection configured.")

        from platform_api.services.generation_freeze import configure_generation_freeze

        configure_generation_freeze(redis_conn)
        logger.info("Music-web generation freeze configured.")

        # --- Configure audit middleware ---
        configure_audit_middleware(audit_service=get_audit_service())
        logger.info("Audit middleware configured.")

        # --- Configure WebSocket dependencies ---
        configure_ws_dependencies(
            auth_service=get_auth_service(),
            notification_service=get_notification_service(),
        )
        logger.info("WebSocket notification dependencies configured.")

        class _DbAdminProvider:
            """Resolves admin user IDs for WebSocket alert fan-out (abuse + pipeline-stuck)."""

            def __init__(self, pool: Any) -> None:
                self._pool = pool

            async def get_admin_user_ids(self) -> list[str]:
                rows = await self._pool.fetch(
                    "SELECT id::text AS id FROM users WHERE role = 'admin'"
                )
                return [str(r["id"]) for r in rows]

        # --- Abuse alerts (Phase 3) ---
        try:
            from platform_api.services.abuse_alert_service import (
                AbuseAlertService,
                set_abuse_alert_service,
            )

            set_abuse_alert_service(
                AbuseAlertService(
                    redis=redis_conn,
                    notification_service=get_notification_service(),
                    admin_provider=_DbAdminProvider(db_pool),
                    absorb_alert_threshold=settings.abuse_absorb_alert_threshold,
                    polish_probe_threshold=settings.abuse_polish_probe_threshold,
                    redeem_burst_threshold=settings.abuse_redeem_burst_threshold,
                    redeem_burst_window_seconds=settings.abuse_redeem_burst_window_seconds,
                )
            )
            logger.info("Abuse alert service configured.")
        except Exception as exc:
            logger.warning("Abuse alert service not configured (non-fatal): %s", exc)

        try:
            from platform_api.services.telegram_ops_alert_service import (
                install_telegram_ops_hooks,
            )

            install_telegram_ops_hooks()
            logger.info("Telegram ops activity feed hooks installed.")
        except Exception as exc:
            logger.warning("Telegram ops hooks not installed (non-fatal): %s", exc)

        # --- Pipeline stuck-batch housekeeping (PLATFORM_WORKERS_REQUIREMENTS.md §8) ---
        # No dedicated `platform_worker` process exists yet, so this runs as an
        # in-process scheduled loop (same stopgap pattern as other periodic sweeps
        # in this codebase) until that infra lands.
        try:
            from platform_api.dependencies import get_batch_repo
            from platform_api.services.pipeline_stuck_alert_service import (
                PipelineStuckAlertService,
                set_pipeline_stuck_alert_service,
            )

            pipeline_stuck_service = PipelineStuckAlertService(
                batch_repo=get_batch_repo(),
                redis=redis_conn,
                notification_service=get_notification_service(),
                admin_provider=_DbAdminProvider(db_pool),
                stuck_threshold_seconds=settings.pipeline_stuck_threshold_seconds,
                alert_cooldown_seconds=settings.pipeline_stuck_alert_cooldown_seconds,
            )
            set_pipeline_stuck_alert_service(pipeline_stuck_service)

            async def _pipeline_stuck_alert_loop() -> None:
                while True:
                    await asyncio.sleep(settings.pipeline_stuck_scan_interval_seconds)
                    try:
                        await pipeline_stuck_service.scan_and_alert()
                    except Exception as exc:
                        logger.warning("Pipeline stuck-batch scan iteration failed: %s", exc)

            pipeline_stuck_task = asyncio.create_task(
                _pipeline_stuck_alert_loop(), name="pipeline-stuck-alert-scan"
            )
            logger.info(
                "Pipeline stuck-batch alert service configured (threshold=%ds, scan every %ds).",
                settings.pipeline_stuck_threshold_seconds,
                settings.pipeline_stuck_scan_interval_seconds,
            )
        except Exception as exc:
            logger.warning("Pipeline stuck-batch alert service not configured (non-fatal): %s", exc)

        # --- Web music subscription period maintenance ---
        try:
            from platform_api.db.asyncpg_adapter import wrap_pool
            from platform_api.services.v2.subscription_service import SubscriptionService

            async def _run_subscription_maintenance() -> None:
                # SubscriptionService speaks fetch_one/fetch_all, so hand it the
                # adapter (routers use wrap_pool too) instead of the raw pool.
                handled = await SubscriptionService(wrap_pool(db_pool)).process_due_subscriptions()
                if handled:
                    logger.info(
                        "Web music subscription maintenance handled %s row(s)",
                        handled,
                    )

            async def _subscription_maintenance_loop() -> None:
                while True:
                    try:
                        await _run_subscription_maintenance()
                    except Exception as exc:
                        logger.warning("Web music subscription maintenance failed: %s", exc)
                    await asyncio.sleep(900)

            subscription_maintenance_task = asyncio.create_task(
                _subscription_maintenance_loop(),
                name="web-music-subscription-maintenance",
            )
            logger.info("Web music subscription maintenance loop started (every 15 minutes).")
        except Exception as exc:
            logger.warning("Web music subscription maintenance not configured (non-fatal): %s", exc)

        # --- Durable B2 backfill sweep ---
        # Every 15 minutes: reprocess stuck/failed upload jobs (with provider
        # Recovery Audio), backfill studio MP3s missing from B2, and mark jobs
        # permanently failed after repeated attempts. Alerts ops on failures.
        try:
            from platform_api.services.streaming_upload_service import StreamingUploadService

            b2_backfill_interval = int(
                getattr(settings, "b2_backfill_scan_interval_seconds", 900) or 900
            )

            async def _b2_backfill_loop() -> None:
                while True:
                    await asyncio.sleep(max(60, b2_backfill_interval))
                    try:
                        # Single-winner across uvicorn workers: the loop starts in
                        # every worker, but only one claims each interval so the
                        # sweep (and its alert) does not run 4x.
                        stats = await StreamingUploadService(db_pool).run_backfill_sweep_periodic(
                            b2_backfill_interval
                        )
                        if stats and any(
                            stats.get(key)
                            for key in (
                                "jobs_failed",
                                "backfill_failed",
                                "permanent",
                                "backfilled",
                            )
                        ):
                            logger.info("B2 backfill sweep: %s", stats)
                    except Exception as exc:
                        logger.warning("B2 backfill sweep iteration failed: %s", exc)

            b2_backfill_task = asyncio.create_task(
                _b2_backfill_loop(), name="b2-backfill-sweep"
            )
            logger.info(
                "B2 backfill sweep loop started (every %ss).", b2_backfill_interval
            )
        except Exception as exc:
            logger.warning("B2 backfill sweep not configured (non-fatal): %s", exc)

        # --- Streaming upload auto-retry (B2 capture assurance) ---
        try:
            from platform_api.services import streaming_upload_service as _streaming_svc

            if not getattr(_streaming_svc, "_AUTO_RETRY_ENABLED", True):
                logger.info("Streaming upload auto-retry is disabled by env.")
            else:
                auto_retry_task = asyncio.create_task(
                    _streaming_svc.run_streaming_auto_retry_loop(db_pool),
                    name="streaming-auto-retry",
                )
                logger.info("Streaming upload auto-retry loop started.")
        except Exception as exc:
            logger.warning("Streaming upload auto-retry loop not started (non-fatal): %s", exc)

        # --- Streaming capture health report (Telegram, hourly) ---
        try:
            from platform_api.services import streaming_health_report as _stream_health

            if not getattr(_stream_health, "_HEALTH_REPORT_ENABLED", True):
                logger.info("Streaming capture health report is disabled by env.")
            else:
                asyncio.create_task(
                    _stream_health.run_streaming_health_report_loop(db_pool),
                    name="streaming-health-report",
                )
                logger.info("Streaming capture health report loop started.")
        except Exception as exc:
            logger.warning(
                "Streaming capture health report loop not started (non-fatal): %s",
                exc,
            )

        # --- Credit-grant invariant check (Telegram, daily) ---
        # Flags stacked grant lots / multiple period grants per day — the class of
        # bug that minted a period grant every day. Silent unless a violation.
        try:
            from platform_api.services import credit_invariants as _credit_inv

            if not getattr(_credit_inv, "_ENABLED", True):
                logger.info("Credit invariant check is disabled by env.")
            else:
                asyncio.create_task(
                    _credit_inv.run_credit_invariant_loop(db_pool),
                    name="credit-invariant-check",
                )
                logger.info("Credit invariant check loop started.")
        except Exception as exc:
            logger.warning("Credit invariant check not started (non-fatal): %s", exc)

        # --- Proactive credit grant maintenance (period/daily minting off GET) ---
        # Runs at startup + hourly so wallet balances are correct without a read
        # mutating them (GET /me/credits is read-only). Idempotent per period.
        try:
            from platform_api.services import grant_maintenance as _grant_maint

            if not getattr(_grant_maint, "_ENABLED", True):
                logger.info("Credit grant maintenance is disabled by env.")
            else:
                asyncio.create_task(
                    _grant_maint.run_grant_maintenance_loop(db_pool),
                    name="credit-grant-maintenance",
                )
                logger.info("Credit grant maintenance loop started.")
        except Exception as exc:
            logger.warning("Credit grant maintenance not started (non-fatal): %s", exc)

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

        logger.info("Platform API ready on port 8000 — idle until requests or batch generation.")

    except Exception as exc:
        logger.error("Failed to initialize application resources: %s", exc)
        # Still yield so the app can serve error responses / health degraded
        # In production, you'd likely want to fail hard here.

    yield

    # --- Shutdown: cleanup resources ---
    if pipeline_stuck_task is not None:
        pipeline_stuck_task.cancel()
        try:
            await pipeline_stuck_task
        except asyncio.CancelledError:
            pass
        except Exception as exc:
            logger.warning("Error stopping pipeline stuck-alert task: %s", exc)

    if subscription_maintenance_task is not None:
        subscription_maintenance_task.cancel()
        try:
            await subscription_maintenance_task
        except asyncio.CancelledError:
            pass
        except Exception as exc:
            logger.warning("Error stopping subscription maintenance task: %s", exc)

    if b2_backfill_task is not None:
        b2_backfill_task.cancel()
        try:
            await b2_backfill_task
        except asyncio.CancelledError:
            pass
        except Exception as exc:
            logger.warning("Error stopping B2 backfill task: %s", exc)

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

    from platform_api.config import validate_production_settings

    validate_production_settings(settings)

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

    from platform_api.middleware.request_log import RequestLogMiddleware

    app.add_middleware(RequestLogMiddleware)

    from platform_api.middleware.geo_access import MusicWebGeoMiddleware

    app.add_middleware(MusicWebGeoMiddleware)

    # Last added = first to run: rewrite /api/v1/v2 → /api/v2 before routing.
    from platform_api.middleware.legacy_api_paths import LegacyNestedV2PathMiddleware

    app.add_middleware(LegacyNestedV2PathMiddleware)

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
        admin_invitations,
        admin_pipeline,
        blog_posts,
        admin_content_pools,
        admin_image_sample_packs,
        auth,
        batch,
        billing,
        callbacks,
        control_panel,
        content_pools,
        credits,
        generation,
        health,
        image_jobs,
        image_sample_packs,
        key_pool,
        licenses,
        media,
        music_downloads,
        music_history,
        plans,
        progress,
        profiles,
        prompts,
        redeem_codes,
        settings_router,
        stats,
        youtube,
        users,
        ws,
    )

    # --- Wire ALL router dependencies ---
    from platform_api.wire_dependencies import wire_all_dependencies
    wire_all_dependencies(app)

    from platform_api.routers import profile_video_templates
    from platform_api.routers import client_logs
    from platform_api.routers import (
        admin_music_languages,
        music_languages,
        suno_blocklist,
        suno_blocklist_admin,
    )
    from platform_api.routers import channel_setup
    from platform_api.routers import channel_prompts
    from platform_api.routers import ai_routing
    from platform_api.routers import marketplace
    from platform_api.routers import (
        public_desktop,
        streaming_public,
        streaming_admin,
        streaming_library,
    )
    from platform_api.routers import web_music, web_music_licenses
    from platform_api.routers import v2_subscriptions, v2_credits, v2_topups, webhooks_cutluy
    from platform_api.routers import v3_billing

    v1 = settings.api_v1_prefix
    v2 = settings.api_v2_prefix
    v3 = settings.api_v3_prefix

    def _mount(router, *prefixes: str) -> None:
        for prefix in prefixes:
            app.include_router(router, prefix=prefix)

    # Health: root probes + same-origin under v1/v3 (admin /health is SPA HTML).
    app.include_router(health.router)
    _mount(health.router, v1, v3)

    # Former v1 surface — dual-mounted on /api/v1 (temporary) and /api/v3 (canonical).
    _core = (
        auth.router,
        billing.router,
        users.router,
        licenses.router,
        plans.router,
        credits.router,
        profiles.router,
        profile_video_templates.router,
        prompts.router,
        redeem_codes.router,
        generation.router,
        batch.router,
        content_pools.router,
        callbacks.router,
        control_panel.router,
        ws.router,
        settings_router.router,
        stats.router,
        progress.router,
        youtube.router,
        admin.router,
        admin_pipeline.router,
        admin_invitations.router,
        blog_posts.router,
        admin_content_pools.router,
        client_logs.router,
        key_pool.router,
        media.router,
        music_history.router,
        music_languages.router,
        admin_music_languages.router,
        suno_blocklist.router,
        suno_blocklist_admin.router,
        music_downloads.router,
        image_jobs.router,
        image_sample_packs.router,
        admin_image_sample_packs.router,
        channel_setup.router,
        channel_prompts.router,
        ai_routing.router,
        marketplace.router,
        public_desktop.router,
        streaming_public.router,
        streaming_admin.router,
        streaming_library.router,
        web_music.router,
        web_music_licenses.router,
        webhooks_cutluy.router,
    )
    for router in _core:
        app.include_router(router, prefix=v1)

    # CutLuy billing: temporary /api/v2 + canonical /api/v3 (resource prefixes).
    # On v3, mount these *before* the dual-mounted v1 credits router so
    # /credits/balance|history prefer the CutLuy ledger handlers.
    _cutluy_billing = (
        v2_subscriptions.router,
        v2_credits.router,
        v2_topups.router,
    )
    for router in _cutluy_billing:
        app.include_router(router, prefix=v2)
        app.include_router(router, prefix=v3)

    for router in _core:
        app.include_router(router, prefix=v3)

    # Unified wallet (v3-only). Registered after core so unique paths
    # (/me/credits, /billing/quote|charge|refund, admin grants) are available;
    # overlapping /plans/public and /credits/pricing keep the earlier core handlers.
    app.include_router(v3_billing.docs_router, prefix=v3)
    app.include_router(v3_billing.router, prefix=v3)

    @app.get(f"{v3}/openapi.json", include_in_schema=False)
    async def v3_openapi() -> dict:
        spec = app.openapi()
        paths = {
            path: item
            for path, item in spec.get("paths", {}).items()
            if str(path).startswith(v3)
        }
        return {
            **spec,
            "info": {**spec.get("info", {}), "title": "Credits-only API v3"},
            "paths": paths,
        }

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
