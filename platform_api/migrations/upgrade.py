"""Alembic CLI entrypoint that runs behind the cross-process advisory lock.

Production had two migration paths: the API startup runner (which takes
`pg_advisory_lock(782550187)`) and deploy scripts that ran `alembic upgrade head`
directly over SSH, bypassing the lock. Only the runner is serialized, so a deploy
and a starting worker could upgrade concurrently — the class of overlap that left
`alembic_version = 178` recorded while its DDL was missing.

Deploy tooling should invoke this module instead of `alembic upgrade head`:

    python -m platform_api.migrations.upgrade

It reuses `run_pending_migrations()` exactly, so both paths share one lock.
"""

from __future__ import annotations

import asyncio
import logging
import sys

from platform_api.migrations.runner import run_pending_migrations

logger = logging.getLogger(__name__)


def main() -> int:
    try:
        asyncio.run(run_pending_migrations())
    except Exception:  # noqa: BLE001 - a failed upgrade must fail the deploy
        logger.exception("Locked migration run failed")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
