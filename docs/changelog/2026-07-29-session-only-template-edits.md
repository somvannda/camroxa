# Session-only unsaved edits + restorable original templates

**Date:** 2026-07-29  
**Status:** implemented (desktop)  
**Branch:** `fix/session-only-template-edits`

## Summary

Unsaved style and workspace draft tweaks no longer survive app restart. They stay in memory for the current session only. Saving a video template keeps an immutable `originalTemplate` snapshot so users can restore the first known original after overwrite. Style preset “Restore original” still resets factory recipes for the active session.

## Product impact

- **Before:** Tweaking Spectrum/Particles/Logo/Background without Save wrote `%LOCALAPPDATA%/Camxora/video-presets/*.json`, and unsaved workspace drafts wrote `video-drafts/*.json`, so edits came back after restart. Save overwrote templates in place with no backup.
- **After:**
  1. Unsaved style edits reset to the last **saved** template (and factory style recipes) on restart.
  2. Save/overwrite keeps `originalTemplate`; left-rail **Restore original** puts that snapshot back.
  3. While the app stays open, unsaved edits remain; closing the app discards them.

## Technical impact

- `domain_preset_store` and `video_draft_store` are in-memory; legacy disk JSON is deleted once on first use.
- `VideoLocalStore` stores `originalTemplate` on create/install and seeds it on first Save for older records; `restore_template_to_original()` restores it.
- Left rail adds **Restore original** for the selected video template.

## Files touched

- `camxora_python/features/video/lib/domain_preset_store.py`
- `camxora_python/features/video/lib/spectrum_session_presets.py`
- `camxora_python/features/video/services/video_draft_store.py`
- `camxora_python/features/video/services/video_local_store.py`
- `camxora_python/features/video/views/video_view.py`
- `camxora_python/features/video/widgets/left_rail.py`
- `camxora_python/features/video/widgets/spectrum_inspector.py`
- `camxora_python/features/video/widgets/particles_inspector.py`
- `camxora_python/features/video/widgets/logo_inspector.py`
- `camxora_python/features/video/widgets/background_inspector.py`
- `camxora_python/tests/test_domain_preset_store.py`
- `camxora_python/tests/test_video_draft_store.py`
- `camxora_python/tests/test_video_local_store.py`
- `camxora_python/tests/test_spectrum_session_presets.py`
- `CHANGELOG.md`
- `docs/changelog/2026-07-29-session-only-template-edits.md`

## Migration / deploy

- Desktop-only. Restart the app.
- First launch after upgrade clears leftover `video-presets/*.json` and `video-drafts/*.json`.
- Existing catalog rows get `originalTemplate` seeded from the current saved payload on the next Save (then Restore returns to that seed). New / marketplace installs capture the install-time snapshot immediately.
- No API / sandbox deploy.

## Tests

- `pytest camxora_python/tests/test_domain_preset_store.py camxora_python/tests/test_video_draft_store.py camxora_python/tests/test_video_local_store.py camxora_python/tests/test_spectrum_session_presets.py`

## Follow-ups

- Optional: Save As flow for marketplace templates (`can_save_template`) so packs cannot be overwritten in place.
- Optional: explicit “Save style preset” if users want style overrides to survive without saving the whole video template.
