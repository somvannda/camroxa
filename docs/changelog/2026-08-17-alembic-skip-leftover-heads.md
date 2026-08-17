# Prevent leftover Alembic 084 files from hanging API startup

## Summary

Sandbox music catalog went empty because a retired `084_provider_balance_events.py` stayed on the server after a later `084_user_products_web_music` chain reached `104`. `tar` syncs overwrite files but never delete leftovers, so `alembic upgrade heads` tried to apply the old sibling branch on every worker start. The database pool never initialized.

## Product impact

**Before:** A leftover migration file could hang all API workers. Music home/explore showed empty placeholders even when published tracks existed.

**After:** Startup ignores leftover sibling heads of an already-applied revision, and full `platform_api` syncs prune revision files that are not in the deploy tarball. A stuck upgrade fails after 180s instead of serving pool-not-initialized 500s forever.

## Technical impact

- `platform_api/migrations/runner.py` chooses a single applied-lineage target when two revisions share a parent and only one is in `alembic_version` history.
- Upgrade is wrapped in `asyncio.wait_for(..., 180)`.
- `sync_platform_api_sandbox.py` / `sync_platform_api_production.py` delete extra `migrations/versions/*.py` after extract (production sync is not run by this change).

## Tests

- `pytest platform_api/tests/test_migrations_runner.py`

## Deploy

File-scoped sandbox hotfix of `runner.py` only. Do not full-sync `platform_api` from this mixed working tree.
