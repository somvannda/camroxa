# Startup maintenance waits for the restart burst

**Date:** 2026-11-09
**Surface:** `platform_api`
**Branch:** `fix/startup-background-grace`

## Summary

After the 2026-11-08 API restart the DB pool monitor reported "saturated" for
**8 minutes** (11 warnings, 0×503). Three maintenance loops ran the instant the
process started — the studio sweeper, streaming auto-retry and credit-grant
maintenance — exactly while every client reconnected.

## Change

- `_STARTUP_BACKGROUND_GRACE_SECONDS = 60` in `main.py`; the studio sweeper
  sleeps before its first pass.
- `run_streaming_auto_retry_loop()` and `run_grant_maintenance_loop()` accept
  `startup_delay` (default 0 for tests/other callers); `main.py` passes 60s.
- Loops that already sleep first (pipeline-stuck scan, B2 backfill, streaming
  health report, credit invariants) are unchanged.

## Impact

Request traffic during a restart no longer competes with three simultaneous
maintenance scans. Nothing is delayed beyond 60s after start; the loops keep
their normal intervals afterwards.

## Tests

```bash
python -m pytest platform_api/tests/test_startup_background_grace.py \
  platform_api/tests/test_db_pool_backpressure.py \
  platform_api/tests/test_web_music_b2_ingest_retry.py -q   # 12 passed
```

## Follow-ups

- If the pool still looks busy after restarts, instrument acquire waiters
  rather than guessing further.
