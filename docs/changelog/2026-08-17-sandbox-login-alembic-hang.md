# Sandbox login restored after Alembic hang + auth import 500

## Summary

Sandbox login failed because `camxora-api` never finished startup. A later API sync reintroduced broken merge stubs (`e5077c52f2b7` → `fffddbe8fbb3` → `ff781163cfbb` → `1f0ad008d202`) that still pointed at the deleted `084_provider_balance_events` revision. All four workers stuck on `alembic upgrade heads`, so every login returned `500 Database pool not initialized`.

After the graph was linearized, login still returned 500 because the deployed auth router referenced `AccountLockedError` without importing it. Wrong-password and lockout paths crashed instead of returning 401/403.

## Product impact

**Before:** Music, app, and admin sandbox login all failed with a 500.

**After:** Health is 200 and login returns a normal 401 for bad credentials.

## What was applied (sandbox only)

- Quarantined the four broken merge stub files.
- Made `103_merge_credit_refund_heads` a linear child of `102`.
- Redeployed the leftover-skip Alembic runner.
- Imported `AccountLockedError` in `platform_api/routers/auth.py`.
- Cleared Redis auth lockout/failure keys.

## Tests

- `https://api.sandbox.camxora.com/health` → 200, `database: true`
- Login probes on API / music / app / admin → 401 `AUTHENTICATION_ERROR` (not pool 500)
