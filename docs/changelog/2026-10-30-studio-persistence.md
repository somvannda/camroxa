# Studio clone — milestone 3 (persistence)

**Date:** 2026-10-30
**Branch:** `feat/studio-shell`
**Surfaces:** musicapi (unchanged), `platform_api`, `camxora.com`

## Goal

Turn the project view from a browser-local sketch into a real Suno Studio
project: hydrate the arrangement from the saved `state` document and autosave
edits back as versions.

## Evidence

The `state` schema came from Suno's shipped chunks, not from a HAR. Full write-up
and module ids: [docs/studio-state-schema.md](../studio-state-schema.md).

Key facts that shaped the implementation:

- positions are **beats**, not pixels or seconds; default `timing.bps = 2`
  (120 BPM);
- track volume is `amplitude` (0–1), pan is `balance`, plus `solo`/`mute`;
- Main is the root `state.amplitude`;
- audio clips are `{ startBeats, endBeats, readStartBeats, asset: { type: "clip", id } }`;
- `save-project` takes the **whole** state plus `base_version_id`, returns
  `version_id`, `409 latest_version_id`, `429` when saving too often.

## What landed

### Backend

`platform_api/services/web_music_service.py`

- `_musicapi_studio_request` keeps the upstream status; `_musicapi_studio_call`
  wraps it (previously the status was lost, so `409`/`429` could not be mapped).
- `save_studio_session` → upstream `409` becomes `ConflictError` with
  `latest_version_id` in `details`; `429` becomes `RateLimitedError`.
- `get_studio_session_version`.
- `resolve_studio_clips` — provider clip id → `{ task_id, variant }` from
  `suno_tasks.audio_id_ok/alt`, so a saved arrangement can be played again.
- `add_studio_session_clips` now returns the resolved `clip_ids`.

`platform_api/routers/web_music.py`

- `POST /web-music/studio/sessions/{id}/save`
- `GET  /web-music/studio/sessions/{id}/versions/{version_id}`
- `POST /web-music/studio/clips/resolve`

### Web

`camxora.com/lib/web-music-api.ts`

- `StudioSaveConflictError` (carries `latestVersionId`), `saveStudioSession`,
  `getStudioSessionVersion`, `resolveStudioClips`; `updateStudioSessionClips`
  returns `clip_ids`.

`camxora.com/components/StudioShell.tsx`

- Timeline is measured in beats: 24 bars × 4 beats, default 120 BPM. Bar
  readout now reports `bar.beat.1`.
- Clip positions live in `clip.startBeats`; dragging converts pixels to beats.
- Hydration: `GET project` → `state.tracks[].clips[]` → `resolveStudioClips` →
  local tracks with `remoteId`, mixer values, `startBeats`/`lengthBeats`.
- Autosave 3 s after the last edit, **merging into the loaded state**:
  unknown fields (eq, instrument, signal chains, routing, non-audio clips) are
  preserved; only mixer values and audio clips are rewritten.
- Clips we cannot map to a song are neither played nor rewritten, so they stay
  intact on Suno.
- `409` adopts `latest_version_id` and retries once; `429` retries after
  `retry_after`. Errors surface inline; success shows no claim of being saved
  beyond Suno's own autosave model.

## Verification

- `npx tsc --noEmit` and `npm run check:ui` pass.
- Browser smoke test: the view renders, hydration failure falls back to an empty
  project without crashing, no unexpected console errors.

## Still open

- **Live round trip is the merge gate:** create a project with a mapped clip,
  save, reload, and confirm Suno's own editor still opens it.
- Interactive transport verification was blocked in this environment (the
  desktop browser window was not visible, so synthetic clicks had no user
  activation and Chrome throttled the rAF loop). Transport logic is unchanged
  from milestone 2 apart from the beats conversion.
- Export (`render-state`) and version restore remain.
