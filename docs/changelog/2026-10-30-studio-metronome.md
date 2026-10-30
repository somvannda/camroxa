# Studio clone — metronome

**Date:** 2026-10-30
**Branch:** `feat/studio-shell`
**Surface:** `camxora.com`

## Goal

The transport's metronome button existed but did nothing. `state.metronome`
(`{ enabled, amplitude }`) is part of the captured project document, so the
control can be real instead of decorative.

## What landed

`camxora.com/components/StudioShell.tsx`

- The button toggles `metronome` with `aria-pressed` and an accent state.
- Autosave writes `metronome: { enabled, amplitude }` back into the state
  document, preserving any unknown keys; hydration restores both.
- Clicks are scheduled from the transport loop at every beat (`timing.bps`),
  with a higher-pitched accent on each bar (`BEATS_PER_BAR`), played through the
  Main gain so the fader and mute behaviour stay consistent. Clicks stop with the
  transport; toggling mid-play does not burst a backlog.

`camxora.com/app/globals.css`: `.stv-icon.on` for toggled transport buttons.

## Verified live (project `dfd09f57-…`)

- Button starts unpressed; clicking it sets `aria-pressed="true"` and the accent
  class.
- After the 3 s autosave: `state.metronome = { enabled: true, amplitude: 1 }`,
  new version `60f81f82-…`.
- Reload: the button hydrates pressed, and no autosave fires just from loading.

`npx tsc --noEmit` and `npm run check:ui` pass.

## Not covered

- No UI for `metronome.amplitude` (Suno has a slider); the captured value is
  honoured for playback but not editable yet.
- The accent follows the first `timeSignatureChanges` entry
  (`subdivisionsPerBar × beatsPerSubdivision`, default 4); mid-song signature
  changes are not applied to the click, and the ruler still draws fixed 4-beat
  bars.
