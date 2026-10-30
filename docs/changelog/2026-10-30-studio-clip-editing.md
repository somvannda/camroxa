# Studio clone — milestone 4 (clip editing)

**Date:** 2026-10-30
**Branch:** `feat/studio-shell`
**Surface:** `camxora.com`

## Goal

Make the timeline editable the way a DAW is: trim a clip's edges, split it at the
playhead, duplicate it, and move the playhead — all persisted through the same
`state` document.

## What landed

`camxora.com/components/StudioShell.tsx`:

- **Trim** — edge handles on each clip. Dragging the left handle moves
  `startBeats` and shifts `readStartBeats` by the same amount (the source offset
  cannot go below 0); the right handle changes the length. Both write
  `startBeats` / `lengthBeats` / `readStartBeats`.
- **Split at playhead** — the clip becomes two arrangements sharing one source:
  the left keeps `startBeats … playhead`, the right starts at the playhead with
  `readStartBeats` advanced by the left half's length.
- **Duplicate** — a copy with a new arrangement id placed after the original.
- **Clip context menu** — right-click a clip: Duplicate, Split at playhead,
  Delete. Delete removes the arrangement only; the song stays in the library.
- **Playhead seek** — clicking the ruler or an empty lane moves the playhead, so
  split has a target (and the transport has a scrub point).
- **Undo / redo** — a 60-step history over the arrangement and Main fader,
  recorded 450 ms after an edit settles. Header buttons plus Ctrl/Cmd+Z and
  Ctrl/Cmd+Shift+Z (or Ctrl+Y); ignored while typing.
- **Fades** — selecting a clip reveals two top-corner handles; dragging them sets
  `fadeInBeats` / `fadeOutBeats`, drawn as diagonal overlays. Splitting keeps the
  left fade-in and the right fade-out. Audio is ramped on a per-clip gain node
  (source → clip gain → track gain → Main), so the fade is audible, not cosmetic.
- Playback honours `readStartBeats`: a trimmed clip starts at its source offset.

`camxora.com/app/globals.css`: clip handles, selected-clip outline, context menu
and backdrop, using existing `--s-*` tokens.

## Verified in the browser (live project `dfd09f57-…`)

1. Ruler click at 50 % → playhead at `00:24.000`, bar `013.1.1`.
2. Right-click → menu lists Duplicate / Split at playhead / Delete.
3. Split → two clips at 0 % and 50 %.
4. Right-edge trim of the second clip by 25 % → width 25 %.
5. Duplicate the first clip → third clip at 50 %.
6. Autosave wrote exactly:
   - `0..48` read `0` (split left)
   - `48..72` read `48` (split right, trimmed to 24 beats)
   - `48..96` read `0` (duplicate)
7. Reload → the three clips hydrate back to the same positions and widths, and
   no autosave fires from loading.
8. Undo/redo: adding a track enabled Undo, Undo dropped it back to one track and
   enabled Redo, Redo restored it; deleting a clip dropped to two clips and Undo
   restored the third. Autosave then persisted two tracks with the three clips.
   Buttons start disabled at the hydrated baseline and toggle correctly.
9. Fade-in drag on the first clip (20 % of the lane) set a 39.58 % overlay on its
   48-beat length; autosave wrote `fadeInBeats: 19` and `fadeInCurve: 1`, and a
   reload restored the overlay and handle position without saving again.

`npx tsc --noEmit` and `npm run check:ui` pass.

## Not covered

- Trim/split are not undoable yet (no undo stack in this shell).
- Fades, clip gain, reverse and clip-level automation are still missing; the
  state supports them (`fadeInBeats`, `fadeOutBeats`, `amplitude`, `reversed`).
- Playback of packaged tracks still needs the encrypted player (see the
  persistence changelog).
