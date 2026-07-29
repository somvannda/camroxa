# Preview hitch: skip GPU framebuffer grab while playing

**Date:** 2026-07-29  
**Status:** implemented (desktop branch)  
**Branch:** `fix/spectrum-vivid-position-audio`

## Summary

Live preview could freeze briefly every few seconds because `paintGL` periodically called `grabFramebuffer()` (GPU pipeline stall) and recomputed the logo visible-radius alpha scan every frame when Attach was on.

## Product impact

- **Before:** Preview hitch / stutter every ~few seconds during playback.
- **After:** No framebuffer grab while audio is playing; logo radius scan is cached until the logo or circle mask changes. Freeze snapshot still updates when paused (for export UX).

## Technical impact

- `_cache_clean_preview_frame`: skip when `audio_playing`; otherwise throttle to ≥2.5s.
- `_logo_visible_radius_ratio_cached`: cache by logo array id + circleMask.

## Files touched

- `camxora_python/visualizer/preview_widget.py`
- `CHANGELOG.md`
- `docs/changelog/2026-07-29-preview-playback-hitch-fix.md`

## Migration / deploy

- Desktop-only. Restart Camxora and play a track in Video preview.

## Tests

- Manual: play preview 30s+; hitch should be gone or greatly reduced.

## Follow-ups

- If hitch remains with Motion Trails on, profile trail quad allocations / GC.
- Export path still computes logo radius each run (acceptable offline).
