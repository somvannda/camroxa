# CAPTURE GAPS — what was not captured, and why

Companion to `SCREEN_MANIFEST.md` and `SCREENSHOT_INDEX.md`.

**Final state: 64 DONE · 0 PART · 1 OPEN** of 65. Spec through §102, 84 images.

Everything `DONE` has an image and a measured section — including six captured
**negatives** where the screen we expected does not exist (S47 mixer, S50/S51 export
dialog, S54/S56 sharing, S59 conflict, S62 offline).

## One insight worth carrying forward

`Drum & Bass Demo` is a **legacy project**: it cannot export or generate (§77).
Opening an `Untitled Project` from the library fixed both instantly, which is what
cleared S37, S29, S50/S51 and S45. **Any future capture involving export, generation,
takes or plugins must start from a native project.**

## The one that remains

| Screen | State | Exactly what is missing |
|---|---|---|
| S61 credits | OPEN | Needs an account with no credits. Ours has balance, so this cannot be produced honestly. |

### S60 - lyrics moderation refusal (DONE, §102)

Captured on https://suno.com/create while signed in as the reference account. Switched
to **Advanced**, pasted four lines of a known copyrighted song into the lyrics editor,
set style pop rock, piano and a title, then pressed **Create**. Suno answered with a
bottom-centre orange toast:

> **Couldn't generate that.**
> Your lyrics contain copyrighted material. Please change it and try again.

The composer kept the lyrics, style and title, so the refusal is recoverable in place;
there was no dialog, inline field error or navigation. The check runs on submit, after
the draft is accepted. Image: screens/S60-moderation.jpeg (1440 x 900).

## Live-session findings (2026-11-06, signed in)

The gaps were re-exercised with the real Studio. What is now known, and what still needs
an image:

### S44 — Convolution IR (`DONE`, §98)

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

and the image (`screens/S44-convolution-ir-loaded.jpeg`) shows the loaded card: preset
label `Custom`, asset name `Halls · New England Hall`, a single orange impulse trace
(spike at the start, decaying tail) on the slot's time axis, and `Enable trim` still
disabled. §98 has the element-by-element table.

### S30 — warp markers (`DONE`, §97)

Staged exactly as the gap note suggested: an audio clip on an Audio track, the
**Stretch** switch `on` (`role=switch`, `aria-checked=true`), **Transients** selected,
clip editor open, zoom raised two steps, project tempo changed **146 → 108 BPM**.
`screens/S30-warp-markers.jpeg` shows the markers drawing: white pennant heads on the
waveform's top edge, hairline stems, density following transients, clipped to the clip's
bounds. §97 has the measurements and the registry extract below.

The project document contains a real warp-marker registry:

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
the project, not on the clip row. So the model is confirmed: **markers are auto-generated
per clip by the Stretch mode**, and the three modes differ only in which positions they
choose.

### S32 — CC lane (`DONE`, §99)

A generated MIDI clip (from "Write a simple 4-bar bass line") exposes the CC lanes the
spec described, behind the clip editor's **Parameters** button:

```
Velocity   Pitch Bend   Modulation
```

The lanes sit under the note lane and share its x-axis. Evidence from 2026-11-06/07:

- The Modulation lane's paint surface is a canvas with **no React pointer handlers on the
  canvas or its wrapper**, so nothing at the element level receives a gesture.
- With `Modulation` selected on a real MIDI clip, each of these was dispatched at the
  lane: single click, drag, alt-drag, right-click (`contextmenu`) and double-click. The
  project issued **no save request** afterwards and no point elements appeared, so the
  lane did not change.
- Conclusion: the lane is **read-only in this build**; the tabs exist, the lane paints,
  but no gesture edits it. Closed as a documented negative in **§99** (image: the
  existing `S32-modulation-lane-empty.jpeg`).

### Library details confirmed live (for §19.1/§19.2)

- Level-2 toolbar is chips, not a select: `(filter icon)` · `New` · `Liked only` (heart)
  · `In Project` · `Stems` · `Uploads`.
- Song tag strip carries `V6 · <key> · <BPM>` (e.g. `V6 · A minor · 146 BPM`).
- Project ages include the remainder: `5d, 9h ago`, not `5d ago`.
- `New workspace` creates `New workspace — 0 songs` in place, immediately, with no
  dialog.
- Level-1 Workspaces list shows the create row plus **four** workspace rows; workspace
  rows reveal `More` and `Open` on hover, project rows reveal only `Open`. The `More`
  menu was not reached by synthetic input, so its items remain uncaptured.
- `See all` expands in place and becomes `Show less`.
- Uploads is the **same date-grouped list** as songs, with a `Play` per row rather than
  only a filename list. Ours now groups by `created_at` and auditions through the shared
  preview element.
- Double-clicking a song row opens a **song detail rail** (title, `key · BPM · duration ·
  date`, Remix/Like/Dislike/More, ±44 px Play, Info/Stems tabs, Styles with copy + show
  more, Lyrics with copy + show more, Comments and notes). It dismisses the list and does
  not add a clip. Captured as an EXTRA in §100 and implemented as D-018.

**Caveat:** the capture project was edited during this session (audio clip added, tempo
left at **108 BPM**, a generated Bass track, one new default-named workspace). It is an
`Untitled Project`, not `Drum & Bass Demo`.

## If a next session wants to finish it

1. **S61** — only with a genuine trigger. It would be captured as
   "error taxonomy" evidence, not as a screen we can stage. S60 is captured
   (`screens/S60-moderation.jpeg`, §102).

### Recording (G21) — observed with no input device

Not a manifest screen; recorded here because Arm/Record were previously only known as
buttons.

- **Arm** toggles the button's own tooltip between `Arm track for recording` and
  `Disarm track`; there is no other visible state change on the row in this capture.
- **Record** swaps the transport's `Record` for **`Stop recording`** with a small
  `Options` disclosure beside it, and swaps `Play` for **`Pause`**. The clock advances
  while recording; no count-in overlay appeared.
- No microphone permission prompt or error surfaced in the page, and **stopping produced
  no take** on the armed MIDI track (no clip, no take lane, no new text). With no input
  device, the result is silence rather than a failure message.

**Implemented as D-020.** Our build records microphone takes on one armed track
(`MediaRecorder` → upload → `Take N` clip), with no count-in, monitoring, take lanes or
`Options` menu because none of that was captured. The reference's take/render path
remains unobserved; treat D-020 as a documented divergence, not parity.

## Editing caveat

While testing warping, the `Drum & Bass Demo` tempo was changed from **174 → 110 BPM**
and left there. It is a library copy; revert with the tempo popover or `CTRL Z`.

### Take lanes (extra, §101)

The toolbar's first icon (left of `New`) opens nothing under synthetic input; its menu remains uncaptured, so no filter control is invented in our toolbar.


Clicking the track's `Take lanes` section with no clip selected shows the empty state
`Create a clip to see alternate takes here` (`EXTRA-take-lanes-empty.jpeg`). That proves
takes are a **clip-level** stack, but the populated lane (alternate list, active take,
comping) is still uncaptured. Our build has no sections framework, so nothing is
implemented from this yet.
