"""Run Alembic migrations programmatically on API startup."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from alembic import command
from alembic.config import Config

from platform_api.config import get_settings

logger = logging.getLogger(__name__)


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
    """Apply any pending Alembic revisions to the configured database."""
    logger.info("Running database migrations (alembic upgrade heads)...")
    await asyncio.to_thread(_upgrade_head_sync)
    logger.info("Database migrations up to date.")
