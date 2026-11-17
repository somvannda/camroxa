# Pixel adjudication — the 55 `REVIEW` screens (W9)

**Date:** 2026-11-17
**Workstream:** W9, spawned from `docs/studio/RESIDUAL_VERIFICATION_PLAN.md` (D3)
**Branch:** `qa/pixel-adjudication`, base `origin/main` `83ec6786`
**Inputs:** `docs/studio/reports/pixel-diff/summary.json`, `2026-11-17-pixel-diff.md`,
`docs/studio/reference/screens/*`, `docs/studio/compare/*`, `docs/studio/reports/pixel-diff/*.png`,
`components/studio/*` at `83ec6786`.
**Scope:** adjudication only. No server, no port, no capture, no product or reference change,
`G:\Developments\Projects\Camxora` untouched, nothing pushed.

> **Base movement.** The measurement was made on `90db80ab` (55 `REVIEW`). During the work
> `origin/main` advanced to `83ec6786`, whose summary now has **54 `REVIEW`**: S56 became
> `NO-FRAME` because its reference frame was the marketing hero and has been re-filed as an S01
> frame. That is the same conclusion this report reaches for S56 (§3 row 42, `REGION`), so the row
> is kept here — 55 rows — with its diff % marked as measured at `90db80ab`, and S56 noted as now
> a corpus gap rather than a diffable row. No other row's verdict, frame, capture or percentage
> changed between the two commits.

---

## 1. What `REVIEW` means, and what I did

`scripts/pixel-diff.mjs:361-371` gives a row `STRUCTURAL` when its edge-structure score is
≥ 0.6 and `REVIEW` otherwise. `REVIEW` is therefore **an edge-detector's abstention, not a
verdict**: it says the layout skeleton could not be matched automatically. The remaining
55 rows were judged by eye, frame against capture, at full resolution — the pair was cropped
and zoomed wherever a control-level claim was needed (top bars, menus, rails, cards, rows).

Verdict vocabulary, applied strictly:

| Verdict | Meaning as used here |
|---|---|
| **ALLOWED** | Every captured control is present, in order; the delta is brand, palette/type, our own prose or an additive control (CLONE_DEFINITION §5). |
| **STATE** | The delta is caused by app state, project data or capture staleness. Capture is honest but cannot prove the surface — recapture. |
| **LAYOUT** | A captured control is missing, moved, reordered or differently sized, or a captured functional string differs. |
| **REGION** | The evidence frame is a crop/panel or the wrong surface, so the percentage is a framing artefact. |

A crop frame with a *separately visible* layout delta is scored **LAYOUT**, not REGION — the
percentage is still meaningless, and that is said in the evidence column.

### 1.1 The one finding that changes the most rows: stale captures

Seven paired captures predate the fix that addresses their own delta. The diff is therefore
measuring a build that no longer exists:

| Capture | Added | Superseded by | What the current build does |
|---|---|---|---|
| `ours-entry-overlay.png` | 11-16 13:21 (`efe2e4a1`) | `a97f2c14` 11-16 17:11 | Start overlay rebuilt: 5 tiles + `Browse Studio projects ›` + ✕ (`StudioOnboarding.tsx:104-143`) |
| `ours-shortcuts.png` | 11-14 (`d70f24b3`) | `a97f2c14` 11-16 | Shortcuts overlay rebuilt: search field, header ✕, two-column groups (`StudioLearn.tsx:294-334`, `globals.css:5486-5493`) |
| `ours-track-options.png` | 11-14 (`d70f24b3`) | `106f1209` 11-16 | `Bounce track` moved *after* the captured rows (`StudioTrackPanel.tsx:349-366`) |
| `ours-clip-info.png` | 11-15 (`274b27e8`) | `f8918ce4` 11-16 | Rail header now carries like/dislike (`StudioClipInfo.tsx:149-170`) |
| `ours-plugin-catalog.png` | 11-15 (`274b27e8`) | `68a67e07` 11-16 | 10 named plugins incl. Stereo Utility (`lib/studio-plugins.ts:234-245`) |
| `ours-plugin-dock-eq-convolution.png` | 11-14 (`0148a9a7`) | `68a67e07` 11-16 | IR slot reads `NO ASSET LOADED` (`StudioPluginDock.tsx:297`) |
| `ours-editor-1024.png` | 11-14 (`d70f24b3`) | `StudioHeader.tsx:309` + `globals.css:4982` | Bar/beat readout only hides below 900 px, not at 1024 |

**These 8 rows are `STATE` (recapture), not defects.** Four of them (S14, S19, S27, S44) were
scored `LAYOUT` by W2 for exactly the delta that has since been fixed.

Also note: three pairs share one capture (`ours-plugin-dock-eq-convolution` → S41/S42/S44;
`ours-sign-in` → S02 only; `ours-share-dialog` → S54). Where one capture feeds several rows the
percentages are not independent samples, and a stale capture stales all its rows.

---

## 2. Counts

| Verdict | Rows |
|---|---|
| **LAYOUT** | **11** |
| **STATE** | **28** |
| **REGION** | **10** |
| **ALLOWED** | **6** |
| **Total** | **55** |

Of the 28 `STATE` rows, **8 are stale captures** (§1.1), **14 are project-content/state**
(different tracks, chains, panes, data), and **6 are surface-state** (panel or menu closed, wrong
overlay variant, badge/selection state).

---

## 3. The 55 rows

Diff % is the harness number from `summary.json`; it is **not** a severity score (brand,
palette and framing are inside it). Evidence is one line, from the frame/capture pair.

| # | Screen | Verdict | Evidence | Diff % |
|---|---|---|---|---|
| 1 | S01 Marketing signed out | ALLOWED | Suno's corporate homepage vs our product marketing page — different site, outside §1's Studio scope; CTAs/nav are our IA and prose | 31.16 |
| 2 | S02 Sign-in modal | LAYOUT | Frame: modal with Google/Apple/phone + Discord/Facebook/Microsoft; ours: `/login` route, email+password only — 6 provider controls absent | 49.19 |
| 3 | S03 Signed-in entry reopened | STATE | Capture is the compact 3-tile "How do you want to start?" dialog; the 5-tile start overlay (incl. `Browse Studio projects ›`) landed in `a97f2c14` after the capture | 5.36 |
| 4 | S05 Empty project | LAYOUT | Frame shows one `Audio Track` row with M/S/R and two lane strips; our zero-track project renders none | 3.05 |
| 5 | S06 Onboarding overlay | STATE | Same stale capture as S03; HEAD's overlay has Edit Your Song / Upload Audio / Create a song / Open a project / Empty Project + browse pill | 5.46 |
| 6 | S07 Project menu | STATE | All 9 captured rows present in order; our additive `Import project…` and `Send to Suno Sync` sit after them, and the What's This card covers rows 1-3 | 8.63 |
| 7 | S08 Version history | LAYOUT | Frame: dot list, selected row carries a chevron; ours: label + always-visible `Restore` pill + note, so a row is ~2× taller | 7.61 |
| 8 | S09 Settings · Performance | ALLOWED | All tabs/cards/toggle present; extra `Count-in before recording` card is additive; display-serif→sans and dialog scale are type/palette | 12.77 |
| 9 | S10 Settings · Window management | ALLOWED | Card copy and `Panels / Windows / Show toggle` match; the segmented control sits under the copy instead of inline-right; dialog 758×357 vs 793×428 | 12.38 |
| 10 | S13 Learn menu | LAYOUT | Menu is 206 px vs the frame's ~242 px, so the `Keyboard Shortcuts` + `shift ?` row and `Learning Center` wrap to two lines | 7.51 |
| 11 | S14 Keyboard shortcuts | STATE | Stale capture (7 rows, no search); HEAD renders the 920 px dialog with search, header ✕ and grouped rows | 11.78 |
| 12 | S15 What's This? card | STATE | Hover card present in both at top-right; the arrangement behind it is a different project (ours has Drum/Bass clips, the frame is bare) | 4.48 |
| 13 | S16 Empty editor | LAYOUT | Same as S05: no starter `Audio Track` row; everything else (bars, prompt bar, faders, transport) matches within 2.37 % | 2.37 |
| 14 | S19 Track options menu | STATE | Stale capture: Bounce was 4th row; HEAD appends it after `Delete` (`StudioTrackPanel.tsx:349`), keeping all six captured rows intact | 8.51 |
| 15 | S20 Add track menu | STATE | Audio/MIDI/Upload and their A/M/U accelerators all present; menu opens below the trigger because our track list is full (5 tracks vs none) | 7.96 |
| 16 | S21 Hidden tracks | ALLOWED | Hidden rows, `Unmute all`, `Show All Hidden Tracks` (+ `shift alt H`) and the count chip all present; per-row Show/Mute are pills rather than icon toggles | 22.66 |
| 17 | S22 Ruler zoom levels | REGION | Frame is a 2900×600 ruler strip; different zoom (ours 9-14 bars) and a whole-viewport capture — % is framing | 34.61 |
| 18 | S23 Section markers | REGION | Frame is a 920×840 panel crop at ~1.6× zoom over bars 33-57; our capture has no marker in view, so the anatomy stays unevidenced | 35.02 |
| 19 | S24 Loop region | LAYOUT | Ours paints one 10×18 `Loop end` pill; frame has triangular loop-in and loop-out flags, tint behind the clips, and an active loop toggle | 28.75 |
| 20 | S25 Clip selected / trim grips | STATE | Selected-clip outline matches the frame; the project behind is 1 track vs the frame's 12 and the What's This tooltip is anchored elsewhere | 17.44 |
| 21 | S27 Clip info rail | STATE | Stale capture: like/dislike now sit in the rail header (`StudioClipInfo.tsx:149`); art is a colour block because the clip has no artwork/date | 15.69 |
| 22 | S28 Clip colour submenu | LAYOUT | Submenu now paints, but offers 5 swatches (~28 px) in one row; the frame has 20 in four hue rows (~40 px) | 49.76 |
| 23 | S29 Take lanes | STATE | Take rows 2/1 with tick, close ✕ and per-take activation present; no waveforms because the takes are loop clips with no audio URL | 12.22 |
| 24 | S30 Stretch modes / warp markers | STATE | Our selected clip renders as a black body with one flat green line, so neither waveform nor warp pennants can draw; stretch modes exist as rows in the clip-settings panel | 11.91 |
| 25 | S32 Modulation lane | REGION | Frame is a 3200×350 lane strip; ours is a whole viewport with the lane docked and a piano-key column at its left edge | 17.77 |
| 26 | S33 Velocity lane | REGION | Frame is a 3200×260 lane strip; ours is a whole viewport, lane empty (no notes), same piano-key column offset | 21.95 |
| 27 | S34 Prompt bar idle | STATE | Bar anatomy (＋, input, BETA, ✕, 88.2, options, send) matches; different project data behind it | 22.01 |
| 28 | S35 Prompt bar attachment | STATE | `Drum Kit Main` chip + ✕ in the same slot of the bar in both; ours adds the FX block below | 22.72 |
| 29 | S36 Prompt conversation dock | STATE | Dock and composer match; ours shows real messages where the frame shows the empty-state copy, and the clip rail is closed | 15.86 |
| 30 | S39 Plugin catalog | STATE | Stale capture: the nameless 10th tile cannot be produced from HEAD's data (Stereo Utility has name + description); recapture to confirm | 10.92 |
| 31 | S40 Plugin dock · one slot | STATE | Master chain + EQ card + ghost rail present; different preset/parameters and ghost labels | 16.89 |
| 32 | S41 Plugin dock · multiple | STATE | Different chains (ours EQ + Compressor, frame Compressor + EQ + EQ); our dock cards are ~165 px tall vs ~205 px | 23.07 |
| 33 | S42 EQ card | REGION | Frame is a 1000×524 card crop at ~2×; band selector, shape buttons and Freq/Q/Gain all exist in the docked card | 10.37 |
| 34 | S43 Compressor sidechain | REGION | Frame is a 1040×660 crop of the routing list; our popover lists the same Pre-fx/Post-fader rows in the same order plus `None` | 47.89 |
| 35 | S44 Convolution card | STATE | Stale capture: it shows "No impulse response"; HEAD renders the frame's `NO ASSET LOADED` (`StudioPluginDock.tsx:297`) | 9.76 |
| 36 | S46 Preset menu / stepper | REGION | Frame is an 840×450 crop; stepper + `Clear all settings` / `Save preset…` / preset list present in the same order | 41.27 |
| 37 | S48 Master chain with limiter | STATE | Master chain is empty, so the Limiter card the screen is about never renders; ghost rail offers Compressor/Reverb/Delay | 14.43 |
| 38 | S49 Export menu | STATE | `Full Song` / `Selected Time Range` / `Multitrack` match including casing; HEAD appends WAV/MP3 + Normalise + JSON after them | 18.71 |
| 39 | S51 Export result toast | REGION | Frame is a 1500×180 toast strip; text, ✕ and progress strip match, scope word differs (Full Song vs Multitrack) | 21.44 |
| 40 | S53 Library songs | STATE | Tag strip and row height match; key/BPM tags are empty for these clips (measured client-side) and artwork falls back to a letter tile | 17.45 |
| 41 | S54 Share permission copy | ALLOWED | Title, body block, `Done` + `Copy Link` in the same order; guarantee reworded (our prose) and an origin URL + expiry note added | 23.94 |
| 42 | S56 Shared link logged out | REGION | The reference frame is the marketing hero — it contains no share surface; a corpus defect, not a layout claim. **Now `NO-FRAME` on `83ec6786`** (frame re-filed as S01) | 39.12 |
| 43 | S58 Empty library | REGION | Frame is a 720×280 panel crop; `No songs found.` + `Reset all filters` match in position and order | 7.43 |
| 44 | S60 Moderation refusal | LAYOUT | Same string, but ours renders it inline in the form footer; the frame floats it as a toast above `Create` | 17.10 |
| 45 | S61 Insufficient credits | LAYOUT | Frame is the `You out of credits` modal (body, $6 stepper, `Turn on auto-reload`, `Not now`); ours shows one inline line and no modal | 12.67 |
| 46 | S63 1280 px | STATE | Both fit at 1280 with the 260 px gutter; different demo project and the MIDI editor docked in both | 21.69 |
| 47 | S64 1024 px | STATE | Stale capture: the bar/beat readout only hides below 900 px (`globals.css:4982`), so HEAD keeps it at 1024 | 23.17 |
| 48 | S65 768 px / desktop gate | ALLOWED | Card structure, prose slot, `Back to Create` and the 767 px gate match; logo illustration, wordmark and body copy are ours | 8.87 |
| 49 | EXTRA-generation-refused | STATE | Only frame is the legacy render-failure dialog; ours shows the policy-refusal dock — copy and placement are not comparable | 23.81 |
| 50 | EXTRA-generation-refused-legacy | STATE | Same capture and frame as #49 (shared evidence), same adjudication | 23.81 |
| 51 | EXTRA-library-uploads | LAYOUT | Rows are icon + name + duration; the frame also carries artwork and a size/type line (`32.1 MB`), and groups use absolute dates | 9.27 |
| 52 | EXTRA-library-song-detail | STATE | Remix, like/dislike/more, player, Info/Stems, Styles, Lyrics, Comments all present; art and waveform absent because the clip has neither | 12.04 |
| 53 | EXTRA-project-load-error | LAYOUT | Ours is a bare `se-error` alert with a ✕; the frame offers `Try again` and `Details`, so there is no retry path from the failure | 3.31 |
| 54 | EXTRA-restoring-last-project | STATE | Capture is the settled empty editor ("Your session is empty"); the frame keeps the previous arrangement visible while restoring. `83ec6786` suppresses that placeholder while loading, so a recapture can hold the real state | 18.36 |
| 55 | EXTRA-take-lanes-empty | STATE | Empty-band copy matches verbatim and is correctly centred; the frame additionally has the clip rail open | 13.73 |

*S30 note:* our selected clip renders as a black body with one flat green line, so the waveform and
the warp pennants cannot draw; the stretch modes themselves exist as rows in the clip-settings
panel. That is a capture/content state, not a layout claim — but **a clip that paints black is
worth its own check**, because if a real clip renders that way it is a render bug.

---

## 4. Ranked LAYOUT rows — 11 screens, 10 fixes

Ordered by how much of the captured surface is lost. Percentages are the harness's and are
included only for reference.

| # | Screen (diff %) | What is wrong | File:line | Fix |
|---|---|---|---|---|
| 1 | **S61** Insufficient credits (12.67) | The captured `You out of credits` modal does not exist. Ours is one inline line above a disabled Create button — no title, body, $6 amount stepper, `Turn on auto-reload` or `Not now`. No auto-reload component exists in the tree (`grep auto-reload` → only `lib/studio-errors.ts:17`). | `components/CreateStudio.tsx:4373` | Build the captured modal (amount stepper, `Turn on auto-reload`, `Not now`) and open it on the 402/credit path, or record it as an absence in `CLONE_DEFINITION.md` §5. The capture script already names it (`scripts/capture-screens.mjs:1163`). |
| 2 | **S02** Sign-in (49.19) | Six captured sign-in providers are absent (Google, Apple, phone, Discord, Facebook, Microsoft) and the surface is a route, not a modal. The login page is 36 lines of email + password. | `app/(auth)/login/page.tsx` | Decide the W0 item: modal vs route, and add the provider cluster (or record both as absences). Nothing was captured for a provider flow, so a route is defensible only if recorded. |
| 3 | **S05 / S16** Empty project (3.05 / 2.37) | A new empty project has zero tracks. The frame's empty project shows one `Audio Track` row (M/S/R, arm, two lane strips). S16 is otherwise the closest pair in the set, which pins the delta to this row. | `components/studio/StudioTimeline.tsx:515` (empty branch) · `components/studio/StudioTrackPanel.tsx:547` (`Add new track`) | Seed one `Audio Track` when a project has no tracks (or render it as a placeholder row above `Add new track`). Two screens ride on it. |
| 4 | **S28** Clip colour submenu (49.76) | The submenu paints again (fixed in `90db80ab`), but `CLIP_COLORS` is 5 colours rendered as one row of ~28 px swatches; the frame shows 20 swatches in four hue rows at ~40 px. 15 captured choices are missing. | `components/studio/StudioEditorShell.tsx:191` (`CLIP_COLORS`) · `:6607` (render) | Expand to 20 colours grouped by hue (4×5) at the captured swatch size, or record a 5-colour palette as a brand decision. |
| 5 | **S24** Loop region (28.75) | One loop boundary is draggable: a 10×18 rounded `Loop end` pill. The frame has triangular loop-in *and* loop-out flags, the tint painted **behind** the clips, and the transport loop button in its active box. | `components/studio/StudioTimeline.tsx:462-479` · `app/globals.css:5418-5419` | Render both flags (start + end), drop `se-loop-band`'s `z-index:1` above the clips, and mark the transport loop toggle `.on` while the loop is armed. |
| 6 | **S13** Learn menu (7.51) | The menu is `min-width:206px`; `Keyboard Shortcuts` + its `shift ?` accelerator and `Learning Center` need ~242 px, so two captured rows wrap to two lines and the menu grows ~80 px. | `app/globals.css:5364` | `min-width: 242px` (or `white-space: nowrap` on the row label with the accelerator right-aligned). |
| 7 | **S08** Version history (7.61) | Rows are `label + Restore` pills (~2× the frame's row height) and the list carries a permanent explanatory note. The frame is a dot list where the selected row shows a chevron and clicking the row restores. | `components/studio/StudioProjectMenu.tsx:597-608` (row) · `:617` (note) | Restore the dot marker and row-click affordance with a chevron on the selected row; keep `Restore` for keyboard/AT only, and drop the note below the list. |
| 8 | **EXTRA-project-load-error** (3.31) | The load-error surface is a bare alert string. The frame offers `Try again` and `Details`; ours has neither, so a failed project GET leaves the user with a dismissable toast. | `components/studio/StudioEditorShell.tsx:7424` | Add `Try again` (re-run the project GET) and `Details` (expand the error) to `.se-error`. `scripts/capture-screens.mjs:1257` already records this delta. |
| 9 | **S60** Moderation refusal (17.10) | The refusal copy matches the frame, but it renders inline in the form footer (`.s-error`) instead of as the floating toast above `Create`, so it pushes the Create row and cannot be dismissed. | `components/CreateStudio.tsx:4367` | Route refusals through the toast/banner layer at the captured anchor above the Create button (keep the inline copy for form validation only). |
| 10 | **EXTRA-library-uploads** (9.27) | Upload rows are file icon + filename + duration. The frame's rows carry artwork and a second metadata line (`32.1 MB`), and use absolute day groups (`May 18, 2026`) where ours shows `Today`/`Yesterday`. | `components/studio/StudioLibrary.tsx:869-879` (row) · `:849` (day label) | Add the size/type meta line when the upload payload exposes it, and label groups from the date (relative labels only for the current day). Lowest priority: the payload may not carry size. |

**Not defects, but recorded (not ranked):**

- **S30** — see the note above: black clip body, no waveform/pennants. Verify a real clip paints.
- **S41/S48** — the dock's loaded cards are ~165 px tall against the frame's ~205 px, which is why
  three captured cards cannot fit. Weak evidence (panel is resizable), so left in `STATE`.

---

## 5. Remaining ALLOWED divergences, grouped

All six rows have every captured control present and in the captured order.

**Brand / wordmark / illustration (2 rows)**
- **S01** — Suno's corporate homepage against our product marketing page: different nav IA, hero,
  cards and footer player. Outside §1's Studio scope; ours is a Camxora marketing surface.
  *If W0 wants the signed-out page held to the capture, this becomes LAYOUT (different page
  composition). It is not a Studio surface.*
- **S65** — `CAMXORA Studio` wordmark, bar-chart logo instead of the laptop photo, and our body
  copy; card structure, prose slot, `Back to Create` and the 767 px gate all match.

**Palette / typography / chrome (4 rows)**
- **S09** — display serif → sans, dialog 758×357 vs 793×428, toggle styling.
- **S10** — same dialog scale; the segmented control sits under the card copy instead of
  inline-right (same three options, same labels, same order).
- **S21** — per-row `Show` / `Mute` are labelled pills where the frame uses icons; the popover is
  anchored to the track list (ours has 5 tracks, the frame 7).
- **S54** — dialog scale and type; the frame is a 1200×600 crop, so the size relationship is not
  measurable anyway.

**Our own prose (3 rows)**
- **S01** — the whole page's marketing copy.
- **S54** — the permission guarantee is reworded (`create` → `make`, different second sentence).
  §3 makes help/permission prose ours; `Done` and `Copy Link` are in the captured order.
- **S65** — the desktop-gate body copy.

**Additive controls (2 rows)**
- **S09** — `Count-in before recording` card (second setting).
- **S54** — raw origin URL row and the expiry note.

---

## 6. REGION rows and what a recapture must fix (10)

| Screen | Frame shape | Why the % is meaningless | Recorded sub-delta |
|---|---|---|---|
| S22 | 2900×600 ruler strip | Strip vs whole viewport | Zoom 9-14 bars vs 1-29 (state); minor ticks absent |
| S23 | 920×840 panel crop (~1.6×) | Crop vs whole viewport | No section marker in our view — anatomy unevidenced |
| S32 | 3200×350 lane strip | Strip vs whole viewport | Lane reserves a ~40 px piano-key column; tabs stacked under a clip-name header |
| S33 | 3200×260 lane strip | Strip vs whole viewport | Same column offset; lane empty (no notes) |
| S42 | 1000×524 EQ-card crop (~2×) | Crop vs whole dock | Cards are ~165 px tall vs ~205 px in the frame |
| S43 | 1040×660 routing-list crop | Crop vs whole viewport | None — Pre-fx/Post-fader rows and order match |
| S46 | 840×450 preset-menu crop | Crop vs whole viewport | None — stepper and menu rows match |
| S51 | 1500×180 toast strip | Crop vs whole viewport | Scope word (Full Song vs Multitrack) — state |
| S56 | 1920×1211 marketing hero | Frame has no share surface at all | Corpus defect — **already resolved upstream**: `83ec6786` re-files the frame and makes S56 `NO-FRAME` |
| S58 | 720×280 panel crop | Crop vs whole viewport | None — copy and button match |

---

## 7. What W3 should recapture (STATE, 28)

**Stale (8)** — S03, S06, S14, S19, S27, S39, S44, S64: recapture on `90db80ab`; nothing to fix.

**Content/state (14)** — S15, S20, S25, S29, S30, S34, S35, S36, S40, S41, S48, S49, S53, S63:
recapture with the reference's content (a Limiter on the master chain for S48, a two-card chain for
S41/S40, a clip whose waveform actually paints for S25/S30) so the surfaces can be diffed at all.

**Surface state (6)** — S07 (dismiss the What's This card before shooting),
EXTRA-generation-refused ×2 (a policy refusal, not the legacy render failure),
EXTRA-restoring (hold `.se-loading` with the previous arrangement visible),
EXTRA-take-lanes-empty (close the clip rail), EXTRA-library-song-detail (a clip with artwork).

---

## 8. Sign-off

- 55/55 `REVIEW` rows adjudicated: **LAYOUT 11 · STATE 28 · REGION 10 · ALLOWED 6**.
- 10 ranked LAYOUT entries covering 11 screens, all with `file:line`: 2 are whole surfaces
  missing (S61's out-of-credits modal, S02's six providers), 1 is a two-screen data seed
  (S05/S16), 1 is a 20→5 control set (S28), 1 is loop-region anatomy (S24), 1 is a menu width
  (S13), 1 is a row anatomy (S08), and 3 are error/row surfaces (load error, refusal toast,
  upload rows).
- The single biggest quality change available for D3 is **recapture, not code**: 8 rows are
  measuring superseded builds (§1.1), and 4 of those were scored `LAYOUT` by W2 for deltas that
  have since been fixed.
- No server ran, no capture was taken, no product or reference file changed. Only this report
  was added.
- Measured on `90db80ab`; re-based onto `83ec6786` without a verdict change. That commit already
  fixes the `EXTRA-restoring` symptom (no empty-session placeholder while loading) and moves S56
  to `NO-FRAME` — both matching this report's calls, so the current main has **54 `REVIEW`**
  rows, all adjudicated here.
