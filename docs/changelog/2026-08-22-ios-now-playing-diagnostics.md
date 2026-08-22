# iOS Now Playing diagnostics (2026-08-22)

## Problem
Lock screen / Dynamic Island show **Play** while in-app audio is already playing; sync only after a second pause/play cycle.

## Changes
- **`now-playing-debug.ts`**: structured snapshots of media element + `navigator.mediaSession` with mismatch flags (`UI_ON_MEDIA_PAUSED`, `MS_ON_MEDIA_PAUSED`, `MEDIA_NOT_IN_DOM`, `POS_FAIL`, etc.).
- **`player-provider.tsx`**: bind listeners on the in-DOM `<video>`/`<audio>` via `bindMediaRef`; post `now_playing_diag` and `media_element_event` traces; native playback uses media element `paused` as source of truth; lock-screen Media Session handlers work for HLS/native paths.
- **`media-session.ts`**: `syncMediaSessionPlayback()` returns `{ playbackState, positionOk, positionError }`.
- **`content_license_service.py`**: allow `now_playing_diag` and `media_element_event` client trace events.

## How to read traces
After playing on iPhone Safari, run:
```bash
python scripts/deploy/probe_sandbox_play_traces.py
```

Look for rows where `flags=` includes:
| Flag | Meaning |
|------|---------|
| `MEDIA_NOT_IN_DOM` | Listeners/state tied to wrong element |
| `UI_ON_MEDIA_PAUSED` | React UI thinks playing, element paused |
| `MS_ON_MEDIA_PAUSED` | Media Session says playing, element paused |
| `MS_PAUSED_MEDIA_PLAYING` | Lock screen paused, element actually playing |
| `POS_FAIL` | `setPositionState` rejected (often duration/position) |
| `COMPUTED_NOT_PLAYING` | Sync chose paused while ref says playing |

## Deploy
```bash
python scripts/deploy/hotfix_sandbox_ios_hls_now_playing.py
```
