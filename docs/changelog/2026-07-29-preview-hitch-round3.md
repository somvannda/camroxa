# Preview hitch every ~4s — hard-pause music-download polls

**Date:** 2026-07-29  
**Status:** implemented (desktop local; restart app to pick up)

## Summary

Round 2 only stretched the music-download timer to 60s while preview played, but `_on_sync_succeeded` still forced `setInterval(4_000)` whenever `pending_count > 0`, undoing the backoff. That matches the user’s “every 4 seconds” report. Round 3 **stops the timer entirely** while Video preview plays, ignores success/fail interval updates until pause, and resumes 4s/12s cadence only after pause.

## Product impact

- **Before:** Preview hitch every ~4s when any Suno downloads were pending (or after a sync that reported pending).
- **After:** No music-download poll while preview is playing; downloads resume when paused/stopped.

## Technical impact

- `MusicDownloadCoordinator`: `_preview_playing` gate; `set_preview_playing(True)` → `timer.stop()`; `_apply_interval` no-ops while playing; `_poll` returns early while playing.
- `VideoPipelineCoordinator.set_preview_playing(True)` now stops its timer (was 30s stretch).
- Video view wiring unchanged (`_on_preview_playback_state_changed`).

## Files touched

- `camxora_python/shared/services/music_download_coordinator.py`
- `camxora_python/shared/services/video_pipeline_coordinator.py`
- `camxora_python/tests/test_music_download_coordinator.py`
- `docs/changelog/2026-07-29-preview-hitch-round3.md`
- `CHANGELOG.md` (desktop Unreleased)

## Migration / deploy

Desktop-only. Fully restart the app (Python module reload). No API/sandbox deploy.

## Tests

- `pytest camxora_python/tests/test_music_download_coordinator.py` — includes pause-while-playing regression.

## Follow-ups

- If hitch remains with no pending downloads and polls stopped, re-check hitch log (`preview hitch … Xms`) for GPU/template causes.
- Image page `poll_interval_ms = 4000` only while that page is visible; leave alone unless hitch happens off Video.
