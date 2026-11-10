"""Local preview entrypoint for the Creator Program worktree.

The shared local database is ahead of this branch with an unmerged migration
from the Studio worktree, so Alembic cannot resolve this branch's head. This
entrypoint skips the startup migration step only for local UI previews.

Run:
    python -m uvicorn preview_api:app --app-dir scripts/creator-program \
        --host 127.0.0.1 --port 8101 \
        --env-file G:/Developments/Projects/Camxora/platform_api/.env

Never use this for sandbox or production.
"""

from __future__ import annotations

import platform_api.migrations.runner as migration_runner


async def _skip_pending_migrations() -> None:
    return None


migration_runner.run_pending_migrations = _skip_pending_migrations

from platform_api.main import app  # noqa: E402,F401
