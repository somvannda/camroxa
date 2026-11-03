# Production ran an unapplied migration: `reason` was still `varchar(100)`

**Date:** 2026-11-03
**Surfaces:** `platform_api`
**Migration:** `179_credit_txn_reason_text_reassert`

---

## What verification found

After deploying `178_credit_txn_reason_text`, a read-only production audit showed:

```
alembic_version                     = 178
credit_transactions.reason          = character varying(100)
```

The revision was recorded but its DDL was not in effect, so the reason-width fix
was **not live**: an admin adjustment with a reason longer than ~81 characters
still failed with `value too long for type character varying(100)`.

The same audit confirmed the drift was isolated, not systemic:

| Migration | Expected effect | Present |
|---|---|---|
| `174` credits-only two-tier | `users.distrokid_*`, `billing_payments` nullable | ✅ |
| `177` all credits expire 30d | no live lot with `NULL` expiry | ✅ |
| `178` reason → `TEXT` | `credit_transactions.reason = text` | ❌ |

`ALTER ... TYPE TEXT` was verified to work on the production table (run inside a
transaction and rolled back): 64,168 rows, instant, no rewrite.

## Likely cause

`174` rebuilds tables from `*_archive` snapshots (`CREATE TABLE x_archive AS
TABLE x` … rename back), and the deploy that applied `178` also ended with
`DEPLOY_LOCK_NOT_OWNER`. Two overlapping upgrade runners would explain it: one
applied `178`, the other restored a pre-`178` snapshot afterwards, while
`alembic_version` stayed at `178`.

## Fix

1. **Migration `179`** re-asserts the type unconditionally:
   `ALTER TABLE credit_transactions ALTER COLUMN reason TYPE TEXT`.
   PostgreSQL treats a type change to the current type as a no-op, so it is
   safe on a database that already has it, and the `178 → 179` gate guarantees
   it is actually executed this time.
2. **Startup schema assertion** — `runner.verify_schema_assertions()` runs after
   every upgrade and checks the facts the application depends on, starting with
   `credit_transactions.reason = text`. A mismatch logs at CRITICAL with the
   actual value, so a "version ahead of schema" state can never again pass as a
   healthy deploy.
3. It deliberately **does not raise**: turning a degraded column into a failed
   API startup would be a bigger outage than the column itself.

## Files touched

- `platform_api/migrations/versions/179_credit_txn_reason_text_reassert.py` (new)
- `platform_api/migrations/runner.py` — `_SCHEMA_ASSERTIONS`, `verify_schema_assertions()`, called after upgrade
- `platform_api/tests/test_migration_179_reason_reassert.py` (new, 5 tests)

## Tests

- migration `179` follows `178` and issues the ALTER;
- its downgrade is a deliberate no-op (narrowing would truncate real reasons);
- the assertion passes on `text`, reports `character varying`, and never raises
  when the query itself fails.

`test_migration_179_reason_reassert.py` + `test_migrations_runner.py` → 13 passed.
`alembic heads` → single head `179`; `upgrade 178:179 --sql` renders cleanly.

## Deploy + verification

1. Deploy `platform_api` (startup applies `179`).
2. Re-run the audit: `reason` must read `text`, `alembic_version = 179`.
3. Check the startup log for a `Schema assertions failed` CRITICAL — its absence
   confirms the assertion ran and passed.

## Follow-ups

- Find out why two runners overlapped. The advisory lock exists, but the deploy
  logged `DEPLOY_LOCK_NOT_OWNER`, so either the lock was released early or a
  second process bypassed it.
- Consider extending `_SCHEMA_ASSERTIONS` with the other facts migrations are
  supposed to guarantee (the `credit_wallet_lots` tag constraint, for example).
