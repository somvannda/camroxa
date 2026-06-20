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

import httpx
from fastapi import APIRouter, Depends

from platform_api.config import Settings, get_settings

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


# ---------------------------------------------------------------------------
# Default dependency stubs (replaced by real implementations in production)
# ---------------------------------------------------------------------------


class _StubDatabasePool:
    """Stub database pool that always reports connectivity failure.

    In production, this is replaced with a real asyncpg pool dependency.
    """

    async def execute(self, query: str) -> Any:
        raise ConnectionError("No database pool configured")


_stub_db_pool = _StubDatabasePool()


def get_db_pool() -> DatabasePool:
    """Dependency providing the database pool for health checks."""
    return _stub_db_pool


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


async def _check_suno(settings: Settings) -> bool:
    """Check Suno API reachability with a lightweight request."""
    if not settings.suno_api_base_url:
        return False
    try:
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(_HEALTH_CHECK_TIMEOUT)
        ) as client:
            url = f"{settings.suno_api_base_url.rstrip('/')}/api/v1/generate/credit"
            resp = await client.get(
                url,
                headers={"Authorization": f"Bearer {settings.suno_api_key}"},
            )
            # Any non-5xx response means the service is reachable.
            return resp.status_code < 500
    except Exception:
        logger.debug("Health check: Suno API unreachable", exc_info=True)
        return False


async def _check_fal(settings: Settings) -> bool:
    """Check Fal AI reachability with a lightweight request."""
    if not settings.fal_api_base_url:
        return False
    try:
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(_HEALTH_CHECK_TIMEOUT)
        ) as client:
            # Use a HEAD or GET on the base URL to verify reachability.
            url = settings.fal_api_base_url.rstrip("/")
            resp = await client.get(
                url,
                headers={"Authorization": f"Key {settings.fal_api_key}"},
            )
            return resp.status_code < 500
    except Exception:
        logger.debug("Health check: Fal AI unreachable", exc_info=True)
        return False


async def _check_slai(settings: Settings) -> bool:
    """Check SLAI reachability with a lightweight request."""
    if not settings.slai_api_base_url:
        return False
    try:
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(_HEALTH_CHECK_TIMEOUT)
        ) as client:
            url = settings.slai_api_base_url.rstrip("/")
            resp = await client.get(
                url,
                headers={"Authorization": f"Bearer {settings.slai_api_key}"},
            )
            return resp.status_code < 500
    except Exception:
        logger.debug("Health check: SLAI unreachable", exc_info=True)
        return False


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
    # Run all checks concurrently.
    db_result, suno_result, fal_result, slai_result = await asyncio.gather(
        _check_database(db_pool),
        _check_suno(settings),
        _check_fal(settings),
        _check_slai(settings),
    )

    # Determine overall status.
    if not db_result:
        status = "unhealthy"
    elif not (suno_result and fal_result and slai_result):
        status = "degraded"
    else:
        status = "healthy"

    uptime_seconds = int(time.time() - _START_TIME)

    return {
        "status": status,
        "database": db_result,
        "services": {
            "suno": suno_result,
            "fal": fal_result,
            "slai": slai_result,
        },
        "uptime_seconds": uptime_seconds,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
