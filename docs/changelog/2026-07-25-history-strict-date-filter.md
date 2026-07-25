# History From–To calendar filter is strict

**Date:** 2026-07-25  
**Status:** implemented (sandbox API deploy pending)

## Summary

History calendar filtering was too loose: mid-days between create and planned run could match, and `updated_at` could pull old batches into “today” after retries/rewrites. Client and API now use the same strict rule: planned-run window overlaps From–To, or the batch was created on a day inside that range. Updates are ignored.

## Product impact

- **Before:** Filtering From=To=today could still show older batches that were touched today, or batches whose create→plan gap crossed the selected day.
- **After:** A single-day From/To only shows batches planned for that day (or spanning it) and batches created that day. Hint text under the filters explains the rule.

## Technical impact

- Desktop: `matches_history_date_range` / `history_batch_planned_window` in `music_composer.py`; History hint in `history_card.py`.
- API: `GET` music history list SQL in `music_history.py` (main query + schema-drift fallback).

## Files touched

- `camxora_python/shared/lib/music_composer.py`
- `camxora_python/features/music/widgets/history_card.py`
- `camxora_python/tests/test_music_composer.py`
- `platform_api/routers/music_history.py`
- `CHANGELOG.md`, `platform_api/CHANGELOG.md`

## Migration / deploy

- No DB migration.
- Deploy Platform API sandbox hotfix for `music_history.py`.
- Desktop: restart / rebuild to pick up client filter + hint (API alone already filters server-side).

## Tests

- `pytest camxora_python/tests/test_music_composer.py` — created-day match, mid-gap reject, `updated_at`-only reject, multi-day planned overlap.

## Follow-ups

- See `2026-07-25-history-date-filter-wipe-fix.md` — inverted From/To + API refetch wiped History; desktop now normalizes and filters client-side.
