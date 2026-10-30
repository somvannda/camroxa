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
  A project with no saved version has no `state` at all, so hydration falls back
  to the captured default document; the first autosave creates version 1.
- New lanes are built from the captured track defaults (EQ bands, `instrument`,
  heights, colour) instead of borrowing another track, so an empty project can
  be saved without inventing fields.
- Main and new-track faders now start at Suno's default `1.0` (100 %).
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
- **Live probe against a throwaway Suno project** (`82abd622-…`, created for
  this test):
  - `GET /api/studio/project/{id}` on a fresh project returns metadata only.
  - Saving the captured default state returns `200 {version_id}`; after that the
    same GET returns `state` + `latest_version_id`, and the version endpoint
    round-trips the document.
  - Through the platform proxy: save `200`, stale `base_version_id` → `409` with
    `error.details.latest_version_id`, version read `200` with
    `state.amplitude = 0.75` and `timing.bps = 2`, clip resolve `200`.
- **Full UI round trip** against `dfd09f57-…` ("CAMXORA UI round trip") in the
  running web app: open the empty project, add a track, add "Drive tonight",
  wait for autosave, then reload.
  - Saved state: one audio track (`amplitude 1`, `balance 0`, 7-key EQ,
    `instrument {type:"song"}`, `height 86`) and one clip
    (`asset {type:"clip", id: ff7778ac…}`, `startBeats 0`, `endBeats 96`,
    `readStartBeats 0`, loop/warp present).
  - After reload the clip hydrates back at the same position, the track fader
    reads 100, and no autosave fires just from loading.

### What live testing changed

- `POST /api/project/{id}/clips` returns `404 Project not found` for a Studio
  project id — it is project/workspace membership, not the timeline. The clip
  add/remove calls were removed; the arrangement is written only through
  `save-project`.
- Adding a clip now resolves `task + variant → provider clip id` through a new
  `POST /studio/clips/provider-id` proxy, which is what `asset.id` needs.
- Opening `/studio/editor` without a project creates an empty project, and an
  added clip joins that project rather than the clip's own project.

## Still open

- **Playback of packaged tracks:** the plain stream route returns
  `422 encrypted_playback_required` when a clip has a ready encrypted package
  (both variants of "Drive tonight" do). The web app has no encrypted player
  yet, so Studio playback is silent for those tracks — a pre-existing product
  gap, now recorded rather than hidden.
- Interactive transport verification still needs a visible browser window: the
  desktop window was off-screen in this environment, so real clicks had no user
  activation and Chrome throttled the rAF loop. Playback/transport logic is
  unchanged from milestone 2 apart from the beats conversion.
- Export (`render-state`) and version restore remain.
- Probe projects `82abd622-…` ("CAMXORA platform probe"), `cd053766-…` and
  `dfd09f57-…` ("CAMXORA UI round trip") are still on the account and should be
  deleted once no longer needed.
