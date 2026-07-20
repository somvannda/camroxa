# Music History date + status + batch filters

**Date:** 2026-07-20  
**Status:** implemented (desktop + API)

## Summary

Music History calendar filtering treated planned run dates only, so batches created today but planned for a later run day disappeared when filtering by today. Filters were also client-only on the last 8 batches. Added Status and Batch dropdowns, fixed date matching, raised history fetch limit, and optional server-side date filters.

## Product impact

**Before**
- From/To often looked broken for future-planned batches.
- No status or batch filter.
- Show all left dates looking active while ignored.
- Only ~8 recent batches loaded.

**After**
- Date filter matches planned run date **or** created/updated day.
- Status: All / Success / Failed / Pending.
- Batch: All batches or a specific batch id.
- Show all clears date + status + batch filters (hint explains date filter is off).
- Loads up to History window setting (capped at API 100); changing dates refetches from API.

## Technical impact

- `HistoryFiltersState` gains `status`, `batch_id`.
- `matches_history_date_range` / `song_matches_history_status_filter`.
- `GET /music/history?from_date&to_date&limit` (limit max 100, default 25).

## Files touched

- `camxora_python/shared/lib/music_composer.py`
- `camxora_python/shared/lib/music_status.py`
- `camxora_python/features/music/widgets/history_card.py`
- `camxora_python/features/music/views/music_view.py`
- `camxora_python/shared/services/platform_api.py`
- `camxora_python/shared/workers/data_workers.py`
- `camxora_python/tests/test_music_composer.py`
- `camxora_python/tests/test_music_history_card.py`
- `platform_api/routers/music_history.py`
- `platform_api/CHANGELOG.md`
- `CHANGELOG.md`
- `docs/changelog/2026-07-20-music-history-filters.md`

## Migration / deploy

1. Deploy `platform_api` (history limit + date query params).
2. Restart/rebuild desktop app.

## Tests

- `pytest camxora_python/tests/test_music_composer.py camxora_python/tests/test_music_history_card.py`
- `pytest platform_api/tests/test_music_history_router.py`

## Follow-ups

- Per-channel filter.
- Dedicated Draft failed / Suno failed status buckets if needed.

## Incident

**Symptom:** Desktop `GET /music/history` returned 500 after date filters shipped.  
**Cause:** asyncpg `$n::date` bindings reject plain strings (`'str' object has no attribute 'toordinal'`).  
**Fix:** parse query params with `date.fromisoformat` before `pool.fetch`.  
**Verify:** history refresh with From/To set returns 200; sandbox probe with date strings succeeds.
