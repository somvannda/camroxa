# Fix Suno dual-channel absorb spike (`increment_usage` count kwargs)

**Date:** 2026-08-03  
**Status:** implemented  
**Branch:** `fix/admin-routes-production-restore`

## Problem

Retry batch (10 songs, Primary + Secondary) exploded the daily fail/retry absorb
counter (25/day). Production logs showed:

```text
TypeError: UsageTrackingRepository.increment_usage() got an unexpected keyword argument 'count'
```

After plan music deduct, `_submit_song_to_suno` calls
`attribute_secondary_daily_usage(...)`, which passes `count=` / `include_monthly=`
to `increment_usage`. Production `usage_tracking_repo.py` still used the old
signature without those kwargs, so submit crashed **before** calling Suno.

Each failure took the `platform_absorb` refund path (`charged_credit_units=0` on
subscription). Job workers retried each song up to 5 times → roughly
`10 songs × 5 attempts` absorbs per Retry batch.

## Fix

Deploy updated `platform_api/repositories/usage_tracking_repo.py` so
`increment_usage` accepts `count` and `include_monthly` (matching enforcement).

## Deploy

`python scripts/deploy/hotfix_usage_tracking_count_kwargs.py both`

Also clear today's fail-absorb for affected users after deploy.
