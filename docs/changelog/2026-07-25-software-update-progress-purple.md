# Software update progress bar — purple gradient

**Date:** 2026-07-25  
**Status:** implemented (desktop; restart / rebuild for packaged app)

## Summary

The mandatory software-update gate progress bar no longer uses a dark track + cyan chunk. The track is transparent and the fill uses the Camxora purple CTA gradient.

## Product impact

**Before:** Dark gray track with solid cyan (`#4ac0ff`) fill.  
**After:** No track background; fill is `#7466F1` → `#A259FF` left-to-right.

## Technical impact

- Theme only: `QProgressBar#software_update_progress` / `::chunk` in `deep_blue.py`.

## Files touched

- `camxora_python/shared/themes/deep_blue.py`
- `CHANGELOG.md`
- `docs/changelog/2026-07-25-software-update-progress-purple.md`

## Migration / deploy

- Dev: restart desktop app to reload theme.
- Packaged: rebuild installer if shipping this polish in the next sandbox build.

## Tests

- Manual: trigger update gate download and confirm purple gradient progress with no dark track.

## Follow-ups

- None.
