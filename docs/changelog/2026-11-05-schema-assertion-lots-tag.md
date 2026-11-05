# Assert the lot tag constraint too

**Date:** 2026-11-05
**Surfaces:** `platform_api`
**Migration:** none

## Why

`_SCHEMA_ASSERTIONS` covered one fact: `credit_transactions.reason = text`. That
was the column the `178` incident lost, but it is not the only fact a table
rebuild can quietly change.

Migration `174` rebuilds tables from `*_archive` snapshots. If a rebuild restored
an older `credit_wallet_lots` definition, the `tag` CHECK would lose `admin`, and
every admin comp would start failing inserts — with `alembic_version` still
looking correct.

## Change

A second assertion:

```sql
SELECT count(*)::text
FROM pg_constraint
WHERE conrelid = 'public.credit_wallet_lots'::regclass
  AND contype = 'c'
  AND position('admin' in pg_get_constraintdef(oid)) > 0
```

expected `1`. Comparison is now `str(actual) != expected`, so integer-returning
queries work alongside the text ones.

## Impact

- A failed assertion already appears on `/health` as `schema.ok = false` and
  drops the overall status to `degraded` (from `#479`).
- No behaviour change when the schema is correct.

## Tests

- 19 pass across `test_schema_status.py`, `test_migration_179_reason_reassert.py`
  and `test_migrations_runner.py`.
- New test: a constraint without `admin` is reported and flips `schema.ok`.
- The SQL was run read-only against a local database and returns `1`.

## Follow-ups

- Add assertions for the `credit_wallet_lots` unique `(user, period)` grant
  invariant and the `alembic_version.version_num` width.
