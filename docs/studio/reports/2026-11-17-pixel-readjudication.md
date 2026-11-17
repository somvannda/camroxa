# Pixel re-adjudication — the 53 `REVIEW` rows on the fixed build (W9b)

**Date:** 2026-11-17
**Workstream:** W9b, spawned from `docs/studio/RESIDUAL_VERIFICATION_PLAN.md` (D3)
**Branch:** `qa/pixel-readjudication`, base `origin/main` `9f7c2baa`
**Worktree:** `C:\Users\Kong Somvannda\AppData\Local\Temp\camxora-res-readj`
**Inputs:** `docs/studio/reports/pixel-diff/summary.json` (generated `2026-11-17T05:43:26Z`, 53
`REVIEW`), `2026-11-17-pixel-adjudication.md` (W9), `docs/studio/reference/screens/*`,
`docs/studio/compare/*`, `docs/studio/reports/pixel-diff/*.png`, `CLONE_DEFINITION.md`,
`2026-11-17-recapture.md`, `2026-11-17-s02-signin.md`, product source at `9f7c2baa`.
**Scope:** adjudication only. No server, no port, no capture, no push, no deploy, no provider
call; `G:\Developments\Projects\Camxora` untouched.

> **Why this run exists.** W9 adjudicated the set on `90db80ab`/`83ec6786`. Since then
> `b3d718f4` (20 clip colours, default Audio Track, Learn width), `e2cf8d0c` (loop flags),
> `ee7582bc` (version history), `8e19647a` (shortcuts width, anchored catalogue menu, 1024
> readout), `15a39191` (load-error retry/Details, upload meta), `8721f748` (demo tile),
> `617713a2`/`1b2f87bb` (S02 providers + capture), `d1b1a9a8` (S61 modal), `5b4c1c14` (MIDI
> overview) and the W10 recapture all landed. W9's LAYOUT list is measured against a build
> that no longer exists.

---

## 1. Method and the counting rule

Every `REVIEW` row was re-judged by eye at full resolution against its own reference frame and
its **current** capture; diff PNGs and region crops were used wherever a control-level claim
was needed. `summary.json` was not regenerated (that is W2's tool); its percentages are quoted
as-is and are **not** treated as severity. Seven captures now post-date W9 (§2), and several
were taken *before* today's fix and therefore cannot prove the fix — those are scored `STATE`
with the superseding commit named.

Verdicts, applied with W9's vocabulary:

| Verdict | Meaning here |
|---|---|
| **ALLOWED** | Every captured control is present, in captured order; the residual is brand, palette/type, our prose, a recorded absence, or an additive control **appended after** the captured run. |
| **STATE** | The delta is app state, project data, capture staleness, or the capture predates the fix. The capture cannot prove the surface; recapture named in §5. |
| **LAYOUT** | A captured control is missing, reordered, materially displaced or resized, or a captured list row is displaced by an additive row (rule 4). |
| **REGION** | The frame is a crop/panel/lane strip, or shows a different *surface composition* (modal vs route), so the percentage is a framing artefact while the captured controls exist. |

**The rule-4 test used for this report** (this is the distinction W9 missed):

- An additive control **appended after** the last captured row is `ALLOWED` (S19's
  `Bounce track`, S49's `Project (JSON)`).
- An additive control **inserted inside** the captured run, or a captured control **replaced
  by an additive primary**, is `LAYOUT` even when the captured rows keep their relative order,
  because the captured control has moved (CLONE_DEFINITION rule 4).
- A **surface composition** difference (card vs fanned tiles, route vs modal, panel vs floating
  card) is `REGION`, not LAYOUT, when the captured control set/order is intact — except where
  the composition **removes** a captured control (S36), which is LAYOUT.

A crop frame with a separately visible control defect is still scored for that defect.

---

## 2. What moved since W9, and what it did to the rows

| Commit | Change | Rows it decides |
|---|---|---|
| `b3d718f4` | default `Audio Track`, 20 clip colours, Learn menu 242 px | S05/S16 (row landed), S28 (colours), S13 (fixed) |
| `e2cf8d0c` | triangular loop flags at both ends, left one drags | S24 — **fix in code, capture still 11-14** |
| `ee7582bc` | version history as dot/rail list, chevron on newest, row-click restore | S08 — **fix in code, capture still 11-14** |
| `8e19647a` | shortcuts `max-width`, anchored catalogue menu, 1024 readout | S14, S39 — capture predates the fix |
| `15a39191` | load-error `Try again`/`Details`, upload type+size meta, menu scroll | EXTRA-project-load-error, EXTRA-library-uploads |
| `8721f748` | Drum & Bass Demo tile seeds a project | S03/S06 — capture predates the tile |
| `617713a2`, `1b2f87bb` | six sign-in providers + S02 capture; S61 modal + capture | S02, S61 |
| `5b4c1c14` | MIDI editor overview strip | S63 — capture predates the strip |
| `83ec6786` | no empty-session placeholder while loading | EXTRA-restoring-last-project |
| `106f1209` | additive project-menu rows moved **after** the nine captured rows | S07 — capture predates the move |

**Measured shrink on the named rows** (summary % → this run's reading):

| Row | W9 % | Now | Verdict | Shrink proven by capture? |
|---|---|---|---|---|
| S13 Learn menu | 7.51 | **4.66** | ALLOWED | yes — one line per row, no wrap |
| S44 Convolution | 9.76 | **5.65** | REGION | yes — `NO ASSET LOADED` present |
| S16 Empty editor | 2.37 | **2.36** | LAYOUT (add row) | track row now present; add row now visible as displaced |
| S05 Empty project | 3.05 | **3.04** | LAYOUT (add row) | track row now present; add row displaced |
| S39 Plugin catalog | 10.92 | **10.60** | STATE | no — capture predates `8e19647a` |
| S14 Shortcuts | 11.78 | **10.95** | LAYOUT (content) | no — capture predates `8e19647a` |
| S61 Credits modal | 12.67 | **11.25** | LAYOUT (rule 4) | modal now present; control demoted |
| S02 Sign-in | 49.19 | **43.96** | REGION | six providers now present in captured order |
| S28 Colour submenu | 49.76 | **49.25** | LAYOUT (rule 4) | 20 swatches in four rows now present |
| S24 Loop region | 28.75 | 28.75 | STATE | no — capture predates `e2cf8d0c` |
| S08 Version history | 7.61 | 7.61 | STATE | no — capture predates `ee7582bc` |

The percentages for `STATE` rows are measuring a superseded build (or a different project);
they are **not** evidence either way. That is the single largest remaining measurement gap.

---

## 3. The 53 rows

| # | Screen | Verdict | Evidence (frame ↔ capture) | Diff % |
|---|---|---|---|---|
| 1 | S01 Marketing signed out | **ALLOWED** | Suno corporate homepage vs our product marketing page — different site, outside Studio scope; nav/hero/body/footer are our IA and prose. | 31.16 |
| 2 | S02 Sign-in modal | **REGION** | Six captured providers now exist in the captured order (Google, Apple, Phone, or, Discord/Facebook/Microsoft — `AuthProviders.tsx`). Residual is the surface: captured modal over the marketing page vs our `/login` route, recorded in `reports/2026-11-17-s02-signin.md:33-37`. Google renders disabled + "not configured in this build" because the capture box has no OAuth credentials — state, not a missing control. | 43.96 |
| 3 | S03 Signed-in entry reopened | **STATE** | Capture predates `8721f748`: it shows Edit/Upload/Create/**Open a project**/Empty, no Demo tile. HEAD renders the five captured-order tiles incl. `Drum & Bass Demo` (`StudioOnboarding.tsx:129-164`). Composition is a centred card vs the frame's fanned tiles — a `REGION`-class residual after recapture, not a missing control. | 5.92 |
| 4 | S05 Empty project | **LAYOUT** | The captured `Audio Track` row now exists with M/S/A and lane strips. But `+ Add new track` is pinned directly under the last row (y≈180 of 1277); the frame centres it in the free list space (y≈670 of 1245). Same row, two screens. | 3.04 |
| 5 | S06 Onboarding overlay | **STATE** | Same stale capture as S03 (no Demo tile; "Open a project" instead). HEAD has the five captured-order tiles + Browse pill + ✕. | 6.03 |
| 6 | S07 Project menu | **STATE** | Capture 11-14 predates `106f1209`: in it `Import project…`/`Send to Suno Sync` sit *inside* the nine captured rows; HEAD moves both **after** `Show Quick Start again` (`StudioProjectMenu.tsx:482-546`). Left-column hover card covers rows 1-3 — capture state. | 8.63 |
| 7 | S08 Version history | **STATE** | Capture 11-14 shows label + always-on `Restore` + note. HEAD is the captured dot/rail: dot, `hh:mm PM` on the newest row (seconds on older), chevron on the newest, row-click restore, note removed (`StudioProjectMenu.tsx`, `ee7582bc`). Recapture only. | 7.61 |
| 8 | S09 Settings · Performance | **ALLOWED** | Tabs/cards/toggle match; `Count-in before recording` card is additive; serif→sans and dialog scale are type/palette. | 12.77 |
| 9 | S10 Settings · Window management | **ALLOWED** | Copy and `Panels / Windows / Show toggle` match; segmented control sits under the copy rather than inline-right — same three options, same order; dialog scale differs. | 12.38 |
| 10 | S13 Learn menu | **ALLOWED** | Fixed. Menu is now 242 px: `Keyboard Shortcuts` + `shift ?` and `Learning Center` each one line, `What's This?` with `On`. `YouTube Tutorials` is the one sanctioned absence (§5). | 4.66 |
| 11 | S14 Keyboard shortcuts | **LAYOUT** | Width cap fixed at `globals.css:5544` **after** this capture, so the capture still shows the 480 px dialog. But the content also differs from the frame in HEAD: the captured groups `GENERAL`, `EFFECTS CHAIN`, `CLIP EDITOR · AUDIO`, `CLIP EDITOR · MIDI` and their rows (e.g. `Select All Plugins`, `Clear Plugin Selection`, `Quantize Warp Markers`, `Move Notes Left/Right`) do not exist; our five groups are Playback/Tracks/Editing/View/Project with a different keymap (`lib/studio-help.ts:227-233`, rows `:164-221`). | 10.95 |
| 12 | S15 What's This? card | **STATE** | Card is at the same anchor (under BPM, top-right) and the copy is ours; the arrangement behind it is a different project (ours has a Loop clip, the frame is bare). | 4.48 |
| 13 | S16 Empty editor | **LAYOUT** | The default `Audio Track` row landed and the delta shrank. Remaining: `+ Add new track` under the row (y≈180) vs centred in the list (frame y≈670); an extra in-flow group `–` row also sits above it (`StudioTrackPanel.tsx:465-481`). Same cause as S05. | 2.36 |
| 14 | S19 Track options menu | **ALLOWED** | All six captured rows present in order (Rename track, Color ›, Collapse controls, Duplicate, Hide & Mute Track, Delete); `Bounce track` is appended **after** Delete (`StudioTrackPanel.tsx:349-366`). | 6.41 |
| 15 | S20 Add track menu | **STATE** | Audio/MIDI/Upload and A/M/U all present in order. Menu opens below the trigger because our 4-track project puts `Add new track` at the top; the frame has no tracks and the menu above. Follows the S05/S16 add-row position; re-check after that fix. | 7.96 |
| 16 | S21 Hidden tracks | **LAYOUT** | Captured popover content matches (row, Show/Unmute, Unmute all, Show All Hidden Tracks + `shift alt H`, count chip). But the chip is an in-flow row **below** `Add new track` (`globals.css:5468`, markup `StudioTrackPanel.tsx:604`), so it sits ~36 px lower than the frame and the popover — anchored `bottom:32px` above it (`:5470`) — opens over and hides `+ Add new track`, which the frame keeps visible on the chip's row. | 22.66 |
| 17 | S22 Ruler zoom levels | **REGION** | Frame is a 2900×600 ruler strip; ours is a whole viewport at a different zoom (9-14 bars vs 1-29) — framing. | 34.61 |
| 18 | S23 Section markers | **REGION** | Frame is a 920×840 panel crop at ~1.6× over bars 33-57; ours has no marker in view at this zoom, so the anatomy is unevidenced (unchanged). | 35.02 |
| 19 | S24 Loop region | **STATE** | Capture 11-14 has the single 10×18 `Loop end` pill. HEAD renders both triangular flags with aria labels (`StudioTimeline.tsx:477-491`, `e2cf8d0c`), tint stays behind clips and the transport loop button is boxed. Recapture only. | 28.75 |
| 20 | S25 Clip selected / trim grips | **STATE** | Selected-clip outline/grips present; the project is 1 clip vs the frame's 9 tracks, and the capture predates the `/seed/demo-loop.wav` fixture fix, so no waveform paints. | 17.44 |
| 21 | S27 Clip info rail | **ALLOWED** | Back, title, like/dislike, art, Remix, player, Info/Stems, Styles, Lyrics, Comments all present. The rail is a full-height panel, not the captured floating card — explicitly recorded as ours in `CLONE_DEFINITION.md:69`. Art is a letter tile and the player bar is empty (clip has no artwork/audio) — state. `Details` block is additive. | 14.69 |
| 22 | S28 Clip colour submenu | **LAYOUT** | Swatches fixed: `Auto` + 20 colours in four hue rows (`StudioEditorShell.tsx:6699-6713`); palette values are ours. The context menu behind it still **interleaves** additive rows: `Copy settings`/`Paste settings` between `Delete` and `Heal Edits` (`:6558-6578`), `Split on Transients`/`Make Beat 1`/`Create Section` between `Split` and `Rename` (`:6607-6637`). Captured rows are displaced (rule 4). | 49.25 |
| 23 | S29 Take lanes | **STATE** | Take rows 2/1, active-tick and close ✕ present; no waveforms because the capture predates the fixture fix, and the frame additionally has the clip rail open. Take-header controls in the frame are hidden by its What's This card, so no missing-control claim. | 12.22 |
| 24 | S30 Stretch modes / warp markers | **STATE** | Clip Settings panel present (Volume, Loop, Reverse, Pitch, Stretch/On Beat/Transients/Start and End, Formant, Speed, Quantize). The clip paints black with one flat green line — the `/demo-loop.wav` 404 fixture bug fixed in `c35c9088`; capture 11-15 predates it, so no waveform/pennants can draw. | 11.91 |
| 25 | S32 Modulation lane | **REGION** | Frame is a 3200×350 lane strip vs a whole viewport; lane docked with a piano-key column at its left, tabs under a clip-name header. | 17.77 |
| 26 | S33 Velocity lane | **REGION** | Frame is a 3200×260 lane strip vs whole viewport; lane empty (no notes), same column offset. | 21.95 |
| 27 | S34 Prompt bar idle | **STATE** | Bar anatomy (＋, input, BETA, ✕, 88.2, options, send) matches; different project data behind it. | 22.01 |
| 28 | S35 Prompt bar attachment | **STATE** | `Drum Kit Main` chip + ✕ in the same slot in both; ours adds the FX block below and hides the dock contents ("No effects on this track yet"). Same bar. | 22.72 |
| 29 | S36 Prompt conversation dock | **LAYOUT** | Empty-state copy and composer match; the frame keeps the **track panel** between the chat column and the timeline, ours removes it entirely when the assistant is open (`globals.css:4807` `.se-shell.has-assistant .se-tracks{display:none}`). A captured panel is missing, not merely a different state. | 15.86 |
| 30 | S39 Plugin catalog | **STATE** | Ten named tiles incl. Stereo Utility/Rhythm Gate; capture predates `8e19647a`, so the catalogue options menu still paints over the dialog title at top-left (the `Create new plugin` strip). Fixed by the anchored `.sp-catalog-menu`; recapture only. | 10.60 |
| 31 | S40 Plugin dock · one slot | **STATE** | Master chain + EQ card + ghost rail present; different preset/parameters and ghost labels. | 16.89 |
| 32 | S41 Plugin dock · multiple | **STATE** | Different chains (ours EQ + Compressor; frame Compressor + EQ + EQ); dock cards ~165 px vs ~205 px (panel is resizable) — content state. | 23.07 |
| 33 | S42 EQ card | **REGION** | Frame is a 1000×524 card crop at ~2×; band selector, shape buttons and Freq/Q/Gain exist in the docked card. | 10.37 |
| 34 | S43 Compressor sidechain | **REGION** | Frame is a 1040×660 routing-list crop; the popover lists Pre-fx/Post-fader in the same order plus additive `None`. | 47.89 |
| 35 | S44 Convolution card | **REGION** | Fixed: `NO ASSET LOADED` + IR grid + Mix/Gain/Pre/Width all present; capture 11-15 refreshed. Frame is a 940×400 card crop (2.35:1) vs full viewport, so card size/percentage is framing. | 5.65 |
| 36 | S46 Preset menu / stepper | **REGION** | Frame is an 840×450 crop; stepper + `Clear all settings` / `Save preset…` / preset list present in order. | 41.27 |
| 37 | S48 Master chain with limiter | **STATE** | Our master chain is empty, so the Limiter card the screen is about never renders; ghost rail offers Compressor/Reverb/Delay. Recapture with a limiter loaded. | 14.43 |
| 38 | S49 Export menu | **STATE** | `Full Song` / `Selected Time Range` / `Multitrack` match including casing; `Project (JSON)` is appended after them. The What's This card covers `Full Song`, so the pair is not clean; dismiss it and recapture (otherwise ALLOWED). | 18.71 |
| 39 | S51 Export result toast | **REGION** | Frame is a 1500×180 toast strip; text, ✕ and progress strip match, scope word differs (Full Song vs Multitrack) — state inside a crop. | 21.44 |
| 40 | S53 Library songs | **STATE** | Tag strip and row anatomy match; key/BPM tags are empty for these clips and artwork is a letter tile — the payload does not carry them. Only 3 rows vs the frame's 12. | 17.45 |
| 41 | S54 Share permission copy | **ALLOWED** | Title, body block, `Done` + `Copy Link` in captured order; guarantee reworded (our prose) and additive origin URL + expiry note. Frame is a 1200×600 crop, so scale is not measurable. | 23.94 |
| 42 | S58 Empty library | **REGION** | Frame is a 720×280 panel crop; `No songs found.` + `Reset all filters` match in position and order. | 7.43 |
| 43 | S60 Moderation refusal | **LAYOUT** | Copy matches, but it renders as an inline `.s-error` block in the form footer (`CreateStudio.tsx:4388-4393`), not the captured dismissible floating toast above `Create`. It pushes the Create row and has no ✕. Unchanged by today's work. | 17.10 |
| 44 | S61 Insufficient credits | **LAYOUT** | The captured modal now exists (title, ✕, meter, body, stepper, `Turn on auto-reload`, `Not now`) and the delta fell. But `Turn on auto-reload` is a permanently disabled switch (`CreateCreditsModal.tsx:309-331`) instead of the captured white primary button, and additive `Buy credits` (`:344-351`) is inserted **before** the captured `Not now`, displacing it (rule 4). Amount $5 vs $6 is pricing-table data (allowed). | 11.25 |
| 45 | S63 1280 px | **STATE** | Capture 09:17 predates the MIDI overview strip (`5b4c1c14`), so the captured mini-roll is absent; different project (2 tracks vs 5). Also note our additive MIDI-bar cluster (Instrument/Chord/Arp, ±12, Clear, Import MIDI, Keys) shifts the captured `Key/Scale/View` right — toolbar flow, flagged for a strict rule-4 reading, not counted. | 21.69 |
| 46 | S65 768 px / desktop gate | **ALLOWED** | Card structure, prose slot, `Back to Create` and the 767 px gate match; logo illustration, wordmark and body copy are ours. | 8.87 |
| 47 | EXTRA-generation-refused | **STATE** | Frame is the legacy render-failure dialog; ours is the policy-refusal dock. Copy and placement are not comparable — wrong surface, not a missing control. | 23.81 |
| 48 | EXTRA-generation-refused-legacy | **STATE** | Shared capture/frame with #47; same adjudication. | 23.81 |
| 49 | EXTRA-library-uploads | **STATE** | Capture 09:17 predates `15a39191`: rows now carry type + size (`StudioLibrary.tsx:881-891`); day headers already match the captured `Today`/`Yesterday`/absolute-date pattern (`lib/studio-library-grouping.ts:17-28`). Recapture only. | 9.27 |
| 50 | EXTRA-library-song-detail | **STATE** | Remix, like/dislike/more, player, Info/Stems, Styles, Lyrics, Comments all present; art and waveform absent because the clip has neither. | 12.04 |
| 51 | EXTRA-project-load-error | **STATE** | Capture 09:17 predates `15a39191`: HEAD adds `Could not open this project`, `Details` and `Try again` (`StudioEditorShell.tsx:7517-7528`). Recapture only. | 3.31 |
| 52 | EXTRA-restoring-last-project | **STATE** | Capture 09:17 shows the settled empty editor ("Your session is empty"); `83ec6786` suppresses that placeholder while loading. Recapture can hold the previous arrangement. | 18.36 |
| 53 | EXTRA-take-lanes-empty | **STATE** | Empty-band copy matches verbatim and is centred; the frame additionally has the clip rail open. | 13.73 |

---

## 4. Counts

| Verdict | Rows |
|---|---|
| **LAYOUT** | **8** |
| **STATE** | **26** |
| **REGION** | **11** |
| **ALLOWED** | **8** |
| **Total** | **53** |

Of the 26 `STATE` rows: **8 are stale captures superseded by a named commit**
(S03, S06, S07, S08, S24, S39, EXTRA-library-uploads, EXTRA-project-load-error), **2 more are
stale capture-plus-data** (S30, EXTRA-restoring), **12 are project/content state**
(S15, S25, S29, S34, S35, S40, S41, S48, S49, S53, S63, EXTRA-library-song-detail), **2 are
wrong-surface pairs** (EXTRA-generation-refused ×2), **1 is surface state**
(EXTRA-take-lanes-empty), and **S20** is a menu anchored to the misplaced add-row.

---

## 5. Remaining LAYOUT list (8 rows, 7 causes)

Ordered by how much of the captured surface is lost.

| # | Screen (diff %) | What is wrong | File:line |
|---|---|---|---|
| 1 | **S36** Conversation dock (15.86) | Opening the assistant removes the captured track panel entirely; the frame keeps chat → tracks → timeline. | `camxora.com/app/globals.css:4807` — `.se-shell.has-assistant .se-tracks{display:none}` |
| 2 | **S61** Out-of-credits modal (11.25) | Captured primary `Turn on auto-reload` is demoted to a permanently disabled switch; additive `Buy credits` primary is inserted before the captured `Not now`, displacing it. Modal itself now matches. | `camxora.com/components/CreateCreditsModal.tsx:309-331` (switch), `:344-351` (additive primary) |
| 3 | **S14** Shortcuts (10.95) | Captured sections/rows (`GENERAL`, `EFFECTS CHAIN`, `CLIP EDITOR · AUDIO`, `CLIP EDITOR · MIDI`, `Select All Plugins`, `Clear Plugin Selection`, `Quantize Warp Markers`, …) are replaced by Playback/Tracks/Editing/View/Project with a different keymap. Width cap is fixed (`globals.css:5544`). | `camxora.com/lib/studio-help.ts:227-233` (groups), `:164-221` (rows) |
| 4 | **S28** Clip colour submenu (49.25) | Swatches fixed to 20/4 rows. Context menu still interleaves additive rows inside the captured run: Copy/Paste settings after Delete; Split on Transients/Make Beat/Create Section after Split. Captured rows are displaced (rule 4). The same menu is S26's surface. | `camxora.com/components/studio/StudioEditorShell.tsx:6558-6578`, `:6607-6637` |
| 5 | **S05 / S16** Empty project (3.04 / 2.36) | `+ Add new track` is pinned under the last row instead of centred in the free list space (≈465 px higher in the frame); the extra in-flow group `–` row adds a third line to the track row. Default `Audio Track` itself is fixed. | `camxora.com/app/globals.css:5406` (`.se-add-wrap`), `:4678` (`.se-track-list`); markup `StudioTrackPanel.tsx:525` |
| 6 | **S21** Hidden tracks (22.66) | The hidden-count chip is an in-flow row below `Add new track` instead of on the captured add-row; its popover then opens over and hides `+ Add new track`. Popover content/order matches. | `camxora.com/app/globals.css:5468` (`.se-hidden-wrap`), `:5470` (`.se-hidden-pop`); markup `StudioTrackPanel.tsx:604` |
| 7 | **S60** Moderation refusal (17.10) | Refusal renders inline in the form footer, not the captured dismissible floating toast above `Create`; no ✕, and it pushes the Create row. | `camxora.com/components/CreateStudio.tsx:4388-4393` |

**Verdict class if fixed as recorded, not counted here:** S02 and S03/S06 are `REGION`
(surface composition: route vs modal; card vs fanned tiles). They must be recorded in
`CLONE_DEFINITION.md §5`, otherwise a strict D3 reviewer can reclassify them as LAYOUT.

**Secondary observations, not counted (documented so they are not silently dropped):**

- **S20** — the add-track menu opens below the trigger; the frame opens above. It follows the
  S05/S16 add-row position; re-check after that fix.
- **S63** — additive MIDI-bar controls (Instrument/Chord/Arp, ±12, Clear, Import MIDI, Keys)
  shift the captured `Key / Scale / View` right. Toolbar flow, not a menu row; if rule 4 is
  read strictly for toolbars, this becomes LAYOUT.
- **S29** — the frame's take-header controls are behind its own What's This card, so no
  missing-control claim can be made either way; recapture both with help off.
- **S41/S48** — dock cards ~165 px vs ~205 px in the frame; panel is resizable, weak evidence,
  left as STATE.

---

## 6. What recapture must fix (STATE, 26)

**Stale capture, fix already in code (8 + 2):** S03, S06, S07, S08, S24, S39,
EXTRA-library-uploads, EXTRA-project-load-error; plus S30 and EXTRA-restoring (capture predates
the fixture fix / the loading change).

**Content/state, recapture with the reference's content (12):** S15, S25, S29, S34, S35, S40,
S41, S48 (Limiter on master), S49 (dismiss What's This), S53, S63, EXTRA-library-song-detail.

**Wrong surface / surface state (4):** EXTRA-generation-refused ×2 (capture the policy
refusal the product actually shows, or record the legacy frame as a corpus gap),
EXTRA-take-lanes-empty (close the clip rail), S20 (re-shoot after the add-row fix).

**Also recapture S14, S39, S44 and S13** where the capture lags today's chrome fixes even
though the row is not STATE (S14/S28/S61 stay LAYOUT regardless).

---

## 7. D3 verdict

> **D3: FAIL — eight unexplained LAYOUT rows remain:** S36 (track panel removed when the
> assistant opens), S61 (`Turn on auto-reload` demoted, `Not now` displaced by additive
> `Buy credits`), S14 (captured shortcut sections/rows replaced), S28 (additive rows
> interleaved inside the captured clip menu), S05/S16 (`+ Add new track` displaced), S21
> (hidden-count chip on its own row; popover hides `Add new track`), S60 (refusal inline
> instead of the captured toast). Everything else is ALLOWED (8), STATE (26, recapture) or
> REGION (11, framing/surface composition).

The D3 count cannot go to zero by recapture alone: seven causes above are current-build layout
or rule-4 displacements, not stale pixels. The fastest route to a defensible zero is:
fix the three one-component items (S60 toast, S36 keep the track panel, S05/S16/S21 add-row
layout), move the two interleaved clip-menu additions after the captured run (S28), decide
the shortcuts catalogue (S14: either adopt the captured groups/rows or record ours in §5), and
decide auto-reload (S61: build the captured primary button, or record the disabled switch and
the `Buy credits` insertion in §5).

---

## 8. Sign-off

- 53/53 `REVIEW` rows re-adjudicated against `9f7c2baa`: **LAYOUT 8 · STATE 26 · REGION 11 ·
  ALLOWED 8**.
- Every named fix was checked in the capture **and** the source: S13/S19/S27/S28-colours/S44 pass
  on the current capture; S05/S16's default track, S24's flags, S08's dot list, S14's width,
  S39's menu anchor, S61's modal, S02's providers, the demo tile, the MIDI overview and the
  load-error/upload meta are fixed in code but **five captures still predate their fix**.
- No server ran, no capture was taken, no product or reference file changed; only this report
  was added. Nothing pushed.
- Base `origin/main` `9f7c2baa` (`summary.json` generated 12:43 local on `1b2f87bb`; no capture
  or percentage changed after that commit).
