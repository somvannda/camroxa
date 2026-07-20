# Continue Progress + auto-resume after API outage

**Date:** 2026-07-20  
**Status:** implemented (desktop; restart app)

## Summary

When sandbox API returns 502, Progress polling and auto-video pause. Local export could stay wedged as “busy,” so nothing resumed after the API recovered. Added Progress right-click **Continue Progress** (stage-aware: drafts → Suno → images → export → merge) and auto-resume on the video coordinator when `/progress` succeeds again after an outage.

## Product impact

**Before**
- API down → auto-video paused; after recovery, a stuck busy flag could block the next export forever.
- Users had to manually pick Retry Drafts / Start Export / etc.

**After**
- Right-click any Progress row → **Continue Progress** runs the next sensible step for that row.
- If export is wedged busy, Continue cancels/clears first (with a short retry), then starts.
- When the API recovers, status shows “API recovered — resuming auto-video…” and cooldowns clear so the next ready row can start.

## Technical impact

- `features/progress/lib/continue_progress.py` — action planner.
- `OperationalRowsCard.continue_progress_requested` + Progress view handler / pending flush.
- `VideoPipelineCoordinator`: `_api_outage` flag, `kick()`, recover stale busy on poll fail, clear cooldowns on recovery.

## Files touched

- `camxora_python/features/progress/lib/continue_progress.py`
- `camxora_python/features/progress/widgets/operational_rows_card.py`
- `camxora_python/features/progress/views/progress_view.py`
- `camxora_python/shared/services/video_pipeline_coordinator.py`
- `camxora_python/tests/test_continue_progress.py`
- `CHANGELOG.md`
- `docs/changelog/2026-07-20-continue-progress-auto-resume.md`

## Migration / deploy

- Restart desktop app (`python main.py`). No API/DB changes.

## Tests

- `pytest camxora_python/tests/test_continue_progress.py`

## Follow-ups

- Offline Start Export using cached profiles/settings when billing/progress APIs are down (local encode only).
- Soft-cancel into a healthy daemon job without process kill when only Progress polling is failing.

## Update — export menu visibility

**Rebuild MP4 / Force Regenerate MP4** (and Start Export / Start Merging) were gated on right-clicking the Export or Merge column only. After canceling an export, users often right-clicked Stage/Music and saw no rebuild actions. Those actions now appear on any cell when the row is eligible.
