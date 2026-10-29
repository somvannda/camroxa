# Web-music Trash: per-version, Suno-shaped

**Date:** 2026-10-29
**Branch:** `feat/web-trash-workspace`
**Surface:** `camxora.com` Library/Create + Platform API

## Summary

Deleting used to hard-delete a song row (both versions) with no way back. Suno
trashes **clips** first and only deletes permanently from `/me/trash`. Ours now
does the same, per version.

Verified against the live Suno bundle/UI:

- `/me/trash` is a real route (sibling of `/me`, `/me/albums`, `/me/playlists`).
- `POST /api/gen/trash` with `{ trash: boolean, clip_ids: string[] }` toggles
  `is_trashed` on clips (batch).
- Song menu action `songActions.moveToTrash` opens a confirm modal with a count.
- Trash actions: `clipBrowserElements.restoreToLibrary` and
  `TrashedClipDeletePermanentlyClicked`, both using `selectedCount`.

## Product impact

- **Create**: row `⋮ → Move to Trash` and the rail action trash **that version**
  only, with a confirm modal naming it ("Move Version 1 to Trash?"); the other
  version stays in the library.
- **Library**: a **Trash** tab next to History. It lists trashed versions with
  **Restore to library** and **Delete permanently**, plus **Empty Trash**.
- Trashed versions disappear from the feed/library counts and cannot be played,
  streamed, or downloaded.
- Library bulk delete also soft-deletes (moves to Trash).

## Technical impact

- Migration `169_suno_task_trash` (superseded): `trashed_at`.
- Migration `170_trash_variants`: `trashed_variants TEXT[]` (`ok` = Version 1,
  `alt` = Version 2), backfilling old trashed rows with both, dropping
  `trashed_at`, and adding a partial index.
- `delete_generation(..., variant=None, permanent=False)` — appends the version
  to `trashed_variants`; `permanent` keeps the hard delete.
- `restore_generation(..., variant=None)` — removes versions from the array.
- `empty_trash()` — deletes songs whose versions are both trashed.
- `list_generations(trashed=)` — `cardinality < 2` for the library,
  `> 0` for Trash.
- Playback guard is per version: `NOT (variant = ANY(trashed_variants))`.
- Responses expose `trashed_variants` (list **and** detail; the detail payload is
  read from the source row because refresh helpers rebuild it).
- Routes: `DELETE /generations/{id}?variant=&permanent=`,
  `POST /generations/{id}/restore?variant=`, `DELETE /trash`.

## Files touched

| File | Change |
|---|---|
| `platform_api/migrations/versions/169_suno_task_trash.py` | First pass (song-level) |
| `platform_api/migrations/versions/170_trash_variants.py` | Per-version `trashed_variants` |
| `platform_api/services/web_music_service.py` | Variant delete/restore, list filter, playback guard, payload |
| `platform_api/routers/web_music.py` | `variant` params, `trashed_variants` in the response model |
| `platform_api/tests/test_web_music_delete_generation.py` | 14 tests for trash semantics |
| `camxora.com/lib/library-api.ts` | `trashed_variants` type |
| `camxora.com/lib/web-music-api.ts` | `delete(id, {variant, permanent})`, `restore(id, variant)` |
| `camxora.com/components/CreateStudio.tsx` | Per-version Move to Trash + modal copy |
| `camxora.com/components/LibraryView.tsx` | Trash tab, per-version list, restore/delete permanently |
| `camxora.com/app/globals.css` | `.s-trash-actions` |

## Migration/deploy

1. Run Alembic through `170_trash_variants` **before** the API serves the code.
2. No new env var. Rollback: revert code, then downgrade 170 (restores
   `trashed_at` and marks any trashed row).
3. Existing rows default to `{}`, so nothing disappears on deploy.

## Tests

- `pytest test_web_music_delete_generation.py` → **14 passed**
- Wider web-music group (`router`, `generate_queue`, `reference_video`) → **36 passed**
- Live smoke test: trash V1 → `trashed_variants: ok`, V1 stream → 404, V2 stream →
  422 `encrypted_playback_required` (packaged tracks), row present in Trash list,
  restore → `[]`.
- `npx tsc --noEmit` clean; `npm run check:ui` compliant.

## Follow-ups

- Suno batches: one `POST /api/gen/trash {clip_ids: [...]}` for many clips and
  multi-select in Trash. Ours is per-row for now.
- No `/library/trash` URL: Trash is a tab, and `?trash=1` opens it.
- Trashed files stay in B2 until permanently deleted; no auto-purge (manual only).
- Audio-result "Move to Trash" uses `studio_operations` and still hard-deletes.

## Update — per-version permanent delete and a Trash route

- **`171_purged_variants`** adds `purged_variants TEXT[]`. Deleting one version
  permanently hides that version (`purged`) while the sibling stays playable; the
  row is removed once both are purged. `permanent=true` without a `variant`
  still deletes the whole song.
- List filter is now `cardinality(trashed_variants) + cardinality(purged_variants) < 2`;
  playback guards both arrays.
- **`POST /generations/trash`** `{ trash, clip_ids: ["taskId:variant"] }` mirrors
  Suno's `POST /api/gen/trash`, used by multi-select in Trash.
- Trash view supports selection with **Restore selected** / **Delete permanently**.
- **`/library/trash`** route renders the Library on the Trash tab (Suno's
  `/me/trash` equivalent); the workspace dropdown shortcut points at it.
