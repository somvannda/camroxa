# CAPTURE GAPS — what was not captured, and why

Companion to `SCREEN_MANIFEST.md` and `SCREENSHOT_INDEX.md`.

**Final state: 60 DONE · 3 PART · 2 OPEN** of 65. Spec through §96, 69 images.

Everything `DONE` has an image and a measured section — including six captured
**negatives** where the screen we expected does not exist (S47 mixer, S50/S51 export
dialog, S54/S56 sharing, S59 conflict, S62 offline).

## One insight worth carrying forward

`Drum & Bass Demo` is a **legacy project**: it cannot export or generate (§77).
Opening an `Untitled Project` from the library fixed both instantly, which is what
cleared S37, S29, S50/S51 and S45. **Any future capture involving export, generation,
takes or plugins must start from a native project.**

## The 5 that remain

| Screen | State | Exactly what is missing |
|---|---|---|
| S30 warp markers | PART §94 | The system is captured (Stretch modes with "Markers placed on transients and note starts"). **Live 2026-11-06:** markers *are* generated — an audio clip with stretch on + Transients produced a `markersRegistry` entry with 358+ source→timeline marker pairs. What is still missing is only the rendering check: no marker ticks were seen on the waveform canvas, and a screenshot is needed to close that. |
| S32 CC lane | PART §74 | The `Modulation` lane renders but accepts no drawn points; the lane tabs (`Velocity` / `Pitch Bend` / `Modulation`) were reached live on 2026-11-06 behind the clip editor's **Parameters** button. The lane canvas has no React pointer handlers, so the draw gesture is not a plain click/drag. Needs the gesture or a project with CC data. |
| S44 convolution IR | PART §78 | **Live 2026-11-06:** the IR slot is fed by the `Impulse Response` button in the preset row, which opens an 11-entry IR library (halls/rooms/chambers/outdoors/ambiences/plates). Selecting one flips the card to `Custom · Halls · New England Hall` and draws the stereo waveform. Screenshot of the loaded card is the remaining evidence. |
| S60 moderation | OPEN | Needs a policy-violating prompt. **Do not fabricate** — capture it only if it happens naturally. |
| S61 credits | OPEN | Needs an account with no credits. Ours has balance, so this cannot be produced honestly. |

## Live-session findings (2026-11-06, signed in)

The gaps were re-exercised with the real Studio. What is now known, and what still needs
an image:

### S44 — Convolution IR (`PART` → content found, screenshot pending)

The IR slot is fed by the **`Impulse Response`** button in the card's preset row (the
one that reads `None`), not by drag/drop and not by clicking the slot itself. It opens
an IR library:

```
Halls · New England Hall    Halls · Amber Hall      Halls · Boreal Chapel
Rooms · Timber Room         Rooms · Terrazzo Room   Chambers · La Brea Chamber
Chambers · Grotto           Outdoors · Sequoia Basin
Ambiences · Wide Air        Plates · Aria Plate     Plates · Velvet Plate
```

Selecting one flips the card from `NO ASSET LOADED` to:

```
Convolution
Custom
Halls · New England Hall
Mix   Gain   Pre   Width
```

and the trim-timeline widget now draws two stereo waveform canvases (three canvases in
the card) with the `Enable trim` switch still disabled. The time ruler over the slot is
`0s / 1s / 2s / 3s`, as captured. Open question for the image: how the tail/trim handles
render once the waveform has data.

### S30 — warp markers (`PART` → marker model found, screenshot pending)

Staged exactly as the gap note suggested: an audio clip on an Audio track, the
**Stretch** switch `on` (`role=switch`, `aria-checked=true`), **Transients** selected,
clip editor open, zoom raised two steps, project tempo changed **146 → 108 BPM**.

The project document then contains a real warp-marker registry:

```json
"markersRegistry": {
  "warp_285c271949a146b2de63674e759b8f50": {
    "0.0029400000000000003": -0.01088568538340112,
    "0.8431500000000001": 1.9948734628594622,
    "1.05207": 2.493609732662129,
    ...
    "176.96218": 430.49772960
  }
}
```

At least **358 markers** were generated for the clip, spanning 0 → ~177 beats (source
positions) mapped to -0.01 → 430.5 seconds of timeline. The key is the marker's source
position, the value its timeline time; the registry is keyed `warp_<hash>` and lives on
the project, not on the clip row. So the model S30 was missing is confirmed: **markers
are auto-generated per clip by the Stretch mode**, and the three modes differ only in
which positions they choose. No marker DOM exists (the waveform is canvas), so the
remaining question — and the only reason this stays `PART` — is whether ticks are drawn
on the waveform at that zoom.

### S32 — CC lane (`PART` → tabs reached, draw gesture still unknown)

A generated MIDI clip (from "Write a simple 4-bar bass line") exposes the CC lanes the
spec described, behind the clip editor's **Parameters** button:

```
Velocity   Pitch Bend   Modulation
```

The lanes sit under the note lane and share its x-axis. The Modulation lane's paint
surface is a canvas with **no React pointer handlers on the canvas or its wrapper**, so
the draw gesture is not a plain click/drag on the canvas element. Still unknown: whether
points can be drawn at all.

### Library details confirmed live (for §19.1/§19.2)

- Level-2 toolbar is chips, not a select: `(filter icon)` · `New` · `Liked only` (heart)
  · `In Project` · `Stems` · `Uploads`.
- Song tag strip carries `V6 · <key> · <BPM>` (e.g. `V6 · A minor · 146 BPM`).
- Project ages include the remainder: `5d, 9h ago`, not `5d ago`.
- `New workspace` creates `New workspace — 0 songs` in place, immediately, with no
  dialog.
- The level-1 Workspaces list shows the create row plus **four** workspace rows.

**Caveat:** the capture project was edited during this session (audio clip added, tempo
left at **108 BPM**, a generated Bass track, one new default-named workspace). It is an
`Untitled Project`, not `Drum & Bass Demo`.

## If a next session wants to finish them

1. **S44** — with the window visible, screenshot the Convolution card after selecting
   `Halls · New England Hall` (state already reachable). One image closes it.
2. **S30** — same session: select the audio clip, open Clip editor, keep `Transients`,
   and screenshot the waveform at 2×. Markers are confirmed in the document; the image
   decides whether ticks draw (DONE) or whether the system is model-only (documented
   negative).
3. **S32** — the lane tabs are reached; the draw gesture is not a plain click/drag on
   the canvas. Try modifier-drag and right-click on the lane's wrapper, or open a
   project that already has CC data.
4. **S60 / S61** — only with a genuine trigger. Both would be captured as
   "error taxonomy" evidence, not as a screen we can stage.

## Editing caveat

While testing warping, the `Drum & Bass Demo` tempo was changed from **174 → 110 BPM**
and left there. It is a library copy; revert with the tempo popover or `CTRL Z`.
