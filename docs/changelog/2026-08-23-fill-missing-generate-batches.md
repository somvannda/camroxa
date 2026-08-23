# Fill missing generate batches

**Date:** 2026-08-23  
**Branch:** `bugfix/fill-missing-batch-gaps`  
**Surfaces:** camxora_python (desktop)

## Summary

Generate builds one `POST /batches` per planned day × channel pair, then used
to stop on the first exception. A production run for 24–29 Aug (2 pairs) saved
9 of 12 batches; 28 Aug pair 2 and both 29 Aug pairs never reached the API and
were never retried.

The desktop now loads existing history for the planned dates, skips slots
that already exist, keeps creating after a single failure, and retries
timeouts/429/5xx. Clicking Generate again fills leftover days instead of
recreating the whole plan.

## Product impact

- Partial Generate no longer leaves silent holes for later days.
- A second Generate on the same dates/channels creates only the missing cells.
- The status line reports created / already existed / still missing.

## Files touched

- `camxora_python/shared/lib/music_batch_plan.py`
- `camxora_python/shared/workers/data_workers.py`
- `camxora_python/features/music/views/music_view.py`
- `camxora_python/tests/test_music_batch_plan.py`

## Migration / deploy

Desktop-only. No API/admin/music_web deploy. Ships with the next desktop
installer from this branch or merged `main`. Existing users can click Generate
again on the original date range to fill leftover day/pair slots.
