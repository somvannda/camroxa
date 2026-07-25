# History date filter no longer wipes the list

**Date:** 2026-07-25  
**Status:** implemented (desktop restart required)

## Summary

After the strict History date filter, choosing an inverted From/To (screenshot: From `7/26/2027`, To `7/26/2026`) sent that range to the API, which returned zero batches and replaced the in-memory History with an empty list. Last batch and other filters then had nothing to show. Desktop now normalizes inverted ranges, filters dates client-side only on the loaded recent window, and treats Last batch as “newest loaded batch” regardless of From/To.

## Product impact

- **Before:** A bad or inverted calendar range cleared History entirely; Last batch could show nothing; Jul 26–27 looked “broken” even when recent batches existed.
- **After:** From/To auto-swap when inverted; table filters the loaded batches by planned run / created day; Last batch always shows the newest loaded batch; Show all still clears the date filter.

## Technical impact

- `normalize_history_date_range` + History card widget sync.
- `MusicView.refresh_history` no longer passes From/To to the API.
- `matches_history_filters`: Last batch skips date matching.
- Removed ShellDateEdit click-through mouse eating (could corrupt year when opening the popup).

## Files touched

- `camxora_python/shared/lib/music_composer.py`
- `camxora_python/features/music/widgets/history_card.py`
- `camxora_python/features/music/views/music_view.py`
- `camxora_python/shared/widgets/shell_date_edit.py`
- `camxora_python/tests/test_music_composer.py`
- `CHANGELOG.md`

## Migration / deploy

- Desktop restart only (no API redeploy required for this fix).

## Tests

- `pytest camxora_python/tests/test_music_composer.py camxora_python/tests/test_shell_date_edit.py camxora_python/tests/test_music_history_card.py`

## Follow-ups

- If users need History for dates older than the History window (settings), consider a dedicated “load older” path with server-side dates again — without replacing the current list on empty results.
