# Schema assertions now surface on `/health`

**Date:** 2026-11-05
**Surfaces:** `platform_api`
**Migration:** none

---

## Why

Production sat with `alembic_version = 178` and
`credit_transactions.reason` still `character varying(100)` while `/health`
reported `"status": "healthy"`. The runner already logged a `CRITICAL` when a
recorded revision's schema fact was missing — the line was there, nobody was
looking for it, and every dashboard stayed green.

A log line is not a signal. This makes it one.

## What changed

- **`services/schema_status.py`** (new) — in-process record of the last
  assertion pass: `{checked, ok, failures}`. Each worker records its own result
  during startup; a worker that never ran migrations reports `checked: false`.
- **`migrations/runner.py`** — `verify_schema_assertions()` calls
  `schema_status.record(failures)`.
- **`routers/health.py`** — `/health` returns a `schema` object and drops to
  `degraded` when an assertion fails. It never reports `unhealthy`: the API is
  still serving, and turning a wrong column into a failed health check would
  cause an outage rather than describe one.

```json
{
  "status": "degraded",
  "schema": {
    "checked": true,
    "ok": false,
    "failures": ["credit_transactions.reason: 'character varying' (expected 'text')"]
  }
}
```

## Files touched

- `platform_api/services/schema_status.py` (new)
- `platform_api/migrations/runner.py` — record the result
- `platform_api/routers/health.py` — report it, degrade status
- `platform_api/tests/test_schema_status.py` (new, 6 tests)

## Tests

- status starts `unchecked`, records failures, and resets;
- the runner records both a passing pass and the exact production failure
  (`character varying`);
- health regression suite: 26 passed (`-k health`), no change to existing
  healthy/degraded/unhealthy cases.

## Follow-ups

- Route the `degraded` transition through the existing Telegram ops alert so it
  pages rather than waits to be polled.
- Extend `_SCHEMA_ASSERTIONS` with the `credit_wallet_lots` tag constraint.
- Serialize migration execution across workers — the overlap that most likely
  dropped `178`'s DDL in the first place.
