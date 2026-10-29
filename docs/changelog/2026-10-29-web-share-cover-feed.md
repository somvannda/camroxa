# Share sheet + Suno-shaped cover flow

**Date:** 2026-10-29
**Branch:** `feat/web-remix-submenu`
**Surface:** `camxora.com` Create/Library + Platform API

## Summary

Two follow-ups to the Remix submenu work:

1. The Share sheet lost four icons (Telegram, X, Instagram, More).
2. "Cover queued" pointed at a screen Suno does not have.

Both are fixed at the root cause rather than patched in the UI.

## 1. Share sheet icons

The tiles rendered `<i class="icon fa-brands fa-telegram">`. In the bundled
Font Awesome 7 stylesheet, `.fa-brands` only sets `--fa-family`; the rules that
actually apply `font-family` and `::before` live on
`.fa-classic, .fa-regular, .fa-solid, .fab, .far, .fas`. Bare `fa-brands`
markup therefore had no glyph and drew nothing.

`ShareClipModal` now ships an inline `ShareIcon` component with hand-written
SVG for all nine targets, so the sheet no longer depends on an icon font being
loaded or containing a particular brand glyph.

Targets and behaviour are unchanged:

| Target | Behaviour |
|---|---|
| Copy Link | clipboard + toast |
| WhatsApp | `wa.me/?text=<title> <url>` |
| Download | MP3 of that version |
| Facebook | `facebook.com/sharer/sharer.php?u=` |
| Telegram | `t.me/share/url` |
| X | `twitter.com/intent/tweet` |
| Instagram | copies the link (no web share endpoint) |
| LinkedIn | `linkedin.com/sharing/share-offsite` |
| More | `navigator.share`, falling back to copy |

## 2. Cover is a song, not a queue

Suno behaviour (confirmed against the live product): Cover creates a **pending
song in the workspace feed**, and that same row becomes the finished song.
There is no separate cover screen, which is why the toast "see Cover queue" led
nowhere — that section was invented here, not cloned.

### Backend

`platform_api/services/web_music_service.py`:

- `_materialize_studio_operation_song()` — after a portfolio edit is accepted,
  insert a **pending** `suno_tasks` row (`source = web_music`) copying the source
  song's title/lyrics/style/model/instrumental/workspace/image. The row is keyed
  by the existing `(user_id, request_hash)` unique constraint with
  `request_hash = "studio:<operation_id>"`, so repeats are a no-op — no migration.
  These edits are single-take, so `purged_variants = {alt}` keeps Version 2 out
  of the feed.
- `_sync_studio_operation_song()` — when the operation poll reports completion,
  write `audio_url_ok`, `image_url_ok`, `duration_ok`, `title_ok` and
  `external_task_id` onto that row and schedule
  `schedule_web_music_b2_backfill()` so the clip becomes playable. Failures mark
  the row `failed` with the message; the existing refund still runs.
- `get_studio_operation()` self-heals the row when a completed operation is
  fetched after a process restart (no background poller exists for
  `studio_operations`).
- Applies to `cover`, `remaster`, `mashup`, `extend`, `add_vocals`,
  `add_instrumental`, `replace_section`. `stems`, `cover_image` and `video` are
  unchanged — they are not songs.

### Frontend

- `CreateStudio`: `coverFromRow()` no longer stuffs the operation into
  `audioHistory` or runs its own 3-second poll loop. It toasts
  **"Cover started — it will appear in your feed"** and refreshes the list.
- The temporary **Cover queue** section is gone; the pending feed row *is* the
  queue. The existing `hasPending` effect polls generations every 15 s, so the
  row flips to ready on its own.
- `audioResultRows` excludes feed-backed operation types, so a take cannot show
  up both as a song and under "Audio results". Stems/video/cover-image stay.
- `LibraryView` toast matches ("it will appear in your library").

## Files touched

| File | Change |
|---|---|
| `camxora.com/components/ShareClipModal.tsx` | Inline SVG icons, no icon-font dependency |
| `camxora.com/components/CreateStudio.tsx` | Cover row refresh, Cover queue removed, Audio-results filter |
| `camxora.com/components/LibraryView.tsx` | Cover toast copy |
| `platform_api/services/web_music_service.py` | `_materialize_studio_operation_song`, `_sync_studio_operation_song`, hooks, self-heal |

## Migration/deploy

No migration; head stays `173_web_music_reports`. Restart `platform_api` so the
new service code is loaded.

## Tests

- `python -m py_compile platform_api/services/web_music_service.py` — clean.
- DB-level exercise against the local database (fake operation, cleaned up after):
  - pending row created with title `"<song> (Cover)"` and `purged_variants = {alt}`
  - repeat call is idempotent (1 row)
  - completion flips it to `success` with audio/image/duration/title and
    schedules the B2 backfill
  - error path sets `failed` + message
- `npx tsc --noEmit` clean; `npm run check:ui` compliant.
- `/generations` and `/studio/operations` → 200 after the API restart.

## Follow-ups

- No background sweeper for `studio_operations`: a user who closes the tab
  immediately after starting a cover leaves the row pending until the next poll.
- Cover results are single-take; Suno sometimes returns two takes.
- Still missing vs Suno's menu: Manage ▸, Sample this song,
  Use as Inspiration.

## Song Radio

Suno's **Song Radio** starts a station from a song and keeps similar tracks
playing. Ours:

- `GET /web-music/generations/{id}/radio?limit=` returns
  `{ seed, items }`. Neighbours are scored by style-word overlap, with a bonus for
  the same model and workspace, drawn from the user's finished, non-trashed
  songs.
- The menu item plays the seed clip and enqueues the rest, so `Next` continues
  the station; the toast reports how many songs were queued.
- Both Create and Library, disabled until the clip is ready.

Verified: `radio?limit=5` → 200 with seed `Quiet Morning River Five` and four
ranked neighbours.

## Edit ▸

Suno's edit menu (per its help centre) holds **Song Details**, **Open in
editor**, **Replace Section** and **Crop Song**. Ours now mirrors the two we can
serve:

| Item | Status |
|---|---|
| Song Details | ✅ modal renames the version and edits the displayed lyrics |
| Open in Editor | ✅ `/studio/editor` |
| Replace Section | disabled — needs a waveform section picker |
| Crop Song | disabled — no crop service yet |

- `PATCH /generations/{id}` now takes `title` and/or `lyrics` (either alone),
  plus the existing `variant` (title is per version). An empty body is a 422.
- `updateWebMusicGeneration()` helper; `SongDetailsModal` shared by Create and
  Library. Lyrics edits change what is displayed and downloaded — the audio is
  not regenerated, which matches Suno's "Edit Displayed Lyrics".

Verified: title-only → 200, lyrics-only → 200, `{}` → 422;
`pytest test_web_music_router.py` → 13 passed.

