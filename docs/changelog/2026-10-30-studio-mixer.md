# Studio clone — milestone 2 (mixer wired to playback)

**Date:** 2026-10-30
**Branch:** `feat/studio-shell`
**Surface:** `camxora.com` (Studio project view)

## Goal

F6/F10 were visual only: faders, S, M and Main changed nothing you could hear.
This milestone makes them audible without inventing any Suno contract — the
mixer is local playback state, exactly like the (still browser-local) timeline.

## What changed

`camxora.com/components/StudioShell.tsx`:

- Playback is a Web Audio graph instead of one `<audio>` element: every placed
  clip is a stream routed through its track's `GainNode` into the `Main` gain,
  so multiple clips play together at their timeline positions.
- Track volume, mute, solo and the Main fader now move gain, with a 15 ms ramp.
  Solo excludes non-soloed tracks; mute wins over solo.
- Transport runs off one audio clock: play/pause, rewind, Space, and a playhead
  / clock / bar readout updated by `requestAnimationFrame` (no per-frame React
  renders).
- Clips start and stop as the playhead crosses them; the transport stops at the
  end of the 24-bar ruler.
- Clips carry a stable `uid`, so the same song can sit on a lane twice without
  sharing a drag offset.
- Clip width and playback length come from real durations
  (`duration_seconds`, then measured `loadedmetadata`), not a fixed 16%.
- Streams use the same-origin proxy unless the declared URL is same-origin:
  cross-origin media without CORS is silent when tapped into the graph.

## Verified in the browser

Ran the shell on `localhost:3103` with the backends down (no songs, so no clips)
and inspected the live audio graph through `AudioContext.prototype.createGain`:

| Action | Master | Track 1 | Track 2 |
|---|---|---|---|
| 2 tracks, play | 0.800 | 0.800 | 0.800 |
| M on track 1 | 0.800 | 0.000 | 0.800 |
| S on track 2 | 0.800 | 0.000 | 0.800 |
| unmute 1 (S still on 2) | 0.800 | 0.000 | 0.800 |
| S off | 0.800 | 0.796 → 0.800 | 0.800 |
| track 2 fader 40% | 0.800 | 0.800 | 0.400 |
| Main 50% | 0.501 | 0.800 | 0.400 |

Also verified: clock and playhead advance together, pause freezes both, Space
toggles play/pause, rewind returns to `00:00.000`, and the console is clean
apart from the expected `ECONNREFUSED` proxy errors.

`npx tsc --noEmit` and `npm run check:ui` pass.

## Still not verified

Audible multi-clip mixing needs the platform API (`:8100`) and musicapi
(`:4003`) plus the live Suno cookie, so it is a **live check**, not a merge
gate yet.

## Next

Autosave / versions / hydration / export stay blocked on one HAR of a real
Studio session (create → add clip → drag → save → export) to capture the
`state` document.
