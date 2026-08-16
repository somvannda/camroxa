# User Spent song meter showed 0/300 while Suno was billed

**Date:** 2026-08-16  
**Surfaces:** platform_api (admin `GET /user-spend`)

## Problem

Admin **User Spent** showed Song (`S`) at **0%** for every subscriber even when
Suno was consuming plan song packages. Draft / image / video / merge chips were
correct.

Production `usage_tracking` stores the song counter as `music`. The rollup
copied that key through as `music`, while the page reads `meters.song`. Result:
real usage (e.g. 300/300, 210/300, 1033/1200) rendered as `0 / limit`.

Wallet was not supposed to move for in-quota monthly subscribers. Those events
are `billing=plan_allowance`, `coverage=song_package`, `amount=0`. The dashboard
made it look like Suno was free.

## Fix

Map usage keys onto the chip buckets before returning meters:

- `music` → `song`
- `background_image` / `thumbnail_image` → `image` (unchanged)
- `video_merge` → `merge` (unchanged)
- `video_manual` → `video` (was omitted, so manual exports under-counted)

## Verify

- User Spent Song chip matches `usage_tracking` `music` monthly_count for the
  current billing `period_start`.
- Monthly 2-channel users at cap show ~100% on `S`, not 0%.
