# W5 — independent manual run, area B (plugins) and area E (viewports)

**Date:** 2026-11-17
**Agent:** W5 (`qa/manual-run`) — a different agent from Agent A; A's pass set was not used
**Base:** `origin/main` `90db80ab`
**Worktree:** `C:\Users\Kong Somvannda\AppData\Local\Temp\camxora-res-manual-run`
**Scope executed:** **162 / 509** checks — **B (138)** and **E (24)** in full
**Verdict:** **150 PASS · 12 FAIL · 0 N/A · 0 BLOCKED**

The walkthrough is a scripted real-browser run (Playwright/Chromium at 1× DPR) against the
full local stack. Every row below was produced by driving the UI, not by reading code;
code references are only used to name the cause of a failure.

**Base difference vs the checklist.** The checklist was written at `4abff799`. Five web files
changed before this run (`git diff 4abff799 90db80ab`): `StudioPluginDock.tsx` and
`lib/studio-plugins.ts` gained the Delay ▸ Tempo note-division select plus the `bpm` prop,
`StudioEditorShell.tsx` passed that prop (and renamed one menu row to `Download .WAV`),
`StudioSongDetail.tsx` changed one label, and `globals.css` dropped `overflow-y:auto` from
`.se-clip-menu`. The first change makes checklist row B-41/G-2 stale; the last one is the
cause of the new E-18/E-24 failure (D4).

---

## 1. Totals

| Area | Checks | PASS | FAIL | N/A | BLOCKED |
|---|---|---|---|---|---|
| **B — plugins** | 138 | 128 | 10 | 0 | 0 |
| **E — viewports** | 24 | 22 | 2 | 0 | 0 |
| **This pass** | **162** | **150** | **12** | **0** | **0** |

Failing ids: **B-51, B-52, B-55, B-56, B-76, B-97, B-98, B-101, B-102, B-108, E-18, E-24**.
Each has a screenshot in `docs/studio/reports/evidence-w5/`.

---

## 2. What was actually running

One stack, started once, kept alive for the whole pass:

| Component | Port | Evidence it was live |
|---|---|---|
| moto (S3) | 9000 | bucket `camxora-studio` created; IR/export paths answered |
| platform API | 8100 | `/health` 200; sandbox DB `camxora_pfm_sandbox`; Studio token set; Suno base → `:4003` |
| musicapi | 4003 | `/health` 200; `STUDIO_INTERNAL_TOKEN` matches the platform value |
| web dev server | 3103 | `/studio` 200; editor loads P1/P2/P-long |
| platform worker | — | started, drains `job_queue` |

Account: `somvannda@gmail.com` / `StudioLocal!2026`. No provider credits were spent.

### Fixtures (built through the sandbox API, as the checklist requires)

| Fixture | Contents |
|---|---|
| **P1** | 120 BPM 4/4; **Drums** (two audio clips from `song-w5-1`, clip A ends before clip B), **Bass** (MIDI clip, 8 notes), **Vox** (uploaded audio, no `songId`), **Scratch** (hidden + muted, one clip); Drums chain = Compressor → Reverb; master = Limiter |
| **P2** | P1 with clip A carrying `sourceAudioUrl`, `sourceDuration` and a two-take stack |
| **P-long** | P1 with a 96-character title (E-13 truncation) |
| **P-legacy** | P1 with a chain entry saved as `pluginId: "chorus"` (B-76) |

### Honest limits of this run

- **B-105 / B-106 / B-108** exercise the *designed plugin* flow. The authoring call
  (`POST …/plugins/author` + its poll) was answered by a network mock returning a ready
  descriptor, because the real call spends credits (the checklist's G-3 rule). The UI states
  are real; the agent's output is not.
- **B-138** proves the graph is not silent (the master meter moved: `-18.1 → -13.5 dB pk`).
  DSP correctness is out of scope for a UI pass (G-1).
- **E-01/E-07** do not assert the mirror dot. It is conditional on a Suno link
  (`StudioSaveStatus.tsx:51`) and this fixture is unlinked, so the dot is absent by design;
  the mirror states are F-area rows.
- **E-18/E-24** measure the clip menu's *box* and its individual rows. A box that is capped
  while its content paints past the viewport is exactly the failure these rows look for; the
  five off-screen rows are counted, not inferred.
- **B-107** ran with Drums selected. The no-track fallback
  (`selectedTrack ?? tracks[0]`, `StudioEditorShell.tsx:5509`) is present but was not forced.
- **B-41 is record-only** (per the checklist): see observation O-4 — the row text and flag
  G-2 are stale at this commit.
- No row was marked N/A or BLOCKED: every B and E row was executable on this stack.

---

## 3. Ranked defects

Ranked by user impact and blast radius. None of these were fixed (the pass records, it does
not repair).

### D1 — Dragging an EQ band handle never changes Frequency (B-55, B-56)

Dragging a handle horizontally leaves `Freq` at its old value; only `Gain` follows the
pointer. Vertical drag works, so the control looks half-alive.

Reproduce: Drums → EQ → drag the Band 1 handle left 200 px and up 60 px → readouts show
`Freq 1.0khz` (unchanged) and `Gain 21.1db`. Dragging to the bottom-right corner still shows
`1.0khz`, so the “clamps to 20 hz / 20 kHz” row cannot pass either.

Cause: `EqCard.dragTo` emits **two** `onChange` calls in one event
(`components/studio/StudioPluginDock.tsx:488-489`), and both are applied through
`setParam(chain, …)` with the same pre-update `chain` snapshot
(`components/studio/StudioPluginDock.tsx:1044-1047` → `StudioEditorShell.tsx:7350`). The
second call (`band*.gain`) overwrites the first (`band*.freq`).

Evidence: `B-55-1689x1277.png`, `B-56-1689x1277.png`.

### D2 — Undo/redo does not refresh the plugin dock (B-97, B-101)

`Ctrl+Z` restores the document (saved JSON flips back to `compressor, reverb`) but the rail
does not change: after removing the last slot, undo leaves the rail empty until a reload.
Redo has the same shape, so “add → undo → redo” cannot be read off the UI.

Reproduce: remove every effect on Drums, press `Ctrl+Z` → `.sp-slot` count stays 0; reload
→ the removed compressor returns with its preset and values. Verified from the API in the
same session: the chain order after `Ctrl+Z` was `compressor, reverb` while the dock still
rendered `Reverb, Compressor`.

Cause: `applyHistoryEntry` resets `localTracks` but not `localChains` / `localMasterChain`
(`StudioEditorShell.tsx:1931-1945`); those caches are only cleared when the project id
changes (`StudioEditorShell.tsx:3226-3246`), and `chains = localChains ?? derivedChains`
keeps serving the stale map (`StudioEditorShell.tsx:3227`).

Evidence: `B-97-1689x1277.png`, `B-101-1689x1277.png`.

### D3 — A designed plugin cannot actually be dragged onto a track (B-108)

The card advertises `application/x-camxora-plugin` and the track rows have a drop handler,
but the card only exists inside the assistant, and the assistant hides the track panel
(`.se-shell.has-assistant .se-tracks{display:none}`, `app/globals.css:4777`). Measured:
**0 visible track rows** while the card is on screen, so there is no drop target at any of
the four viewports.

Reproduce: Drums → Add effect → ⋯ → Create new plugin → prompt → Build it (mock) → the
card appears → try to drag it to a track row: no row is visible.

Cause: card in `StudioEditorShell.tsx:6320-6348`; drop handler on the hidden panel
(`StudioEditorShell.tsx:5872-5879`).

Evidence: `B-108-1689x1277.png`.

### D4 — The clip menu's lower rows paint off-screen with no way to scroll to them (E-18, E-24)

At 768×1024 the menu's box is capped at 633 px but its content is 1064 px and
`overflow-y` computes to **`visible`**: the last five rows sit at y≈1410, i.e. 386 px below the
viewport, and no scrollbar exists. `Add FX`, `Download .WAV`, `Get MIDI` and the transform
rows are therefore unreachable at tablet width. The same five rows overflow at 1689×1277.

Reproduce: any clip → right-click near the bottom of the timeline → count rows whose rect is
outside the viewport (`5`), and read `getComputedStyle(menu).overflowY` (`visible`).

Cause: `overflow-y:auto` was removed from `.se-clip-menu` in `90db80ab`
(`app/globals.css:5008`) while the inline `maxHeight` cap stayed
(`StudioEditorShell.tsx:6428-6437`). This is a regression introduced by the newest commit,
not by the checklist's base.

Evidence: `E-18-768x1024.png`, `E-24-1689x1277.png`.

### D5 — The header's clock overlaps the tempo controls at 768 px (E-24)

At 768×1024 the centre column cannot fit the transport plus the time group: its content is
187 px wide inside a 103 px column, so the time group (x 370–447) runs underneath the tempo
group (x 371–517). The clock and the BPM field paint on top of each other.

Reproduce: 768×1024 → open P1 → measure `.se-head-center` (`scrollWidth` 187 vs
`clientWidth` 103) and the two groups' rects (they intersect).

Cause: the header is a three-column grid (`auto 1fr auto`) whose side columns do not shrink
— the chip caps at 150 px but the right column keeps BPM + signature + Export + Library —
so at ≤900 the 1fr column is narrower than its content (`app/globals.css:4982` shrinks the
header but not the centre content).

Evidence: `E-24-768x1024.png` (header at 768), `ours-studio-editor-768x1024.png`.

### D6 — Footer chain chips belong to the master chain, not the selected track (B-102)

With Drums holding Compressor → Reverb → Delay, the footer shows a single chip: **Limiter**
(the master chain). The row that expects the track's chain in order cannot pass, and B-95's
“footer chip for it disappears” is unprovable for track slots.

Reproduce: select Drums (chain compressor → reverb → delay) and read the footer: one chip,
`Limiter`, is shown. Adding/removing a track effect never changes the chip row.

Cause: `StudioFooter` is fed `masterChain.map(entry => entry.type)` at
`StudioEditorShell.tsx:7354-7355`, while the footer renders it as `.se-chain-chip`
(`components/studio/StudioFooter.tsx:109-133`).

Evidence: `B-102-1689x1277.png`.

### D7 — A legacy `chorus` chain entry renders no slot at all (B-76)

A project saved with `pluginId: "chorus"` (the pre-rename id) shows an **empty rail** — not a
Rhythm Gate slot. The migration exists (`sanitizeChain`, `lib/studio-plugin-chain.ts:256-279`)
but the editor never sanitizes the loaded document: `derivedChains` returns `data.chains`
raw (`StudioEditorShell.tsx:3205-3208`), and the dock silently drops ids it does not know
(`StudioPluginDock.tsx:780`, `if (!plugin) return null`). The same raw read means the audio
graph never builds the effect either.

Reproduce: open P-legacy (`chains["t-drums"] = [{pluginId:"chorus", params:{rate:6,depth:40,mix:30}}]`)
→ rail is empty.

Evidence: `B-76-1689x1277.png`.

### D8 — Popping a slot out collapses its place in the rail (B-98)

The popped card correctly becomes a fixed overlay at `right:24px; bottom:88px`, but the rail
does not keep a placeholder: the next slot jumps from **x=468 to x=10**. The checklist
expects the gap to stay.

Reproduce: with two slots (Compressor → Reverb) press **Pop out** on slot 1 and measure slot 2's
left edge: `468` before, `10` after. The popped card itself lands correctly.

Cause: `.sp-slot.is-popped{position:fixed;…}` (`app/globals.css:4464`) removes the card from
flow without reserving its width.

Evidence: `B-98-1689x1277.png`.

### D9 — Frequency readouts keep a trailing `.0` between 1 kHz and 10 kHz (B-51, B-52)

`1.0khz`, `4.0khz`, `6.0khz` where the checklist's formatting rule (B-19) and the B-51/B-52
expected values say `1khz`, `4khz`, `6khz`. Above 10 kHz (`14khz`) and below 1 kHz
(`120hz`) the format is right.

Reproduce: Drums → EQ → band 1 reads `1.0khz` (row expects `1khz`); band 3 reads `4.0khz`.
The same value formatted by the 10 kHz branch reads `14khz`, so only 1000–9999 is affected.

Cause: `formatValue` uses `toFixed(value >= 10000 ? 0 : 1)` for Hz
(`components/studio/ParamKnob.tsx:28`).

Evidence: `B-51-1689x1277.png`, `B-52-1689x1277.png`.

### Observations (not scored as B/E failures)

- **O-1 — `Ctrl+Shift+,` cannot open Studio Settings on a normal keyboard.** The handler
  requires `event.key === ","`, but Shift+Comma yields `">"` (`StudioProjectMenu.tsx:187`).
  E-18 had to open Settings from the project menu. Cross-area: C-08 will hit the same wall.
- **O-2 — The plugin catalogue ignores Escape.** The backdrop click and ✕ close it
  (`StudioPluginDock.tsx:1264-1389` has no key handler). E-17 initially failed because the
  dialog stayed open; it was closed with ✕.
- **O-3 — After a project loads nothing is selected**, so the bottom band is empty until a
  track is clicked (`selectedTrack` starts `null`, `StudioEditorShell.tsx:764`). E-02/E-03
  select Drums first; the checklist's “default landing band” reads as if a surface were
  already mounted.
- **O-4 — B-41 and flag G-2 are stale.** At `90db80ab` Delay's Tempo mode *does* render a
  note-division select (`Time division`: 1/32 · 1/16 · 1/8 · 1/4 · 1/2 · 1 bar), which is the
  behaviour the row was written to record as missing. Recorded as PASS on the row's
  record-only instruction, with this note.
- **O-5 — Toasts use typographic quotes** (`Preset “W5 preset” saved.`), where the rows
  spell straight quotes (B-88, B-130). Cosmetic; the assertion normalises them.
- **O-6 — The header is 52 px at every width** (`globals.css:4616`), so the ≤900 “shrinks to
  52 px” rule repeats the base height instead of shrinking it. E-11 still passes (52 px at 768).
- **O-7 — The library panel's own box is 360 px while the body reserves 368 px** (`E-08`).
  The row's “takes 368 px” matches the reservation; the 8 px difference is a gap, not a bug.

---

## 4. Per-check results

### B — plugins, every card and control (138 checks)

Fixture: P1 (Drums with Compressor → Reverb, MIDI Bass, uploaded Vox, hidden+muted Scratch). Track 1 selected unless the row says otherwise. Viewport 1689×1277 for every row; the viewport matrix is area E. Rows were executed against the real dev stack; only the credit-spending plugin authoring call in B-105/B-106 was mocked at the network layer.

#### B1. Dock chrome and catalogue (22)

| ID | Verdict | Evidence (measured) |
|---|---|---|
| B-01 | PASS | .sp-empty = "No effects on this track yet. /  / Add effect" |
| B-02 | PASS | .sp-slot aria-labels = ["Compressor slot 1","Reverb slot 2"] |
| B-03 | PASS | title="Add a track plugin"; autofocus=Search plugins; close + options buttons present |
| B-04 | PASS | order = Compressor / Convolution / Delay / Distortion / EQ / Gate / Limiter / Reverb / Rhythm Gate / Stereo Utility |
| B-05 | PASS | Compressor card: preview, 3 mini knobs, description matches the registry |
| B-06 | PASS | results = ["Reverb"] |
| B-07 | PASS | results = ["Limiter"] |
| B-08 | PASS | .sp-none = "No effects match “zzzz”.", 0 cards |
| B-09 | PASS | dialog stayed open; slot count unchanged (2) |
| B-10 | PASS | rows = ["Create new plugin"] |
| B-11 | PASS | card = "Create new plugin / BETA / Describe it in the prompt bar" |
| B-12 | PASS | slot 3 = Delay; query cleared on reopen |
| B-13 | PASS | two independent slots: Delay slot 3, Delay slot 4 |
| B-14 | PASS | ghosts = 1, Add effect present |
| B-15 | PASS | present=["Compressor","Reverb"]; ghosts=["Add Delay"] |
| B-16 | PASS | Delay appended directly (no dialog) -> slot 3 |
| B-17 | PASS | section.sp-dock[aria-label="Plugins for Drums"] |
| B-18 | PASS | header order = dot -> name -> preset+stepper -> bypass -> move/popout/close |
| B-19 | PASS | Compressor readouts = {"Thresh":"-18db","Ratio":"4","Knee":"6db","Atk":"10ms","Rel":"120ms","Gain":"0db"} |
| B-20 | PASS | 6 controls disabled; .is-bypassed applied and cleared |
| B-21 | PASS | widths=448,448,448; overflowX=auto; single row |
| B-22 | PASS | toggle=per-slot button; panels=0 popped; windows=2/2 popped |

#### B2. Compressor (8)

| ID | Verdict | Evidence (measured) |
|---|---|---|
| B-23 | PASS | {"Thresh":"-18db","Ratio":"4","Knee":"6db","Atk":"10ms","Rel":"120ms","Gain":"0db"} |
| B-24 | PASS | DOM order = Thresh / Ratio / Knee / Atk / Rel / Gain |
| B-25 | PASS | min=-60 (-60db), max=0 (0db), -200 clamps to -60 |
| B-26 | PASS | 1 -> "1", 20 -> "20" |
| B-27 | PASS | path + dot moved; width stable at 216px |
| B-28 | PASS | 9 rows; current = ["None"] |
| B-29 | PASS | button label = "Bass — Post-fader" |
| B-30 | PASS | label="None"; saved JSON sidechain=null |

#### B3. Convolution (7)

| ID | Verdict | Evidence (measured) |
|---|---|---|
| B-31 | PASS | {"Mix":"50%","Gain":"0db","Pre":"0ms","Width":"100%"} |
| B-32 | PASS | button="NO ASSET LOADED"; svg aria-label="No asset loaded"; no envelope path |
| B-33 | PASS | 6 category rows; "HALLS" collapses/expands |
| B-34 | PASS | IR label="Halls › Cathedral"; envelope drawn; preset label=Custom |
| B-35 | PASS | menu closed by Escape; asset unchanged ("Halls › Cathedral") |
| B-36 | PASS | menu rows = 6; no "Design response." row |
| B-37 | PASS | Design response. row present; designer dialog opened |

#### B4. Delay (6)

| ID | Verdict | Evidence (measured) |
|---|---|---|
| B-38 | PASS | {"Time":"350ms","Feedback":"35%","Mix":"25%","Low Cut":"120hz","High Cut":"12khz"} |
| B-39 | PASS | tablist "Delay mode": Time / Tempo; Time selected |
| B-40 | PASS | Tempo aria-selected=true, class .on |
| B-41 | PASS | record-only: as-built Tempo mode shows a Time division select (1/32 / 1/16 / 1/8 / 1/4 / 1/2 / 1 bar) instead of the ms knob; row text and flag G-2 are stale at 90db80ab |
| B-42 | PASS | after reload Tempo selected; saved JSON mode="tempo" |
| B-43 | PASS | {"Time":"375ms","Feedback":"55%","Mix":"30%","Low Cut":"250hz","High Cut":"6.0khz"} (High Cut reads 6.0khz, not the row's 6khz) |

#### B5. Distortion (5)

| ID | Verdict | Evidence (measured) |
|---|---|---|
| B-44 | PASS | {"Drive":"30%","Tilt":"0","Bass":"0db","Freq":"800hz"} |
| B-45 | PASS | tabs = Hard / Fold / Align / Sine / Crush; Hard selected |
| B-46 | PASS | Fold:1, Align:1, Sine:1, Crush:1, Hard:1 |
| B-47 | PASS | ends read "-100" and "100" with no unit |
| B-48 | PASS | dial at 630hz = 49.9% of travel (log 49.9%, arithmetic 3.1%) |

#### B6. EQ (10)

| ID | Verdict | Evidence (measured) |
|---|---|---|
| B-49 | PASS | band select + enable switch + 6 shapes + shared curve + Freq/Q/Gain |
| B-50 | PASS | options=Band 1, Band 2, Band 3, Band 4; selected=Band 1; handle .on = Band 1 |
| B-51 | FAIL | Expected `1khz`, measured **`1.0khz`** (Q `1`, Gain `0db`). Trailing-zero defect, see D9. — `B-51-1689x1277.png` |
| B-52 | FAIL | Band 3 measured **`4.0khz`** where the row expects `4khz`; bands 2 and 4 read `200hz` / `10khz`. Trailing-zero defect, see D9. — `B-52-1689x1277.png` |
| B-53 | PASS | aria-checked flips; handle count 4 -> 3 -> 4 |
| B-54 | PASS | pressed moved through Low cut / Bell / High shelf / Low shelf / High cut / Notch; saved band1.type=5 after Notch |
| B-55 | FAIL | After a 200 px horizontal + 60 px vertical drag on the Band 1 handle: **Freq stayed `1.0khz`**, Gain followed to `21.1db`. See D1. — `B-55-1689x1277.png` |
| B-56 | FAIL | Dragged past the curve's top-left corner: **Freq still `1.0khz`** (row expects `20hz`), Gain went to `21.1db`; bottom-right gave `-16.3db` with Freq unchanged. See D1. — `B-56-1689x1277.png` |
| B-57 | PASS | 11 EQ card controls disabled while bypassed |
| B-58 | PASS | no text inside the curve; handles = ["Band 1 handle","Band 2 handle","Band 3 handle","Band 4 handle"] |

#### B7. Gate (4)

| ID | Verdict | Evidence (measured) |
|---|---|---|
| B-59 | PASS | {"Threshold":"-45db","Floor":"-60db","Attack":"2ms","Hold":"50ms"} |
| B-60 | PASS | DOM order = Threshold / Floor / Attack / Hold |
| B-61 | PASS | {"Threshold":"-40db","Floor":"-70db","Attack":"1ms","Hold":"30ms"} |
| B-62 | PASS | {"Threshold":"-50db","Floor":"-60db","Attack":"10ms","Hold":"120ms"} |

#### B8. Limiter (4)

| ID | Verdict | Evidence (measured) |
|---|---|---|
| B-63 | PASS | {"Lookahead":"3ms","Pre Gain":"0db","Attack":"1ms","Release":"60ms"} |
| B-64 | PASS | {"Lookahead":"3ms","Pre Gain":"6db","Attack":"1ms","Release":"50ms"} |
| B-65 | PASS | {"Lookahead":"5ms","Pre Gain":"0db","Attack":"3ms","Release":"120ms"} |
| B-66 | PASS | 0 mode tabs, 0 asset slots, 4 knobs |

#### B9. Reverb (5)

| ID | Verdict | Evidence (measured) |
|---|---|---|
| B-67 | PASS | {"Decay":"2.4s","Mix":"25%","Width":"100%","Damping":"40%","Predelay":"20ms","Low Cut":"120hz","High Cut":"14khz"} |
| B-68 | PASS | readouts = ["2.4s","25%","100%","40%","20ms","120hz","14khz"] |
| B-69 | PASS | {"Room":{"Decay":"1.2s","Mix":"18%","Width":"100%","Damping":"55%","Predelay":"10ms","Low Cut":"120hz","High Cut":"14khz"},"Hall":{"Decay":"3.2s","Mix":"28%","Width":"120%","Damping":"40%","Predelay":"25ms","Low Cut":"120hz","High Cut":"12khz"},"Plate":{"Decay":"1.8s","Mix":"22%","Width":"90%","Damping":"30%","Predelay":"5ms","Low Cut":"150hz","High Cut":"16khz"}} |
| B-70 | PASS | max readout 20.0s; setting 25 clamps to 20 |
| B-71 | PASS | 0 mode tabs, 7 knobs |

#### B10. Rhythm Gate (5)

| ID | Verdict | Evidence (measured) |
|---|---|---|
| B-72 | PASS | options=1/16 / 1/8 / 1/4; value=1 (1/8) |
| B-73 | PASS | Depth=75% Mix=65% from a 0..1 model |
| B-74 | PASS | {"Atk":"0.1","Rel":"0.2"} |
| B-75 | PASS | after reload Rate=1/4; saved JSON rate=2 |
| B-76 | FAIL | P-legacy (`pluginId:"chorus"`) renders **0 slots** — no Rhythm Gate slot appears. See D7. — `B-76-1689x1277.png` |

#### B11. Stereo Utility (5)

| ID | Verdict | Evidence (measured) |
|---|---|---|
| B-77 | PASS | {"Level":"0db","Width":"150%","Pan":"0","Bass Mono":"120hz"} |
| B-78 | PASS | DOM order = Level / Width / Pan / Bass Mono |
| B-79 | PASS | readout = 200% |
| B-80 | PASS | -100 / 100, no unit |
| B-81 | PASS | rows = ["Clear all settings","Save preset…","Default"] |

#### B12. Presets and the dirty/Update cycle (9)

| ID | Verdict | Evidence (measured) |
|---|---|---|
| B-82 | PASS | label=Custom; Update button visible |
| B-83 | PASS | label=Vocal; Update gone; Knee stayed 9db |
| B-84 | PASS | rows = ["Clear all settings","Save preset…","Default","Vocal","Drum Bus","Gentle"] |
| B-85 | PASS | walked Vocal -> Drum Bus -> Gentle -> Default -> Vocal |
| B-86 | PASS | {"Thresh":"-18db","Knee":"6db","Gain":"0db"} |
| B-87 | PASS | label=Custom, no Update, Thresh back to -18 |
| B-88 | PASS | toast "Preset “W5 preset” saved."; menu + stepper include "W5 preset"; Ratio 7.5 kept |
| B-89 | PASS | inline field closed; "Discard me" absent from the menu |
| B-90 | PASS | after reload the preset is listed and applies Ratio 7.5; stored in pluginPresets |

#### B13. Chain operations (12)

| ID | Verdict | Evidence (measured) |
|---|---|---|
| B-91 | PASS | swapped to Reverb/Compressor then back |
| B-92 | PASS | Move Compressor left is disabled |
| B-93 | PASS | Move Reverb right is disabled |
| B-94 | PASS | aria-pressed=true, .is-bypassed, 6 knobs disabled, footer unchanged |
| B-95 | PASS | after removing Compressor the remaining slot is "Reverb slot 1" |
| B-96 | PASS | .sp-empty visible after removing the last slot |
| B-97 | FAIL | After removing the last slot and pressing Ctrl+Z the rail stayed at **0 slots**; the API document did revert (verified in-session). See D2. — `B-97-1689x1277.png` |
| B-98 | FAIL | Popped card: `position:fixed`, right gap 24 px, bottom gap 88 px — correct. But slot 2 moved **x=468 → x=10**: the rail keeps no placeholder. See D8. — `B-98-1689x1277.png` |
| B-99 | PASS | Dock works inline; poppedOut survived the reload |
| B-100 | PASS | Bass shows the empty state; Drums kept 3 slots |
| B-101 | FAIL | add → Ctrl+Z left the rail at **3 slots** (expected 2); Ctrl+Shift+Z likewise invisible. Saved JSON and a reload agree with the intended order. See D2. — `B-101-1689x1277.png` |
| B-102 | FAIL | Footer chips = **["Limiter"]** (the master chain) while Drums holds `compressor, reverb, delay`. See D6. — `B-102-1689x1277.png` |

#### B14. Designed (custom) plugins (8)

| ID | Verdict | Evidence (measured) |
|---|---|---|
| B-103 | PASS | .se-prompt.is-design, seeded placeholder, BETA badge |
| B-104 | PASS | restate + Build it / Change something… visible |
| B-105 | PASS | status line = "Starting the plugin authoring agent…" |
| B-106 | PASS | card aria-label = "W5 Designer, designed plugin" with Add to track |
| B-107 | PASS | slot added to the selected track as a Custom slot with 3 designed knobs |
| B-108 | FAIL | Payload type is correct (`application/x-camxora-plugin`) but **0 visible track rows** exist while the designed card is open, so the drop cannot be performed. See D3. — `B-108-1689x1277.png` |
| B-109 | PASS | 0 stepper buttons, preset disabled, knobs = ["Warmth","Air","Focus"] |
| B-110 | PASS | design tint and plugin context chip cleared |

#### B15. Master chain dock (8)

| ID | Verdict | Evidence (measured) |
|---|---|---|
| B-111 | PASS | .se-master-strip.is-selected; section.sp-dock[aria-label="Master chain"] |
| B-112 | PASS | controls = Lookahead / Pre Gain / Attack / Release / Link; Link reads On |
| B-113 | PASS | rows = ["Default","Clean","Warm","Loud"] |
| B-114 | PASS | menu row disabled; ghosts = ["Add EQ","Add Compressor"] |
| B-115 | PASS | EQ slot and Compressor slot each expose one Amount knob 0-100 |
| B-116 | PASS | footer chips ["Limiter","EQ","Compressor"] -> ["Limiter","Compressor"] |
| B-117 | PASS | footer plus selected Main and reopened the master dock |
| B-118 | PASS | saved masterChain = limiter/compressor; after reload + Main the dock and chips show both |

#### B16. Impulse Response Designer (6)

| ID | Verdict | Evidence (measured) |
|---|---|---|
| B-119 | PASS | dialog with preview + #ir-name / #ir-length / #ir-decay |
| B-120 | PASS | Name="Custom hall", Length=2.4s, Decay=2.6 |
| B-121 | PASS | preview path changed; labels = ["3.7s","4.2"] |
| B-122 | PASS | slot label "Custom › Custom hall"; picker has a Custom group listing it |
| B-123 | PASS | asset unchanged ("Custom › Custom hall"); "Discarded response" was not added |
| B-124 | PASS | after reload the Custom group still lists "Custom hall" |

#### B17. Wavetable Designer (6)

| ID | Verdict | Evidence (measured) |
|---|---|---|
| B-125 | PASS | MIDI editor open, .se-midi-design absent |
| B-126 | PASS | .se-midi-design visible |
| B-127 | PASS | 16 partial sliders + presets group |
| B-128 | PASS | preset "Square" redrew the preview; partials = ["100","0","33","0","20"] |
| B-129 | PASS | partial 0 -> flat line; partial 100 -> single sine |
| B-130 | PASS | toast "Wavetable “W5 table” saved."; instrument options = ["Triangle","Sine","Saw","W5 table"] |

#### B18. Clip-owned effects (4)

| ID | Verdict | Evidence (measured) |
|---|---|---|
| B-131 | PASS | 10 plugin rows + Cancel |
| B-132 | PASS | toast shown; saved clip.fx = [compressor] |
| B-133 | PASS | Remove FX enabled for a clip with fx |
| B-134 | PASS | fx cleared; Remove FX disabled again and Add FX available |

#### B19. Sends and routing surfaces (4)

| ID | Verdict | Evidence (measured) |
|---|---|---|
| B-135 | PASS | Delay + Reverb sliders, 0..100, both 0 |
| B-136 | PASS | saved tracks[t-drums].sends.delay = 42; slider 42 after reload |
| B-137 | PASS | .sp-sends is a sibling of .sp-rail, not part of the chain list |
| B-138 | PASS | meter samples = ["-18.1 dB pk","-13.9 dB pk","-13.5 dB pk","-24.3 dB pk","-24.3 dB pk","-24.3 dB pk"] |

### E — viewports (24 checks)

Rules come from `app/globals.css` media queries. Every row was measured in the live editor at the stated viewport; `ours-studio-editor-<viewport>.png` holds the frame for E-04/E-24.

| ID | Verdict | Evidence (measured) |
|---|---|---|
| E-01 | PASS | 19 header controls visible; sync dot count=1 (unlinked fixture) |
| E-02 | PASS | clientHeight=1277, scrollHeight=1277, head=52px, dock bottom=1225, footer bottom=1277 |
| E-03 | PASS | slot widths=448,448, lefts=10,468 |
| E-04 | PASS | docs/studio/reports/evidence-w5/ours-studio-editor-1689x1277.png |
| E-05 | PASS | .se-meter display=none |
| E-06 | PASS | [data-help="speed"] display=none |
| E-07 | PASS | save/export/library/transport/time/BPM visible; sync dot count=1 (unlinked fixture) |
| E-08 | PASS | body reserves 368px; panel box 360px; timeline clientWidth=652 (>=4x96); no page h-scroll (1280/1280) |
| E-09 | PASS | slot 1 x=10..458; overflowX=auto (1463/1280); 0 clipped knobs |
| E-10 | PASS | .se-shell visible; .se-desktop-gate display=none |
| E-11 | PASS | header=52px; hidden = undoGroup, save, stop, inputToggle, metronome |
| E-12 | PASS | clock display=block; bar/beat=none |
| E-13 | PASS | chip 150px (max 150px, truncated=true); Play starts at 322 > chip right 262 |
| E-14 | PASS | .se-prompt display=none |
| E-15 | PASS | .se-tracks width=260; mute/solo/arm/options visible |
| E-16 | PASS | 2 columns; overflowY=auto (990/611) |
| E-17 | PASS | slot width=260; 0 knobs outside the card |
| E-18 | FAIL | Settings, share and transform dialogs fit 768×1024. The clip menu does not: its box is capped (633 px, bottom 1016) but **5 menu rows sit below the viewport** (last row at y≈1410) with `overflow-y: visible` — no scrollbar. `Add FX` / `Download .WAV` are unreachable. See D4. — `E-18-768x1024.png` |
| E-19 | PASS | assistant 360px; body padding-left=392px; timeline scrolls (11558/376) |
| E-20 | PASS | takes fit (127px); MIDI 341px (max-height 360px), inner scroll=true |
| E-21 | PASS | gate display=flex (1024px tall); shell display=none |
| E-22 | PASS | heading + desktop-only sentence + Back to Create -> /create |
| E-23 | PASS | 0 chrome nodes visible; scrollWidth body=767 doc=767; 1 focusable control (link) |
| E-24 | FAIL | Header: 0 overlaps and no page h-scroll at 1689/1280/767, but at **768 the time group (370–447) overlaps the tempo group (371–517)** — centre content 187 px in a 103 px column. Clip menu: box 308..471 × 383..1269 within 1689×1277, but **5 rows overflow to y≈1410 with `overflow-y: visible`**. See D5 and D4. — `E-24-768x1024.png` |

---

## 5. What remains of the 509

| Area | Checks | Status after this pass |
|---|---|---|
| A — entry, gates, chrome | 16 | **not run by W5** |
| B — plugins | 138 | **done: 128 PASS / 10 FAIL** |
| C — every menu and dialog | 210 | **not run by W5** |
| D — arrangement, clip, warp, MIDI | 88 | **not run by W5** |
| E — viewports | 24 | **done: 22 PASS / 2 FAIL** |
| F — async boundaries | 33 | **not run by W5** |
| **Total** | **509** | **162 executed (31.8 %), 347 remaining** |

Remaining work on the plan's D6: an independent pass over **A (16), C (210), D (88) and
F (33)** — 347 checks — plus a **re-run of the 12 failed rows** (10 in B, 2 in E) after they
are fixed. D6 cannot be declared done from this report alone.

The 12 failures are behavioural, not all cosmetic: **D1 (EQ frequency), D2 (undo refresh),
D3 (designed-plugin drop), D4 (clip-menu overflow), D5 (header collision at 768)** should be
fixed before the D6 “second walkthrough” is considered complete. D4 and D5 are measurement
failures the earlier structural checks missed; D4 is a regression introduced by `90db80ab`,
the same commit this pass is based on.

---

## 6. Reproducing this pass

The harness lives in `camxora.com/tests/e2e/`:

| File | What it does |
|---|---|
| `w5-harness.ts` | login, P1/P2 fixtures, knob/readout helpers, verdict recorder |
| `w5-b1.spec.ts` … `w5-b5.spec.ts` | area B, sections B1–B19 |
| `w5-e.spec.ts` | area E, four viewports |

```powershell
# stack (one lifetime): moto :9000 + bucket, platform API :8100 (sandbox DB,
# Studio token, moto storage, Suno base -> :4003), musicapi :4003, web :3103
cd camxora.com
npx playwright test tests/e2e/w5-b1.spec.ts tests/e2e/w5-b2.spec.ts tests/e2e/w5-b3.spec.ts `
  tests/e2e/w5-b4.spec.ts tests/e2e/w5-b5.spec.ts tests/e2e/w5-e.spec.ts --workers=1 --reporter=list
```

Verdict rows are written to `docs/studio/reports/evidence-w5/results-b.json` and
`results-e.json`; screenshots for the failing rows and the four viewport frames are in the
same directory.
