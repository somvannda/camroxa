"""Health check router.

Exposes GET /health (no authentication required) that reports service status,
database connectivity, external service reachability, uptime, and timestamp.

Requirements: 18.1, 18.2, 18.3
"""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime, timezone
from typing import Any, Protocol

from fastapi import APIRouter, Depends

from platform_api.config import Settings, environment_display_label, get_settings
from platform_api.dependencies import get_db_pool as get_app_db_pool

logger = logging.getLogger(__name__)

# Module-level start time for uptime calculation.
_START_TIME: float = time.time()

# Health check timeout per service (seconds).
_HEALTH_CHECK_TIMEOUT = 3.0

router = APIRouter(tags=["health"])


# ---------------------------------------------------------------------------
# Protocols for injectable dependencies (database pool, external clients)
# ---------------------------------------------------------------------------


class DatabasePool(Protocol):
    """Protocol for an async database pool used in health checks."""

    async def execute(self, query: str) -> Any: ...


def get_db_pool() -> DatabasePool:
    """Dependency providing the real database pool for health checks."""
    return get_app_db_pool()


# ---------------------------------------------------------------------------
# Individual service health checks
# ---------------------------------------------------------------------------


async def _check_database(pool: DatabasePool) -> bool:
    """Check database connectivity by running SELECT 1 with a timeout."""
    try:
        await asyncio.wait_for(
            pool.execute("SELECT 1"),
            timeout=_HEALTH_CHECK_TIMEOUT,
        )
        return True
    except Exception:
        logger.debug("Health check: database unreachable", exc_info=True)
        return False


async def _check_provider_pool(provider: str) -> dict[str, Any]:
    """Return key pool status for a provider (no env fallbacks)."""
    from platform_api.dependencies import get_key_pool_service

    try:
        key_pool = get_key_pool_service()
    except Exception:
        logger.debug("Health check: key pool unavailable for %s", provider, exc_info=True)
        return {"provider": provider, "available": False, "reason": "key_pool_unavailable"}
    if key_pool is None:
        return {"provider": provider, "available": False, "reason": "key_pool_unavailable"}

    try:
        status = await key_pool.get_pool_status(provider)
    except Exception as exc:
        logger.debug("Health check: key pool status error for %s", provider, exc_info=True)
        return {"provider": provider, "available": False, "reason": f"status_error:{type(exc).__name__}"}

    active = int(status.get("active_keys", 0) or 0)
    return {
        "provider": provider,
        "available": active > 0,
        "pool": status,
    }


async def _check_suno() -> bool:
    result = await _check_provider_pool("suno")
    return bool(result.get("available", False))


async def _check_fal() -> bool:
    result = await _check_provider_pool("fal")
    return bool(result.get("available", False))


async def _check_slai() -> bool:
    result = await _check_provider_pool("slai")
    return bool(result.get("available", False))


# ---------------------------------------------------------------------------
# Health endpoint
# ---------------------------------------------------------------------------


@router.get("/health")
async def health_check(
    settings: Settings = Depends(get_settings),
    db_pool: DatabasePool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Return service health status.

    Checks database, Suno, Fal AI, and SLAI concurrently with 3-second
    timeouts per service. Returns overall status:
    - "healthy": all services reachable
    - "degraded": database up but one or more external services unreachable
    - "unhealthy": database unreachable

    No authentication required.
    """
    (
        db_result,
        suno_ok,
        fal_ok,
        slai_ok,
        suno_pool,
        fal_pool,
        slai_pool,
        deepseek_pool,
        openai_pool,
        cala_pool,
        kie_pool,
    ) = await asyncio.gather(
        _check_database(db_pool),
        _check_suno(),
        _check_fal(),
        _check_slai(),
        _check_provider_pool("suno"),
        _check_provider_pool("fal"),
        _check_provider_pool("slai"),
        _check_provider_pool("deepseek"),
        _check_provider_pool("openai"),
        _check_provider_pool("cala"),
        _check_provider_pool("kie"),
    )

    # Determine overall status.
    if not db_result:
        status = "unhealthy"
    elif not (suno_ok and fal_ok and slai_ok):
        status = "degraded"
    else:
        status = "healthy"

    uptime_seconds = int(time.time() - _START_TIME)

    return {
        "status": status,
        "environment": (settings.environment or "").strip().lower() or "unknown",
        "environment_label": environment_display_label(settings),
        "database": db_result,
        "services": {
            "suno": suno_ok,
            "fal": fal_ok,
            "slai": slai_ok,
            "deepseek": bool(deepseek_pool.get("available", False)),
            "openai": bool(openai_pool.get("available", False)),
            "cala": bool(cala_pool.get("available", False)),
            "kie": bool(kie_pool.get("available", False)),
        },
        "service_pools": {
            # Public endpoint: expose reachability only, not per-provider key
            # counts (total/active/exhausted), which are infrastructure detail.
            name: {
                "available": bool(pool.get("available", False)),
                "health_indicator": pool.get("health_indicator", "unknown"),
            }
            for name, pool in (
                ("suno", suno_pool),
                ("fal", fal_pool),
                ("slai", slai_pool),
                ("deepseek", deepseek_pool),
                ("openai", openai_pool),
                ("cala", cala_pool),
                ("kie", kie_pool),
            )
        },
        "uptime_seconds": uptime_seconds,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
