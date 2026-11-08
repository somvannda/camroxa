# DB pool: bounded acquire wait and saturation warnings

**Date:** 2026-11-08
**Surface:** `platform_api`
**Branch:** `fix/db-pool-timeout`

## Summary

Each API worker creates `asyncpg.create_pool(min_size=4, max_size=8)` **without
an acquire timeout**. When all 8 connections were busy, requests waited
indefinitely behind them — production `POST /auth/refresh` was measured at
13–90s during the web-music polling incident, which is what made the desktop
treat a slow refresh as a dead session.

## Product impact

- A request that cannot get a connection now fails in **10s** with `503
  DATABASE_BUSY` + `Retry-After: 2`, instead of hanging for tens of seconds.
  Both the desktop client and the web app treat this as retryable.
- Operators get a warning when the pool stays fully checked out for **30s**,
  naming the size/idle counts, plus an info line when it recovers.
- No query semantics change: this bounds *waiting for a connection*, not the
  duration of an individual query.

## Technical impact

- `platform_api/config.py`
  - `db_pool_acquire_timeout_seconds` (default **10**)
  - `db_pool_saturation_log_seconds` (default **30**)
- `platform_api/main.py`
  - `create_pool(..., timeout=settings.db_pool_acquire_timeout_seconds)`
  - `_watch_pool_saturation()` background task (5s sampling) logs
    "Database pool saturated" after the configured window and "recovered".
  - `asyncio.TimeoutError` → `_db_pool_timeout_handler` → `503 DATABASE_BUSY`
    (registered before the catch-all handler).
  - Monitor task cancelled on shutdown.
- `platform_api/tests/test_db_pool_backpressure.py` (new, 6 tests): saturation
  predicate, exception safety, 503 shape, timeout→503, monitor warning,
  bounded defaults.

## Files touched

| File | Change |
|---|---|
| `platform_api/config.py` | Two settings |
| `platform_api/main.py` | Acquire timeout, 503 handler, saturation monitor |
| `platform_api/tests/test_db_pool_backpressure.py` | New tests |

## Migration/deploy

No schema change. API-only deploy; both settings are env-overridable
(`PLATFORM_DB_POOL_ACQUIRE_TIMEOUT_SECONDS`, `PLATFORM_DB_POOL_SATURATION_LOG_SECONDS`).

## Tests

```bash
python -m pytest platform_api/tests/test_db_pool_backpressure.py -q   # 6 passed
python -m pytest platform_api/tests/test_auth_middleware.py \
  platform_api/tests/test_health_router.py -q                          # 54 passed
```

`ruff` on `main.py` still reports only the pre-existing findings (`sys` import,
`auto_retry_task`, `get_audit_service`); none are on the added lines.

## Follow-ups

- Pool sizing is still 4–8 per worker (2 API workers → 16 interactive
  connections). Revisit only if saturation warnings appear after this ships.
- Per-acquire latency histograms would pinpoint slow query holders better than
  the saturation warning alone.
