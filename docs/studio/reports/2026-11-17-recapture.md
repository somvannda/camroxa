# Recapture of the 8 stale STATE screens (W10)

**Date:** 2026-11-17
**Workstream:** W10, spawned from `docs/studio/RESIDUAL_VERIFICATION_PLAN.md` (D3)
**Branch:** `qa/recapture`, base `origin/main` `c5390ef1`
**Worktree:** `C:\Users\Kong Somvannda\AppData\Local\Temp\camxora-res-recapture`
**Inputs:** `docs/studio/reports/2026-11-17-pixel-adjudication.md` (W9) §1.1 and §7,
`2026-11-17-capture-plan.md`, `2026-11-17-capture-run.md`, `docs/studio/reference/PAIRING.json`.
**Scope:** captures, the capture script, PAIRING and this report. No product component, no
reference frame, no frame rename, no push, no deploy, `G:\Developments\Projects\Camxora`
untouched. **Zero provider credits spent** — every provider-backed state is a route mock.

> **Headline.** All **8** stale captures were re-shot on `c5390ef1`. **7 of 8 now match the
> reference frame's own size exactly** (aspect delta 0 %, whole-frame comparable; five of them
> were `different-viewport` before). **5 rows improved**, 2 moved slightly up while becoming
> real comparisons, 1 crossed into `STRUCTURAL`, and 3 uncovered product deltas that W9's
> stale-capture assumption had hidden (S14's dialog width, S39's menu placement, S64's clipped
> readout). The script also carried a dead audio fixture (`/demo-loop.wav`, 404) that had
> silently emptied every clip waveform in every capture it ever produced; that is fixed.
> `check:clone` passes 73/73; `check:pixels` is now **10 STRUCTURAL / 53 REVIEW** (was
> 9 / 54).

---

## 1. Why these eight

W9 §1.1 lists the captures that predate the fix that addresses their own delta — eight rows
measuring builds that no longer exist. Four of them (S14, S19, S27, S44) had even been scored
`LAYOUT` by W2 for exactly the delta that has since been fixed. Nothing in the app needed
changing to move them; they needed fresh pixels.

| Screen | Old capture (mtime / commit) | Superseded by | What HEAD should show |
|---|---|---|---|
| S03, S06 | `ours-entry-overlay.png` 11-16 13:21 | `a97f2c14` | 5-tile start overlay + `Browse Studio projects ›` + ✕ |
| S14 | `ours-shortcuts.png` 11-14 | `a97f2c14` | shortcuts dialog with a search field and grouped rows |
| S19 | `ours-track-options.png` 11-14 | `106f1209` | the six captured rows, `Bounce track` appended after them |
| S27 | `ours-clip-info.png` 11-15 | `f8918ce4` | like/dislike in the rail header, artwork hero |
| S39 | `ours-plugin-catalog.png` 11-15 | `68a67e07` | ten named plugin tiles |
| S44 | `ours-plugin-dock-eq-convolution.png` 11-14 | `68a67e07` | IR slot reads `NO ASSET LOADED` |
| S64 | `ours-editor-1024.png` 11-14 | `StudioHeader.tsx:309` | bar/beat readout still present at 1024 px |

(S39 and S44 shared one file with S41/S42. S44 now has its own; S39 already had a file of
its own.)

---

## 2. Stack actually used

One shell lifetime, web server started from **this worktree**:

| Component | Port | State |
|---|---|---|
| moto (S3 stand-in) | 9000 | already running; the bucket was **re-created** because the instance had lost it (`storage` was failing with `HeadBucket → 404`) |
| platform API | 8100 | already running against the sandbox DB. Readiness after the bucket fix: `tables ✓ pricing ✓ storage ✓ internal_token ✓ suno_api_base_url ✓`, `musicapi ✗`, `suno_callback_base_url ✗` |
| web dev server | **3104** | `npm run dev -- -p 3104` in `camxora.com` of this worktree (`PLATFORM_API_URL=http://127.0.0.1:8100`) |
| login | — | `somvannda@gmail.com` / `StudioLocal!2026`, through `POST /api/v3/auth/login` |

`:3103` was held by another worktree's dev server (`camxora-res-manual-run`), so the capture
server was moved to `:3104` as instructed rather than killing someone else's process.
`musicapi` was **not** healthy on `:4003` during this pass (internal-token mismatch with the
running platform API). That is not used by any of these eight screens: project CRUD is the
platform DB, the library/generation lists are route mocks, and the waveform decodes
`public/demo-loop.wav`. No provider call was attempted, so no provider error path was
exercised.

Captures were taken with `CAPTURE_BASE_URL=http://localhost:3104`.

---

## 3. Script additions

`camxora.com/scripts/capture-screens.mjs` grows from 25 to **33 rows / 32 capture files**.
Eight rows and eight scenarios were added; two fixture bugs were fixed on the way.

| Screen | Capture file | Viewport | Scenario step that produces the state |
|---|---|---|---|
| S03 | `ours-entry-overlay-reopened.png` *(new file)* | 1094×1245 | one-track project → select the track (prompt-bar chip) → project menu ▸ **Show Quick Start again** |
| S06 | `ours-entry-overlay.png` *(re-shot)* | 1094×1245 | brand-new empty project, first run (no `studio:onboarded:*` flag) |
| S14 | `ours-shortcuts.png` | 1115×1245 | Learn pill ▸ **Keyboard Shortcuts**, query cleared so the groups render |
| S19 | `ours-track-options.png` | 1094×1245 | `button[aria-label="Options for Audio Track"]` |
| S27 | `ours-clip-info.png` | 1920×1277 | generation mock with `image_url` + clip `songId` → right-click clip ▸ **Clip Info** |
| S39 | `ours-plugin-catalog.png` | 1689×1277 | track dock ▸ **Add effect** ▸ catalogue header **⋯** (Catalogue options) |
| S44 | `ours-plugin-dock-convolution.png` *(new file)* | 1689×1277 (crop frame) | track dock ▸ **Add effect** ▸ **Convolution** |
| S64 | `ours-editor-1024.png` | 1024×900 | four-track project → select `Bass Line` → footer **Automation** |

Two fixture changes and one dead-asset fix were required, all capture-side:

1. **`createProject` now carries `songId`.** It built lanes from an explicit field list, so a
   clip's provenance was dropped on save and `StudioEditorShell` resolved `clipSource: null`
   — no artwork, no source title, no date. S27 cannot be evidenced without it.
2. **S64 scopes the track click to the track strip.** The clip carries the track's title, so
   `getByRole("button", { name: "Bass Line" })` matched both the track name button and the
   clip button (strict-mode violation). The first attempt failed; the row was re-run.
3. **The audio fixture pointed at a 404.** Every scenario used `/demo-loop.wav`, but the file
   lives at `public/seed/demo-loop.wav` — the capture plan's §7 precondition ("`public/demo-loop.wav`
   (present)") was wrong. The dev log shows `GET /demo-loop.wav 404` on every run, so **no
   clip in any capture this script has produced ever decoded audio**, which is why clip bodies
   painted as flat colour blocks. Fixed to `/seed/demo-loop.wav` (31 occurrences) and all
   eight rows re-shot again after the fix. `public/seed/demo-loop.wav` peaks at 3.7 % of full
   scale, so even decoded the trace is a thin line — a fixture-volume limit, not a render bug.

`--list` prints the authority: `33 rows → 32 capture files`.

---

## 4. What each frame now shows (and what is still wrong)

Every PNG was opened and inspected at full resolution, not just asserted in the DOM.

| Screen | Frame evidences | Residual delta | Class |
|---|---|---|---|
| **S03** | Overlay open over a **one-track** project (matching the frame's single `Audio Track` row), five tiles, `Browse Studio projects ›`, `Start empty`, ✕; prompt bar carries the `Audio Track ×` chip (dimmed by the backdrop but legible) | Our overlay is a **3+2 card grid with a subtitle and a second pill**; the frame is a horizontal fan of five tiles with no subtitle and one pill. Tile geometry is our own design — needs an ALLOWED/LAYOUT call | state fixed → **layout call for W0** |
| **S06** | First-run overlay on a brand-new empty project: same 5 tiles, browse pill, ✕ | Same grid-vs-fan delta; behind it, our zero-track empty project shows the "Your session is empty" placeholder where the frame has an `Audio Track` row (that is S05/S16's delta, out of scope) | state fixed → layout (W0) |
| **S14** | Keyboard Shortcuts dialog with the search field, header ✕ and two-column grouped rows | **The dialog is 480 px wide, not the frame's ~746 px**, because `.se-dialog{max-width:480px}` (`app/globals.css:5270`) caps `.se-shortcuts-dialog{width:min(920px,92vw)}` (`:5487`). Rows wrap to 2–3 lines (`Play from the start of the time selection`, `Move the focused track up / down`), and the dialog cannot fit the captured row count. **W9's "HEAD renders the 920 px dialog" is not true at this commit** | **LAYOUT** (new cause) |
| **S19** | `Audio Track options` menu: Rename track, Color, Collapse controls, Duplicate, Hide & Mute Track, Delete — then **Bounce track last** | None at control level. The six captured rows are present in the captured order and the additive row is appended, exactly as `StudioTrackPanel.tsx:349-366` intends | **control-level PASS**; 6.43 % is chrome/palette/viewport |
| **S27** | Clip-info rail with the **artwork hero** (art + `131-Audio 0001` + `Aug 5, 2026`), **like and dislike in the header**, Remix, the waveform player row, Info/Stems tabs, Source/Styles/Lyrics/Details/Comments | The two header buttons render **disabled** (`disabled={!onToggleLike}`, `StudioClipInfo.tsx:155,165`) because the clip-inspector call site (`StudioEditorShell.tsx:5991-6002`) passes neither handler — only the library's song detail does. The player row now renders (it did not before the audio fix) but draws a flat trace and has no play affordance, where the frame shows a green encoded waveform with a play button | **LAYOUT** (header cluster present but inert; player incomplete) |
| **S39** | `Add a track plugin` dialog with search, the **Catalogue options** menu open, `My plugins` (Create new plugin) and the ten audio-effect tiles — Compressor, Convolution, Delay, Distortion, EQ, Gate, Limiter, Reverb, Rhythm Gate, then **Stereo Utility** starting below the fold exactly as the frame's last row does | The options menu is `position:fixed` with no coordinates when opened from the catalogue header (`StudioPluginDock.tsx:1327-1342`, `.sp-ir-menu` at `globals.css:4528`), so it paints at the dialog's top-left and **covers the "Add a track plugin" title and the first third of the search field**. Every card in the DOM here carries a name *and* a description, so W9's "nameless 10th tile" does not reproduce at this commit | **LAYOUT** (menu placement) |
| **S44** | Convolution card: empty IR slot, `NO ASSET LOADED` chip, Mix/Gain/Pre/Width | None in content — the string now matches the frame verbatim. The 5.65 % is the 940×400 card crop compared against a whole 1689×1277 viewport | **REGION** (frame is a crop) |
| **S64** | 1024×900 editor with four tracks, the automation band open, and the bar/beat readout **still in the header** | The readout is present but **clipped to `001.`**: at ≤1100 px `.se-head-group.se-time .se-readout{min-width:0;padding:0}` (`globals.css:4627`) lets the header squeeze it. The reference reads `042.3.1`. The automation band also offers only `Volume`/`Pan` where the frame has `Velocity`/`Pitch Bend`/`Modulation` | **LAYOUT** (truncated control) |

### 4.1 What this does to the W9 verdicts

S19 moves to a control-level pass. S03/S06/S14/S27/S39/S44/S64 stop being "measure the wrong
build" and become judgeable — and three of them (S14, S39, S64) are **not** fixed by the
commits that motivated the re-shoot: the dialog is still capped at 480 px, the catalogue menu
still lands on top of the dialog title, and the readout is still clipped. Those are new
`LAYOUT` claims with `file:line`, not recapture failures.

### 4.2 One finding that closes an open question: the 404 audio fixture

W9 §3 flagged S30 — "our selected clip renders as a black body with one flat green line …
a clip that paints black is worth its own check, because if a real clip renders that way it is
a render bug". It is **not** a render bug: the capture script had been requesting
`/demo-loop.wav`, which does not exist (`public/seed/demo-loop.wav` does), so the Waveform
component had nothing to decode and every clip body fell back to its flat colour. The fixture
is fixed here; whoever re-shoots S25/S30 gets decoded waveforms for free and should not spend
time on the renderer.

---

## 5. Retaken

| Screen | Attempts | Reason |
|---|---|---|
| S64 | 3 | first run died on a strict-mode locator collision (track name vs clip title); the scenario now scopes the click to the track strip. Re-shot again after the audio-fixture fix |
| S03 S06 S19 S27 | 2 | first pass had no decoded audio (`/demo-loop.wav` 404); re-shot after pointing the fixture at `/seed/demo-loop.wav` |
| S14 S39 S44 | 2 | re-shot with the rest of the set after the audio fix; their surfaces do not depend on it, so the frames are unchanged in content |
| S39 | — | the requested menu is open and its placement defect is the evidence — retaking it closed would hide the thing the row is about |

No other row needed a second pass: each frame was inspected and holds the state it claims
(menus open, panels uncovered, overlays present).

---

## 6. PAIRING edits

Four field edits over three entries — only where a filename changed or a group split.

| Screen | Field | From | To |
|---|---|---|---|
| S03 | `capture` | `ours-entry-overlay.png` | `ours-entry-overlay-reopened.png` |
| S06 | `sharedWith` | `"S03"` | *(deleted — S06 now owns `ours-entry-overlay.png`)* |
| S44 | `capture` | `ours-plugin-dock-eq-convolution.png` | `ours-plugin-dock-convolution.png` |
| S44 | `sharedWith` | `"S41"` | *(deleted — S44 has its own file)* |

The five-way plugin-dock group therefore ends as **`S41` anchor + `S42 sharedWith S41`** on
`ours-plugin-dock-eq-convolution.png`; `S40` and `S46` keep the files W3 gave them. The
overlay group ends as **`S06` anchor on `ours-entry-overlay.png`** plus `S03` on its own file.
`check:clone` confirms both groups: 64 paired captures, 73/73 evidenced.

---

## 7. Gate counts, before → after

`check:pixels` before = the committed `summary.json` at `b3d718f4` (generated
2026-11-17T03:24:17Z, before this pass).

| Gate | Before | After |
|---|---|---|
| `check:clone` | passes — 73/73 evidenced, 64 captures, 31 specs, 2 negative, metrics 8/8, strings 70/70 | **passes** — identical counts |
| `check:pixels` screens / diffable | 73 / 63 | 73 / **63** |
| `IDENTICAL` | 0 | 0 |
| `WITHIN` | 0 | 0 |
| `STRUCTURAL` | **9** | **10** |
| `REVIEW` | **54** | **53** |
| `NO-FRAME` | 10 | 10 |

Per screen (`diff %`, before → after; comparability is the harness's own classification):

| Screen | Before | After | Frame size match | Comparability |
|---|---|---|---|---|
| S03 | 5.36 | **5.92** | 1689×1277 → **1094×1245 = ref** | different-viewport → **full-viewport** |
| S06 | 5.46 | **6.03** | 1689×1277 → **1094×1245 = ref** | different-viewport → **full-viewport** |
| S14 | 11.78 | **10.95** | 1689×1277 → **1115×1245 = ref** | different-viewport → **full-viewport** |
| S19 | 8.51 | **6.41** | 1689×1277 → **1094×1245 = ref** | different-viewport → **full-viewport** |
| S27 | 15.69 | **14.69** | 1689×1277 → **1920×1277 = ref** | different-viewport → **full-viewport** |
| S39 | 10.92 | **10.60** | 1689×1277 = ref (unchanged) | full-viewport |
| S44 | 9.76 | **5.65** | 1689×1277 (frame is a 940×400 crop) | crop-or-panel |
| S64 | 23.17 | **25.97** | 1024×900 = ref (unchanged) | full-viewport → **STRUCTURAL** (edge 0.41 → 0.63) |

S03, S06 and S64 rise slightly because the number is now a real whole-frame comparison of
matching viewports instead of a framing artefact; S64 crossed the edge-structure threshold and
is now judged `STRUCTURAL` by the harness rather than abstaining. S14, S19, S27, S39 and S44
fall because the control they are about is now on screen (and, for S27/S19/S03/S64, because
the clips now decode audio instead of painting as flat blocks).

---

## 8. Still stale (deliberately out of scope)

The eight rows above were W9's *stale* group. The remaining **20** `STATE` rows from W9 §7
still measure old captures and are untouched here:

- **content/state (14):** S15, S20, S25, S29, S30, S34, S35, S36, S40, S41, S48, S49, S53, S63
  — they need the reference's project data (a Limiter on the master chain for S48, a two-card
  chain for S40/S41, a clip whose waveform paints for S25/S30), not just a fresh shot.
- **surface state (6):** S07 (dismiss the What's This card first), EXTRA-generation-refused ×2,
  EXTRA-restoring, EXTRA-take-lanes-empty, EXTRA-library-song-detail.

S24, S08, S61 and S02 were **not** touched, per instruction — their fixes are not in this
build. S28's clip-colour submenu is still clipped by `.se-clip-menu{overflow:auto}` (W3 §4),
which is why it stays at 49.25 % on this commit.

---

## 9. Sign-off

- **Screens recaptured: 8** (S03, S06, S14, S19, S27, S39, S44, S64) → **8 files**
  (6 replaced, 2 new: `ours-entry-overlay-reopened.png`, `ours-plugin-dock-convolution.png`).
- **Retaken after review: all 8** (audio fixture fixed between passes); S64 three times.
- **Still stale: 20** STATE rows (listed above), plus S28's blocked submenu.
- **New product deltas found by the fresh frames: 3** (`LAYOUT`) — S14 dialog capped at 480 px,
  S39 catalogue menu covering the dialog title, S64 readout clipped to `001.` — plus S27's
  inert like/dislike cluster and incomplete player row. All have `file:line` in §4; none was
  fixed here.
- **Script defect fixed:** the audio fixture pointed at `/demo-loop.wav`, which 404s; every
  clip in every capture this script has made lacked a waveform. Now `/seed/demo-loop.wav`
  (31 occurrences). This also explains W9's S30 "black clip" note — not a render bug.
- **Gates:** `check:clone` passes (73/73, 64 captures); `check:pixels` **63 diffable ·
  10 STRUCTURAL · 53 REVIEW · 10 NO-FRAME** (before: 63 · 9 · 54 · 10).
- Nothing pushed, nothing deployed, production untouched, no credits spent.
- Commit: single commit on `qa/recapture` (working tree clean; not pushed).
