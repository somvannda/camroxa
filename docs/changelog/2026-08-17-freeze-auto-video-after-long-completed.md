# Freeze auto-video after Long completed

**Date:** 2026-08-17  
**Surfaces:** `camxora_python` (desktop)  
**Branch:** `bugfix/freeze-auto-video-after-long-completed`

## Summary

Auto-video was re-exporting albums that had already shown **Long completed**
after the user deleted per-track MP4s or moved the run folder. The selector
only counted remaining track MP4s and ignored the merge label, a leftover
`MERGED_*.mp4`, and the `pipeline_complete` latch.

## Product impact

- After a known long merge, missing track files mean **archived**, not
  unfinished. Auto-video will not reopen that long branch.
- **Long completed · Reel pending** can still auto-start reel when that toggle
  is on.
- Explicit **Rebuild / Repair / Force** on Progress still regenerate.
- First-time export and stub-MP4 repair on unfinished rows are unchanged.

## Technical impact

- `branch_is_conclusively_complete()` in `desktop_video_automation.py`.
- `select_next_auto_video_candidate` skips `pipeline_complete` rows and treats
  a conclusive long/reel merge as outputs-ready even when track MP4s are gone.
- `VideoPipelineCoordinator` refuses to start auto-export when the selected
  branch is already conclusive. `repair_unhealthy=True` stays for unfinished
  rows only.

## Files touched

- `camxora_python/features/video/lib/desktop_video_automation.py`
- `camxora_python/shared/services/video_pipeline_coordinator.py`
- `camxora_python/tests/test_desktop_video_automation.py`
- `CHANGELOG.md`

## Migration / deploy

Desktop-only. Restart the desktop app (or ship the next installer). No API /
sandbox / production deploy.

## Tests

- `pytest camxora_python/tests/test_desktop_video_automation.py -q`

## Follow-ups

- Persist `pipeline_complete` when a local `MERGED_*.mp4` is first seen
  (covers historical rows whose latch never saved).
- Optional backfill of `pipeline_complete` for YouTube Done / known merge rows.
