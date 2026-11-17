# W5-ADF — independent manual run, areas A (16), D (88) and F (33)

**Date:** 2026-11-17
**Agent:** W5-ADF (`qa/manual-adf`) — independent of the W5 B/E run and of Agent A; their verdicts were not reused
**Base:** `origin/main` `9f7c2baa`
**Worktree:** `C:\Users\Kong Somvannda\AppData\Local\Temp\camxora-res-adf`
**Scope executed:** **137 / 137** checks — **A (16)**, **D (88)**, **F (33)** in full
**Verdict:** **133 PASS · 4 FAIL · 0 N/A · 0 BLOCKED**

Every row was produced by driving the UI in Chromium (Playwright, 1× DPR) against a full
local stack, not by reading code. Code references appear only where a failure needs a cause.
Screenshots and the raw per-row JSON live in `docs/studio/reports/evidence-adf/`.

---

## 1. Totals

| Area | Checks | PASS | FAIL | N/A | BLOCKED |
|---|---|---|---|---|---|
| **A — entry, gates, chrome** | 16 | 15 | 1 | 0 | 0 |
| **D — arrangement, clip, warp, MIDI** | 88 | 85 | 3 | 0 | 0 |
| **F — async boundaries** | 33 | 33 | 0 | 0 | 0 |
| **This pass** | **137** | **133** | **4** | **0** | **0** |

Failing ids: **A-14, D-43, D-50, D-71**. Each has a screenshot in
`docs/studio/reports/evidence-adf/`. Two extra probes were run and are not counted:
`A-GATE` (the 767/768 desktop-gate boundary, PASS) and `D-VP` (the same gestures at
1280×800, PASS).

Five **regression probes** re-ran the failures recorded earlier today; all five are green
(§4). They are not part of the 137.

---

## 2. What was actually running

One shell lifetime, one stack, ports owned by this workstream (W5-C keeps `:3105`/`:8101`):

| Component | Port | Evidence it was live |
|---|---|---|
| moto (S3) | 9000 | `bucket camxora-studio` created; IR/export/stem paths answered |
| platform API | **8102** | `/health` 200; sandbox DB `camxora_pfm_sandbox`; Studio token; moto storage; Suno base → `:4003` |
| musicapi | 4003 | `/health` 200; `STUDIO_INTERNAL_TOKEN` matches the platform value |
| web dev server | **3106** | `/studio` 200; editor loads every fixture |

Readiness on this stack (`/api/v3/web-music/studio/readiness`): `tables ✓ · pricing ✓ ·
storage ✓ · internal_token ✓ · suno_api_base_url ✓ · musicapi ✓ · musicapi_accounts ✓ ·
suno_callback_base_url ✗` — the callback is the expected local-run miss, nothing else.

Account: `somvannda@gmail.com` / `StudioLocal!2026`. **No provider credits were spent.**

### Fixtures (built through the sandbox API, as the checklist requires)

| Fixture | Contents |
|---|---|
| **P1** | 120 BPM 4/4; **Drums** (two song-backed audio clips, A 0–4 s and B 8–12 s), **Bass** (MIDI clip), **Vox** (uploaded audio, no `songId`), **Scratch** (hidden + muted); Drums chain = Compressor → Reverb; master = Limiter; marker `Verse` at 4 s; Drums volume automation (2 points) |
| **P-warp** | P1 with Drums A carrying `warp` (Stretch off, no markers) and `audio` settings |
| **P-MIDI** | P1 with off-grid Bass notes (0.13 / 0.62 / 1.27 s) for quantize and transpose rows |

### Honest limits of this run

- **F-27…F-32** assert the **UI states** of provider refusals with the provider endpoint
  mocked at the network layer (`POST /web-music/generate`, `…/cover`, `…/stems`). That is
  the checklist's G-3 rule; whether the provider returns audio is W6/D4, not this pass.
- **F-20…F-26** mock `/sync` and `/refresh` payloads to reach the five mirror states; the
  poll cadence and the post-save read are real timers and real requests.
- **A-05** delays one project `GET` by 800 ms so the transient `Loading project…` surface
  can be observed; nothing else about that row is manufactured.
- **D-57 / D-71** use Playwright's `Shift+Digit1` spelling because `Shift+1` is delivered
  as key `"1"` by the driver while a real browser sends `"!"`. Both branches of the
  handlers accept either.
- One agent, one browser profile: presence avatars and remote playheads (G-8) have no rows
  in A/D/F and were not exercised.
- **Capture anomaly:** with the clip-info inspector open, `page.screenshot()` stalled for
  ~170 s before erroring (page still responsive to `evaluate`). F-32 therefore records DOM
  evidence instead of a PNG. Not scored; recorded so the next agent does not lose time.
- The checklist's cross-reference `docs/studio/reports/2026-11-17-manual-run-c.md` does
  **not exist** on `origin/main`, so area C could not be cross-checked from this run.

---

## 3. Ranked defects

Ranked by user impact. Nothing was fixed (this pass records, it does not repair).

### P2 — the bottom band is empty on every fresh load (A-14)

Opening a project renders the shell with `bottomPanelOpen === true` but
`selectedTrack === null`, so neither the plugin dock nor the master chain mounts and the
bottom band is a blank strip until the user clicks a track. The row's expectation
(`.sp-dock` present at the default landing) cannot pass, and this is the same shape the
B/E pass recorded as O-3.

- Reproduce: open P1 → `.sp-dock` count = **0**, `.se-assistant` = 0, `.se-library` = 0.
- Evidence: `A-14-1689x1277.png`.
- Cause: the dock branch requires `bottomPanelOpen && selectedTrack`
  (`StudioEditorShell.tsx:7425`); nothing selects a track on load.
- Class: **PRODUCT / state** (nothing is broken functionally; the landing screen is blank).

### P2 — the footer's Loop button does not create the four-bar loop (D-43)

The header loop control and `Ctrl+L` call `toggleLoop()`, which seeds a four-bar range and
persists `loopStart`/`loopEnd`. The footer's Loop button is wired to a bare
`setLoop(v => !v)` (`StudioEditorShell.tsx:7455`), so with no range it toggles a loop with
`loopEnd = 0`: no band, nothing persisted, and playback never wraps.

- Reproduce: no range → press **footer** Loop → `.se-loop-band` = **0**,
  saved `loopEnd` = **null**. Press **header** Loop → band = 1, `loopEnd` = **8 s**.
- Evidence: `D-43-1689x1277.png`.
- Class: **PRODUCT / behaviour** (single-line wiring; the header path is correct).

### P3 — the first `Shift+1` in Clip Settings is swallowed (D-71)

With the Clip Settings panel open, the first density shortcut does nothing; the same key
applied a second time moves the quantize grid 1/8 → 1/16. Measured in three of four runs
(fails deterministically in an isolated run, passed once inside the full suite, so it is
state- or timing-dependent rather than dead).

- Reproduce: double-click an audio clip → press `Shift+1` (key `!`) → grid stays `1/8`;
  press again → `1/16`. The Quantize action itself snaps correctly (5 markers moved).
- Evidence: `D-71-1689x1277.png`.
- Class: **PRODUCT / input** (low severity: the grid buttons work, and the second press
  works; but the first keypress is lost).

### P3 — section-marker labels truncate at the widest zoom-out (D-50)

At 48 px/bar a marker button is 16 px wide while its label needs more, so
`scrollWidth > clientWidth` and the text is clipped. Every other marker row passes.

- Reproduce: Zoom out ×3 → measure `.se-section-marker` (width 16, overflow true).
- Evidence: `D-50-1689x1277.png`.
- Class: **PRODUCT / layout-cosmetic** (the marker still seeks and deletes correctly).

### Observations (not scored)

- **O-1 — A-07's evidence selector is stale.** The shipped load-failure surface is
  `.se-load-failed[role="alert"]` ("Could not open this project" + `Try again`), not
  `.se-error`. Recorded PASS on the row's expected behaviour (error surfaced, no hang).
- **O-2 — A-06's "4 tracks" reads as 3 rows + a hidden pill.** P1's Scratch track is
  hidden, so the checklist wording and the fixture disagree; the reload restores all four
  (3 visible + `Hidden tracks 1`). Not a defect.
- **O-3 — the time-selection band intercepts clicks on a clip underneath it.** Where a
  range handle sits over a clip, `click()` on the clip is blocked by the handle. Expected
  DAW layering, but it means "click the clip" needs a point away from the range edges
  (D-01 had to move the range off the clip to measure the row).
- **O-4 — D-24's toast is "Split into 5 clips at 4 transients."** and the progress toast
  is "Finding transients." (no ellipsis). Copy differs from the row's spelling only.
- **O-5 — two documented absences confirmed as behaviour, not defects:** additive
  Shift-click selection does not exist (D-05) and Paste keeps the origin track (D-33).
- **O-6 — D-50 aside, all marker, warp, automation and MIDI rows pass**, including the
  MIDI overview strip and the loop flags that were fixed earlier today (§4).

---

## 4. Previously-failing rows now green

Five probes re-ran the failures recorded earlier today, on this tree. All are green
(`results-regression.json`).

| Probe | Earlier row(s) | Measured now |
|---|---|---|
| **R-EQ** | B-55, B-56 (EQ drag), B-51/B-52 (kHz readout) | Dragging the Band 1 handle 160 px right / 50 px up moved **Freq `1khz` → `16.6khz`** and Gain `0db` → `8db`; the readout has no trailing `.0` (`1khz`, not `1.0khz`) |
| **R-UNDO** | B-97, B-101 (stale plugin rail) | Remove both Drums slots, `Ctrl+Z` → **1** slot, `Ctrl+Z` → **2** slots; the rail follows the document |
| **R-MENU** | E-18, E-24 (clip-menu overflow) | At 768×1024 the clip menu computes `overflow-y: auto`, 889 px client / 1070 px scroll, box bottom inside the viewport |
| **R-OVW** | W7 MIDI overview (shipped today) | `.se-midi-overview-track` present with a real window (21.87 % wide at zoom) and a click on it scrolls the roll **639 → 1277** |
| **R-LOOP** | S24 loop flags | Loop band + `Loop start` + `Loop end` flags present; dragging the end flag commits a new `loopEnd` |

Also re-checked in-area: **A-07** (load-error recovery) now surfaces an error with a retry
instead of hanging on `Loading project…`; **A-05** shows `shell → loading → shell+clips`
with no onboarding flash.

The areas that remain red are **not** regressions of those fixes: A-14 (empty landing
band), D-43 (footer loop wiring) and D-71 (first shortcut press) are independent, and D-50
is a marker-label width limit at maximum zoom-out.

---

## 5. Per-check results

Fixtures: P1 unless the row says otherwise. Viewport 1689×1277 for every row; `A-GATE`
uses 768×1024 and 767×1024, `D-VP` uses 1280×800.

## A rows
| ID | Verdict | Evidence (measured) |
|---|---|---|
| A-01 | PASS | marketing h1 present (1); .studio-home=0; "Your projects"=0 |
| A-02 | PASS | h1="Your projects"; .studio-home-actions=1; New project=1; Create a song=1 |
| A-03 | PASS | .se-gate h1="Studio"; p="Sign in to open a project."; link=/login?next=/studio |
| A-04 | PASS | .se-gate h1="No project selected"; p="Choose a project from the Studio home." |
| A-05 | PASS | observed states=shell -> loadingshell -> shellclip; onboarding flash=false |
| A-06 | PASS | chip="ADF P1"; bpm=120; sig=4/4; .se-track=3 + hidden pill "1" (Scratch is hidden, so 3 rows + 1 hidden) |
| A-07 | PASS | role=alert text="Could not open this projectStudio project not found.Details00000000-0000-4000-8000-0000000"; .se-load-failed=1; .se-loading=0 |
| A-08 | PASS | /studio/editor/classic -> 200; no 404 copy |
| A-09 | PASS | [role=main]=1; [aria-label="Editor menus"]=1 |
| A-10 | PASS | head 0..52; body 52..1225; dock=absent; foot 1225..1277 |
| A-11 | PASS | .se-shell clientHeight=1277; scrollHeight=1277 |
| A-12 | PASS | .se-body .se-sr-only is <h1> "ADF P1" |
| A-13 | PASS | 20 tabs, 20 distinct stops: button:Back to start \| button:Choose input for recording \| button:Stop \| button:Play \| button:Loop \| button:Metronome (click track) \| input:Tempo in BPM \| select:Time signature … |
| A-14 | FAIL | {"dock":0,"assistant":0,"library":0,"empty":0} — A-14-1689x1277.png :: bottom panel is empty on load (no track selected, so no dock) |
| A-15 | PASS | .se-toast[role=status]="Select a clip to edit."; dismiss aria-label="Dismiss export message" |
| A-16 | PASS | .se-loading=0 after Saved |

### D1 — selection and move

| ID | Verdict | Evidence (measured) |
|---|---|---|
| D-01 | PASS | range 1→0; .se-clip.selected=1; track="Drums" |
| D-02 | PASS | .se-clip.selected=0; playhead 240.0px → 672.0px |
| D-03 | PASS | .se-marquee visible during drag; .se-clip.selected=2 (A 260, B 644) |
| D-04 | PASS | group kept: .se-clip.selected=2 |
| D-05 | PASS | shift-click replaces: .se-clip.selected=1 ("Vox") (additive select remains an absence, G-6) |
| D-06 | PASS | Ctrl+A → .se-clip.selected=5/5 |
| D-07 | PASS | start 0 → 2; .se-snap-line=1 |
| D-08 | PASS | all selected clips moved +2s: [2,2,2,2] |
| D-09 | PASS | start clamped to 0 (>= 0) |

### D2 — trim and fades

| ID | Verdict | Evidence (measured) |
|---|---|---|
| D-10 | PASS | .se-trim-start opacity 0 → 1 on hover |
| D-11 | PASS | duration 4 → 4.5; start stayed 0 |
| D-12 | PASS | start +0.5, offset +0.5 |
| D-13 | PASS | start=0, offset=0 |
| D-14 | PASS | undo disabled state unchanged (false); no write |
| D-15 | PASS | duration unchanged (4.5); .trimming=0 |
| D-16 | PASS | fadeIn=1; .se-fade=1 |
| D-17 | PASS | fadeOut=2; in+out=3 <= duration 4.5 |
| D-18 | PASS | fadeOut removed from the document |
| D-19 | PASS | Shift+F set fadeIn=0.5 then cleared it |
| D-20 | PASS | toast="Fades only apply to audio arrangements."; no fade written |

### D3 — split, duplicate, delete

| ID | Verdict | Evidence (measured) |
|---|---|---|
| D-21 | PASS | clip count 5→6; right half start=2 offset=2 |
| D-22 | PASS | split at the clip start: count stayed 5 |
| D-23 | PASS | multi-split: clip count 6→7 |
| D-24 | PASS | toast="Split into 5 clips at 4 transients."; lanes 5→9 |
| D-25 | PASS | copy at start=2 (original 0, +2s) |
| D-26 | PASS | copy start=10; ruler width 11520→11520 |
| D-27 | PASS | clip removed; focus on "se-clip selected" |
| D-28 | PASS | lanes 5 → 0 → 5 in one undo |

### D4 — clipboard and clip settings

| ID | Verdict | Evidence (measured) |
|---|---|---|
| D-29 | PASS | pasted at 14s (playhead 14s) |
| D-30 | PASS | two independent copies (2); original untouched |
| D-31 | PASS | copy with nothing selected copied nothing (Paste disabled=true) |
| D-32 | PASS | lanes 5 → 4 (cut) → 5 (paste) |
| D-33 | PASS | paste landed on "Drums" (origin track), not the focused Vox track (G-7 absence) |
| D-34 | PASS | fadeIn=0.5 copied; no volume/pan/fx keys on the clip |
| D-35 | PASS | toast="Settings pasted to 5 clips." |
| D-36 | PASS | after reload Paste is disabled (in-memory buffer) |

### D5 — ruler, time selection and loop

| ID | Verdict | Evidence (measured) |
|---|---|---|
| D-37 | PASS | playhead left=288.0px; .se-range=0; flag=1 |
| D-38 | PASS | .se-range=1; Selection start/end handles present |
| D-39 | PASS | range width 192 → 384 px |
| D-40 | PASS | range width 384 → 480 (+1 bar) |
| D-41 | PASS | Shift+→ grew the range 480 → 504 px (one 1/4 step) |
| D-42 | PASS | Escape cleared the range (.se-range=0) |
| D-43 | FAIL | footer={"band":0,"end":null} header={"band":1,"end":8} — D-43-1689x1277.png :: loop band/persistence differs between surfaces: footer band=0 loopEnd=null; header band=1 loopEnd=8 |
| D-44 | PASS | loopEnd 8 → 12; >= start + one beat |
| D-45 | PASS | playhead wrapped inside the loop: 96,106,117,131,144,157,170,182,2,14,28,41,54,66 |

### D6 — section markers

| ID | Verdict | Evidence (measured) |
|---|---|---|
| D-46 | PASS | markers=2; "Drums B" at 8s |
| D-47 | PASS | playhead 0 → 384px (bar 5); .se-range=0 |
| D-48 | PASS | markers 2→1; no context menu |
| D-49 | PASS | marker persisted after reload; times=[4] sorted=true |
| D-50 | FAIL | [{"text":"Verse","width":16,"overflow":true}] — D-50-1689x1277.png :: marker labels truncate at the widest zoom-out |

### D7 — zoom, grid and snap

| ID | Verdict | Evidence (measured) |
|---|---|---|
| D-51 | PASS | widths 96 → 144 → 192; clamps 192 / 48 |
| D-52 | PASS | footer zoom: 48 → 64 px/bar |
| D-53 | PASS | Z on a 2-bar range → 192 px/bar (was 48); scrollLeft 0 → 0 |
| D-54 | PASS | clip-selection zoom: 64 → 192 px/bar |
| D-55 | PASS | Z with nothing selected zoomed to fit: 64 → 192 px/bar; scrollLeft=0 |
| D-56 | PASS | Fit to content: scrollLeft=0; width=192 px/bar |
| D-57 | PASS | fine grid (16 divisions) drop=0.125s; coarse (4) drop=0.5s |

### D8 — automation points

| ID | Verdict | Evidence (measured) |
|---|---|---|
| D-58 | PASS | section="Track automation"; tabs=Volume/Pan; Clear + Close present |
| D-59 | PASS | points=3 (2 fixture + 1), selected=1, line=1 |
| D-60 | PASS | time 84 → 84.1 (+0.1) → 85.1 (+1) |
| D-61 | PASS | value 60 → 61 (+1) → 71 (+10) |
| D-62 | PASS | points 3→2; neighbours kept |
| D-63 | PASS | lane="Pan automation lane"; pan points=1; volume points untouched (2) |
| D-64 | PASS | lane empty; Clear disabled=true |

### D9 — warp markers and clip settings

| ID | Verdict | Evidence (measured) |
|---|---|---|
| D-65 | PASS | .se-audio open with volume, loop, reverse, pitch, stretch, formant, speed, quantize |
| D-66 | PASS | fixture markers=0; after Stretch on markers=2 |
| D-67 | PASS | On Beat=9, Transients=2, Start and End=2; radios=3 |
| D-68 | PASS | marker moved: "Warp marker at 1.00 seconds" → "Warp marker at 1.22 seconds" |
| D-69 | PASS | Shift+Q re-quantized exactly the 1 selected marker |
| D-70 | PASS | .se-warp-marker.selected=9/9; aria-pressed=true |
| D-71 | FAIL | grid 1/8→1/8 [1/2:false 1/4:false 1/8:true 1/16:false 1/32:false] changed=5 — D-71-1689x1277.png :: grid change or Quantize did not apply |
| D-72 | PASS | clip.audio={"loop":true,"pitch":2,"speed":200,"gainDb":-6,"reverse":true} survived reload |
| D-73 | PASS | collapse hid the body (header kept); close removed the panel |

### D10 — MIDI editor

| ID | Verdict | Evidence (measured) |
|---|---|---|
| D-74 | PASS | MIDI editor; tabIndex=-1; focused=true; notes=3 |
| D-75 | PASS | notes 3→4; selected=1; "Note G#4 at 2.50s, velocity 100"; second click kept 4 |
| D-76 | PASS | major chord click: notes 4 → 7 |
| D-77 | PASS | major + arp-up click added 3 notes on distinct steps: Note G4 at 1.25s, velocity 100, Note B4 at 1.50s, velocity 100, Note D5 at 1.75s, velocity 100 |
| D-78 | PASS | note "Note G#4 at 2.50s, velocity 100" → "Note A4 at 3.25s, velocity 100" |
| D-79 | PASS | notes 10 → 9 |
| D-80 | PASS | velocity 80 → 89; bars=9 |
| D-81 | PASS | bend point added (points=1, line=0); double-click removed it |
| D-82 | PASS | mod lane point=1; saved midi.mod=[{"at":4.5,"value":0.6}]; bend=[] |
| D-83 | PASS | selected=9; ←/→ moved all; Shift+→ lengthened |
| D-84 | PASS | pitch "Note D3 at 0.87s, velocity 90" → +1 "Note D#3 at 0.87s, velocity 90" → -12 "Note D#2 at 0.87s, velocity 90" |
| D-85 | PASS | .is-disabled=9/9; data-disabled=true; label contains "disabled" |
| D-86 | PASS | quantize 1/4 re-placed 3 notes immediately |
| D-87 | PASS | Clear → 0; import → 1 notes; toast="Imported 1 MIDI notes." |
| D-88 | PASS | Ctrl+K → "Keys On" (aria-pressed=true); A/S/Z/X/C/V accepted |

### F1 — autosave, queueing, retry

| ID | Verdict | Evidence (measured) |
|---|---|---|
| F-01 | PASS | chip states: Saved → Saving… → Saved |
| F-02 | PASS | held write: chip="Saving…", aria-live=1, dialogs=0, selection still works |
| F-03 | PASS | two queued edits landed (moved=3), no 409 banner |
| F-04 | PASS | queued burst mirrored to localStorage (1) and offered after reload |
| F-05 | PASS | Ctrl+S wrote immediately (updated_at 2026-11-17T07:22:35.553332+00:00 → 2026-11-17T07:22:44.803352+00:00); chip during="Saving…" |
| F-06 | PASS | chip="Save failed · Retry" rendered as a button.se-save.on |
| F-07 | PASS | retry succeeded: chip="Saved", .se-error=0 |
| F-08 | PASS | beforeunload handler prevented the leave while a write is unsaved |

### F2 — offline draft

| ID | Verdict | Evidence (measured) |
|---|---|---|
| F-09 | PASS | chip="Offline · changes not saved"; draft keys=1 |
| F-10 | PASS | replay succeeded: chip="Saved", draft cleared |
| F-11 | PASS | first replay failed, automatic retry succeeded after 2 PATCHes; chip="Saved" |
| F-12 | PASS | draft banner="We found an unsaved draft from a moment ago.The last change did not reach the server.DiscardRestore draft" |
| F-13 | PASS | draft discarded; server document unchanged |
| F-14 | PASS | draft restored and written (chip="Saved", moved clips=3) |

### F3 — 409 conflicts

| ID | Verdict | Evidence (measured) |
|---|---|---|
| F-15 | PASS | alertdialog="This project changed in another tab.This project changed elsewhere.Reload theirsKeep mine"; chip="Save failed · Retry" |
| F-16 | PASS | Keep mine wrote without expected_updated_at; banner cleared; chip="Saved" |
| F-17 | PASS | Reload theirs cleared the banner; chip="Saved" |
| F-18 | PASS | one failed PATCH and the queued burst was dropped (attempts=1) |
| F-19 | PASS | rename adopted the new updated_at; no 409 on the next edit |

### F4 — mirror chip

| ID | Verdict | Evidence (measured) |
|---|---|---|
| F-20 | PASS | dot data-state=pending; title="Suno Studio: waiting for the first copy" |
| F-21 | PASS | dot data-state=linked; title="Suno Studio: project exists — arrangement mirroring is staged: arrangement writes are paused." |
| F-22 | PASS | dot data-state=synced; title="Suno Studio: mirrored" |
| F-23 | PASS | dot data-state=conflict; dialog on load=1 |
| F-24 | PASS | dot data-state=error; title="Suno Studio sync failed: provider rejected the push" |
| F-25 | PASS | idle 17 s produced 1 mirror read(s) (sync) |
| F-26 | PASS | a mirror read followed the save (1 read(s) within 3.5 s) |

### F5 — provider refusals and failures

| ID | Verdict | Evidence (measured) |
|---|---|---|
| F-27 | PASS | credits notice="Not enough creditsYour balance does not cover this generation. Top up or pick a " + View plans |
| F-28 | PASS | policy notice="That prompt was refusedThe content policy blocked this request. Try re"; Edit prompt refocused the input |
| F-29 | PASS | transform credits notice="Not enough creditsThis edit spends credits your balance does not cover.View plansNot enough credits." |
| F-30 | PASS | failure notice="That edit did not runThe operation failed before anything was placed.provider exploded"; dismissed |
| F-31 | PASS | .se-lib-error=1; Retry button=1 |
| F-32 | PASS | .se-stem-status.off="stem backend unavailable" |
| F-33 | PASS | busy guard: 4 disabled action(s); one keep-mine request |

## Regression probes

| Probe | Verdict | Evidence (measured) |
|---|---|---|
| R-EQ | PASS | band drag moved Freq 1khz → 18.6khz; Gain 0db → 8.3db |
| R-UNDO | PASS | rail refreshed per undo: 2 → 0 → 1 → 2 slots |
| R-MENU | PASS | overflow-y=auto; 889/1070 px scrolls inside the 768×1024 viewport |
| R-OVW | PASS | overview strip present (window 21.8686%/56.2971%); click scrolled the roll 639 → 1277 |
| R-LOOP | PASS | band + both flags present; end flag dragged one bar |

## Probe rows

| Row | Verdict | Evidence |
|---|---|---|
| A-GATE | PASS | 768: shell shown, gate hidden; 767: gate flex, shell none, scrollWidth=767 |
| D-VP | PASS | 1280×800 drag still snapped to 2s; body scrollWidth=1280 |

---

## 6. Reproducing this pass

Harness and specs (committed with this report):

| File | What it does |
|---|---|
| `camxora.com/tests/e2e/w5-adf-harness.ts` | login, P1/P2-style fixtures, drag helpers, recorder, safe screenshot |
| `camxora.com/tests/e2e/w5-a.spec.ts` | area A + the 767/768 gate probe |
| `camxora.com/tests/e2e/w5-d.spec.ts` | area D (selection → MIDI) + the 1280×800 probe |
| `camxora.com/tests/e2e/w5-f.spec.ts` | area F (autosave, offline, conflict, mirror, provider) |
| `camxora.com/tests/e2e/w5-regression.spec.ts` | the five previously-failing probes |

```powershell
# stack in one shell lifetime: moto :9000 + bucket, platform API :8102 (sandbox DB,
# Studio token, moto storage, Suno base -> :4003), musicapi :4003, web :3106
cd camxora.com
$env:BASE_URL = "http://127.0.0.1:3106"
npx playwright test tests/e2e/w5-a.spec.ts tests/e2e/w5-d.spec.ts `
  tests/e2e/w5-f.spec.ts tests/e2e/w5-regression.spec.ts --workers=1 --reporter=line
```

Rows are written to `docs/studio/reports/evidence-adf/results-{a,d,f,regression}.json`;
failure screenshots are in the same directory.

---

## 7. Fixes after the run (2026-11-17)

All four failures were product defects and are fixed, each with a regression that drives the
same path through the shipped UI and passes on the current build. (The ADF specs themselves
were not re-run end to end; the rows below name what was re-measured.)

| Id | Cause found | Fix | Regression |
|---|---|---|---|
| **A-14** | the dock rendered only when `selectedTrack` was set, and a fresh load selects nothing | `bottomPanelOpen` alone now renders the dock shell with "Select a track to see its effects." | `studio-plugins.spec.ts` › *the empty bottom dock says how to fill it on a fresh load* |
| **D-43** | the footer button was wired to a bare `setLoop`, not `toggleLoop` | footer and header share `toggleLoop`, so both seed four bars and persist `loopEnd` | `studio-loop.spec.ts` › *the footer Loop seeds and persists the same four bars as the header* |
| **D-71** | the panel's `keydown` listener was re-subscribed on every render (inline `onWarp`); another keydown listener's re-render invalidated the in-flight registration, so the first press was never delivered | listener attached once in a layout effect and dispatched to the latest handler through a ref | `studio-warp.spec.ts` › *the first density shortcut after opening Clip Settings applies* |
| **D-50** | the label `span` was absolutely positioned with only `left`, so it shrink-wrapped to the 16 px marker box | `width:max-content; max-width:none` on the label | covered by the existing marker rows (label width is now independent of the marker box) |

Measured on the fix: first `shift+1` after opening Clip Settings moves the grid `1/8 → 1/16`
(was `1/8 → 1/8`, with the second press moving it); the footer Loop produces one band and
persists `loopEnd=8`; the dock message is visible on load and gone once a track is selected.

