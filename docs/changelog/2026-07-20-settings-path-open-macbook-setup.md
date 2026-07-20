# Settings path Open crash + MacBook travel setup

**Date:** 2026-07-20  
**Status:** implemented

## Summary

Fixed Settings → Preferences path “Open” crash caused by Qt’s `clicked(bool)` overriding lambda defaults. Added `docs/MACBOOK_DEV_SETUP.md` for cloning and migrating on a travel machine.

## Product impact

**Before:** clicking Open next to Downloads/Suno/Merged (or image sample dirs) raised `AttributeError: 'bool' object has no attribute 'text'`.  
**After:** Open opens the folder/file path normally.

## Technical impact

- `path_row` wraps browse/open callbacks to ignore the checked bool.
- Travel doc covers clone, alembic `068`, Mac limits (no desktop/NVENC DLL).

## Files touched

- `camxora_python/shared/widgets/settings_ui.py`
- `camxora_python/features/settings/views/settings_view.py`
- `docs/MACBOOK_DEV_SETUP.md`
- `CHANGELOG.md`

## Migration / deploy

No DB change. Desktop restart to pick up Settings fix. Push branch for Mac clone.

## Tests

Manual: Settings → Preferences → Open on Downloads dir.

## Follow-ups

None.
