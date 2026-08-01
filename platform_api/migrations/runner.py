"""Run Alembic migrations programmatically on API startup."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

import asyncpg
from alembic import command
from alembic.config import Config

from platform_api.config import get_settings

logger = logging.getLogger(__name__)

# Arbitrary fixed key for the cross-process migration advisory lock (see
# `run_pending_migrations` docstring). Any stable int64 works — it just needs
# to be the same constant everywhere this runs.
_MIGRATION_ADVISORY_LOCK_KEY = 782550187


def _upgrade_head_sync() -> None:
    platform_api_root = Path(__file__).resolve().parents[1]
    alembic_ini = platform_api_root / "alembic.ini"
    if not alembic_ini.is_file():
        logger.warning("Alembic config not found at %s; skipping migrations.", alembic_ini)
        return

    cfg = Config(str(alembic_ini))
    cfg.set_main_option("sqlalchemy.url", get_settings().database_url)
    # This repository currently has multiple Alembic heads, so startup must
    # advance all heads instead of assuming a single branch tip.
    command.upgrade(cfg, "heads")


async def run_pending_migrations() -> None:
    """Apply any pending Alembic revisions to the configured database.

    With `API_WORKERS` > 1, every Uvicorn worker process runs this on its own
    startup, independently and with no coordination between them. Without a
    lock, two workers can end up running `alembic upgrade heads` concurrently:
    the DDL from one worker's migration can invalidate cached query plans on
    connections the *other* worker (or this same worker's own request-serving
    pool) already has open, surfacing as a burst of unrelated 500s across
    almost every endpoint for as long as those poisoned connections stay in
    rotation — not a one-off blip, but sustained until the pool cycles or the
    process restarts. A Postgres session advisory lock serializes this: only
    one worker actually runs the upgrade at a time, others block until it
    finishes and then run it themselves as a fast no-op (DB already at head).
    """
    dsn = get_settings().database_url.replace("postgresql+asyncpg://", "postgresql://", 1)
    lock_conn = await asyncpg.connect(dsn)
    try:
        logger.info("Waiting for migration advisory lock (coordinates multiple API workers)...")
        await lock_conn.execute("SELECT pg_advisory_lock($1)", _MIGRATION_ADVISORY_LOCK_KEY)
        logger.info("Running database migrations (alembic upgrade heads)...")
        await asyncio.to_thread(_upgrade_head_sync)
        logger.info("Database migrations up to date.")
    finally:
        try:
            await lock_conn.execute("SELECT pg_advisory_unlock($1)", _MIGRATION_ADVISORY_LOCK_KEY)
        finally:
            await lock_conn.close()
