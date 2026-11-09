# MIDI editor — scope (not built)

The MIDI clip editor is the last captured Studio surface that is not in our build. This
is the plan for it; it is **not** a licence to render dead UI. Nothing ships until each
slice has a working model behind it.

Evidence: `reference/screens/S31-midi-clip-editor.jpeg` (3200×560, 2× DPR),
`S63-1280px.jpeg`, `S64-1024px.jpeg`. Feature ids: `SUNO_STUDIO_FEATURE_INVENTORY.md`
§6 (MIDI-001…MIDI-006).

## Built (this branch)

- **Model** — `lib/studio-midi.ts`: notes on `clip.midi.notes`, MIDI-number to frequency,
  names, sanitising and quantise.
- **Entry/panel** — Add-track → MIDI creates a four-bar clip and opens a bottom editor
  (piano gutter, note grid, velocity lane, tabs, control bar). Click adds a snapped note,
  drag moves it (time + pitch), double-click deletes.
- **Playback and export** — synth voices are scheduled into the same per-track input for
  live playback and for the offline renderer, so chains, mute/solo and volume apply.
- **Tests** — `tests/studio-midi.test.ts` (model) and `tests/e2e/studio-midi.spec.ts`
  (panel geometry, add/move/delete, persistence, reopen).

Still open: velocity editing in the lane, transpose/octave, key/scale controls, and the
pitch-bend/modulation lanes (tabs are disabled with reasons).

## What the capture shows

From S31 (divide pixel values by 2 for CSS px) and the bottom panel in S64:

| Region | Capture | Notes |
|---|---|---|
| Panel | bottom sheet under the arrangement, full width above the footer | S64: starts ≈ y584 at 1024 wide |
| Piano gutter | note rows at left, dark, no labels visible in S31 crop | S64 shows two octaves of rows |
| Ruler | same bar thinning as the main ruler (labels every 2+ bars) | reuse `StudioTimeline` ruler rules |
| Tabs | `Velocity` (active, white underline) · `Pitch Bend` · `Modulation` | S31: 34 CSS px tall, 13 px labels |
| Velocity lane | vertical sticks with dot caps on a blue baseline | 180 CSS px including the tab/control gaps |
| Control bar | power toggle · `Loop Off` · `Quantize 1/2 ▾` · `Key C Maj` · `Scale Off` · `View All` pill | S31: single 34 px row; C is yellow in the key value |
| Clip header | the MIDI clip is a normal clip row above the piano roll | clip label + note blocks |

## Decisions needed before the first slice

1. **Instrument.** WebAudio oscillator per note (cheap, ours) or a sampled instrument?
   Recommend a simple sine/triangle synth with an ADSR gain, because it needs no assets.
2. **Export.** MIDI has to be rendered by the same offline renderer as audio clips to be
   honest. Recommend synthesising notes into the clip buffer before the chain, so mix,
   range and per-track exports keep working.
3. **Key/scale.** We do not have key/BPM detection (D-016 hit the same wall). Recommend
   `Key` and `Scale` default to the project key setting we add explicitly, not detection.
4. **Where MIDI is enabled.** The Add-track menu currently disables MIDI with a reason.
   Enabling it is the entry point; the menu should keep Upload below it.

## Data model (proposal)

```ts
type MidiNote = { id: string; pitch: number; start: number; length: number; velocity: number };

type MidiClip = {
  id: string;
  title?: string;
  start: number;      // timeline position, seconds
  duration: number;   // clip length
  color?: string;
  midi: {
    notes: MidiNote[];
    /** Optional lanes captured by the tabs; absent means flat. */
    pitchBend?: Array<{ at: number; value: number }>;
    modulation?: Array<{ at: number; value: number }>;
  };
};
```

Clips live in the same `lanes` array as audio clips with a discriminant, so selection,
drag, split, trim and undo keep working through the existing paths.

## Slices (each shippable on its own)

1. **Model + panel shell.** MIDI track creation, an empty MIDI clip, and the bottom panel
   with piano gutter, ruler, tabs and a velocity lane drawn from notes (read-only).
   Tests: unit for note/pitch↔row math; pixel gate for the panel geometry at 1689×1277.
2. **Note editing.** Draw, move, resize and delete notes on the grid; velocity lane edits
   set velocity. Tests: e2e for each gesture, undo/redo covered by the document writer.
3. **Quantize, transpose, octave, key/scale.** Quantize menu (1/1…1/32, triplets), octave
   up/down, key + scale selection. Tests: unit for quantize math, e2e for the menus.
4. **Playback + export.** Synth voices scheduled with the transport, offline render for
   mix/range/per-track exports. Tests: existing export e2e plus a rendered-buffer check.

## Non-goals for the first pass

- MIDI file import/export (TRK-004) — separate feature.
- Automation of plugin params from MIDI.
- Piano-roll zoom beyond the captured `View All` / bar-fit zoom.

## Risks

- The MIDI panel changes the shell height; the dock and footer already compete for the
  bottom. S64 shows the MIDI panel **replacing** the plugin dock area while open, so the
  shell needs a `midiOpen` state that hides the dock.
- Export correctness is the expensive part; slice 4 must not ship without it or the
  feature becomes a toy.
- Every coordinate above is approximate; re-measure against S31/S64 at implementation
  time, as the capture contract requires.
