# Manual QA checklist — W5 (independent walkthrough)

**Date:** 2026-11-17
**Prepared by:** W5-prep agent (planning only)
**Branch:** `qa/manual-plan`
**Base:** `origin/main` `4abff799` (while preparing, `main` advanced to `a6dafa2c`; those two
commits are docs-only W4 evidence — `git diff --stat` over `camxora.com/{components/studio,lib,app/studio,app/globals.css}`
is empty, so this enumeration still describes the code)
**Status:** ready to execute — nothing was run, no server was started, no port was opened.

This document turns Agent A's ad-hoc walkthrough into an **enumerable** checklist. Every row below
was derived by reading the code at the base commit, not from memory. The executing agent (W5,
`qa/manual-deep`) works **one area at a time**, ticks the box, and records PASS / FAIL / N-A plus a
one-line note where the expected result did not happen.

It deliberately contains **no** commands that start a server: execution assumes the full stack is
already up (owned by W4/`:3103`), per `RESIDUAL_VERIFICATION_PLAN.md` §3 Wave 2.

---

## 0. How to run this

1. **Fixture first.** The checks name three fixtures; create them once, then keep them for every area.

   | Fixture | Contents | Needed for |
   |---|---|---|
   | **P0** | empty project (`title: "Untitled project"`, 120 BPM, 4/4, no tracks) | onboarding, empty states |
   | **P1** | 120 BPM 4/4. Track 1 `Drums` (2 audio clips from **one generated song**, so `songId` is set, arranged so clip A ends before clip B starts), Track 2 `Bass` (**MIDI clip**, ≥ 8 notes, ≥ 2 bars), Track 3 `Vox` (**uploaded** audio clip, no `songId`), Track 4 `Scratch` (hidden + muted, 1 clip). Track 1 chain = Compressor → Reverb. | nearly everything |
   | **P2** | copy of P1 where the Track 1 clip has been **Extend**-ed once (so it has `sourceAudioUrl` + a `takes` stack) | Heal Edits, take lanes |

2. **Two sizes minimum per area.** Run every table at **1689×1277** first; the viewport table (§E)
   then re-runs the marked rows at the other three sizes.
3. **Screenshots.** Name them `<AREA>-<ID>-<viewport>.png` (e.g. `C-C04-1689x1277.png`). A FAIL
   without a screenshot is not evidence.
4. **Multi-client surfaces.** Presence avatars and remote playheads need a second signed-in
   browser profile; they are not given their own rows (see G-8). Run them only if a second
   profile is available, and record N-A otherwise.
5. **Do not "fix while testing".** Record the delta; the plan's §5 report classifies deltas as
   layout / state / absence / provider.

Column meaning: **Evidence / selector** is the DOM hook or the visible string to assert on. Selectors
are the real class names and `aria-label` values in the components named in each area's preface.

---

## 1. Plugin registry — reference enumeration

Source: `camxora.com/lib/studio-plugins.ts` (data), `components/studio/StudioPluginDock.tsx` (render),
`lib/studio-plugin-chain.ts` (mutations). Registry order is the catalogue order and is asserted in
`B-03`. `tier` decides knob position (`primary` first, `secondary` after) and size class.

Legend: `unit` is the readout suffix; `choices` means the control renders as a `<select>` instead of
a knob; `tempoSynced` is declared on Delay ▸ Time but **no render path reads it** (see §G, flag G-2).

### 1.1 Compressor — id `compressor`

Description: “Classic dynamics compressor: threshold, ratio, and knee set how hard peaks are…”
Modes: none. Asset slot: none. Presets: **Vocal**, **Drum Bus**, **Gentle**.

| Param | Label | Min | Max | Default | Unit | Tier |
|---|---|---|---|---|---|---|
| `threshold` | Thresh | −60 | 0 | −18 | db | primary |
| `ratio` | Ratio | 1 | 20 | 4 | ratio | primary |
| `knee` | Knee | 0 | 40 | 6 | db | primary |
| `attack` | Atk | 0 | 200 | 10 | ms | primary |
| `release` | Rel | 5 | 1000 | 120 | ms | primary |
| `gain` | Gain | −12 | 24 | 0 | db | secondary |

Card extras: live transfer-curve SVG (`aria-label="Compressor transfer curve"`) and a **Sidechain**
menu (None / every other track × Pre-fx / Post-fader).

### 1.2 Convolution — id `convolution`

Description: “Places the signal in a sampled real space: load an impulse response, then shape it…”
Modes: none. Asset slot: `irAssetId`, label **Impulse response**, empty label **No asset loaded**
(rendered uppercase in the button: `NO ASSET LOADED`). Presets: none.

| Param | Label | Min | Max | Default | Unit | Tier |
|---|---|---|---|---|---|---|
| `mix` | Mix | 0 | 100 | 50 | % | primary |
| `gain` | Gain | −24 | 24 | 0 | db | primary |
| `pre` | Pre | 0 | 200 | 0 | ms | secondary |
| `width` | Width | 0 | 200 | 100 | % | secondary |

Card extras: IR envelope SVG, grouped picker (`role="menu" aria-label="Impulse responses"`),
**Design response.** row only when Settings ▸ Content ▸ Advanced content is on.

### 1.3 Delay — id `delay`

Description: “Echo with feedback and mix, free-running in milliseconds or synced to the beat…”
Modes: **Time** (`time`) · **Tempo** (`tempo`). Asset slot: none.
Presets: **Slap**, **Eighth**, **Dub**.

| Param | Label | Min | Max | Default | Unit | Tier |
|---|---|---|---|---|---|---|
| `time` | Time | 1 | 2000 | 350 | ms | primary (`tempoSynced`) |
| `feedback` | Feedback | 0 | 95 | 35 | % | primary |
| `mix` | Mix | 0 | 100 | 25 | % | primary |
| `lowCut` | Low Cut | 20 | 2000 | 120 | hz | secondary |
| `highCut` | High Cut | 1000 | 20000 | 12000 | hz | secondary |

### 1.4 Distortion — id `distortion`

Description: “A comprehensive distortion / waveshaper: drive into a pre-tilt tone stage, six…”
Modes: **Hard** · **Fold** · **Align** · **Sine** · **Crush**. Asset slot: none. Presets: none.

| Param | Label | Min | Max | Default | Unit | Tier |
|---|---|---|---|---|---|---|
| `drive` | Drive | 0 | 100 | 30 | % | primary |
| `tilt` | Tilt | −100 | 100 | 0 | — | primary |
| `bass` | Bass | −24 | 24 | 0 | db | secondary |
| `freq` | Freq | 20 | 20000 | 800 | hz | secondary |

### 1.5 EQ — id `eq`

Description: “Four-band parametric EQ: per-band frequency, gain, Q, filter shape and enable on a shared curve.”
Modes: none. Asset slot: none. Presets: none. The card is custom: band selector, enable switch, six
filter-shape buttons, a shared curve, then Freq / Q / Gain for the selected band.

| Param | Label | Min | Max | Default | Unit | Tier |
|---|---|---|---|---|---|---|
| `band1.freq` | Freq | 20 | 20000 | 1000 | hz | primary |
| `band1.q` | Q | 0.1 | 18 | 1 | — | primary |
| `band1.gain` | Gain | −24 | 24 | 0 | db | primary |
| `band1.type` | Shape | 0 | 5 | 1 | — | primary |
| `band1.on` | On | 0 | 1 | 1 | — | primary |
| `band2.*` | Freq / Q / Gain / Shape / On | 20–20000 / 0.1–18 / −24–24 / 0–5 / 0–1 | | 200 / 1 / 0 / 1 / 1 | hz / — / db / — / — | primary |
| `band3.*` | Freq / Q / Gain / Shape / On | 20–20000 / 0.1–18 / −24–24 / 0–5 / 0–1 | | 4000 / 1 / 0 / 1 / 1 | hz / — / db / — / — | primary |
| `band4.*` | Freq / Q / Gain / Shape / On | 20–20000 / 0.1–18 / −24–24 / 0–5 / 0–1 | | 10000 / 1 / 0 / 1 / 1 | hz / — / db / — / — | primary |

Shape values (button order, `aria-label`): 0 `Low cut` · 1 `Bell` · 2 `High shelf` ·
3 `Low shelf` · 4 `High cut` · 5 `Notch`.

### 1.6 Gate — id `gate`

Description: “Noise gate: silences the signal below the threshold, with floor, attack, hold, and…”
Modes: none. Asset slot: none. Presets: **Tight**, **Slow**.

| Param | Label | Min | Max | Default | Unit | Tier |
|---|---|---|---|---|---|---|
| `threshold` | Threshold | −80 | 0 | −45 | db | primary |
| `floor` | Floor | −80 | 0 | −60 | db | secondary |
| `attack` | Attack | 0 | 50 | 2 | ms | secondary |
| `hold` | Hold | 0 | 500 | 50 | ms | secondary |

### 1.7 Limiter — id `limiter`

Description: “Brickwall lookahead limiter: drives the signal into a fixed ceiling with lookahead…”
Modes: none. Asset slot: none. Presets: **Loud**, **Transparent**.

| Param | Label | Min | Max | Default | Unit | Tier |
|---|---|---|---|---|---|---|
| `lookahead` | Lookahead | 0 | 20 | 3 | ms | primary |
| `preGain` | Pre Gain | −12 | 24 | 0 | db | primary |
| `attack` | Attack | 0 | 50 | 1 | ms | secondary |
| `release` | Release | 5 | 500 | 60 | ms | secondary |

### 1.8 Reverb — id `reverb`

Description: “Algorithmic reverb with time, mix, width, damping, predelay, and low/high cut…”
Modes: none. Asset slot: none. Presets: **Room**, **Hall**, **Plate**.

| Param | Label | Min | Max | Default | Unit | Tier |
|---|---|---|---|---|---|---|
| `time` | Decay | 0.2 | 20 | 2.4 | s | primary |
| `mix` | Mix | 0 | 100 | 25 | % | primary |
| `width` | Width | 0 | 200 | 100 | % | secondary |
| `damping` | Damping | 0 | 100 | 40 | % | secondary |
| `predelay` | Predelay | 0 | 250 | 20 | ms | secondary |
| `lowCut` | Low Cut | 20 | 2000 | 120 | hz | secondary |
| `highCut` | High Cut | 1000 | 20000 | 14000 | hz | secondary |

### 1.9 Rhythm Gate — id `rhythmGate`

Description: “Transport-synced rhythmic gate. Rate picks the division, depth sets the cut, attack/release shape it.”
Modes: none. Asset slot: none. Presets: none. Migrated from the legacy `chorus` id.

| Param | Label | Min | Max | Default | Unit | Tier | Choices |
|---|---|---|---|---|---|---|---|
| `rate` | Rate | 0 | 2 | 1 | — | primary | `0` 1/16 · `1` 1/8 · `2` 1/4 |
| `depth` | Depth | 0 | 1 | 0.75 | % (0–1 renders 0–100 %) | primary | — |
| `mix` | Mix | 0 | 1 | 0.65 | % (0–1 renders 0–100 %) | primary | — |
| `attack` | Atk | 0.01 | 0.45 | 0.12 | — | secondary | — |
| `release` | Rel | 0.01 | 0.45 | 0.22 | — | secondary | — |

### 1.10 Stereo Utility — id `stereoUtility`

Description: “Balance, width and mono bass: keeps the low end centred and shapes the stereo image.”
Modes: none. Asset slot: none. Presets: none.

| Param | Label | Min | Max | Default | Unit | Tier |
|---|---|---|---|---|---|---|
| `level` | Level | −24 | 12 | 0 | db | primary |
| `width` | Width | 0 | 200 | 150 | % | primary |
| `pan` | Pan | −100 | 100 | 0 | — | primary |
| `bassMono` | Bass Mono | 20 | 300 | 120 | hz | secondary |

### 1.11 Preset behaviour (all plugins)

- Preset menu rows, in order: **Clear all settings** (class `danger`) → **Save preset…** →
  (inline name + Save when chosen) → **Default** → starter presets (only where defined) → user presets.
- Header label shows `entry.presetName`, or **Custom** when `entry.dirty` is true; dirty also reveals
  the **Update** button.
- `‹` / `›` stepper walks `[Default, …starter, …user]`; it is hidden on designed (custom) slots.
- Selecting a preset replaces the whole parameter map and clears `dirty`; `Clear all settings` applies
  the plugin's default map but names the preset **“Custom”**.

---

## A. Entry, gates and chrome — 16 checks

Components: `app/studio/(public)/page.tsx`, `app/studio/editor/page.tsx`,
`components/studio/StudioEditorShell.tsx` (lines 5296–5330), `app/globals.css` `.se-desktop-gate`.

| ID | Area | Action | Expected result | Evidence / selector | ☐ |
|---|---|---|---|---|---|
| A-01 | Entry | Open `/studio` signed **out** | Marketing page renders (no project grid, no "Your projects") | `.studio-home` absent; `StudioMarketing` copy | ☐ |
| A-02 | Entry | Open `/studio` signed **in** | "Your projects" + New project + Create a song | `h1` = `Your projects`; `.studio-home-actions` | ☐ |
| A-03 | Entry | Open `/studio/editor` signed **out** | Gate card: `Studio` / `Sign in to open a project.` + Sign in button | `.se-gate h1`, `a.btn-primary[href^="/login"]` | ☐ |
| A-04 | Entry | Open `/studio/editor` with no `?project=` | Gate card: `No project selected` / `Choose a project from the Studio home.` | `.se-gate` (second branch) | ☐ |
| A-05 | Entry | Open `/studio/editor?project=P1` | `Loading project…` then the shell appears; no flash of the empty-state onboarding | `.se-loading` → `.se-shell`; `aria-live="polite"` | ☐ |
| A-06 | Entry | Reload that URL | Project title, BPM, signature and tracks all return | `.se-chip`, `input[aria-label="Tempo in BPM"]`, `.se-track` count = 4 | ☐ |
| A-07 | Entry | Open `/studio/editor?project=<random-uuid>` | An error is surfaced, editor does not hang on "Loading project…" | `.se-error[role="alert"]` | ☐ |
| A-08 | Entry | Open `/studio/editor/classic` | Legacy editor renders (linked from the footer in the reference layout) | route exists, no 404 | ☐ |
| A-09 | Chrome | Check landmarks on the editor | Exactly one `role="main"`; floating menus live in `role="region" aria-label="Editor menus"` | `[role="main"]` count = 1; `[aria-label="Editor menus"]` | ☐ |
| A-10 | Chrome | Verify the four editor bands | Header, body (tracks + timeline), bottom panel, footer all visible, no overlap | `.se-head`, `.se-body`, `.sp-dock`, `.se-foot` | ☐ |
| A-11 | Chrome | Body background / shell height | Shell fills the viewport exactly; no page scrollbar on the shell | `.se-shell{height:100dvh;overflow:hidden}` | ☐ |
| A-12 | Chrome | Screen-reader-only project title | Project name is announced once as the level-1 heading | `.se-sr-only` inside `.se-body` | ☐ |
| A-13 | Chrome | Tab through the editor from the project chip | Focus order follows header → tracks → timeline → prompt → footer; no focus trap outside dialogs | `Tab` × 20, capture each `document.activeElement` | ☐ |
| A-14 | Chrome | Verify default landing band | Bottom panel open (`2` toggles it off/on), assistant and library closed | `.sp-dock` present; `.se-assistant` absent; `.se-library` absent | ☐ |
| A-15 | Chrome | Check the toast surface | Toast appears bottom-right with a dismiss ✕ labelled `Dismiss export message` | `.se-toast[role="status"]` | ☐ |
| A-16 | Chrome | Check the freshness guarantee | After any successful save, no stale "Loading project…" chip remains | `.se-loading` absent | ☐ |

---

## B. Plugins — every plugin, every parameter — 138 checks

Components: `components/studio/StudioPluginDock.tsx`, `components/studio/ParamKnob.tsx`,
`components/studio/StudioMasterDock.tsx`, `components/studio/StudioIRDesigner.tsx`,
`components/studio/StudioWavetableDesigner.tsx`, `lib/studio-plugin-chain.ts`.
Run with **Track 1 selected** unless the row says otherwise. Fixture chain: Compressor → Reverb.

### B1. Dock chrome and catalogue — 22 checks

| ID | Area | Action | Expected result | Evidence / selector | ☐ |
|---|---|---|---|---|---|
| B-01 | Dock | Select a track with an empty chain | Rail shows `No effects on this track yet.` + **Add effect** | `.sp-empty`, `.sp-add-inline` | ☐ |
| B-02 | Dock | Select Track 1 (chain fixture) | Two slots in signal order: Compressor, Reverb | `.sp-slot` count = 2; `aria-label="Compressor slot 1"`, `"Reverb slot 2"` | ☐ |
| B-03 | Catalogue | Press **Add effect** | Modal dialog titled `Add a track plugin`; search focused; ✕ and ⋯ present | `.sp-dialog[role="dialog"]`, `#sp-catalog-title`, `autoFocus` input | ☐ |
| B-04 | Catalogue | Count the `Audio effects` cards | Exactly 10, in registry order: Compressor, Convolution, Delay, Distortion, EQ, Gate, Limiter, Reverb, Rhythm Gate, Stereo Utility | `.sp-catalog .sp-card .sp-card-name` | ☐ |
| B-05 | Catalogue | Inspect one card | Each card shows a preview trace + 3 mini knobs, the name, and the description string from §1 | `.sp-card-preview`, `.sp-card-desc` | ☐ |
| B-06 | Catalogue | Type `rev` in search | Only Reverb remains | `.sp-catalog .sp-card` count = 1 | ☐ |
| B-07 | Catalogue | Search a word that only appears in a description (e.g. `brickwall`) | Limiter matches (search is name **or** description, case-insensitive) | result name = `Limiter` | ☐ |
| B-08 | Catalogue | Search `zzzz` | `No effects match “zzzz”.` and no cards | `.sp-none` | ☐ |
| B-09 | Catalogue | Click a card's **Learn** chip | Plugin is **not** added; dialog stays open | `event.stopPropagation` on `.sp-card-learn` | ☐ |
| B-10 | Catalogue | Open the ⋯ menu | One row: `Create new plugin` | `.sp-ir-menu[aria-label="Catalogue options"]` | ☐ |
| B-11 | Catalogue | Check the `My plugins` section | `Create new plugin` card with a `BETA` badge and description `Describe it in the prompt bar` | `.sp-create`, `.sp-card-badge` | ☐ |
| B-12 | Catalogue | Add **Delay** from the catalogue | Dialog closes, query resets, Delay appends as slot 3 | `.sp-slot` count = 3; `aria-label="Delay slot 3"` | ☐ |
| B-13 | Catalogue | Re-open and add the **same plugin** again | A second, independent slot appears (same plugin twice is legal) | two `Delay slot *` articles with different `key` | ☐ |
| B-14 | Dock | Inspect the empty rail add row | `Add effect` button + up to 3 ghost suggestions | `.sp-empty-rail`, `.sp-add`, `.sp-ghost` | ☐ |
| B-15 | Dock | Check ghost suggestions on the fixture chain | Ghosts exclude Compressor and Reverb (already present) and show at most 3 | `.sp-ghost` names ∉ {Compressor, Reverb} | ☐ |
| B-16 | Dock | Click a ghost suggestion | That plugin is appended directly, no dialog | chain length +1; matching name | ☐ |
| B-17 | Dock | Read the dock accessible name | `Plugins for Drums` | `section.sp-dock[aria-label]` | ☐ |
| B-18 | Dock | Inspect a slot header | Colour dot, name, preset stepper + preset name, bypass, ‹ › move, pop-out, ✕ | `.sp-slot-head` children in that order | ☐ |
| B-19 | Dock | Check all knob readouts | Every knob shows label **and** the formatted value (db 1 dp, hz as `khz` at ≥1000, ms integer, s 1 dp, % integer; trailing zeros are dropped, so `4` not `4.0`) | `.sp-knob-readout` | ☐ |
| B-20 | Dock | Hover a bypassed slot's controls | All knobs/selects disabled (`disabled` attribute), slot dimmed `.is-bypassed` | `.sp-slot.is-bypassed` | ☐ |
| B-21 | Dock | Resize to 1689 width with 4 slots | Rail scrolls horizontally; slots keep `width:448px` and never wrap | `.sp-rail` overflow-x, `.sp-slot` widths | ☐ |
| B-22 | Dock | Check the pop-out affordance per window mode | `toggle` → per-slot pop-out button; `panels` → none and all docked; `windows` → all floating | `aria-label` `Pop out X` / `Dock X`; `.sp-slot.is-popped` | ☐ |

### B2. Compressor — 8 checks

| ID | Area | Action | Expected result | Evidence / selector | ☐ |
|---|---|---|---|---|---|
| B-23 | Compressor | Read the six defaults on a fresh slot | Thresh −18db, Ratio 4, Knee 6db, Atk 10ms, Rel 120ms, Gain 0db | inputs `aria-label` Thresh/Ratio/Knee/Atk/Rel/Gain | ☐ |
| B-24 | Compressor | Check tier order | Primary five first, then Gain last (secondary) | `.sp-knob-grid` DOM order | ☐ |
| B-25 | Compressor | Sweep Thresh to both ends | Clamps at −60 and 0; readout follows | `input[aria-label="Thresh"]` | ☐ |
| B-26 | Compressor | Sweep Ratio to 1 and 20 | Readout shows `1` / `20` (unitless params keep one decimal at most); no NaN | `aria-valuetext` | ☐ |
| B-27 | Compressor | Watch the transfer curve while dragging Thresh | Curve knee/dot move with the value, no reflow | `svg[aria-label="Compressor transfer curve"]` | ☐ |
| B-28 | Compressor | Open **Sidechain** | Menu shows `None`, then per track `X — Pre-fx` and `X — Post-fader`; current choice highlighted | `[aria-label="Sidechain"]`, `.sp-sidechain-menu` | ☐ |
| B-29 | Compressor | Pick `Bass — Pre-fader`/Post-fader | Button label becomes `<Track> — Post-fader`; menu closes | `.sp-sidechain button span` | ☐ |
| B-30 | Compressor | Set sidechain back to None | Label returns to `None`; no ducking spec remains in the document | `.sp-sidechain`, saved JSON | ☐ |

### B3. Convolution — 7 checks

| ID | Area | Action | Expected result | Evidence / selector | ☐ |
|---|---|---|---|---|---|
| B-31 | Convolution | Read defaults | Mix 50%, Gain 0db, Pre 0ms, Width 100% | `aria-label` Mix/Gain/Pre/Width | ☐ |
| B-32 | Convolution | Check the empty asset slot | Button label `NO ASSET LOADED`; SVG `aria-label="No asset loaded"`; dashed flat line | `.sp-ir-picker button`, `svg.sp-ir` | ☐ |
| B-33 | Convolution | Open the IR picker | `role="menu" aria-label="Impulse responses"`, grouped by category; categories expand/collapse | `.sp-ir-menu`, `.sp-ir-cat[aria-expanded]` | ☐ |
| B-34 | Convolution | Choose an IR | Button shows the IR label; envelope + `s` ticks render; slot marked dirty (`Custom`) | `svg.sp-ir-wave`, `.sp-preset` = `Custom` | ☐ |
| B-35 | Convolution | Press Escape / click outside while the picker is open | Menu closes, nothing is applied | `document` listeners in `ConvolutionCard` | ☐ |
| B-36 | Convolution | With Advanced content **off**, open the picker | No `Design response.` row | `.sp-ir-menu` rows | ☐ |
| B-37 | Convolution | With Advanced content **on**, click `Design response.` | IR Designer dialog opens (see B-119) | `[aria-label="Impulse response designer"]` | ☐ |

### B4. Delay — 6 checks

| ID | Area | Action | Expected result | Evidence / selector | ☐ |
|---|---|---|---|---|---|
| B-38 | Delay | Read defaults | Time 350ms, Feedback 35%, Mix 25%, Low Cut 120hz, High Cut 12khz | `aria-label` Time/Feedback/Mix/Low Cut/High Cut | ☐ |
| B-39 | Delay | Check the mode tabs | `Time` selected by default; `Tempo` available; `role="tablist" aria-label="Delay mode"` | `.sp-modes button[role="tab"]` | ☐ |
| B-40 | Delay | Click `Tempo` | Tab becomes selected (`aria-selected="true"`, class `.on`) | same | ☐ |
| B-41 | Delay | In `Tempo` mode, inspect the Time control | Still a **ms** knob from 1–2000 (no note-division select). Record as divergence if the reference shows divisions | `input[aria-label="Time"]` | ☐ |
| B-42 | Delay | Reload with `Tempo` selected | Mode survives the reload (persisted in the chain) | saved JSON `mode:"tempo"` | ☐ |
| B-43 | Delay | Apply preset **Dub** | Time 375, Feedback 55, Mix 30, Low Cut 250, High Cut 6khz; dirty clears | `.sp-preset` = `Dub` | ☐ |

### B5. Distortion — 5 checks

| ID | Area | Action | Expected result | Evidence / selector | ☐ |
|---|---|---|---|---|---|
| B-44 | Distortion | Read defaults | Drive 30%, Tilt 0, Bass 0db, Freq 800hz | `aria-label` Drive/Tilt/Bass/Freq | ☐ |
| B-45 | Distortion | Count the mode tabs | Five: Hard, Fold, Align, Sine, Crush; Hard selected first | `.sp-modes button` | ☐ |
| B-46 | Distortion | Click each mode in turn | Exactly one `aria-selected="true"` at a time | `.sp-modes button.on` count = 1 | ☐ |
| B-47 | Distortion | Drag Tilt to both ends | −100 to +100, readout without unit | `aria-valuetext` | ☐ |
| B-48 | Distortion | Drag Freq with log scale | Mid-travel ≈ geometric mean (~630 hz), not arithmetic 10 kHz | `.sp-knob-dial` arc; `log={param.unit==="hz"}` | ☐ |

### B6. EQ — 10 checks

| ID | Area | Action | Expected result | Evidence / selector | ☐ |
|---|---|---|---|---|---|
| B-49 | EQ | Add EQ and inspect the card | Band select, enable switch, 6 shape glyph buttons, shared curve, Freq/Q/Gain | `.sp-eq-card`, `select[aria-label="EQ band"]` | ☐ |
| B-50 | EQ | Check the band selector | Options `Band 1..4`; default selection **Band 1** in the knobs, Band 1 highlighted on the curve | `.sp-band-select`, `.sp-eq-handle.on` | ☐ |
| B-51 | EQ | Read Band 1 defaults | Freq 1khz, Q 1.0, Gain 0db | band knobs | ☐ |
| B-52 | EQ | Select Band 2 / 3 / 4 | Knobs read 200hz / 4khz / 10khz; Q 1.0; Gain 0db | `aria-label` Freq/Q/Gain | ☐ |
| B-53 | EQ | Toggle the band enable switch | Handle disappears from the curve; band contributes 0 dB; `role="switch" aria-checked` flips | `button[aria-label="Band 1 enabled"]` | ☐ |
| B-54 | EQ | Click each of the six shapes | `aria-pressed="true"` moves; curve redraws; model `bandN.type` = 0…5 in the listed order | `.sp-eq-shapes button` | ☐ |
| B-55 | EQ | Drag a band handle across the curve | Freq follows x (log), Gain follows y (±24 dB), readouts update without dropping the drag | `.sp-eq` `onPointerMove` | ☐ |
| B-56 | EQ | Drag a handle beyond the curve bounds | Freq clamps to 20–20000, Gain clamps to ±24 | saved JSON `bandN.freq/gain` | ☐ |
| B-57 | EQ | Disable the whole plugin (bypass) | All EQ controls disabled; curve stays but is inert | `.sp-slot.is-bypassed` + `disabled` | ☐ |
| B-58 | EQ | Check the curve readout | No numeric readout on the curve; handles carry `aria-label="Band N handle"` | `.sp-eq-handle` | ☐ |

### B7. Gate — 4 checks

| ID | Area | Action | Expected result | Evidence / selector | ☐ |
|---|---|---|---|---|---|
| B-59 | Gate | Read defaults | Threshold −45db, Floor −60db, Attack 2ms, Hold 50ms | `aria-label` | ☐ |
| B-60 | Gate | Check tiers | Threshold primary; Floor/Attack/Hold secondary (render after it) | `.sp-knob-grid` order | ☐ |
| B-61 | Gate | Apply preset **Tight** | −40 / −70 / 1 / 30; label = `Tight` | `.sp-preset` | ☐ |
| B-62 | Gate | Apply preset **Slow** | −50 / −60 / 10 / 120 | `.sp-preset` | ☐ |

### B8. Limiter — 4 checks

| ID | Area | Action | Expected result | Evidence / selector | ☐ |
|---|---|---|---|---|---|
| B-63 | Limiter | Read defaults | Lookahead 3ms, Pre Gain 0db, Attack 1ms, Release 60ms | `aria-label` | ☐ |
| B-64 | Limiter | Apply **Loud** | 3 / +6 / 1 / 50 | readouts | ☐ |
| B-65 | Limiter | Apply **Transparent** | 5 / 0 / 3 / 120 | readouts | ☐ |
| B-66 | Limiter | Check no mode tabs / no asset slot | Only the knob grid renders | `.sp-modes` absent | ☐ |

### B9. Reverb — 5 checks

| ID | Area | Action | Expected result | Evidence / selector | ☐ |
|---|---|---|---|---|---|
| B-67 | Reverb | Read defaults | Decay 2.4s, Mix 25%, Width 100%, Damping 40%, Predelay 20ms, Low Cut 120hz, High Cut 14khz | `aria-label` per label | ☐ |
| B-68 | Reverb | Check readout formatting | Decay shows one decimal + `s` (e.g. `2.4s`); Hz switches to `khz` at 1000 and above | `.sp-knob-readout` | ☐ |
| B-69 | Reverb | Apply **Room** / **Hall** / **Plate** | Room 1.2/18/100/55/10/120/14k; Hall 3.2/28/120/40/25/120/12k; Plate 1.8/22/90/30/5/150/16k | `.sp-preset` + readouts | ☐ |
| B-70 | Reverb | Drag Decay to max 20s | Allows fractional steps of 0.1, never exceeds 20 | `input[aria-label="Decay"]` | ☐ |
| B-71 | Reverb | Confirm no mode tabs | Seven knobs only | `.sp-modes` absent | ☐ |

### B10. Rhythm Gate — 5 checks

| ID | Area | Action | Expected result | Evidence / selector | ☐ |
|---|---|---|---|---|---|
| B-72 | Rhythm Gate | Inspect Rate | Renders as a `<select>` with `1/16`, `1/8`, `1/4`; default `1/8` | `select.sp-choice[aria-label="Rate"]` | ☐ |
| B-73 | Rhythm Gate | Check the 0–1 percent params | Depth reads `75%`, Mix reads `65%` (0–1 model rendered 0–100) | `.sp-knob-readout` | ☐ |
| B-74 | Rhythm Gate | Read attack/release defaults | Atk 0.1, Rel 0.2 (0.12 / 0.22 rounded to 1 dp) | readouts | ☐ |
| B-75 | Rhythm Gate | Change Rate to `1/4` and reload | Selection persists (`rate: 2`) | saved JSON | ☐ |
| B-76 | Rhythm Gate | Open a project saved with legacy `chorus` | Slot renders as **Rhythm Gate** with migrated rate/depth/mix (see `sanitizeChain`) | slot name; saved JSON `pluginId:"rhythmGate"` | ☐ |

### B11. Stereo Utility — 5 checks

| ID | Area | Action | Expected result | Evidence / selector | ☐ |
|---|---|---|---|---|---|
| B-77 | Stereo Utility | Read defaults | Level 0db, Width 150%, Pan 0.0, Bass Mono 120hz | `aria-label` | ☐ |
| B-78 | Stereo Utility | Check tiers | Level/Width/Pan primary; Bass Mono secondary last | DOM order | ☐ |
| B-79 | Stereo Utility | Drag Width to 200% | Readout `200%`; no clamp error | `aria-valuetext` | ☐ |
| B-80 | Stereo Utility | Drag Pan to −100 / +100 | Signed value shown (`-100` … `100`), no unit | readout | ☐ |
| B-81 | Stereo Utility | Confirm no presets | Preset menu shows only `Clear all settings`, `Save preset…`, `Default` | `.sp-preset-menu` | ☐ |

### B12. Presets and the dirty/Update cycle — 9 checks

| ID | Area | Action | Expected result | Evidence / selector | ☐ |
|---|---|---|---|---|---|
| B-82 | Presets | Move any knob | Header preset label becomes `Custom`; **Update** button appears | `.sp-preset`, `.sp-update` | ☐ |
| B-83 | Presets | Press **Update** | Label returns to the previous preset name; Update disappears; values persist | `.sp-update` absent | ☐ |
| B-84 | Presets | Open the preset menu on Compressor | Rows: Clear all settings (danger), Save preset…, Default, Vocal, Drum Bus, Gentle | `.sp-preset-menu[role="menu"]` | ☐ |
| B-85 | Presets | Click `‹` / `›` repeatedly | Cycles Default → starter presets → user presets → wraps; each step applies values | `.sp-preset-step` | ☐ |
| B-86 | Presets | Choose **Default** | Defaults restored; `aria-current`-style `.on` on the Default row | `.sp-preset-menu button.on` | ☐ |
| B-87 | Presets | Choose **Clear all settings** | Defaults applied, label becomes `Custom`, slot stays dirty-free | `.sp-preset` = `Custom` | ☐ |
| B-88 | Presets | `Save preset…` → type a name → Enter | Toast `Preset "X" saved.`; preset appears in the menu and in the stepper for that plugin only | `.se-toast`; menu rows | ☐ |
| B-89 | Presets | Re-open `Save preset…` and press Escape | Inline name field closes; no preset saved | `.sp-preset-save` absent | ☐ |
| B-90 | Presets | Reload after saving a preset | User preset persists (stored in project `pluginPresets`) and is selectable | menu rows after reload | ☐ |

### B13. Chain operations — 12 checks

| ID | Area | Action | Expected result | Evidence / selector | ☐ |
|---|---|---|---|---|---|
| B-91 | Chain | Press `›` on slot 1 | Order swaps; slot numbers renumber; signal order follows | `aria-label` `Move Compressor right` | ☐ |
| B-92 | Chain | Press `‹` on slot 1 | Disabled (`disabled`) — first slot cannot move left | `aria-label="Move X left"` | ☐ |
| B-93 | Chain | Press `›` on the last slot | Disabled | `aria-label="Move X right"` | ☐ |
| B-94 | Chain | Press the bypass dot | Slot dims, `aria-pressed="true"`, all controls disabled, footer chip unchanged | `.sp-bypass` | ☐ |
| B-95 | Chain | Press ✕ on a slot | Slot removed; remaining slots renumber; footer chip for it disappears | `aria-label="Remove X"` | ☐ |
| B-96 | Chain | Remove every slot | Empty state returns (`No effects on this track yet.`) | `.sp-empty` | ☐ |
| B-97 | Chain | Undo a removal (Ctrl+Z) | Slot returns with the same preset and parameter values | `.sp-slot` count restored | ☐ |
| B-98 | Chain | Pop out one slot in `toggle` mode | Card moves to a fixed overlay bottom-right (`right:24px; bottom:88px`); rail keeps a placeholder gap | `.sp-slot.is-popped` | ☐ |
| B-99 | Chain | Press **Dock** on the popped card | Card returns inline; state persists across reload | `aria-label="Dock X"` | ☐ |
| B-100 | Chain | Add Delay on Track 1, then select Track 2 | Track 2's chain is unchanged; Track 1 keeps its three slots | `.sp-slot` count per track | ☐ |
| B-101 | Chain | Verify chain is undoable and saved | Add, undo, redo; reload | footer chips + `.sp-slot` reflect each step; JSON matches | ☐ |
| B-102 | Chain | Check footer chain chips | `.se-chain-chip` shows plugin names in order; unknown/`custom` handled | `.se-chain`, `data-plugin` | ☐ |

### B14. Designed (“custom”) plugins — 8 checks

| ID | Area | Action | Expected result | Evidence / selector | ☐ |
|---|---|---|---|---|---|
| B-103 | Designed | ⋯ → **Create new plugin** | Prompt bar switches to design mode: badge stays, placeholder `Make me a new plugin. Here's what I have in mind:` | `.se-prompt.is-design`, `input[aria-label="Describe a part to generate"]` | ☐ |
| B-104 | Designed | Submit a design prompt | Assistant shows the restate + **Build it** / **Change something…** | `.se-design-actions` | ☐ |
| B-105 | Designed | Press **Build it** | Status line reports the authoring job; error state is a `.se-assistant-msg.error` | `role="status"` / `role="alert"` | ☐ |
| B-106 | Designed | After it builds | Draggable card `aria-label="<name>, designed plugin"` + **Add to track** | `.se-design-card` | ☐ |
| B-107 | Designed | Press **Add to track** with no track selected | Falls back to the first track; slot appears as a `Custom` slot with the designed knobs | `.sp-slot`, `.sp-preset` = `Custom` | ☐ |
| B-108 | Designed | Drag the card onto another track row | `dataTransfer` type `application/x-camxora-plugin`; dropping adds the slot to that track | `.se-track` drop handler | ☐ |
| B-109 | Designed | Inspect a custom slot | Preset stepper hidden, preset menu button disabled; knobs are the designed ones with their tiers | `.sp-preset-step` absent, `.sp-preset[disabled]` | ☐ |
| B-110 | Designed | Exit design mode | ✕ labelled `Exit plugin designer`; prompt returns to generate mode | `.se-prompt-context.is-plugin` gone | ☐ |

### B15. Master chain dock — 8 checks

| ID | Area | Action | Expected result | Evidence / selector | ☐ |
|---|---|---|---|---|---|
| B-111 | Master | Click **Main** in the track panel | Bottom panel swaps to the master chain (`aria-label="Master chain"`) | `.se-master-strip.is-selected`, `section.sp-dock` | ☐ |
| B-112 | Master | Inspect the default limiter | Card `Limiter` with Lookahead/Pre Gain/Attack/Release/**Link** (On/Off display) | `.sp-limiter-card`, `aria-label` per knob | ☐ |
| B-113 | Master | Open the limiter preset menu | `Default` + `MASTER_PRESETS` rows | `.sp-preset-menu[aria-label="Master presets"]` | ☐ |
| B-114 | Master | Press **Add effect** | Menu offers `Limiter` (disabled with `Limiter (already added)` when present); ghosts are EQ and Compressor | `.sp-ir-menu[aria-label="Add master effect"]` | ☐ |
| B-115 | Master | Add EQ then Compressor | Each renders a single **Amount** knob 0–100% | `article[aria-label="EQ slot"]` | ☐ |
| B-116 | Master | Remove a master card | Card disappears; footer chain chip count drops | `aria-label="Remove EQ"` | ☐ |
| B-117 | Master | Footer **Add master effect** | Selects Main and opens the bottom panel (never a dead control) | `.se-chain-add` | ☐ |
| B-118 | Master | Reload after editing the master chain | Master chain persists in project data `masterChain` | footer chips after reload | ☐ |

### B16. Impulse Response Designer — 6 checks

| ID | Area | Action | Expected result | Evidence / selector | ☐ |
|---|---|---|---|---|---|
| B-119 | IR designer | Open from the Convolution picker (advanced on) | Dialog `Impulse response designer` with preview, Name, Length, Decay | `[aria-label="Impulse response designer"]` | ☐ |
| B-120 | IR designer | Read the defaults | Name `Custom hall`, Length 2.4s, Decay 2.6 | `#ir-name`, `#ir-length`, `#ir-decay` | ☐ |
| B-121 | IR designer | Move Length / Decay | Live preview redraws; labels show one decimal | `svg.sp-ir`, `<b>` readouts | ☐ |
| B-122 | IR designer | Press **Save response** | Dialog closes; the new IR is selected in the Convolution slot and appears under `Custom` | `.sp-ir-picker` label, `.sp-ir-menu` Custom group | ☐ |
| B-123 | IR designer | Press **Cancel** | Dialog closes, nothing saved, slot asset unchanged | — | ☐ |
| B-124 | IR designer | Re-open the picker | The custom IR is still listed (localStorage-backed) | `Custom` category | ☐ |

### B17. Wavetable Designer — 6 checks

| ID | Area | Action | Expected result | Evidence / selector | ☐ |
|---|---|---|---|---|---|
| B-125 | Wavetable | With Advanced content **off**, open a MIDI clip | No `Design wavetable` button | `.se-midi-design` absent | ☐ |
| B-126 | Wavetable | Turn Advanced content **on**, open the MIDI clip | `Design wavetable` appears | `.se-midi-design` | ☐ |
| B-127 | Wavetable | Open the designer | Dialog `Wavetable designer`; presets group; N partial sliders (1..`WAVETABLE_PARTIALS`) | `[aria-label="Wavetable designer"]` | ☐ |
| B-128 | Wavetable | Press a shape preset | All partial sliders snap to that preset; preview redraws | `.se-wavetable-presets`, `.se-wavetable-preview` | ☐ |
| B-129 | Wavetable | Move partial 1 to 0 then 100 | Preview flattens then becomes a pure sine | `input[aria-label="Partial 1"]` | ☐ |
| B-130 | Wavetable | Save with a name | Toast `Wavetable "X" saved.`; instrument select gains `X` | `.se-toast`, `select[aria-label="MIDI instrument"]` | ☐ |

### B18. Clip-owned effects — 4 checks

| ID | Area | Action | Expected result | Evidence / selector | ☐ |
|---|---|---|---|---|---|
| B-131 | Clip FX | Clip menu → **Add FX…** | Dialog `Add a clip effect` listing all 10 plugins + Cancel | `[aria-label="Add clip effect"]` | ☐ |
| B-132 | Clip FX | Choose Compressor | Toast `Compressor added to the clip.`; dialog closes | `.se-toast` | ☐ |
| B-133 | Clip FX | Re-open the clip menu | **Remove FX** is now enabled (disabled while the clip has no `fx`) | clip menu row | ☐ |
| B-134 | Clip FX | Remove FX | Toast `Clip effects removed.`; Add FX flow can start again | `.se-toast` | ☐ |

### B19. Sends and routing surfaces — 4 checks

| ID | Area | Action | Expected result | Evidence / selector | ☐ |
|---|---|---|---|---|---|
| B-135 | Sends | Inspect the dock's **Sends** group | Delay and Reverb sliders 0–100%, default 0 | `[role="group"][aria-label="Sends"]` | ☐ |
| B-136 | Sends | Raise Delay send | Value persists on the track (`sends.delay`) and survives reload | saved JSON `tracks[].sends` | ☐ |
| B-137 | Sends | Check routing honesty | Sends are per track and are **not** part of the plugin chain list | `.sp-sends` outside `.sp-rail` | ☐ |
| B-138 | Sends | Verify chain playback path exists | Playing with a chain and a send produces audio (no silent graph) | transport plays; `.se-meter` moves | ☐ |

## C. Every menu and dialog — 210 checks

Components: `components/studio/StudioProjectMenu.tsx`, `StudioEditorShell.tsx` (menus live after the
`role="region" aria-label="Editor menus"` block), `StudioTrackPanel.tsx`, `StudioHeader.tsx`,
`StudioFooter.tsx`, `StudioLearn.tsx`, `StudioOnboarding.tsx`, `StudioHome.tsx`,
`app/studio/shared/[token]/page.tsx`.

### C1. Project menu — 12 checks

| ID | Area | Action | Expected result | Evidence / selector | ☐ |
|---|---|---|---|---|---|
| C-01 | Project menu | Click the project chip | Menu `Project options` opens with 11 rows in the listed order | `.se-project-menu[role="menu"]` | ☐ |
| C-02 | Project menu | Read the captured nine, then the additive rows | New Project, Open Project, Rename, Duplicate Project, Version History, Share Project, Open a copy in v1, Studio Settings, Show Quick Start again, **then** Import project…, Send to Suno Sync | DOM order of `[role="menuitem"]` | ☐ |
| C-03 | Project menu | Check `Open a copy in v1` | Permanently `disabled`, tooltip `There is no v1 Studio in this product` | `[role="menuitem"][disabled]` | ☐ |
| C-04 | Project menu | Check the Settings row hint | Row shows `Studio Settings` + `ctrl shift ,` | `.se-project-hint` | ☐ |
| C-05 | Project menu | Press Escape | Menu closes, no dialog opens | — | ☐ |
| C-06 | Project menu | Click outside | Menu closes | `wrapperRef` pointerdown | ☐ |
| C-07 | Project menu | Click the chip again | Menu closes (toggle) | `aria-expanded` | ☐ |
| C-08 | Project menu | Press `Ctrl+Shift+,` | Studio Settings opens directly, menu closed | `[aria-label="Studio Settings"]` | ☐ |
| C-09 | Project menu | Press `Ctrl+Shift+,` while a text input has focus | Nothing opens (typing wins) | `dialog` absent | ☐ |
| C-10 | Project menu | Press `Ctrl+Shift+,` while another dialog is open | Settings do **not** stack on top | `[aria-label="Studio Settings"]` count = 0 | ☐ |
| C-11 | Project menu | Verify busy handling | While an action runs, rows carry `disabled` and errors surface inside the menu | `.se-dialog-error` | ☐ |
| C-12 | Project menu | Reload the page with the menu open | Menu is closed on load (no persisted open state) | — | ☐ |

### C2. Project dialogs — 39 checks

| ID | Area | Action | Expected result | Evidence / selector | ☐ |
|---|---|---|---|---|---|
| C-13 | New Project | Menu → **New Project** | Creates `Untitled project` and navigates to `/studio/editor?project=<new id>` | URL change; `.se-empty` "Your session is empty" | ☐ |
| C-14 | Open Project | Menu → **Open Project** | Dialog `My Projects` with tabs, search, Filters (disabled), sort | `[aria-label="Open project"]`, `.se-projects-tabs` | ☐ |
| C-15 | Open Project | Check the tab list | Two tabs: `Projects`, `Recently Deleted`; Projects selected | `role="tablist" aria-label="Project lists"` | ☐ |
| C-16 | Open Project | Read the card grid | `New Project` card first, then project cards with thumb + title + date | `.se-project-card.is-new`, `.se-project-card` | ☐ |
| C-17 | Open Project | Type in search | List filters by title substring; no match → `No projects match that search.` | `input[aria-label="Search projects"]` | ☐ |
| C-18 | Open Project | Click **Filters** | Disabled, tooltip `Project filters are not built` | `.se-projects-sort[disabled]` | ☐ |
| C-19 | Open Project | Switch sort to `Oldest First` | Order reverses by `updated_at`/`created_at` | `select[aria-label="Sort projects"]` | ☐ |
| C-20 | Open Project | Click a project card | Navigates to that project (full page load) | URL `?project=` | ☐ |
| C-21 | Open Project | Switch to **Recently Deleted** | Lazy load; deleted cards show `Deleted <date>` and a `Restore` label | `aria-label="Restore <title>"` | ☐ |
| C-22 | Open Project | Press `Restore` on a deleted card | Card leaves the deleted list, tab returns to Projects, project is on top | `projectTab` = projects | ☐ |
| C-23 | Open Project | With an empty deleted list | `Nothing here. Deleted projects stay restorable.` | `.se-dialog-note` | ☐ |
| C-24 | Open Project | Close with ✕ labelled `Close projects` | Dialog closes, project unchanged | `aria-label="Close projects"` | ☐ |
| C-25 | Rename | Menu → **Rename** | Dialog `Rename project` prefilled with the current title | `[aria-label="Rename project"]`, `#se-project-title` | ☐ |
| C-26 | Rename | Clear the field and press **Save** | Inline error `A project title is required.`; no request | `.se-dialog-error` | ☐ |
| C-27 | Rename | Enter a new title and Save | Chip updates immediately; dialog closes; next edit does **not** 409 | `.se-chip`, save chip `Saved` | ☐ |
| C-28 | Rename | Press Escape | Dialog closes without saving | — | ☐ |
| C-29 | Duplicate | Menu → **Duplicate Project** | Fork created as `<title> copy`, then navigates into the copy | URL change; chip ends with `copy` | ☐ |
| C-30 | Duplicate | Go back to the original | Original is byte-identical (fork does not mutate it) | track/clip counts equal | ☐ |
| C-31 | Versions | Menu → **Version History** | Side panel `Version history` opens; `Loading versions…` first | `aside.se-history[aria-label="Version history"]` | ☐ |
| C-32 | Versions | With no versions | `No versions yet. Versions are captured automatically as you edit.` | `.se-history-note` | ☐ |
| C-33 | Versions | With versions | Grouped under a date heading with `‹ date ›` stepper | `.se-history-stepper` | ☐ |
| C-34 | Versions | Press `Restore` on a version | Arrangement is replaced and the editor reloads | `window.location.reload` | ☐ |
| C-35 | Versions | Close with ✕ | Panel closes; note `Restoring replaces the arrangement and reloads the editor.` remains visible before closing | `aria-label="Close version history"` | ☐ |
| C-36 | Share | Rename to `Untitled project`, then **Share Project** | Naming gate `Name project before sharing` appears first | `[aria-label="Name project before sharing"]` | ☐ |
| C-37 | Share | In the gate, press **Skip** | Share dialog opens without renaming (still `Untitled project`) | `[aria-label="Share project"]` | ☐ |
| C-38 | Share | In the gate, type a name and press **Save** | Title is saved, then the share dialog opens for the new name | chip + share title | ☐ |
| C-39 | Share | With a named project, **Share Project** | Share dialog opens directly, no gate | — | ☐ |
| C-40 | Share | Read the body copy | View-and-fork only: “Anyone with the link can view this project and create their own editable copy.” | `.se-dialog-lead` | ☐ |
| C-41 | Share | Wait for link creation | `Creating the link…` → readonly link field `aria-label="Share link"` + expiry sentence | `input[aria-label="Share link"]` | ☐ |
| C-42 | Share | Press **Copy Link** | Button label becomes `Copied`; clipboard contains absolute URL | `.se-pill.on` label | ☐ |
| C-43 | Share | Deny clipboard permission, then **Copy Link** | Error `Could not reach the clipboard — select and copy the link above.` | `.se-dialog-error` | ☐ |
| C-44 | Share | Re-open Share for the same project | The existing live share is reused (no duplicate token) | same path as before | ☐ |
| C-45 | Share | Press **Done** | Dialog closes; nothing else changes | — | ☐ |
| C-46 | Suno sync | Menu → **Send to Suno Sync** | Dialog `Suno sync` first shows `Pushing this project to Suno…` | `[aria-label="Suno sync"]` | ☐ |
| C-47 | Suno sync | Read the result sentence | One of: state-sync-off / `Pushed to Suno at …` / `Linked to Suno; the push is queued.` / `Queued — Suno picks it up in the background.` / conflict / rejected | `.se-dialog-note[role="status"]` | ☐ |
| C-48 | Suno sync | Check the skipped-clips note | When clips lack a Suno asset: `<n> clip(s) stay local: no Suno asset yet.` | second `.se-dialog-note` | ☐ |
| C-49 | Suno sync | Press **Close** | Dialog closes and the result is cleared | — | ☐ |
| C-50 | Import | Menu → **Import project…** | Native file picker opens, `accept="application/json,.json"` | `input[aria-label="Import Studio project JSON"]` | ☐ |
| C-51 | Import | Choose a valid exported JSON | New project `<name> (imported)` is created and opened | URL change; chip suffix | ☐ |

### C3. Studio Settings — 12 checks

| ID | Area | Action | Expected result | Evidence / selector | ☐ |
|---|---|---|---|---|---|
| C-52 | Settings | Open Settings | Dialog title `Studio Settings`, nav with Performance / Window management / Content | `.se-settings-nav[aria-label="Settings sections"]` | ☐ |
| C-53 | Settings | Check the default pane | **Performance** active (`aria-current="page"`) | `.se-settings-nav button.on` | ☐ |
| C-54 | Settings | Performance ▸ Ghost drag toggle | Checkbox `Ghost drag for arrangement moves`, default **on**; copy explains the apply-on-drop behaviour | `input[aria-label="Ghost drag for arrangement moves"]` | ☐ |
| C-55 | Settings | Performance ▸ Count-in toggle | `Count-in before recording`, default **off** | `input[aria-label="Count-in before recording"]` | ☐ |
| C-56 | Settings | Windows pane | Radiogroup `Plugin windows` with Panels / Windows / Show toggle; default **Show toggle** | `[role="radiogroup"][aria-label="Plugin windows"]` | ☐ |
| C-57 | Settings | Switch to **Panels**, then open the dock | No per-slot pop-out buttons; all cards docked | `.sp-slot-tools` without pop-out | ☐ |
| C-58 | Settings | Switch to **Windows** | Every slot renders popped out (fixed overlay) | `.sp-slot.is-popped` count = chain length | ☐ |
| C-59 | Settings | Content pane | `Auto-stretch added audio` default **on**; `Advanced content features` default **off** | `.se-settings-card` × 2 | ☐ |
| C-60 | Settings | Turn Advanced content on | MIDI `Design wavetable` and Convolution `Design response.` appear without a reload | B-126, B-37 | ☐ |
| C-61 | Settings | Change a toggle, then reload | All four preferences persist (localStorage `studio:settings`) | `localStorage.getItem("studio:settings")` | ☐ |
| C-62 | Settings | Close with ✕ | Dialog closes; settings already applied | `aria-label="Close"` | ☐ |
| C-63 | Settings | Open Settings from a different project | Same preferences (browser-scoped, not project-scoped) | — | ☐ |

### C4. Clip menu — 35 checks

Right-click the Track 1 clip A (song-backed, no time selection) unless stated.

| ID | Area | Action | Expected result | Evidence / selector | ☐ |
|---|---|---|---|---|---|
| C-64 | Clip menu | Right-click a clip | Menu `Clip options` opens at the pointer, clamped on-screen and capped in height | `.se-clip-menu[role="menu"]`, `maxHeight` | ☐ |
| C-65 | Clip menu | Read the first block | Copy `ctrl C`, Paste `ctrl V`, Duplicate `ctrl D`, Delete `backspace`, Copy settings, Paste settings | first 6 `[role="menuitem"]` | ☐ |
| C-66 | Clip menu | With an empty clipboard, check **Paste** | Disabled until something is copied | `[role="menuitem"][disabled]` | ☐ |
| C-67 | Clip menu | After Copy, re-open | Paste is enabled | — | ☐ |
| C-68 | Clip menu | With no settings copied | **Paste settings** disabled | — | ☐ |
| C-69 | Clip menu | **Copy settings** then open another clip | Paste settings enabled; toast `Clip settings copied.` | `.se-toast` | ☐ |
| C-70 | Clip menu | Paste settings onto a different clip | Toast `Settings pasted to 1 clip.`; fadeIn/fadeOut/audio copied | `.se-toast` | ☐ |
| C-71 | Clip menu | On a clip with no generated edits | **Heal Edits** disabled, tooltip `No generated edits to heal` | row `title` | ☐ |
| C-72 | Clip menu | On the P2 clip (has source/takes) | **Heal Edits** enabled, tooltip about restoring pre-edit audio | row `title` | ☐ |
| C-73 | Clip menu | Heal Edits | Toast `Edits healed to the original clip.`; take lanes close | `.se-toast` | ☐ |
| C-74 | Clip menu | With the playhead outside the clip | **Split** disabled | `disabled` attr | ☐ |
| C-75 | Clip menu | Move the playhead inside and re-open | **Split** enabled, label shows `ctrl E` | — | ☐ |
| C-76 | Clip menu | **Split on Transients** on a clip with audio | Toast `Finding transients…` then `Split into N clips at M transients.` | `.se-toast` | ☐ |
| C-77 | Clip menu | **Split on Transients** on a clip with no audio | Disabled, tooltip `This clip has no audio to analyse` | `title` | ☐ |
| C-78 | Clip menu | **Make Beat 1** on an off-grid clip | Toast `Clip moved to the bar line at X.XXs.`; clip start becomes a bar multiple | `.se-toast` | ☐ |
| C-79 | Clip menu | **Make Beat 1** on a clip already on a bar line | Toast `This clip already starts on a bar line.`; nothing written | `.se-toast` | ☐ |
| C-80 | Clip menu | **Create Section** | Marker appears on the bar ruler at the clip start, labelled with the clip title | `.se-section-marker` | ☐ |
| C-81 | Clip menu | **Rename** | Dialog `Rename clip`; Enter saves, Escape cancels, empty name is ignored | `[aria-label="Rename clip"]` | ☐ |
| C-82 | Clip menu | **Clip Info** | Library closes, inspector `Clip info` opens for that clip | `aside.se-inspector[aria-label="Clip info"]` | ☐ |
| C-83 | Clip menu | **Clip Color** row | Expands to `Auto` + 5 swatches | `.se-clip-menu-colors[role="group"]` | ☐ |
| C-84 | Clip menu | Choose a swatch | Clip fill changes, menu closes, selection persists | `.se-clip` background | ☐ |
| C-85 | Clip menu | Choose **Auto** | Clip falls back to the track colour; Auto shows a tick | `.se-color-auto[aria-pressed="true"]` | ☐ |
| C-86 | Clip menu | **Get Stems** on a song-backed clip | Dialog `Get stems` opens (see C-160) | `[aria-label="Get stems"]` | ☐ |
| C-87 | Clip menu | **Get Stems** on an uploaded clip (no songId) | Disabled, tooltip `No source generation for this clip` | — | ☐ |
| C-88 | Clip menu | **Download WAV** | Disabled without `audioUrl`; enabled with it and starts a download | `disabled` attr | ☐ |
| C-89 | Clip menu | **Get MIDI** | Disabled without `songId`; with it, toast `Transcribing MIDI...` then `MIDI added as a track (N notes).` | `.se-toast` | ☐ |
| C-90 | Clip menu | **Remove FX** / **Add FX…** | Remove disabled with no fx; Add FX always enabled and opens C-131 | — | ☐ |
| C-91 | Clip menu | The Generate block | Extend, Cover…, Remaster, Vocals…, Instrumental…, Mashup…, Replace… — each disabled without `songId`, all disabled while `transformBusy` | row `title` strings | ☐ |
| C-92 | Clip menu | **Mashup…** with one clip selected | Disabled, tooltip `Select two clips that have a source generation` | — | ☐ |
| C-93 | Clip menu | **Replace…** with no time range | Disabled, tooltip `Select a time range over this clip first` | — | ☐ |
| C-94 | Clip menu | **Download MIDI** with no MIDI in the selection | Disabled, tooltip `Select a MIDI clip with notes first` | — | ☐ |
| C-95 | Clip menu | **Clip Info** then close it | Inspector closes, arrangement returns, selection kept | `aria-label="Back to arrangement"` | ☐ |
| C-96 | Clip menu | Press Escape | Menu closes without action | — | ☐ |
| C-97 | Clip menu | Click outside | Menu closes without action | `pointerdown` handler | ☐ |
| C-98 | Clip menu | Right-click a **different** clip while open | Menu moves/refreshes to the new clip (no stale target) | `.se-clip-menu` | ☐ |

### C5. Range (time selection) menu — 9 checks

Drag on the bar ruler first, then right-click the ruler.

| ID | Area | Action | Expected result | Evidence / selector | ☐ |
|---|---|---|---|---|---|
| C-99 | Range menu | Right-click with a range | Menu `Time selection options` with a `from – to` header | `.se-clip-menu-head` | ☐ |
| C-100 | Range menu | Right-click with no range | Nothing opens (menu requires a selection) | — | ☐ |
| C-101 | Range menu | **Loop selection** | Loop band matches the range; loop enabled | `.se-loop-band` | ☐ |
| C-102 | Range menu | **Split Arrangement** | Splits **every** clip crossing the playhead; toast `Arrangement split at the playhead.` | `.se-toast`, clip count | ☐ |
| C-103 | Range menu | **Duplicate time** | Range content repeats after itself, later clips shift right | clip starts | ☐ |
| C-104 | Range menu | **Delete time** | Range is removed on every track and later clips ripple left | clip starts | ☐ |
| C-105 | Range menu | **Delete time on this track** | Disabled when no track is focused; otherwise only that track ripples | `disabled` attr | ☐ |
| C-106 | Range menu | **Export selection** | Runs the range export (WAV or MP3 per the export menu) | download starts | ☐ |
| C-107 | Range menu | **Clear selection** | Range disappears; no other change | `.se-range` absent | ☐ |

### C6. Track menu, add-track, hidden tracks, groups — 23 checks

| ID | Area | Action | Expected result | Evidence / selector | ☐ |
|---|---|---|---|---|---|
| C-108 | Track menu | Press a track's `⌄` | Menu `"<track> options"` with 7 rows | `.se-track-menu[role="menu"]` | ☐ |
| C-109 | Track menu | **Rename track** | Inline input appears, focused, current name selected; Enter commits, Escape cancels, blur commits | `input[aria-label="Track name"]` | ☐ |
| C-110 | Track menu | **Color** | Flyout with 5 swatches (`#38bdf8 #a78bfa #f472b6 #fb923c #4ade80`); choosing closes the menu | `.se-track-menu-colors` | ☐ |
| C-111 | Track menu | **Collapse controls / Expand controls** | Label flips with state; sliders hide when collapsed | row label | ☐ |
| C-112 | Track menu | **Duplicate** | Copy appended with the same clips/volume/pan; visible in the panel | track count +1 | ☐ |
| C-113 | Track menu | **Hide & Mute Track** | Track leaves the list, hidden pill count +1, its clips stop sounding | `.se-hidden-pill` | ☐ |
| C-114 | Track menu | **Delete** | Track removed with its clips; selection falls to a surviving clip or none | `.se-track` count −1 | ☐ |
| C-115 | Track menu | **Bounce track** with no clips | Disabled, tooltip `This track has no clips to bounce` | — | ☐ |
| C-116 | Track menu | **Bounce track** with clips | Label becomes `Bouncing…`, then a WAV is placed at the playhead | `.se-toast`; clip count | ☐ |
| C-117 | Add track | Press **Add new track** | Menu `Add a track` with Audio (A), MIDI (M), Upload (U) | `.se-add-menu` | ☐ |
| C-118 | Add track | **Audio** | Empty audio track appended; `A` shortcut does the same | track count +1 | ☐ |
| C-119 | Add track | **MIDI** | MIDI track appended; `M`-style row exists only in the menu | track label | ☐ |
| C-120 | Add track | **Upload** | Library opens on the Uploads list, not a new empty track | `.se-library` uploads view | ☐ |
| C-121 | Add track | Outside click / Escape / scroll while open | Menu closes (scroll listener is capture-phase) | `window` scroll | ☐ |
| C-122 | Hidden | Press the hidden pill | Popover `Hidden tracks` with one row per hidden track | `.se-hidden-pop[role="dialog"]` | ☐ |
| C-123 | Hidden | **Show** on a row | Track returns to the list; pill count decrements; row disappears | `.se-track` count | ☐ |
| C-124 | Hidden | **Mute / Unmute** on a row | Label and track state flip; track stays hidden | row button label | ☐ |
| C-125 | Hidden | **Unmute all** | Every hidden track unmuted without being shown | saved JSON `muted:false` | ☐ |
| C-126 | Hidden | **Show All Hidden Tracks** | All hidden tracks return; pill disappears | `.se-hidden-pill` absent | ☐ |
| C-127 | Hidden | Press Escape with the popover open | Popover closes | — | ☐ |
| C-128 | Groups | Assign two tracks to group A | Group row appears with chip `A`, level slider, member count | `.se-groups [aria-label="Track groups"]` | ☐ |
| C-129 | Groups | Move a group level | Member tracks' effective level changes; individual faders still work on top | `aria-label="Group A level"` | ☐ |
| C-130 | Groups | Press the group chip | Collapses/expands all members at once (`aria-pressed`) | `.se-group-chip` | ☐ |

### C7. Export menu — 8 checks

| ID | Area | Action | Expected result | Evidence / selector | ☐ |
|---|---|---|---|---|---|
| C-131 | Export | Press **Export** in the header | Menu `Export options` opens; button shows pressed state | `.se-export-menu` | ☐ |
| C-132 | Export | Read the rows | Full Song, Selected Time Range, Multitrack, format WAV/MP3, Normalise mix to −1 dBFS, Project (JSON) | menu rows | ☐ |
| C-133 | Export | With no range and no loop range | **Selected Time Range** disabled (`rangeReady` false) | `disabled` | ☐ |
| C-134 | Export | Create a range, re-open | Selected Time Range enabled | — | ☐ |
| C-135 | Export | Switch to **MP3** | `aria-checked` moves to MP3; the next export is an MP3 encode of the same render | `.se-export-formats` | ☐ |
| C-136 | Export | Toggle **Normalise** | Row shows a leading ✓ and `aria-checked="true"`; mix peak becomes −1 dBFS | `[role="menuitemcheckbox"]` | ☐ |
| C-137 | Export | Run **Full Song** | Header shows `Exporting…`, button disabled, then a download | `.se-pill[aria-label="Export menu"]` | ☐ |
| C-138 | Export | Run **Project (JSON)** | Downloads a JSON containing `data.lanes` and `data.tracks` that re-imports via C-51 | file contents | ☐ |

### C8. Learn, shortcuts, What's This? — 8 checks

| ID | Area | Action | Expected result | Evidence / selector | ☐ |
|---|---|---|---|---|---|
| C-139 | Learn | Press **Learn** | Menu `Learn` with three rows; no YouTube Tutorials row | `.se-learn-menu[role="menu"]` | ☐ |
| C-140 | Learn | **Keyboard Shortcuts** | Dialog with search + five groups (Playback, Tracks, Editing, View, Project) | `[aria-label="Keyboard Shortcuts"]`, `.se-shortcut-group` | ☐ |
| C-141 | Learn | Search `zoom` | Only matching rows remain (action or keys match) | `.se-dialog-list li` | ☐ |
| C-142 | Learn | Press `?` with no dialog open | Shortcut dialog opens; search focused | `input[aria-label="Search shortcuts"]` | ☐ |
| C-143 | Learn | Press `?` inside a text field | Nothing opens | — | ☐ |
| C-144 | Learn | **Learning Center** | Dialog with five numbered steps and a Close | `[aria-label="Learning Center"]` | ☐ |
| C-145 | Learn | Toggle **What's This?** off | Row reads `Off`; hovering `data-help` controls shows no card | `[role="menuitemcheckbox"]` | ☐ |
| C-146 | Learn | With it on, hover the tempo / bypass / clip | Tooltip card with title + sentence; disappears on leave and on scroll | `.se-help-card[role="tooltip"]` | ☐ |

### C9. Header, transport and readouts — 14 checks

| ID | Area | Action | Expected result | Evidence / selector | ☐ |
|---|---|---|---|---|---|
| C-147 | Header | Undo / Redo at load | Both disabled until the first edit | `aria-label="Undo"`, `"Redo"` | ☐ |
| C-148 | Header | Undo then Redo | Both states track the history stack; labels stay enabled correctly | `disabled` flips | ☐ |
| C-149 | Header | **Back to start** twice | First press jumps to the song start, second to `0` | `aria-label="Back to start"`; readout | ☐ |
| C-150 | Header | Record with no armed track | Disabled, tooltip `Arm a track first` | `aria-label="Record"` | ☐ |
| C-151 | Header | Arm a track, press Record | Button becomes `Stop recording` (`aria-pressed`), transport rolls | `aria-pressed` | ☐ |
| C-152 | Header | Open the input picker | Menu `Recording input` with `System default`, device rows, and `Count-in (1 bar)` checkbox | `.se-input-menu` | ☐ |
| C-153 | Header | Toggle Count-in on, start recording | `Count-in 1..4` status appears and Record is disabled during the count | `.se-count-in[role="status"]` | ☐ |
| C-154 | Header | Stop | Transport stops where it is; recording ends; playhead stays | `aria-label="Stop"` | ☐ |
| C-155 | Header | Play / Pause | Icon and label swap; the meter moves while playing | `.se-play`, `.se-meter` | ☐ |
| C-156 | Header | Loop toggle | `aria-pressed` flips; with no range the first four bars become the loop | `.se-loop-band` | ☐ |
| C-157 | Header | Metronome toggle | Label includes the live beat, `data-beat` changes 1..beats | `[data-help="metronome"]` | ☐ |
| C-158 | Header | Type `999` in BPM then blur | Clamps to 300; `5` clamps to 20; the project saves the tempo | `input[aria-label="Tempo in BPM"]` | ☐ |
| C-159 | Header | Change the time signature | Select shows the full `STUDIO_SIGNATURES` list; bars re-count; the project saves it | `select[aria-label="Time signature"]` | ☐ |
| C-160 | Header | Cycle the audition speed | `1× → 0.5× → 2× → 1×`; label and pressed state follow; exports stay 1× | `aria-label="Audition speed"` | ☐ |

### C10. Footer — 9 checks

| ID | Area | Action | Expected result | Evidence / selector | ☐ |
|---|---|---|---|---|---|
| C-161 | Footer | With no track selected | **Plugins** and **Automation** disabled; Clip editor enabled | `aria-label="Plugins"`, `"Automation"` | ☐ |
| C-162 | Footer | Press **Plugins** | Bottom panel opens on the selected track (or track 1 if none) | `.sp-dock` | ☐ |
| C-163 | Footer | Press **Automation** | Automation band opens and take lanes/MIDI/audio editors close | `.se-automation` | ☐ |
| C-164 | Footer | Press **Clip editor** with no clip selected | Toast `Select a clip to edit.` | `.se-toast` | ☐ |
| C-165 | Footer | Press **Clip editor** with a clip selected | Opens the MIDI editor (MIDI clip) or the Clip Settings warp editor (audio clip) | `.se-midi` / `.se-audio` | ☐ |
| C-166 | Footer | Press **Take lanes** | Take-lane band opens, automation and editors close | `.se-takes` | ☐ |
| C-167 | Footer | Check the chain chips area | Empty state shows `Add master effect`; with effects it shows chips + a compact `+` | `.se-chain-add` | ☐ |
| C-168 | Footer | Zoom out / Fit / In | Bar width steps through `48, 64, 96, 144, 192`; Fit derives width from the viewport and content | `.se-ruler-inner` width | ☐ |
| C-169 | Footer | **All projects** link | Navigates to `/studio` | `a[aria-label="All projects"]` | ☐ |

### C11. Remaining dialogs and notices — 17 checks

| ID | Area | Action | Expected result | Evidence / selector | ☐ |
|---|---|---|---|---|---|
| C-170 | Stems | Clip menu → Get Stems | Dialog `Separate stems` with 3 radios: Vocals + instrumental, Core stems, Full 12-stem split (+ credit costs when pricing loads) | `[aria-label="Get stems"]` | ☐ |
| C-171 | Stems | Default selection | `Core stems` preselected (`stemsMode="stems"`) | `input[name="stem-mode"]:checked` | ☐ |
| C-172 | Stems | Press **Separate** | Dialog closes; `Get stems` status reports queued/working; on success one track per stem at the playhead | `.se-stem-status` | ☐ |
| C-173 | Stems | Press **Cancel** | Dialog closes, nothing requested | — | ☐ |
| C-174 | Transform | Clip → **Cover…** | Dialog `Cover this clip`, one text field, `Generate cover` action, credit note when known | `[aria-label="Cover this clip"]` | ☐ |
| C-175 | Transform | Clip → **Vocals…** / **Instrumental…** | Dialogs `Add vocals to this clip` / `Add an instrumental` with their own placeholders and actions | `[aria-label="Add vocals to this clip"]` | ☐ |
| C-176 | Transform | Clip → **Mashup…** with exactly two song clips selected | Dialog `Mashup two clips`, optional instructions, `Create mashup` | `[aria-label="Mashup two clips"]` | ☐ |
| C-177 | Transform | Clip → **Replace…** with a range over the clip | Dialog `Replace section` with a textarea, optional Persona select, and `Replace section` | `[aria-label="Replace section"]` | ☐ |
| C-178 | Transform | In Replace, press **Replace section** with empty lyrics | Notice `Replace section needs lyrics.` | `.se-transform-notice` | ☐ |
| C-179 | Transform | In Replace, create a persona with a name | Button shows `Working...` then the persona appears in the select | `#se-persona-select` | ☐ |
| C-180 | Transform | Escape / Cancel in any transform dialog | Closes without spending credits | — | ☐ |
| C-181 | Clip FX | Clip menu → Add FX… | Dialog `Add a clip effect` (see B-131); Cancel closes | `[aria-label="Add clip effect"]` | ☐ |
| C-182 | Suno conflict | With `sync.status === "conflict"`, load the project | Dialog `Suno has newer changes` with 4 actions | `[aria-label="Suno version conflict"]` | ☐ |
| C-183 | Suno conflict | **Decide later** | Dialog closes for this project only; the sync chip keeps the conflict state | `sunoPromptDismissed` | ☐ |
| C-184 | Suno conflict | **Keep mine** / **Load Suno version** / **Duplicate locally** | Keep mine pushes local, load replaces the document and marks synced, duplicate forks and toasts `Copied to “X”.` | `.se-toast`, sync dot | ☐ |
| C-185 | Save conflict | Force two tabs to write the same project | Banner `This project changed in another tab.` with `Reload theirs` / `Keep mine` | `.se-conflict[role="alertdialog"]` | ☐ |
| C-186 | Save conflict | **Reload theirs** | Server document wins; banner clears; save chip `Saved` | `.se-conflict` absent | ☐ |

### C12. Studio home — My Projects, Recently Deleted — 10 checks

| ID | Area | Action | Expected result | Evidence / selector | ☐ |
|---|---|---|---|---|---|
| C-187 | Home | Signed-in home header | Eyebrow `Camxora Studio`, `Your projects`, sub-copy, Create a song + New project | `.studio-home-head` | ☐ |
| C-188 | Home | Resume block | Newest non-archived project with `Open project` | `.studio-resume` | ☐ |
| C-189 | Home | Search a title fragment | Grid filters live; no match shows `No projects match “…”` + Clear search | `.studio-home-search` | ☐ |
| C-190 | Home | Toggle **Archived** | Archived projects join the grid, styled `.is-archived` | `input[type="checkbox"]` | ☐ |
| C-191 | Home | Sort by `Title` | Alphabetical, pinned first in both sort modes | `select[aria-label="Sort projects"]` | ☐ |
| C-192 | Home | Card menu | Rows: Open, Rename, Duplicate, Pin/Unpin, Archive/Restore, Delete | `.studio-card-menu-pop[role="menu"]` | ☐ |
| C-193 | Home | **Rename** | Dialog prefilled; Save disabled while empty; Enter saves | `#studio-rename-title` | ☐ |
| C-194 | Home | **Delete** | Confirm dialog explains Recently Deleted; `Keep project` cancels; Delete removes it | `#studio-delete-title` | ☐ |
| C-195 | Home | Delete then open the project menu → Open Project → Recently Deleted (editor) | The deleted project is listed there and restorable (C-21) | cross-check | ☐ |
| C-196 | Home | Sync dot on a card | Dot with `aria-label="Suno Studio: <state>"` matching the five states | `.studio-sync-dot` | ☐ |

### C13. Shared project page — 8 checks

| ID | Area | Action | Expected result | Evidence / selector | ☐ |
|---|---|---|---|---|---|
| C-197 | Shared | Open `/studio/shared/<valid token>` signed out | Brand, badge `Read-only Studio share`, project title, BPM/signature/track count, duration | `.shared-studio-card` | ☐ |
| C-198 | Shared | Inspect the timeline | One row per lane, clip positioned by start/duration percentage, no editing affordances | `.shared-studio-track` | ☐ |
| C-199 | Shared | Post a comment with a name | Comment appears at the top with author and timestamp; textarea clears | `.shared-studio-comment-list` | ☐ |
| C-200 | Shared | Press **Reply** on a comment | Reply banner shows `Replying to <author>`; posting nests the reply; Cancel clears it | `.shared-studio-reply-banner` | ☐ |
| C-201 | Shared | Post with an empty body | Button disabled | `disabled` | ☐ |
| C-202 | Shared | With no comments | `No comments yet.` | `.shared-studio-comment-empty` | ☐ |
| C-203 | Shared | Signed out, footer | `Sign in to fork`; signed in, `Fork to Studio` creates a copy and opens it | `.shared-studio-footer-actions` | ☐ |
| C-204 | Shared | Invalid or expired token | `Project unavailable` + the error message | `.shared-studio-empty` | ☐ |

### C14. Onboarding — 7 checks

| ID | Area | Action | Expected result | Evidence / selector | ☐ |
|---|---|---|---|---|---|
| C-205 | Onboarding | Open P0 (empty project) | `How do you want to start?` overlay with 5 tiles | `[aria-label="How do you want to start?"]` | ☐ |
| C-206 | Onboarding | Read the tiles | Edit Your Song, Drum & Bass Demo, Upload Audio, Create a song, Empty Project | `.se-onboard-tile` | ☐ |
| C-207 | Onboarding | **Edit Your Song** | Overlay closes, library opens on All Songs | `.se-library` songs view | ☐ |
| C-208 | Onboarding | **Upload Audio** | Overlay closes, library opens on Uploads | uploads view | ☐ |
| C-209 | Onboarding | **Drum & Bass Demo** | A new project opens with one track holding our `demo-loop.wav` clip at bar one; it plays | `.se-clip` + waveform | ☐ |
| C-210 | Onboarding | **Start empty** / ✕ | Overlay closes and does not return on reload (seen flag per project) | `studio:onboarded:<id>` | ☐ |
| C-211 | Onboarding | Project menu → **Show Quick Start again** | Overlay re-opens even though it was dismissed | `.se-onboard` | ☐ |

## D. Arrangement gestures — 88 checks

Components: `components/studio/StudioTimeline.tsx`, `StudioEditorShell.tsx` (pointer + key handlers),
`lib/studio-snap.ts`, `StudioAutomationPanel.tsx`, `StudioAudioEditor.tsx`, `StudioMidiEditor.tsx`.
Pointer rules that apply everywhere: press → drag only after **3 px** (`DRAG_THRESHOLD_PX`); commit
reads the `pointerup` position, not the last `pointermove`; `pointercancel` aborts without writing.

### D1. Selection and move — 9 checks

| ID | Area | Action | Expected result | Evidence / selector | ☐ |
|---|---|---|---|---|---|
| D-01 | Select | Click a clip | It becomes the only selected clip; its track becomes selected; time range is cleared | `.se-clip.selected`, `.se-track.selected` | ☐ |
| D-02 | Select | Click empty lane space | Selection clears and the playhead seeks to that x position | `.se-clip.selected` count = 0 | ☐ |
| D-03 | Select | Drag a box across two clips | Marquee draws and selects every intersecting clip | `.se-marquee`, `.se-clip.selected` count = 2 | ☐ |
| D-04 | Select | Click inside the marquee after release | Selection is kept (no accidental clear) | — | ☐ |
| D-05 | Select | Shift/⌘-click a second clip | Selection **replaces** (no additive modifier path exists — record as a divergence if the reference supports additive select) | `.se-clip.selected` count = 1 | ☐ |
| D-06 | Select | `Ctrl/⌘ + A` | All clips selected | `.se-clip.selected` count = all | ☐ |
| D-07 | Move | Drag one clip right by ~1 bar | Clip moves, snapped to the grid; snap guide line shows at the new start | `.se-snap-line` | ☐ |
| D-08 | Move | Drag a multi-selection | All selected clips move by the same delta and keep their relative offsets | clip `left` values | ☐ |
| D-09 | Move | Drag a clip left past zero | Start clamps at 0; nothing moves before the origin | saved JSON `start >= 0` | ☐ |

### D2. Trim and fades — 11 checks

| ID | Area | Action | Expected result | Evidence / selector | ☐ |
|---|---|---|---|---|---|
| D-10 | Trim | Select a clip, hover its left edge | Trim grip becomes visible (`opacity` 0→1) | `.se-trim-start` | ☐ |
| D-11 | Trim | Drag the right edge | Duration changes, start fixed, snapped to grid, min one grid step | `.se-trim-end` | ☐ |
| D-12 | Trim | Drag the left edge right | Start moves right and `offset` grows by the same amount (audio does not shift) | saved JSON `offset` | ☐ |
| D-13 | Trim | Drag the left edge left past the clip start | Start clamps at 0, `offset` clamps at 0 | saved JSON | ☐ |
| D-14 | Trim | Release without moving | No write, no history entry | undo disabled state unchanged | ☐ |
| D-15 | Trim | Press `pointercancel` mid-drag | Preview disappears, nothing is written | `.se-clip.trimming` gone | ☐ |
| D-16 | Fade | Drag the top-left corner stub | Fade-in grows, snapped, never overlaps the fade-out | `.se-fade` width | ☐ |
| D-17 | Fade | Drag the top-right stub | Fade-out grows; ceiling = duration − fadeIn | `.se-fade.is-out` | ☐ |
| D-18 | Fade | Drag a fade back to the corner | Fade is removed (value 0 is not persisted) | saved JSON without `fadeIn` | ☐ |
| D-19 | Fade | Select an **audio** clip and press `Shift F` | Toggles a 0.5 s (or duration/4) fade-in; pressing again clears it | `.se-fade` | ☐ |
| D-20 | Fade | Select a **MIDI** clip and press `Shift F` | Toast `Fades only apply to audio arrangements.`; no fade written | `.se-toast` | ☐ |

### D3. Split, duplicate, delete — 8 checks

| ID | Area | Action | Expected result | Evidence / selector | ☐ |
|---|---|---|---|---|---|
| D-21 | Split | Put the playhead inside a clip, press `Ctrl/⌘ + E` | Clip becomes two; the right half keeps musical position via `offset`; both stay on the track | clip count +1 | ☐ |
| D-22 | Split | Split with the playhead exactly on the clip start or end | Nothing happens (guarded by ±0.001 s) | clip count unchanged | ☐ |
| D-23 | Split | Split a multi-selection | Every selected clip crossing the playhead splits | clip count | ☐ |
| D-24 | Split | Split on Transients from the clip menu | N segments at detected onsets; toast reports the counts | `.se-toast` | ☐ |
| D-25 | Duplicate | `Ctrl/⌘ + D` on one clip | Copy appears exactly one bar later, original untouched | clip start delta = `secondsPerBar` | ☐ |
| D-26 | Duplicate | Duplicate near the end of the timeline | Copy lands after the original (never before 0); duration grows to fit | `.se-ruler-inner` width | ☐ |
| D-27 | Delete | Select a clip, press `Backspace` | Clip removed; focus moves to a surviving clip; its track's `clipIds` updated | `.se-clip:focus` | ☐ |
| D-28 | Delete | Delete a multi-selection, then Undo | All removed clips return in one undo step | clip count restored | ☐ |

### D4. Clipboard and clip settings — 8 checks

| ID | Area | Action | Expected result | Evidence / selector | ☐ |
|---|---|---|---|---|---|
| D-29 | Copy | `Ctrl/⌘ + C` then `Ctrl/⌘ + V` | Copy pastes at the snapped playhead; the **earliest** copied clip aligns to it | clip starts | ☐ |
| D-30 | Copy | Paste twice | Two independent copies; original untouched | clip count | ☐ |
| D-31 | Copy | Copy with nothing selected | Nothing is copied; Paste stays disabled in the menu | menu state | ☐ |
| D-32 | Cut | `Ctrl/⌘ + X` | Clip is copied **and** removed in one step; Paste then works | clip count −1 | ☐ |
| D-33 | Clipboard | Paste into a different track | Clip keeps its **origin** track (copy buffer stores `trackId`) — record if reference pastes onto the focused track | track rows | ☐ |
| D-34 | Settings | Copy settings from a clip with fades + clip volume, paste onto another | `audio`, `fadeIn`, `fadeOut` copied; **volume/pan/fx are not** part of the buffer | saved JSON diff | ☐ |
| D-35 | Settings | Paste settings onto a multi-selection | Toast `Settings pasted to N clips.` | `.se-toast` | ☐ |
| D-36 | Clipboard | Reload after copying | Clipboard is empty (in-memory only) and Paste is disabled | menu state | ☐ |

### D5. Loop, ruler and time selection — 9 checks

| ID | Area | Action | Expected result | Evidence / selector | ☐ |
|---|---|---|---|---|---|
| D-37 | Ruler | Click the bar ruler | Playhead jumps to the snapped position; no range is created | `.se-playhead-flag` | ☐ |
| D-38 | Ruler | Drag on the ruler | A time range appears with two edge handles and a shaded band | `.se-range[data-testid="se-range"]` | ☐ |
| D-39 | Ruler | Shift-click elsewhere | The far edge stays put, the clicked edge moves (range extends/reduces) | `.se-range` width | ☐ |
| D-40 | Ruler | Drag a range edge handle | Range resizes from that edge only | `aria-label="Selection start"` | ☐ |
| D-41 | Ruler | `Shift + ←` / `Shift + →` | Range grows/shrinks by one grid step; with no range it starts at the playhead | `.se-range` | ☐ |
| D-42 | Ruler | Press `Esc` | Range clears (unless a dialog is open) | `.se-range` absent | ☐ |
| D-43 | Loop | Enable the loop with no range | Loop band covers the first four bars and is persisted (`loopStart`/`loopEnd` in the document) | `.se-loop-band` | ☐ |
| D-44 | Loop | Drag the round loop handle | Loop end moves, snapped, never before start + one beat | `.se-loop-handle` | ☐ |
| D-45 | Loop | Play through the loop end | Playhead wraps to the loop start and audio restarts from there | playhead readout | ☐ |

### D6. Section markers — 5 checks

| ID | Area | Action | Expected result | Evidence / selector | ☐ |
|---|---|---|---|---|---|
| D-46 | Markers | Create a section from a clip | Marker labelled with the clip title at the clip start | `.se-section-marker` | ☐ |
| D-47 | Markers | Click a marker | Playhead seeks to it; clicking does not start a range | `aria-label="Section X at …"` | ☐ |
| D-48 | Markers | Right-click a marker | Marker removed; no context menu appears | `onContextMenu` preventDefault | ☐ |
| D-49 | Markers | Reload | Markers persist (project `data.markers`) sorted by time | ruler after reload | ☐ |
| D-50 | Markers | Zoom out until labels collide | Marker labels stay readable (no truncation/overlap rules) — record if they overlap | markers at 48 px bars | ☐ |

### D7. Zoom, grid and snap — 7 checks

| ID | Area | Action | Expected result | Evidence / selector | ☐ |
|---|---|---|---|---|---|
| D-51 | Zoom | `Ctrl/⌘ + +` / `Ctrl/⌘ + −` | Bar width steps through 48 → 64 → 96 → 144 → 192 and clamps at both ends | `.se-ruler-inner` width | ☐ |
| D-52 | Zoom | Footer magnifier − / + | Same steps as the keyboard | `aria-label="Zoom out"` / `"Zoom in"` | ☐ |
| D-53 | Zoom | Press `Z` with a range | Zooms to the range (8–192 px/bar) and scrolls it into view | scrollLeft, bar width | ☐ |
| D-54 | Zoom | Press `Z` with clips selected and no range | Zooms to the selected clips' span | same | ☐ |
| D-55 | Zoom | Press `Z` with nothing selected | Zooms to fit | same | ☐ |
| D-56 | Zoom | **Fit to content** | Width derives from viewport/content and scroll resets to 0 | `scrollLeft = 0` | ☐ |
| D-57 | Grid | `Shift + 1` / `Shift + 2` | Grid doubles/halves (1…32 divisions); drag snapping visibly follows | clip drop positions | ☐ |

### D8. Automation points — 7 checks

| ID | Area | Action | Expected result | Evidence / selector | ☐ |
|---|---|---|---|---|---|
| D-58 | Automation | Footer → Automation with a track selected | Band `Track automation` with Volume/Pan tabs, Clear, Close | `.se-automation` | ☐ |
| D-59 | Automation | Click in the lane | Point added at that time/value; line connects it; point is selected | `.se-automation-point` | ☐ |
| D-60 | Automation | `←` / `→` with a point selected | Time moves 0.1 s; `Shift` moves 1 s; clamped to the project | `aria-label="Volume N at Xs"` | ☐ |
| D-61 | Automation | `↑` / `↓` | Value moves by 1 (Shift 10), clamped to 0–100 (volume) / −100–100 (pan) | point `style.bottom` | ☐ |
| D-62 | Automation | Double-click a point | Point removed; neighbouring points stay | point count | ☐ |
| D-63 | Automation | Switch to Pan and add a point | Separate lane; Volume points are untouched | saved JSON `panAutomation` | ☐ |
| D-64 | Automation | Press **Clear** | Lane empties (button disabled when already empty) | `disabled` | ☐ |

### D9. Warp markers and clip settings — 9 checks

| ID | Area | Action | Expected result | Evidence / selector | ☐ |
|---|---|---|---|---|---|
| D-65 | Warp | Double-click an audio clip | `Clip Settings` opens with volume, loop, reverse, pitch, stretch, formant, speed, quantize | `.se-audio` | ☐ |
| D-66 | Warp | Turn **Stretch** on with no markers | Markers are generated for the current mode | `.se-warp-marker` count > 0 | ☐ |
| D-67 | Warp | Choose **On Beat** / **Transients** / **Start and End** | Radio moves and markers regenerate: **Start and End = exactly 2** (clip start + end), **On Beat = one per beat**, **Transients = one per detected onset**, falling back to the 2-marker bounds set when the audio has fewer than 2 onsets. Tooltips are the captured sentences | `[role="radiogroup"][aria-label="Stretch mode"]` | ☐ |
| D-68 | Warp | Drag a marker head | Marker moves on the waveform; source position unchanged; commit on release | `.se-warp-head[aria-label="Warp marker at …"]` | ☐ |
| D-69 | Warp | `Shift + Q` with markers selected | Selected markers quantize to the bar/beat grid; unselected stay | marker positions | ☐ |
| D-70 | Warp | `Ctrl/⌘ + A` | All markers selected (`aria-pressed="true"`) | `.se-warp-marker.selected` | ☐ |
| D-71 | Warp | `Shift + 1` / `Shift + 2`, then **Quantize** | Grid steps finer/coarser; Quantize applies the selected grid (and Triplets when on) | `[aria-label="Quantize grid"]` | ☐ |
| D-72 | Warp | Change Volume / Loop / Reverse / Pitch / Speed | Each writes to the clip and survives a reload; readouts update (`+N dB`, `×½`, `%`) | saved JSON `clip.audio` | ☐ |
| D-73 | Warp | Collapse / close the panel | Collapse hides the body but keeps the header; ✕ closes and restores the arrangement height | `aria-label="Collapse clip settings"` | ☐ |

### D10. MIDI editor — 15 checks

| ID | Area | Action | Expected result | Evidence / selector | ☐ |
|---|---|---|---|---|---|
| D-74 | MIDI | Double-click a MIDI clip | `MIDI editor` opens, scrolled near middle C, panel focused | `.se-midi`, `tabIndex={-1}` | ☐ |
| D-75 | MIDI | Click an empty cell | One note is added, selected, `velocity 100`; clicking the same cell again does not stack | `.se-midi-note` | ☐ |
| D-76 | MIDI | Set **Chord** to Major and click | A chord's worth of notes is added in one gesture | note count +3 | ☐ |
| D-77 | MIDI | Set **Arp** to Up/Down and click | Notes are laid out as an arpeggio over the step | note starts | ☐ |
| D-78 | MIDI | Drag a note | Time snaps to the quantize step, pitch follows the row, clamped at the clip bounds | note `left`/`top` | ☐ |
| D-79 | MIDI | Double-click a note | Note deleted | note count −1 | ☐ |
| D-80 | MIDI | Drag in the velocity lane | That note's velocity follows y (1–127); bar height and dot move; commit on release | `.se-midi-velocity-bar` | ☐ |
| D-81 | MIDI | Switch to **Pitch Bend** and click | Points added (−1…1), polyline drawn; double-click a point removes it | `.se-midi-lane-point` | ☐ |
| D-82 | MIDI | Switch to **Modulation** and click | Points added (0…1) on a separate lane | saved JSON `midi.mod` | ☐ |
| D-83 | MIDI | `Ctrl/⌘ + A`, then `←`/`→` | All notes move one grid step; `Shift + ←/→` lengthens/shortens | note starts/lengths | ☐ |
| D-84 | MIDI | `↑` / `↓` and `Shift + ↑/↓` | Semitone / octave transpose, clamped to the MIDI range | note pitches | ☐ |
| D-85 | MIDI | `0` on selected notes | Toggles the disabled look (`.is-disabled`) and `data-disabled` | note `aria-label` contains `disabled` | ☐ |
| D-86 | MIDI | Change **Quantize** | Notes quantize immediately (no Apply) to 1/4, 1/8 or 1/16 | note starts | ☐ |
| D-87 | MIDI | **Clear**, then **Import MIDI** with a .mid file | Notes cleared; import replaces them, sets BPM/signature from the file, toast `Imported N MIDI notes.` | `.se-toast` | ☐ |
| D-88 | MIDI | `Ctrl/⌘ + K` then press `A`…`;` | Musical typing auditions notes; `Z`/`X` change octave; `C`/`V` change velocity; button reads `Keys On` | `.se-midi-power`, `aria-pressed` | ☐ |

## E. Viewports — 24 checks

Rules come from `app/globals.css` `.se-*` media queries: **≤1600** hides meter + speed, **≤1400**
hides the save chip while a rail is open, **≤1100** hides save/meter/input-toggle/Stop/metronome,
**≤1000** removes rail padding, **≤900** hides the prompt bar and the undo/redo group, fixes the
track panel at 260 px, shrinks the header to 52 px and drops the second time readout, **≤900** also
narrows `.sp-slot` to 260 px and the catalogue to 2 columns, **≤767** swaps the whole shell for the
desktop gate. The gate is `max-width:767px`, so **768 px shows the editor** — that boundary is E-07.

| ID | Area | Action | Expected result | Evidence / selector | ☐ |
|---|---|---|---|---|---|
| E-01 | 1689×1277 | Load P1, no panels open | Header shows chip, undo/redo, full transport, time + bar/beat, BPM, signature, save chip, sync dot, meter, speed, Export, Library | `.se-head` children visible | ☐ |
| E-02 | 1689×1277 | Measure the bands | Header + body + bottom panel + footer exactly fill 1277 px; the shell itself never scrolls | `.se-shell` `scrollHeight === clientHeight` | ☐ |
| E-03 | 1689×1277 | Open the plugin dock | At least 3 slots (448 px each) visible without horizontal overlap of the header | `.sp-slot` `offsetWidth` = 448 | ☐ |
| E-04 | 1689×1277 | Screenshot the reference frame | Capture for the W2/W3 comparison set | `ours-<screen>.png` at 1689×1277 | ☐ |
| E-05 | 1280×800 | Reload P1 | **Master meter is gone** (≤1600 rule) | `.se-meter` `display:none` | ☐ |
| E-06 | 1280×800 | Check the speed pill | **Audition speed is gone** (≤1600 rule) | `[data-help="speed"]` hidden | ☐ |
| E-07 | 1280×800 | Check everything else in the header | Save chip, sync dot, Export, Library, transport still present | — | ☐ |
| E-08 | 1280×800 | Open the library | Rail takes 368 px; timeline keeps ≥ 4 bars at the default zoom; no horizontal page scroll | `.se-shell.has-rail` | ☐ |
| E-09 | 1280×800 | Open the plugin dock | Rail scrolls horizontally; slot 1 fully visible, no clipped knobs | `.sp-rail` | ☐ |
| E-10 | 768×1024 | Reload P1 | **Editor still renders** (gate starts at 767 px) | `.se-shell` visible, `.se-desktop-gate` hidden | ☐ |
| E-11 | 768×1024 | Check the header | 52 px tall; undo/redo group **hidden**; save chip, Stop, input toggle, metronome **hidden** | `.se-head-left .se-head-group` absent in layout | ☐ |
| E-12 | 768×1024 | Check the time readouts | Clock visible, **bar/beat hidden** | `.se-head-group.se-time .se-readout:nth-child(2)` | ☐ |
| E-13 | 768×1024 | Check the project chip | Chip caps at 150 px and truncates a long title without pushing the transport | `.se-chip` max-width | ☐ |
| E-14 | 768×1024 | Look for the prompt bar | **Hidden** (≤900) — the generate surface is unreachable at this width; record as a divergence if the reference keeps it | `.se-prompt` `display:none` | ☐ |
| E-15 | 768×1024 | Check the track panel | 260 px wide, all row controls still usable (mute/solo/arm/⌄) | `.se-tracks` | ☐ |
| E-16 | 768×1024 | Open the plugin catalogue | 2-column grid, cards readable, dialog still scrolls | `.sp-catalog` columns | ☐ |
| E-17 | 768×1024 | Open a plugin slot | Slot narrows to 260 px; knobs reflow without clipping | `.sp-slot` `offsetWidth` = 260 | ☐ |
| E-18 | 768×1024 | Open each dialog in turn (settings, share, clip menu, transform) | Each fits the viewport and scrolls internally; no control is off-screen | `role="dialog"` bounding boxes | ☐ |
| E-19 | 768×1024 | Open the assistant (key `1`) | 360 px panel overlays the left; body padding shifts 392 px; timeline still scrolls | `.se-shell.has-assistant` | ☐ |
| E-20 | 768×1024 | Open take lanes and the MIDI editor | Both fit; MIDI panel caps at 360 px and scrolls its roll | `.se-midi` max-height | ☐ |
| E-21 | 767×1024 | Reload P1 | **Desktop gate**: shell hidden, gate fills the viewport | `.se-desktop-gate{display:flex}`, `.se-shell{display:none}` | ☐ |
| E-22 | 767×1024 | Read the gate | `CAMXORA Studio`, the desktop-only sentence, and a `Back to Create` link to `/create` | `.se-gate-card`, `.se-gate-link` | ☐ |
| E-23 | 767×1024 | Scroll / tap around the gate | No editor chrome behind it, no horizontal scrollbar, link is the only focusable control | `document.body.scrollWidth` | ☐ |
| E-24 | All four | Check clipping and overlap generally | No control is clipped, no two header controls overlap, no text is cut mid-word; clip menu at the bottom-right corner still fully visible (height capped) | screenshots per viewport | ☐ |

---

## F. Async boundaries — 33 checks

Components: `StudioEditorShell.tsx` (`persist`, `performWrite`, `restoreDraft`, `resolveConflict*`),
`StudioSaveStatus.tsx`, `StudioDraft.tsx` (`lib/studio-draft.ts`), `lib/studio-errors.ts`,
`StudioProjectMenu.tsx` (`syncSentence`), assistant/transform notice blocks.
Use DevTools throttling / offline mode; do not stop the server for F-05…F-16.

| ID | Area | Action | Expected result | Evidence / selector | ☐ |
|---|---|---|---|---|---|
| F-01 | Autosave | Move a clip | Save chip goes `Saving…` then `Saved` within a second or two | `.se-save[aria-live="polite"]` | ☐ |
| F-02 | Autosave | Watch the chip during a long write | `Saving…` is announced politely, never a modal; editing stays possible | `aria-live` | ☐ |
| F-03 | Autosave | Make two edits back-to-back on a throttled connection | Both land; no spurious 409 banner; only the newest queued write runs | `.se-conflict` absent; final JSON has both edits | ☐ |
| F-04 | Autosave | Edit, then reload **while** the second write is queued | Draft banner offers the queued burst (draft is mirrored while a write is in flight) | `studio:draft:<id>` in localStorage | ☐ |
| F-05 | Autosave | Press `Ctrl/⌘ + S` | Write is forced immediately (no change required); chip cycles Saving… → Saved | save chip | ☐ |
| F-06 | Autosave | Take the API offline, then edit | Chip becomes `Save failed · Retry` (red/pressed); the chip itself is the retry button | `.se-save.on` inside `button` | ☐ |
| F-07 | Autosave | With a failed save, click the chip | Retry runs; on success the chip returns to `Saved` and the error banner clears | `.se-error` absent | ☐ |
| F-08 | Autosave | With an unsaved change, try to close the tab | Browser's own "Leave site?" guard appears (beforeunload) | `beforeunload` | ☐ |
| F-09 | Offline | Set the browser offline, then edit | Chip reads `Offline · changes not saved`; a draft is written; no request is attempted | `.se-save` label | ☐ |
| F-10 | Offline | Go back online | The queued burst is replayed; chip returns to `Saved`; the draft is cleared | `studio:draft:<id>` absent | ☐ |
| F-11 | Offline | Force the first replay to fail, stay online | A single automatic retry ~1.2 s later replays the burst; a second failure keeps the draft | network log: two PATCHes | ☐ |
| F-12 | Offline | Reload after a failed write | Banner `We found <an unsaved draft from N minutes ago>.` + `The last change did not reach the server.` | `.se-conflict[role="alert"]` | ☐ |
| F-13 | Draft | **Discard** | Draft removed, banner clears, server document unchanged | localStorage empty | ☐ |
| F-14 | Draft | **Restore draft** | Local document is applied **and** written to the server; banner clears | chip `Saved` | ☐ |
| F-15 | Conflict | Force a 409 (two tabs, same project) | Alertdialog `This project changed in another tab.` with both actions; chip is `Save failed` | `.se-conflict[role="alertdialog"]` | ☐ |
| F-16 | Conflict | **Keep mine** | Local document is written without a version guard and the banner clears | chip `Saved` | ☐ |
| F-17 | Conflict | **Reload theirs** | Server document replaces the local one; tracks/clips re-read; banner clears | `.se-conflict` absent | ☐ |
| F-18 | Conflict | After a failed write, check the queued write | The queued burst is dropped (not replayed) so the user does not get a second phantom conflict | log shows no extra PATCH | ☐ |
| F-19 | Conflict | Rename the project, then edit within a second | No 409: the rename's `updated_at` is adopted synchronously | chip `Saved` | ☐ |
| F-20 | Mirror | With sync off in the environment | Sync dot renders the `pending` state; tooltip says the mirror is waiting; no error toast | `.se-sync-dot[data-state="pending"]` | ☐ |
| F-21 | Mirror | With sync on and a linked project | Dot is `linked`; tooltip mentions staged mirroring (and paused writes when `state_sync` is false) | `SYNC_TITLE.linked` text | ☐ |
| F-22 | Mirror | After a successful push | Dot is `synced` (green) | `[data-state="synced"]` | ☐ |
| F-23 | Mirror | With Suno ahead (`status: "conflict"`) | Dot is `conflict` (amber) and the `Suno has newer changes` dialog opens on load until dismissed for that project | `[data-state="conflict"]`, `[aria-label="Suno version conflict"]` | ☐ |
| F-24 | Mirror | With a provider rejection | Dot is `error` (red); tooltip appends `last_error`; skipped-clip counts appear when present | `title` text | ☐ |
| F-25 | Mirror | Leave the editor idle ~45 s | Mirror state refreshes on the 15 s poll (remote check every 4th tick) without a reload | network log | ☐ |
| F-26 | Mirror | Save an edit | A mirror read follows ~2 s after `Saved` | network log | ☐ |
| F-27 | Provider | Submit a prompt with an empty balance | Assistant notice `Not enough credits` + `View plans` link + provider text | `.se-assistant-notice.credits` | ☐ |
| F-28 | Provider | Submit a prompt blocked by policy | Notice `That prompt was refused` + `Edit prompt` button that refocuses the input | `.se-assistant-notice` | ☐ |
| F-29 | Provider | Trigger Extend / Cover / Remaster with no credits | Transform notice `Not enough credits` + `This edit spends credits your balance does not cover.` + `View plans` | `.se-transform-notice.credits` | ☐ |
| F-30 | Provider | Trigger any transform that fails for another reason | Notice `That edit did not run` + the classified sentence + dismissible ✕ | `.se-transform-notice` | ☐ |
| F-31 | Provider | Fail an upload from the library | Library surfaces the error (`Some library data could not load.` or the endpoint message) and offers Retry | `.se-lib-error`, `.se-lib-retry` | ☐ |
| F-32 | Provider | Fail stem separation | `Get stems` status reports the classified error; no tracks are added | `.se-stem-status.off` | ☐ |
| F-33 | Provider | Press a Suno-conflict action twice quickly | Buttons disable while `sunoBusy`; one request only | `disabled` on all four | ☐ |

---

## G. Flags — what is not checkable, and what to record

These are called out so the W5 agent does not silently "pass" something unverifiable, and so the
W0 consolidator knows which rows are observations rather than assertions.

**G-1 — DSP correctness is out of scope for a manual UI pass.** No row claims that the compressor
actually compresses, that the reverb decays for 2.4 s, that warp markers audibly change timing, or
that a send is audible at the stated level. Rows B-138 and the play/loop rows only prove the graph is
not silent. Real signal verification needs an analyser/offline render (a unit or automated task, not
this checklist).

**G-2 — Delay ▸ Tempo mode has a model flag but no UI.** `ParamDef.tempoSynced` is set on
`delay.time`, and `tempoSynced` appears nowhere outside the registry (verified by grep across
`components/studio/*.tsx` and `lib/*.ts`). B-41 is therefore written as *record a divergence if the
reference shows note divisions* — do not mark it FAIL against a remembered reference; compare with
the captured frame.

**G-3 — Provider output is not asserted.** Extend / Cover / Remaster / Vocals / Instrumental /
Mashup / Replace / Stems / Get MIDI rows verify only the **UI states** (enabled/disabled, queued
toast, refusal notice, failure notice). Whether the provider returns audio is D4/W6, which spends
credits and needs separate approval. Where a check needs a real generation, the fixture P1/P2 already
contains one — do not generate new material for this pass.

**G-4 — Beat/transient marker counts are data-dependent.** D-67 asserts the structural rule
(2 / per-beat / per-onset + the 2-marker fallback), not an absolute number; the capture's "~358
markers" figure is a property of that specific asset, not a gate.

**G-5 — Microphone capture is device-dependent.** C-150…C-154 verify arming, the input picker,
count-in state and the record button's own state machine. Whether the take contains the right audio
(and whether the chosen device exists) depends on the host machine and is not checkable here.

**G-6 — Additive clip selection does not exist.** `handleClipPointerDown` ignores Shift/⌘/Ctrl and
always replaces the selection; `selectedIds` is only populated by the marquee, `Ctrl+A`, or the
existing group. D-05 records this as a behaviour; if the reference supports Shift-click, classify it
as an **absence** (§5 of `CLONE_DEFINITION.md`), not a layout defect.

**G-7 — Paste keeps the origin track.** The copy buffer stores `trackId` and `duplicateEntries`
reuses it, so paste never retargets the focused track (D-33). Same classification rule as G-6.

**G-8 — Two-session rows.** D-06 of the plan requires independent verification; the presence avatar
strip (`.se-presence`) and remote playheads can only be checked with a second signed-in client. They
are folded into E-19/F-25 rather than given their own rows, because a single-agent run cannot prove
them. Run them only if W4's stack is still up with two browser profiles.

**G-9 — Clipboard permission is environment-specific.** C-43 (copy-link failure) needs the browser's
clipboard permission denied on purpose; on some builds `navigator.clipboard` is undefined and the
failure path is unreachable. Record N-A with the reason instead of a FAIL.

**G-10 — Pixel identity belongs to W2.** This checklist asserts *structure* (a control exists, is
enabled, sits in the stated place) and *strings*. It does not assert that a frame is pixel-identical;
that verdict comes from `scripts/pixel-diff.mjs` under the tolerance policy in the plan §4/W2.

**G-11 — Three rows depend on pricing data.** C-170 and the transform dialogs show credit costs only
when the `pricing` table answers; if the endpoint is unavailable the cost sentence is absent. Record
`cost shown = n/a`, not FAIL, and note it for D4.

**G-12 — `has-rail` interactivity.** E-08/E-19 cross two breakpoints (≤1000 removes rail padding,
≤1400 hides the save chip while a rail is open). If a screen is captured at 1280 with the library
open, the missing save chip is **expected**, not a regression.

---

## H. Counts

| Area | Scope | Checks |
|---|---|---|
| **A** | Entry, gates, chrome | **16** |
| **B** | Plugins — every card, parameter, mode, preset, chain op, master, designers | **138** |
| **C** | Every menu, dialog, settings pane, home, share, onboarding | **211** |
| **D** | Arrangement, clip, warp and MIDI gestures | **88** |
| **E** | Four viewports incl. the 767/768 gate boundary | **24** |
| **F** | Autosave, queueing, conflict, offline draft, mirror, provider errors | **33** |
| **Total** | | **510** |

Every ID is contiguous inside its area (`A-01…A-16`, `B-01…B-138`, `C-01…C-211`, `D-01…D-88`,
`E-01…E-24`, `F-01…F-33`), so a missing row is visible by inspection and the count can be re-derived
mechanically.

**Suggested execution order** (one sitting per block, commit the notes between blocks):

1. **A + C1–C3** (~60 rows, 45 min) — entry, project menu, settings. Everything else needs a project.
2. **B** (~138 rows, 90 min) — the core W5 requirement. Do one plugin per sub-table, screenshot the
   card, then run the parameter rows against it.
3. **C4–C10** (~110 rows, 60 min) — clip/range/track/export/learn/transport/footer.
4. **D** (~88 rows, 75 min) — gestures; keep P2 handy for Heal Edits and take lanes.
5. **F** (~33 rows, 40 min) — needs DevTools; do it last so failures cannot pollute other areas.
6. **E** (~24 rows, 30 min) — re-run the marked rows at each size; capture all four viewports.

Roughly **5–6 hours** for one agent. That is the cost of the "everything" criterion in the plan's §1;
it is not a smoke test.

---

## I. Per-control verdict template

Copy this block once per area into the W5 report:

```
Area:            B  (Plugins)
Viewport(s):     1689x1277, 1280x800, 768x1024
Fixture:         P1 (chain: Compressor -> Reverb)
Date / agent:    2026-11-__ / qa/manual-deep

PASS:   B-01 ... B-138                     (n)
FAIL:   <ids>  -> one line each, with screenshot
N-A:    <ids>  -> reason (see §G)
Gaps to classify: layout | state | absence | provider
```





