# Studio clone — export (render-state)

**Date:** 2026-10-30
**Branch:** `feat/studio-shell`
**Surfaces:** `musicapi`, `platform_api`, `camxora.com`

## Contract, probe first

`POST /api/studio/render-state` needs `downbeats` as a list of
`[relativeSeconds, beatInBar]` pairs — a flat list of beats is rejected with
`422 list_type`. With the correct shape the call returns **200 and a queued
clip**, not an audio URL:

```json
{ "id": "<clip id>", "status": "queued", "audio_url": "",
  "metadata": { "type": "studio_export", "studio_project_id": "...",
                "studio_project_start_beats": 0, "studio_project_end_beats": 96 } }
```

The clip's `audio_url` stays `https://studio-api.prod.suno.com/api/forbidden`,
so the real file comes from
`GET /api/studio/clip/{clip_id}/download?format=mp3`, which is plan-gated.

## What landed

- **musicapi** — `renderStudioState()` (exact bundle body) and
  `getStudioClipDownload()`; internal routes
  `POST /internal/studio/render-state`,
  `GET /internal/studio/clips/:clip_id`,
  `GET /internal/studio/clips/:clip_id/download`.
- **platform** — `render_studio_export()` checks ownership, reads the saved
  `state`, derives `end_beats` from the clips and builds the `downbeats` pairs
  (`seconds = beat / timing.bps`, `beatInBar = beat % 4 + 1`), then queues the
  render; `get_studio_clip` / `get_studio_clip_download` proxy the result.
  Routes: `POST /studio/sessions/{id}/export`, `GET /studio/clips/{id}`,
  `GET /studio/clips/{id}/download`.
- **web** — the Export button queues the render, polls the download endpoint every
  3 s (120 attempts), opens the file when a `download_url` appears, and surfaces
  Suno's refusal message instead of hanging.

## Verified live

| Step | Result |
|---|---|
| `POST …/export` (platform) | `200 {clip_id, status:"complete", title}` |
| `GET …/clips/{id}` | `200`, `audio_url` = `/api/forbidden` placeholder |
| `GET …/clips/{id}/download` | `200 {"ok": false, "reason": "no_permission", "message": "You don't have permission to download in Studio."}` |

**Plan gate:** the connected pool account (`iamduke1987`, free) can queue the
render but Suno refuses the download. The UI reports
"You don't have permission to download in Studio." so the state is explicit.

## Not covered

- Range export UI (the backend accepts `start_beats` / `end_beats`, but there is
  no selection UI yet).
- Multitrack export (`render-state-multitrack`) is implemented at the API level
  but not surfaced: the captured body needs `project_id`, `studio_project_id`,
  `title`, `state`, `start_beats`, `end_beats`, and Suno answers
  `403 {error_type: "clip_not_unlocked"}` — "This song hasn't been unlocked yet.
  Unlock it to download stems." — for the free pool account. The menu that would
  offer "Song / Stems" is not evidenced yet, so the button stays single-action.
- No retry/backoff beyond the 6-minute poll window.
