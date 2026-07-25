# History status multi-select filter

**Date:** 2026-07-25  
**Status:** implemented (desktop; restart app)

## Summary

History Status was a single-choice dropdown (All / Success / Failed / Pending). It is now a multi-select menu so you can show any combination of buckets (OR). Clearing all checks (or Show all) means All statuses. Also preserves History table scroll position across poll refreshes so selection restore no longer jumps the viewport.

## Product impact

**Before**
- Status filter: pick exactly one of All / Success / Failed / Pending.
- Polling refresh often scrolled History back to the selected row.

**After**
- Status button opens checkable Success / Failed / Pending; label shows e.g. `Failed, Pending`.
- None checked = All statuses.
- Table scroll stays put while History refreshes.

## Technical impact

- `HistoryFiltersState.status` is `tuple[str, ...]` (empty = all).
- `song_matches_history_status_filter` accepts str or sequence; OR match across buckets.
- History card: `QPushButton` + checkable `QMenu` instead of status `QComboBox`.
- `set_rows` preserves scrollbar values; selection without `selectRow` scroll-into-view on refresh.

## Files touched

- `camxora_python/shared/lib/music_composer.py`
- `camxora_python/features/music/widgets/history_card.py`
- `camxora_python/features/music/views/music_view.py`
- `camxora_python/tests/test_music_composer.py`
- `camxora_python/tests/test_music_history_card.py`
- `CHANGELOG.md`
- `docs/changelog/2026-07-25-history-status-multiselect.md`

## Migration / deploy

Restart/rebuild the desktop app. No API or DB changes.

## Tests

- `pytest camxora_python/tests/test_music_composer.py camxora_python/tests/test_music_history_card.py`

## Follow-ups

- Optional: Draft failed vs Suno failed as separate checkboxes.
