# B10 remainder — the MIDI overview strip

**Date:** 2026-11-17
**Workstream:** B10 (clip editor / MIDI lanes), the one deltas left after the Stretch-modes and
Clip-Settings work
**Branch:** `feat/midi-overview`
**Worktree:** `C:\Users\Kong Somvannda\AppData\Local\Temp\camxora-res-overview`
**Base:** `origin/main` @ `f23200e8` — *"feat(studio): credits-exhausted modal with our real pack
ladder"* (the worktree was cut at `c5390ef1`; the branch was rebased onto the newer `main` before
finishing, which only needed one conflict in `CLONE_DEFINITION.md` § 5)

**Method:** implementation + tests only. No server started, no port bound, no deploy, no push,
`G:\Developments\Projects\Camxora` was not touched. Playwright was **written but not run** (the
new spec is in the suite for the next run). `npm ci` populated the fresh worktree (272 packages).

---

## 1. Summary

The recorded absence in `CLONE_DEFINITION.md` § 5 — *"MIDI editor has no overview strip"* — is
closed with a working mini-map, not a picture of one:

- **Position:** a 30 px band directly above the piano roll, full panel width, sitting over the
  same 44 px gutter as the keys and the grid. This is where S31 puts it.
- **Anatomy:** zoom −/+ magnifiers at the left (S31), then a recessed track carrying the whole
  clip's notes as a mini piano roll, bar ticks, and a white-outlined window for the visible slice.
- **Behaviour:** click the strip to jump, drag the window to scroll, double-click to zoom at that
  point, `−`/`+` to zoom a step, and keyboard `←/→`, `PageUp/PageDown`, `Home/End`, `=/-` because
  it is a real `role="slider"`.
- **Truthfulness:** the window is derived from `scrollLeft / (clientWidth − 44) / gridWidth` of the
  actual scroll container, so it cannot drift from what is on screen. The strip renders the same
  `shown` note array the grid does, so it updates during drags and velocity edits.
- **One layout fix was required:** the velocity/bend/mod lanes did not follow the grid's
  horizontal scroll (they were drawn in panel pixels, not grid pixels). They now translate with
  the roll, so a scrolled grid and its lanes stay on the same x-axis. Details in § 7.

| Check | Result |
|---|---|
| `npm run typecheck` | clean |
| `npx vitest run` | **409 passed / 409**, 53 files (17 in `studio-midi-editor.test.tsx`, 5 of them new) |
| Playwright | one new spec written, **not executed** |

---

## 2. The reference frame

**Frame:** `docs/studio/reference/screens/S31-midi-clip-editor.jpeg`, paired as
`S31 — "MIDI clip editor"` in `reference/PAIRING.json`. The file is **3200 × 560** — a 2× device
crop of the clip editor panel, not a full page, so the strip has to be read from the crop rather
than from the whole layout.

Reading the crop top to bottom (device px, 2×):

| Band | Extent | What it shows |
|---|---|---|
| (above) | 0–10 | rounded top edge of the previous panel |
| **Overview strip** | ~12–55 | full-width band, a shade lighter than the grid, no outer border; two magnifier glyphs at the far left (`−` then `+`, ≈16 css px each) inside the piano gutter; a 1 px divider under it |
| Ruler | 55–95 | clip-relative bar numbers (11–24 in this scroll position), the loop bracket drawn as rounded blue bars, playhead flag |
| Note grid | 95–165 | 3–4 note rows before the crop ends; the keys column (white key blocks) is ≈36 css px wide here |
| Lane tabs | 165–200 | `Velocity · Pitch Bend · Modulation` |

**What the pixels support, and what they do not.** Position (above the grid, over the gutter),
height (≈28 css px), the lighter surface, the divider and the −/+ pair are all measurable. The
interior of the band reads as flat dark in this exposure and the visible pitch slice of the grid
is empty, so the density marks and the window outline are **not** resolvable from the frame — the
parity report (B, row 31) is what names the content: *"a mini piano-roll overview strip above the
lanes with zoom ±"*. We therefore match the measurable anatomy exactly and render the two parts
the capture cannot show — per-note density and the visible window — from the model, because a
strip without them would be the decorative control the old absence note objected to.

**Deliberate differences from the frame.** The track gets a 1 px inset outline and the window a
white 1 px border so the viewport is legible on our darker panel; the reference band has no
outline visible at this exposure. The zoom glyphs are 20 px hit targets instead of the captured
16 px, to clear the 24 px pointer minimum with the surrounding 30 px row.

---

## 3. What existed before

`StudioMidiEditor.tsx` already had the pieces the absence note said were missing a consumer:

- `zoom` (1–12) multiplies `fitWidth` into a concrete `width`, and `.se-midi-roll` has
  `overflow: auto` with a `position: sticky` 44 px keys column → **horizontal scrolling already
  existed**, it just had no navigator.
- The velocity/bend/mod lanes were **outside** that scroll container and positioned as
  `44 + start / duration × width` inside the panel's own pixels → at any zoom > 1 they no longer
  lined up with the grid, and no amount of scrolling could fix them.

So the brief's "add a scroll container if the layout cannot scroll" branch did not apply. The
real work was (a) the strip and (b) making the lanes share the grid's x-axis so a scrolled window
means the same thing in both places.

---

## 4. Implementation

### 4.1 DOM (all inside `StudioMidiEditor`)

```
.se-midi
├── .se-midi-head
├── .se-midi-tabs
├── .se-midi-overview                       ← new, 30 px
│   ├── .se-midi-overview-zoom              ← 44 px column, matches the gutter
│   │   ├── button  aria-label="Zoom out the piano roll"
│   │   └── button  aria-label="Zoom in the piano roll"
│   └── .se-midi-overview-track   role="slider"
│       ├── .se-midi-overview-tick  (bar lines, capped at 64)
│       ├── .se-midi-overview-notes (aria-hidden)
│       │   └── .se-midi-overview-note × N
│       └── .se-midi-overview-window (aria-hidden)
├── .se-midi-roll  (overflow:auto; keys sticky; onScroll → syncRollView)
├── .se-midi-velocity
│   ├── .se-midi-velocity-baseline
│   └── .se-midi-lane-scroll  (translateX(−scrollLeft))
└── .se-midi-controls
```

The strip is inserted between the lane tabs and the roll, i.e. immediately above the note grid —
the S31 vertical order. The panel's `max-height` moves 360 → 392 px so the added 30 px row cannot
clip the control bar (the panel is `flex: none` in the shell column; the arrangement loses 32 px,
which is inside the captured editor's own proportion).

### 4.2 State

| State | Purpose |
|---|---|
| `rollView = { clientWidth, scrollLeft }` | the roll's real viewport, measured on mount, on scroll, on zoom (`width` dependency) and through a `ResizeObserver` (window `resize` fallback where it does not exist, e.g. jsdom) |
| `overviewDrag` | pointer capture across the window drag; also drives the grabbing cursor |
| `overviewGrab` (ref) | pointer offset inside the window, so picking it up does not snap it |
| `zoomAnchor` (ref) | the clip ratio a zoom step must keep in place; consumed by the `[width]` effect once the new width lands |

### 4.3 The window ↔ scroll mapping

Let `W` = grid width (`fitWidth × zoom`), `C` = `.se-midi-roll` client width, `G` = 44 px gutter
(the sticky keys), `s` = `scrollLeft`.

```
visible   V = clamp(C − G, 0, W)          // grid pixels actually on screen
window ∋ left%  = s / W × 100
window ∋ width% = V / W × 100              // clamped to [2%, 100%] so it stays visible
maxScroll       = W − V                   // equals scrollWidth − clientWidth
aria-valuenow   = maxScroll > 0 ? s / maxScroll × 100 : 0
```

Invariants this buys:

- **Zoom 1 on a short clip:** `V = W` → window is 100 %, `maxScroll = 0`, the strip is inert by
  construction rather than by a special case (no fake navigation).
- **Deep zoom:** `window.left% + window.width% = 100 %` exactly when `s` is at `maxScroll`, so the
  window's right edge meets the strip's right edge at the clip end.
- **Unmeasured (first paint / SSR):** `C = 0` → `V = W` → full-width window, no divide-by-zero.
- **Scroll both ways:** `scrollToRatio(r)` sets `s = clamp(r × W − V/2, 0, W − V)`, i.e. the
  pointer's clip point goes to the centre of the roll; the browser clamps `scrollLeft` and we read
  it back, so state and DOM never disagree.

Zoom anchors work the same way: `applyZoom(next, anchor?)` records `ratio` (the point under the
view centre, or the double-clicked point) plus `viewport = 0.5`, then the `[width]` effect sets
`s = clamp(ratio × W' − 0.5 × V', 0, W' − V')`. That is why `Ctrl =` / the `+` button no longer
jump back to bar 1 when zooming in.

### 4.4 Density marks

Each note becomes a 2 px block: `left = start/duration`, `width = max(0.6%, length/duration)`,
`top = (84 − pitch) / 49` (the editor's `MIDI_MIN_PITCH..MIDI_MAX_PITCH` range), filled with the
clip colour (`clip.color || hsl(var(--accent))`), opacity 0.75. The marks are derived from the
same `shown` array as the grid, so they follow a live note drag, a velocity change and a delete
without extra wiring. Bar ticks are `1/barCount` apart, capped at 64 so a 96-bar clip does not
produce 96 nodes.

### 4.5 CSS

**13 new rules** in `app/globals.css`, next to the existing `.se-midi-*` block: `.se-midi-overview`,
`-zoom` (+ `.se-icon`, `:hover`, `:disabled`), `-track` (+ `.is-dragging`, `:focus-visible`),
`-tick`, `-notes`, `-note`, `-window`, and `.se-midi-lane-scroll`. Two existing rules are edited:
`.se-midi` (`max-height` 392) and `.se-midi-velocity` (`overflow: hidden`). `touch-action: none` on
the track so a touch drag pans instead of scrolling the page.

---

## 5. Interaction

| Gesture | Result |
|---|---|
| Click the strip | that clip point comes to the middle of the roll |
| Drag the window | pan; the grab point is preserved, so it does not jump on pickup |
| Drag outside the window | the pointer re-centres the view (continuous scrub) |
| Double-click | zoom in one step around the clicked point |
| `−` / `+` buttons | zoom one step, keeping the view centre (`disabled` at 1 and 12) |
| `←` / `→` | pan a quarter of the visible width |
| `PageUp` / `PageDown` | pan a full viewport (slider order: PageUp = forward) |
| `Home` / `End` | clip start / clip end |
| `=` / `-` | zoom in/out, same as the panel's `Ctrl =` / `Ctrl -` |

The strip's key handler calls `stopPropagation`, so `←/→` focus-panned the overview instead of
moving the selected notes, and the panel's captured shortcuts still work when the slider is not
focused. Existing note editing is untouched: `addNote`, note dragging, double-click delete,
velocity drags and every `S14` shortcut were not modified, and the unit tests for all of them
still pass.

---

## 6. Accessibility

- The track is `role="slider"`, `aria-orientation="horizontal"`, focusable, with
  `aria-valuemin=0`, `aria-valuemax=100`, `aria-valuenow` = scroll percentage and
  `aria-valuetext` = `Bars 1.0–2.6 of 4.0` for the visible range.
- `aria-label="Clip overview"`; the zoom buttons have distinct names (`Zoom in/out the piano
  roll`) so they do not collide with the footer transport's `Zoom in` / `Zoom out` labels used by
  `tests/e2e/studio-zoom.spec.ts` and `studio-components.test.tsx`.
- Focus is set explicitly on pointer down (`preventDefault` would otherwise suppress it), and
  `:focus-visible` draws a 2 px accent ring.
- Ticks, note marks and the window are `aria-hidden`; the strip's state lives entirely in the
  slider's value.
- `title` gives the pointer affordance in words: *"Drag to scroll the piano roll; double-click to
  zoom here"*.

---

## 7. What changed outside the new strip (and why)

1. **Lanes follow the roll's scroll.** `.se-midi-lane-scroll` wraps the velocity bars and the
   bend/mod SVG and gets `translateX(−scrollLeft)`. The SVG's inline width becomes
   `44 + width` px so it is 1:1 with the grid instead of being stretched to the panel. Lane
   pointer math gained `+ scrollLeft` so the point you click is still the point you get. Without
   this, driving the overview would visibly slide the grid away from its own lane.
2. **`.se-midi` max-height 360 → 392 px** for the new 30 px row (head 34 + tabs 34 + strip 30 +
   roll 172 + lane 64 + controls 36 ≈ 370 px + borders). No test asserted the old value.
3. **`zoomBy` is anchor-aware.** It now routes through `applyZoom`, so button/`Ctrl +/-` zooming
   keeps the centre. `zoomToSelection` (`Z`) keeps its own fit-then-scroll behaviour and now also
   syncs the overview after its `requestAnimationFrame`.
4. **Clip change resets the horizontal scroll** along with selection and zoom.
5. **`MIDI_GUTTER = 44`** replaces the scattered `44` literals in the lane and selection math.

---

## 8. Tests

### Unit (`tests/studio-midi-editor.test.tsx`, +5)

A 8 s clip at 2 s/bar × 96 px = 384 px wide, with the roll's `clientWidth` stubbed to 200 px
(156 grid px after the gutter) and the strip's rect stubbed to 400 px:

| Test | Asserts |
|---|---|
| maps the clip's notes and marks the visible slice | 2 marks at 0 % / 50 %, window 0 % + 40.625 %, `role=slider`, valuetext `Bars 1.0–… of 4.0` |
| scrolls the roll to the point that is clicked | click at 75 % → `scrollLeft = 210` (288 − 78), `aria-valuenow = 92`, `onChangeNotes` not called |
| drags the window without jumping when it is grabbed | window grab at 75 % → no jump; move to 65 % → `scrollLeft = 172`; move after pointerup → unchanged |
| pans from the keyboard so the strip is a real slider | `→` = 39 px (¼ viewport), `End` = 228, `aria-valuenow` 100, `Home` = 0, notes untouched |
| zooms from the strip and keeps the window truthful | `+` → 576 px, window 27.08 %, `scrollLeft = 39`; double-click → 864 px, `scrollLeft = 570`; `−` → 576 px |

### E2E (`tests/e2e/studio-midi.spec.ts`, +1 test — written, **not run**)

`the overview strip maps the clip and drives the roll's scroll`: opens a MIDI clip, adds 2 notes,
asserts 2 overview marks and the slider's initial value, asserts the roll is not scrollable at the
fit zoom (window 100 %), zooms from the strip, asserts the roll becomes scrollable and the window
shrinks, clicks the strip at 85 % and asserts `scrollLeft > 0` and the window moved, uses `End` /
`Home` to check `aria-valuenow` 100 → 0, then adds a third note to prove editing still works.

Everything else (409 tests, 53 files after the rebase onto `main`) is unchanged and green.

---

## 9. Residual limits

- **No screenshot of the result.** Servers and ports are off-limits for this task, so the strip is
  verified by unit geometry and by reading the CSS, not by a capture. `docs/studio/compare/
  ours-midi-editor.png` should be refreshed by the next `scripts/check-clone-parity.mjs` run; the
  strip is 30 px taller than the previous bottom panel content.
- **The reference's exact note marks are unmeasurable** from S31 at this exposure (§ 2). The
  density bars, their 2 px height and the window border are our reading of the parity description,
  not traced pixels.
- **No playhead in the strip.** The captured band has the playhead flag in the ruler, not in the
  strip; the component has no playhead prop and this task did not add one.
- **Adjacent, unchanged:** `.se-midi-velocity-dot` is still unstyled (the class only carries a
  background colour, no size or position), so the captured velocity dots do not render. It is a
  pre-existing gap in the same lane, unrelated to the overview, and was left alone to keep the
  branch to one logical change.
- `origin/main` moved twice while this branch was open. It was rebased onto `f23200e8` before the
  final commit; the only conflict was the § 5 absence row, resolved by keeping `main`'s new
  master-chain row and replacing the overview row.

---

## 10. Files

| File | Change |
|---|---|
| `camxora.com/components/studio/StudioMidiEditor.tsx` | strip markup, scroll/zoom model, slider keyboard, lane scroll sync |
| `camxora.com/app/globals.css` | 13 new rules (strip + lane scroll layer), `max-height` 392 |
| `camxora.com/tests/studio-midi-editor.test.tsx` | +5 tests |
| `camxora.com/tests/e2e/studio-midi.spec.ts` | +1 spec (not run) |
| `docs/studio/CLONE_DEFINITION.md` | § 5 absence row replaced with the shipped behaviour |
| `docs/studio/reports/2026-11-17-midi-overview.md` | this report |
