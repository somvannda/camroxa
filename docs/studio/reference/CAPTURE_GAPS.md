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
| S30 warp markers | PART §94 | The system is captured (Stretch modes with "Markers placed on transients and note starts"), but no marker ticks ever drew — tried at 174 BPM source and at 110 BPM project tempo. Two possibilities recorded: markers need a **stretched** clip (source BPM ≠ project BPM *and* stretch enabled on that clip), or marker drawing is not shipped. |
| S32 CC lane | PART §74 | The `Modulation` lane renders but accepts no drawn points; needs a workflow we have not found (likely a modifier or a right-click). |
| S44 convolution IR | PART §78 | The IR slot opens nothing when clicked; it needs an **impulse-response file** dropped or chosen. |
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

### S30 — warp markers (`PART` → state staged, screenshot pending)

Staged exactly as the gap note suggested: an audio clip on an Audio track, the
**Stretch** switch `on` (`role=switch`, `aria-checked=true`), **Transients** selected,
clip editor open, zoom raised two steps, project tempo changed **146 → 108 BPM**.
No marker DOM exists (the waveform is canvas), so only a screenshot can confirm whether
ticks draw. If they do not, the negative is now much stronger evidence than before:
stretch on + Transients + a 38 BPM tempo change still produced no ticks.

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

1. **S44** — drop any short WAV onto the Convolution slot; if drag-and-drop works the
   card fills in and the screen is done.
2. **S30** — enable stretch on a clip, then change the project tempo by a large step
   *while the clip editor is open*, and inspect the waveform at 2× zoom.
3. **S32** — try right-click, alt-drag and double-click in the lane; one of them is
   the draw gesture.
4. **S60 / S61** — only with a genuine trigger. Both would be captured as
   "error taxonomy" evidence, not as a screen we can stage.

## Editing caveat

While testing warping, the `Drum & Bass Demo` tempo was changed from **174 → 110 BPM**
and left there. It is a library copy; revert with the tempo popover or `CTRL Z`.
