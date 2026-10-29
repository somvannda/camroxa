# Web-music Trash: delete is recoverable

**Date:** 2026-10-29
**Branch:** `feat/web-trash-workspace`
**Surface:** `camxora.com` Library/Create + Platform API

## Summary

Deleting a song used to run `DELETE FROM suno_tasks`, so one click was final.
Delete now moves the song to **Trash** first; Trash is the only place that can
remove it for good. Matches Suno's two-step delete.

## Product impact

- **Create**: row `⋮ → Move to Trash` and the rail action open a confirm modal
  ("Move to Trash?", restore hint), then a `Moved to Trash` toast.
- **Library**: the trash button opens a real Trash view instead of a bulk-delete
  selector. Each row has **Restore** and **Delete forever**; the toolbar has
  **Empty Trash** (confirm modal says "Delete forever").
- Trashed songs disappear from the library/feed counts, and cannot be played,
  streamed, or downloaded while in Trash.
- Library bulk delete now also moves to Trash; only the Trash view deletes
  permanently.

## Technical impact

- Migration `169_suno_task_trash`: `suno_tasks.trashed_at TIMESTAMPTZ NULL` and a
  partial index `(user_id, trashed_at)`.
- `WebMusicService.delete_generation(..., permanent=False)` — soft by default,
  idempotent for already-trashed rows, hard delete only with `permanent=True`;
  in-flight generations still refused.
- `restore_generation()`, `empty_trash()`.
- `list_generations(..., trashed=)` filters both the page and its count.
- `_fetch_playable_task_row` requires `trashed_at IS NULL`, so playback,
  downloads, streams and public-playlist joins skip trashed rows.
- Routes: `GET /generations?trashed=true`, `DELETE /generations/{id}?permanent=true`,
  `POST /generations/{id}/restore`, `DELETE /trash`.
- Frontend helpers: `deleteWebMusicGeneration(id, permanent?)`,
  `restoreWebMusicGeneration`, `emptyWebMusicTrash`, `listWebMusicGenerations(..., trashed)`.

## Files touched

| File | Change |
|---|---|
| `platform_api/migrations/versions/169_suno_task_trash.py` | New column + index |
| `platform_api/services/web_music_service.py` | Soft/permanent delete, restore, empty, list filter, playback guard |
| `platform_api/routers/web_music.py` | `trashed`, `permanent`, restore, empty-trash routes |
| `platform_api/tests/test_web_music_delete_generation.py` | Rewritten for trash semantics |
| `camxora.com/lib/web-music-api.ts` | Trash helpers |
| `camxora.com/components/CreateStudio.tsx` | "Move to Trash" confirm flow |
| `camxora.com/components/LibraryView.tsx` | Trash view, restore, delete forever, empty |
| `camxora.com/app/globals.css` | `.s-trash-actions` |

## Migration/deploy

1. Run Alembic through `169_suno_task_trash` **before** deploying the API.
2. No new env var. Rollback: revert code, then drop the column/index.
3. Existing rows have `trashed_at = NULL`, so nothing becomes invisible on
   deploy.

## Tests

- `pytest platform_api/tests/test_web_music_delete_generation.py` → **11 passed**
  (soft delete, idempotency, permanent delete, missing row, pending refusal,
  restore, restore-missing, empty-trash count).
- Live smoke test against the local API: trashed row absent from the library and
  present in `?trashed=true`; `stream` → 404; restore → back in the library;
  soft delete → Trash; permanent delete → gone from both.

## Follow-ups

- Trashed songs keep their B2 files until permanently deleted. No automatic
  purge (manual-only by decision); a 30-day sweep can be added later.
- Admin listings (`admin_user_web_music`) and desktop pipeline queries still see
  every row; they were deliberately left unfiltered.
- The audio-result "Move to Trash" actions use a different table
  (`studio_operations`) and still hard-delete with `window.confirm`.
