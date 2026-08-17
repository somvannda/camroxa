"""Run Alembic migrations programmatically on API startup."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Mapping

import asyncpg
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory

from platform_api.config import get_settings

logger = logging.getLogger(__name__)

# Arbitrary fixed key for the cross-process migration advisory lock (see
# `run_pending_migrations` docstring). Any stable int64 works — it just needs
# to be the same constant everywhere this runs.
_MIGRATION_ADVISORY_LOCK_KEY = 782550187
_MIGRATION_TIMEOUT_SECONDS = 180

RevisionDown = str | tuple[str, ...] | None
RevisionMap = Mapping[str, RevisionDown]


def _parents(down: RevisionDown) -> tuple[str, ...]:
    if down is None:
        return ()
    if isinstance(down, tuple):
        return down
    return (down,)


def lineage(down_by_rev: RevisionMap, rev_id: str) -> set[str]:
    """Return rev_id plus every ancestor, including merge parents."""
    found: set[str] = set()
    stack = [rev_id]
    while stack:
        current = stack.pop()
        if current in found:
            continue
        found.add(current)
        stack.extend(_parents(down_by_rev.get(current)))
    return found


def descendants(down_by_rev: RevisionMap, root: str) -> set[str]:
    """Return root plus every revision that eventually depends on it."""
    found = {root}
    changed = True
    while changed:
        changed = False
        for rev, down in down_by_rev.items():
            if rev in found:
                continue
            if any(parent in found for parent in _parents(down)):
                found.add(rev)
                changed = True
    return found


def leftover_fork_revisions(down_by_rev: RevisionMap, current_revs: set[str]) -> set[str]:
    """Find unapplied sibling branches of an already-applied revision.

    This is the leftover-file case: two revisions share the same parent (for
    example two different ``084_*`` files both revise ``083``), the database is
    already on one child, and ``alembic upgrade heads`` would otherwise try to
    apply the other child forever.
    """
    if not current_revs:
        return set()

    applied: set[str] = set()
    for rev in current_revs:
        applied |= lineage(down_by_rev, rev)

    children_by_parent: dict[str, list[str]] = {}
    for rev, down in down_by_rev.items():
        if down is None or isinstance(down, tuple):
            continue
        children_by_parent.setdefault(down, []).append(rev)

    leftover: set[str] = set()
    for children in children_by_parent.values():
        if len(children) < 2:
            continue
        if not any(child in applied for child in children):
            continue
        for child in children:
            if child not in applied:
                leftover |= descendants(down_by_rev, child)
    return leftover


def upgrade_revision_target(
    down_by_rev: RevisionMap,
    heads: list[str],
    current_revs: set[str],
) -> str:
    """Choose an Alembic upgrade target that ignores leftover sibling heads."""
    leftover = leftover_fork_revisions(down_by_rev, current_revs)
    usable = [head for head in heads if head not in leftover]
    if leftover:
        logger.warning(
            "Skipping leftover Alembic head(s) that fork an already-applied "
            "revision: %s. Remove those files from platform_api/migrations/"
            "versions/ on the server so they cannot hang startup.",
            ", ".join(sorted(leftover)),
        )
    if len(usable) == 1:
        return usable[0]
    if not usable:
        raise RuntimeError(
            "All Alembic heads look like leftover forks of an already-applied "
            f"revision. leftover={sorted(leftover)} current={sorted(current_revs)}"
        )
    return "heads"


def _revision_map(script: ScriptDirectory) -> dict[str, RevisionDown]:
    return {rev.revision: rev.down_revision for rev in script.walk_revisions()}


def _upgrade_head_sync(current_revs: set[str] | None = None) -> None:
    platform_api_root = Path(__file__).resolve().parents[1]
    alembic_ini = platform_api_root / "alembic.ini"
    if not alembic_ini.is_file():
        logger.warning("Alembic config not found at %s; skipping migrations.", alembic_ini)
        return

    cfg = Config(str(alembic_ini))
    cfg.set_main_option("sqlalchemy.url", get_settings().database_url)
    script = ScriptDirectory.from_config(cfg)
    target = upgrade_revision_target(
        _revision_map(script),
        list(script.get_heads()),
        current_revs or set(),
    )
    logger.info("Running database migrations (alembic upgrade %s)...", target)
    command.upgrade(cfg, target)


async def _current_revisions(conn: asyncpg.Connection) -> set[str]:
    try:
        rows = await conn.fetch("SELECT version_num FROM alembic_version")
    except asyncpg.exceptions.UndefinedTableError:
        return set()
    return {str(row["version_num"]) for row in rows if row["version_num"]}


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

    Leftover revision files that fork an already-applied parent (two different
    ``084_*`` files after ``083``) are skipped so startup cannot hang trying to
    recreate schema that already exists. The upgrade itself is also time-boxed
    so a stuck migration fails the worker instead of serving
    ``Database pool not initialized`` forever.
    """
    dsn = get_settings().database_url.replace("postgresql+asyncpg://", "postgresql://", 1)
    lock_conn = await asyncpg.connect(dsn)
    try:
        logger.info("Waiting for migration advisory lock (coordinates multiple API workers)...")
        await lock_conn.execute("SELECT pg_advisory_lock($1)", _MIGRATION_ADVISORY_LOCK_KEY)
        current_revs = await _current_revisions(lock_conn)
        await asyncio.wait_for(
            asyncio.to_thread(_upgrade_head_sync, current_revs),
            timeout=_MIGRATION_TIMEOUT_SECONDS,
        )
        logger.info("Database migrations up to date.")
    except TimeoutError as exc:
        raise RuntimeError(
            f"Alembic upgrade exceeded {_MIGRATION_TIMEOUT_SECONDS}s. "
            "A leftover or blocked migration is likely hanging startup."
        ) from exc
    finally:
        try:
            await lock_conn.execute("SELECT pg_advisory_unlock($1)", _MIGRATION_ADVISORY_LOCK_KEY)
        finally:
            await lock_conn.close()
