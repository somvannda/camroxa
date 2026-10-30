# Studio clone — status

Last updated: 2026-10-30 · branch `feat/studio-shell`

The rule for every feature stays in [studio-1to1.md](studio-1to1.md): evidence
first (shipped bundle → help centre → live session). The captured `state`
document is in [studio-state-schema.md](studio-state-schema.md); flow-by-flow
detail is in [studio-flows.md](studio-flows.md).

## Done and verified against live Suno

| Area | What exists | Evidence |
|---|---|---|
| Landing (`/studio`) | Resume card opens the real Suno project (`studio_projects.suno_project_id`), songs column, demo links | live |
| Create / open | `create-project`, `create-or-load-project-for-clip`, indexed locally | live |
| Hydration | `state.tracks[].clips[]` → timeline, mixer values, beats, fades, metronome | live |
| Autosave | 3 s debounce, merges into the loaded state, `409` adopt-and-retry, `429` retry-after | live |
| Mixer | per-track volume / mute / solo, Main fader, persisted to `track.amplitude` / `state.amplitude` | live |
| Clips | add at playhead, drag, trim (start/end/readStart), split, duplicate, delete, fades | live |
| Transport | play/pause, rewind, clock, bar.beat, seek on ruler/lanes, Space | partial (see below) |
| Undo / redo | 60-step history over tracks + Main, buttons and Ctrl/Cmd+Z | live |
| Metronome | toggles `state.metronome`, clicks per beat with downbeat accent | live |
| Library dock | Songs, Liked tabs (drag/click to add) | live |
| Ownership | `403` for another user's indexed project; audited | live + unit tests |

## Blocked — needs a decision

| Item | Blocker |
|---|---|
| Export (`render-state`) | Likely spends credits; needs explicit approval before probing |
| Encrypted playback | Packaged tracks return `422 encrypted_playback_required`; needs the legacy `music_web` DRM player or a policy change |
| Version history / rename / archive | No usable endpoint: `/api/project/{id}/metadata` and the clip list 404 for Studio project ids; version-list probes returned 404/401 |
| Prompt bar | Request not captured |

## Deliberately absent

- **Projects tab in the library dock** — Camxora project ids are not Suno ids
  (fixed for the landing by storing `suno_project_id`; the dock tab would need the
  same mapping plus a project list, so it stays out).
- **Clip gain / loop controls** — the state carries `clip.amplitude` and
  `loop {enabled,startBeats,endBeats}`, but no captured UI shows how Suno exposes
  them; no guessed controls were added.
- **Stems / Uploads / Workspaces tabs** — uploads have URLs but no same-origin
  playback path, and adding them needs `asset: {type:"upload"}` support.

## Known limitations

- Packaged tracks are silent in the editor (see encrypted playback).
- Trim/split/fades are not covered by tests beyond live checks.
- The metronome accent follows the first `timeSignatureChanges` entry; mid-song
  signature changes are ignored.
- Projects created before migration `174` have no `suno_project_id` and are
  hidden from the resume card.
- Migration `174` must be applied in sandbox/production.

## How to verify locally

```
platform_api: python -m uvicorn platform_api.main:app --port 8100
musicapi:     npx tsx src/serve.ts            (musicapi/)
web:          npm run dev                      (camxora.com/)
checks:       npx tsc --noEmit && npm run check:ui
              python -m pytest platform_api/tests/test_studio_project_access.py
```

Test projects used this session (safe to delete on Suno):
`82abd622-…`, `cd053766-…`, `dfd09f57-…`, `06767aec-…`, `3cb281f6-…`.
