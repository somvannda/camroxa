# One locked migration path

**Date:** 2026-11-05
**Surfaces:** `platform_api`, `scripts/deploy`
**Migration:** none

---

## Problem

Production had **two** ways to upgrade the database:

| Path | Lock |
|---|---|
| API startup — `run_pending_migrations()` on every worker | `pg_advisory_lock(782550187)` |
| Deploy — `camxora-production-remote.sh` ran `alembic upgrade head` over SSH | none |

The advisory lock makes the runner safe against itself, but it cannot protect
against a deploy upgrading at the same time. That is the class of overlap that
most plausibly left `alembic_version = 178` recorded while
`credit_transactions.reason` was still `varchar(100)` — a revision marked
applied whose DDL was missing.

Sixteen deploy scripts also invoke alembic directly (some targeted, at least one
a bare `stamp`), so this was a pattern rather than a one-off.

## Change

- **`platform_api/migrations/upgrade.py`** (new) — CLI entrypoint that calls
  `run_pending_migrations()` unchanged, so it takes the same advisory lock and
  exits non-zero when the upgrade fails.
- **`camxora-production-remote.sh`** — calls
  `platform_api/.venv/bin/python -m platform_api.migrations.upgrade` instead of
  the raw Alembic CLI.

Both paths now serialise on one lock. A deploy that overlaps a booting worker
blocks instead of racing it.

## What this does not fix

- The other 15 scripts that run alembic directly are untouched; `check_deploy_hygiene.py`
  still needs a rule to flag them (follow-up).
- The exact cause of the `178` loss remains unproven — the Nov 3 journal no
  longer contains the startup sequence. This removes a known way for it to
  happen, not the only conceivable one.
- `_SCHEMA_ASSERTIONS` still covers only `credit_transactions.reason`; the
  `credit_wallet_lots` tag constraint should join it (follow-up).

## Files touched

- `platform_api/migrations/upgrade.py` (new)
- `scripts/deploy/camxora-production-remote.sh`
- `platform_api/tests/test_locked_migration_entrypoint.py` (new, 4 tests)

## Tests

- `main()` returns 0 on success and 1 when the upgrade raises;
- the remote script references the locked entrypoint and contains no raw
  `alembic upgrade head`;
- the entrypoint imports the runner's function rather than reimplementing it.

16 tests pass with `test_schema_status.py` and `test_migrations_runner.py`;
`bash -n` clean; `ruff` clean.

## Deploy

No migration. Deploy tooling only — takes effect on the next full deploy, since
the remote script is uploaded from the local checkout each run.
