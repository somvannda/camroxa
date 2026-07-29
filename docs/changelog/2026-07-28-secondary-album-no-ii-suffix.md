# Secondary album must be a fresh name (no Primary + II)

**Date:** 2026-07-28  
**Status:** implemented (deployed sandbox + production)

## Summary

Album 2 uniqueness previously used a last-resort `_fallback_distinct_album` that appended `II` / `Alt` / `Remix` / `Dual` to the Primary title. That produced Progress rows like **Forged in Fire** / **Forged in Fire II**. Secondary must always be a **new** title (pool + AI polish, or an unrelated emergency two-word name) — never a Primary clone with a suffix.

## Product impact

- **Before:** When Secondary generation failed or collided, Album 2 became `Primary II` (etc.).
- **After:** Failures use an unrelated emergency title (e.g. `Harbor Prism`). Trivial clones (`… II`, `… Alt`, …) are rejected and regenerated. Desktop image labels no longer invent `Primary II` for empty Secondary.

## Technical impact

- `_fallback_distinct_album` removed; replaced by `_is_trivial_album_clone` + `_emergency_fresh_album`.
- Persist / resolve / run-dir paths regenerate when existing `alt_album` is a trivial clone.
- Rewrite-album (Secondary) uses the same anti-suffix prompt and clone rejection.
- `image_workspace` album labels: empty Secondary shows `—` instead of inventing `II`.

## Files touched

- `platform_api/services/batch_service.py`
- `platform_api/tests/test_batch_service.py`
- `platform_api/CHANGELOG.md`
- `camxora_python/shared/lib/image_workspace.py`
- (hotfix mirror) `MusicGenerator-desktop-hotfix/camxora_python/shared/lib/image_workspace.py`

## Migration / deploy

- No DB migration.
- Deploy `platform_api` to sandbox, then production (album naming is server-side).
- Existing bad `* II` rows are **not** auto-rewritten; use Secondary album rewrite, or regenerate on next draft persist when clone detection fires.

## Tests

- `test_trivial_album_clone_detection`
- `test_emergency_fresh_album_never_suffixes_primary`
- Existing `test_orchestrate_drafts_persists_distinct_channel_albums`

## Follow-ups

- Optional one-shot backfill to rewrite historical `alt_album` values matching trivial-clone patterns.
