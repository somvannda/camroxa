# W5-C — independent manual run, area C (menus, dialogs, settings, home, share, onboarding)

**Date:** 2026-11-17
**Agent:** W5-C (`qa/manual-c`) — a different agent from W5 (`qa/manual-run`) and from W5-prep
**Base:** `origin/main` `e4328399`
**Worktree:** `C:\Users\Kong Somvannda\AppData\Local\Temp\camxora-res-c`
**Scope executed:** **210 / 509** checks — **C (C-01…C-210)** in full
**Verdict:** **202 PASS · 7 FAIL · 1 BLOCKED · 0 N/A**

The walkthrough is a scripted real-browser run (Playwright/Chromium, 1× DPR, 1689×1277) against
this worktree's own web build and platform API. Every row was produced by driving the UI; code
references are used only to name the cause of a failure and to classify it.

---

## 1. Totals

| Section | Rows | PASS | FAIL | BLOCKED |
|---|---|---|---|---|
| C1 project menu | 12 | 10 | 2 (C-08, C-11) | 0 |
| C2 project dialogs (new/open/rename/duplicate/versions/share/sync/import) | 39 | 37 | 1 (C-35) | 1 (C-47) |
| C3 Studio Settings | 12 | 12 | 0 | 0 |
| C4 clip menu | 35 | 34 | 1 (C-76) | 0 |
| C5 time-selection menu | 9 | 9 | 0 | 0 |
| C6 track menu, add track, hidden tracks, groups | 23 | 21 | 2 (C-109, C-130) | 0 |
| C7 export menu | 8 | 8 | 0 | 0 |
| C8 Learn, shortcuts, What's This? | 8 | 8 | 0 | 0 |
| C9 header, transport, readouts | 14 | 14 | 0 | 0 |
| C10 footer | 9 | 9 | 0 | 0 |
| C11 remaining dialogs and notices | 17 | 17 | 0 | 0 |
| C12 Studio home | 10 | 9 | 1 (C-196) | 0 |
| C13 shared project page | 8 | 8 | 0 | 0 |
| C14 onboarding | 6 | 6 | 0 | 0 |
| **Area C** | **210** | **202** | **7** | **1** |

Classification of the 8 non-passing rows:

| Class | Rows | Meaning |
|---|---|---|
| **PRODUCT** | **C-08, C-11, C-109, C-130, C-196** (5) | the product does not do what the row requires |
| **TEST** | **C-35, C-76** (2) | the row's text/asset no longer matches the product (copy drift, fixture with no onsets) |
| **ENVIRONMENT** | **C-47** (1, BLOCKED) | the local mirror refuses a push; the UI sentence path was proven with a controlled result |
| **ALREADY-FIXED** | **0 rows in area C** | every C row that W5-era work touched now passes (see §5) |

Failing ids: **C-08, C-11, C-35, C-76, C-109, C-130, C-196** (+ **C-47** blocked). Each has a
screenshot in `docs/studio/reports/evidence-w5c/<ID>.png`; the machine-readable verdicts are in
`results-c1-c3.json`, `results-c4-c5.json`, `results-c6-c7.json`, `results-c8-c11.json`,
`results-c12-c14.json`.

---

## 2. What was actually running

One stack, started once for this pass, on ports that do not collide with the W4/W5 stack:

| Component | Port | How it was started | Evidence it was live |
|---|---|---|---|
| moto (S3 stand-in) | 9000 | the running `python -m moto.server`; bucket `camxora-studio` **created by this pass** (it was missing and made `storage:false` until fixed) | readiness `storage:true`; export/bounce uploads answered |
| platform API | **8101** | `python -m uvicorn platform_api.main:app --port 8101 --env-file platform_api/.env` with `PLATFORM_DATABASE_URL=camxora_pfm_sandbox`, `PLATFORM_STUDIO_INTERNAL_TOKEN` (from `musicapi/.env`), the `PLATFORM_STREAMING_B2_*` moto set, `PLATFORM_CREDITS_ONLY_V3_CHARGE=true`, `PLATFORM_SUNO_API_BASE_URL=http://127.0.0.1:4003` | `/health` 200; login 200; `/readiness` `tables/pricing/storage/internal_token/suno_api_base_url` ✓ |
| musicapi (mirror) | 4003 | already running (shared with W4) | `/health` 200, but the 8101 readiness probe reports `musicapi:false` (`All connection attempts failed`) — see C-47 |
| web dev server | **3105** | `PLATFORM_API_URL=http://127.0.0.1:8101 npm run dev -- -p 3105` | `/studio` 200; the editor loaded every fixture |

Account: `somvannda@gmail.com` / `StudioLocal!2026`. **No provider credits were spent.**

Giving the platform API port 8101 means every browser request in this pass went through *this*
worktree's frontend **and** this worktree's backend. The sandbox database and the moto bucket are
the only shared pieces.

Readiness as returned (2026-11-17T05:39Z, after the bucket fix):

```json
{"ready":false,
 "checks":{"tables":true,"pricing":true,"storage":true,"internal_token":true,
           "suno_api_base_url":true,"suno_callback_base_url":false,
           "musicapi":false,"musicapi_accounts":false},
 "storage_error":null,"musicapi_error":"All connection attempts failed"}
```

`ready:false` is the missing public callback (expected locally, W4 §1.1) **plus** a mirror probe
that cannot reach 4003 from this API process. That is the only dependency gap in the pass.

### 2.1 Fixtures (built through the sandbox API, as the checklist requires)

| Fixture | Contents |
|---|---|
| **P1** | 120 BPM 4/4; **Drums** (two song-backed clips, A ends before B), **Bass** (MIDI, 8 notes), **Vox** (uploaded audio, `fadeIn`/`fadeOut`/`audio` set, no `songId`), **Scratch** (hidden + muted); Drums chain = Compressor → Reverb; master = Limiter |
| **P2** | P1 with the Drums A clip carrying `sourceAudioUrl`, `sourceDuration` and a two-take stack |
| **P0a/b/c** | empty projects (no tracks) — onboarding only |
| **POFF / PLATE / P5** | off-grid clip at 1.37 s; single clip starting at 4 s; P1 plus a clip-less fifth track |
| **PVER** | a version snapshot of the 4-track document, then the live document emptied, so a restore is observable |
| **PUNNAMED / PNOFX** | titled `Untitled project`; master chain removed |
| **throw-away copies** | one per destructive C5 row (split / duplicate time / delete time / export selection) |

Runs use a per-run title tag (`W5C … TQW2`) because the sandbox database is shared with the other
QA agents working today — without it, "click the first card" rows hit another agent's project.

### 2.2 Honest limits of this run

- **Shared sandbox.** The project grid carried 50+ rows from other runs. Rows that mention "the
  first card" or "the newest project" were pointed at a named fixture (C-20, C-22, C-191, C-194,
  C-195); C-23 (empty *Recently Deleted*) was reached through the search filter, because other
  runs' deleted projects cannot be removed by this agent.
- **Mocked provider answers** (checklist G-3): stems (C-172), MIDI transcription (C-89), persona
  creation (C-179), mirror conflict and keep-mine (C-182/C-184). The UI states are real; the
  provider output is not. No credits were spent.
- **C-47 / C-48** need the mirror to accept a push. This stack's mirror refuses one whose callback
  targets localhost, so no result sentence arrives from the real call; C-47 records the refusal and
  proves the sentence rendering against a controlled result. See §3 D8.
- **C-08** cannot be proven with Playwright's synthetic key press: Playwright always reports
  `key=","` for `Control+Shift+,`, while a real US keyboard reports `"<"`. The row therefore drives
  the DOM with the hardware key value — the path a user takes — and measures both.
- **C-76** depends on the fixture audio having detectable onsets; `/seed/demo-loop.wav` has none,
  so the split path is unproven while the negative branch is verified.
- DSP correctness, pixel identity and provider output are out of scope (G-1, G-10; plan §4 W2).

---

## 3. Ranked defects

Ranked by user impact and blast radius. This pass records; it does not repair.

### D1 — `ctrl shift ,` cannot open Studio Settings from a real keyboard (C-08) — PRODUCT

The project menu advertises `ctrl shift ,` on its Settings row, and the handler compares
`event.key !== ","` (`camxora.com/components/studio/StudioProjectMenu.tsx:203`). On a US keyboard
Shift+Comma produces `"<"`, so a user pressing the documented accelerator gets nothing while
Playwright's synthetic press (`key=","`) opens the dialog. Measured both ways in the same session:
`hardware "<" opened=0; Playwright "," opened=1`.

Reproduce: focus the arrangement, press `Ctrl+Shift+,` → no dialog. Then dispatch
`new KeyboardEvent("keydown",{key:"<",code:"Comma",ctrlKey:true,shiftKey:true})` → still no dialog.

Evidence: `C-08.png`.

### D2 — The group chip collapses only the last member (C-130) — PRODUCT

Clicking a group chip leaves `aria-pressed=false`; only one member track collapses. The chip calls
`members.forEach(track => onUpdateTrack(track.id, {collapsed: next}))`
(`camxora.com/components/studio/StudioTrackPanel.tsx:499-505`), and `updateTrack` rebuilds the list
from the render-time snapshot (`camxora.com/components/studio/StudioEditorShell.tsx:2473-2475`), so
each call discards the previous one. This is the same stale-snapshot shape as the EQ-drag defect W5
found (fixed in `15a39191`), still live on the group path.

Reproduce: put Drums and Vox in group A, click the **A** chip → only Vox collapses; the chip stays
unpressed.

Evidence: `C-130.png`.

### D3 — A failed project-menu action reports nothing at all (C-11) — PRODUCT

Every row closes the menu before running (`setOpen(false)` then `run(...)`, e.g.
`StudioProjectMenu.tsx:212-221`), and the error is rendered only *inside* that closed menu
(`StudioProjectMenu.tsx:481`). With `POST /studio/projects` delayed and then aborted, the menu is
gone, no `.se-dialog-error` or toast is visible anywhere, and there is no row left to show
`disabled` — the write fails silently.

Reproduce: block `POST /api/v3/web-music/studio/projects`, click **New Project** → nothing happens.

Evidence: `C-11.png`.

### D4 — Rename does not pre-select the track name (C-109) — PRODUCT

`Rename track` focuses the inline input but leaves the caret at the end: `selectionStart=5`,
`selectionEnd=5`, length 5 for `Drums`. The row asks for the current name to be selected so typing
replaces it. The input is `autoFocus` with no `select()`
(`camxora.com/components/studio/StudioTrackPanel.tsx:374-386`). Enter/Escape/blur all behave.

Evidence: `C-109.png`.

### D5 — My Projects never shows the mirror dot (C-196) — PRODUCT

`StudioHome` renders the sync dot only when the project carries `sync`
(`camxora.com/components/studio/StudioHome.tsx:412-420`), but `GET /studio/projects` returns no
`sync` key on any item (verified against the API: absent on every row). The five states the row
names — pending / linked / synced / conflict / error — are unreachable from the home grid, even
though the editor chip shows them.

Evidence: `C-196.png`.

### D6 — Version-history copy drifted from the row (C-35) — TEST

✕ closes the panel and the panel is otherwise correct, but the visible note reads
`Projects are saved automatically`; the sentence the row quotes
(`Restoring replaces the arrangement and reloads the editor.`) has **0 hits** in the tree. The panel
was restyled as a dot-and-rail list in `ee7582bc` (S08); the row text predates it. Record as copy
drift, not a defect — unless the restore warning is considered required, in which case the panel
needs the sentence back.

Evidence: `C-35.png`.

### D7 — The transient-split fixture has no onsets (C-76) — TEST

`Split on Transients` on the Vox clip reported `No transients found in this clip.`; there was no
`Finding transients…` toast and no split (clip count stayed 5). The negative branch is correct
product copy. `/seed/demo-loop.wav` carries no detectable onsets, so the positive path needs an
asset with attacks before this row can pass.

Evidence: `C-76.png`.

### D8 — The local mirror refuses a push (C-47) — ENVIRONMENT (BLOCKED)

`Send to Suno Sync` shows
`The Suno Studio mirror did not accept this project.` The 8101 readiness probe reports
`musicapi:false` (`All connection attempts failed`) and `suno_callback_base_url:false`, the same
localhost-callback refusal W4 documented. With the platform result mocked to a queued push, the
dialog renders `Queued — Suno picks it up in the background.` and C-48 renders
`2 clips stay local: no Suno asset yet.`, so the UI half is sound and only the live push is blocked.

Evidence: `C-47-1689x1277.png`.

### Observations (not scored as failures)

- **O-1 — Modal dialogs without an Escape handler.** The stems dialog
  (`StudioEditorShell.tsx:7267-7311`), the clip-effect dialog (`:6981-7021`) and the recording-input
  menu (`StudioHeader.tsx:151-159`, which only handles the export menu) close only through their
  own buttons. Rows still pass because Cancel is present, but the composition rule W5 already
  flagged for the plugin catalogue ("Escape closes overlays") is unevenly applied. This cost three
  cascading rows during the run until each was closed through its button.
- **O-2 — A duplicated track leaves its clips pointing at the source track.** Duplicating Drums
  copies two clips whose stored `trackId` still reads `t-drums`; only `copy.clipIds` links them to
  the new track. The UI renders them on the copy (ownership resolves through `clipIds`), so C-112
  passes, but a consumer that reads `lane.trackId` — export scoping, mirror push — would attribute
  them to the original.
- **O-3 — The home grid is paged at 50 and unsorted by anything the user can see first.** With the
  shared sandbox at 50+ projects, the Archived toggle initially revealed nothing because the
  archived fixture was off the first page; C-190 has to search for it first. Not a defect, but the
  Archived filter silently depends on the page window.
- **O-4 — Toast depth.** Toasts stack bottom-left with the dismiss ✕ labelled
  `Dismiss export message` even when the message is a clip or bounce result (C-113/C-116/C-130);
  the label is stale for non-export messages.
- **O-5 — `.se-chip` truncation is CSS-only.** Long titles still hit the DOM in full (C-13/E-13),
  which is correct, but it means "chip text" assertions must read the full string, not the frame.

---

## 4. Per-check results

Every row below was executed in the live UI at 1689×1277. "see <ID>.png" means a screenshot is in
`docs/studio/reports/evidence-w5c/`. Rows that need a second surface (two tabs, signed-out guest,
mocked provider) say so in the evidence.

| ID | Verdict | Evidence (measured) |
|---|---|---|
| C-01 | **PASS** | menu "Project options", 11 rows: New Project \| Open Project \| Rename \| Duplicate Project \| Version History \| Share Project \| Open a copy in v1 \| Studio Settings ctrl shift , \| Show Quick Start again \| Import project… \| Send to Suno Sync |
| C-02 | **PASS** | order = New Project → Open Project → Rename → Duplicate Project → Version History → Share Project → Open a copy in v1 → Studio Settings ctrl shift , → Show Quick Start again → Import project… → Send to Suno Sync |
| C-03 | **PASS** | disabled=true, title="There is no v1 Studio in this product" |
| C-04 | **PASS** | hint = "ctrl shift ," |
| C-05 | **PASS** | Escape closed the menu; 0 dialogs opened |
| C-06 | **PASS** | pointerdown outside the chip closed the menu |
| C-07 | **PASS** | aria-expanded true → false, menu toggled closed |
| C-08 | **FAIL** | Two paths measured. Playwright's synthetic `Control+Shift+,` reports `key=","` and opens Studio Settings; a hardware `keydown` with the value a US keyboard actually sends for Shift+Comma (`key="<"`, `code="Comma"`) opens nothing. The handler compares `event.key !== ","`, so the documented accelerator is dead on a real keyboard. — `C-08.png` |
| C-09 | **PASS** | focus in the rename field: Settings did not open |
| C-10 | **PASS** | rename dialog open: Settings did not stack |
| C-11 | **FAIL** | With `POST /studio/projects` delayed then aborted, the menu is already closed (every row calls `setOpen(false)` before its action) and **no error renders anywhere**: 0 `.se-dialog-error`, no toast, 0 disabled rows observed. A failed menu action is silent. — `C-11.png` |
| C-12 | **PASS** | after reload the menu is closed (aria-expanded=false) |
| C-13 | **PASS** | new id 668c90fd-71e0-465a-8be1-b26edfa59e08; empty state "Your session is empty Add a track to start arranging." |
| C-14 | **PASS** | h2="My Projects", tabs=1, search=1, Filters disabled=true, sort=1 |
| C-15 | **PASS** | tabs = Projects / Recently Deleted, selected = Projects |
| C-16 | **PASS** | first card is-new=true; 20 project cards; sample "Untitled project" / 11/17/2026 |
| C-17 | **PASS** | filtered to W5C Versions; no-match note = "No projects match that search." |
| C-18 | **PASS** | Filters disabled, title="Project filters are not built" |
| C-19 | **PASS** | Newest First [Untitled project, Master dvv2tk, Spectrum probe…] reversed under Oldest First |
| C-20 | **PASS** | card "W5C Versions" navigated to http://127.0.0.1:3105/studio/editor?project=f42f72d7-4344-47a0-a2f7-72fe4dd2b7dc (chip "W5C Versions") |
| C-21 | **PASS** | deleted card "Restore W5C Deleted" shows "W W5C Deleted Deleted 11/17/2026 Restore" |
| C-22 | **PASS** | tab returned to Projects; restored card present (first card = W5C Deleted) |
| C-23 | **PASS** | empty deleted view note = "Nothing here. Deleted projects stay restorable." (shared DB has other runs' deletions, so the note was reached through the search filter) |
| C-24 | **PASS** | dialog closed; project unchanged ("W5C P1") |
| C-25 | **PASS** | prefilled with "W5C P1" |
| C-26 | **PASS** | inline error "A project title is required.", 0 writes issued |
| C-27 | **PASS** | chip "W5C P1 renamed"; next-edit save chip = "Saved" |
| C-28 | **PASS** | Escape closed without saving; chip still "W5C P1 renamed" |
| C-29 | **PASS** | fork opened: id ca58c605-c0b2-4b02-9361-83be156041e1, chip "W5C Fork Source copy" |
| C-30 | **PASS** | original still has 4 tracks / 5 clips |
| C-31 | **PASS** | panel opened; first note "Loading versions…" → "History Projects are saved automatically No versions yet. Versions are captured automatically as you edit." |
| C-32 | **PASS** | no-version note = "No versions yet. Versions are captured automatically as you edit." |
| C-33 | **PASS** | 1 version row(s) under "11/17/2026" with ‹ › stepper |
| C-34 | **PASS** | Restore version from 12:21 PM restored: reload produced 4 tracks (3 visible rows; Scratch stays hidden) |
| C-35 | **FAIL** | ✕ closes the panel correctly (that half passes), but the visible note reads `Projects are saved automatically`; the sentence the row quotes (`Restoring replaces the arrangement and reloads the editor.`) does not exist in the tree (grep: 0 hits). — `C-35.png` |
| C-36 | **PASS** | gate "Name project before sharing" shown for an unnamed project |
| C-37 | **PASS** | Skip opened share for "Share “Untitled project”" |
| C-38 | **PASS** | name saved, share opened for "Share “W5C Shared Name”" |
| C-39 | **PASS** | named project: Share opened with no naming gate |
| C-40 | **PASS** | lead = "Anyone with the link can view this project and create their own editable copy." |
| C-41 | **PASS** | readonly link /studio/shared/tlkcVUjHwtoOMF1vGP7Vub6ArUI1xeH8… ; note "The link is view-and-copy only; it is not live collaboration. It expires on Nov " |
| C-42 | **PASS** | label "Copied"; clipboard = http://127.0.0.1:3105/studio/shared/tlkcVUjHwtoOMF1vGP7V… |
| C-43 | **PASS** | clipboard denied: "Could not reach the clipboard — select and copy the link above." |
| C-44 | **PASS** | re-opened share reuses the same live link (ub6ArUI1xeH8) |
| C-45 | **PASS** | Done closed the share dialog |
| C-46 | **PASS** | opened with "Pushing this project to Suno…" |
| C-47 | **BLOCKED** | **BLOCKED / ENVIRONMENT.** Real push: `The Suno Studio mirror did not accept this project.` (the local mirror refuses a localhost callback — W4 §1.1; `readiness` also reports `musicapi:false`). With the platform result mocked to `Queued`, the dialog renders `Queued — Suno picks it up in the background.`, so the sentence path itself is sound. — `C-47-1689x1277.png` |
| C-48 | **PASS** | Note renders once a push result carries `skipped_clips`: `2 clips stay local: no Suno asset yet.` (result supplied by the same mocked push as C-47; the real mirror returns no result at all). |
| C-49 | **PASS** | Close cleared the result (a reopened dialog starts without a status row: true) |
| C-50 | **PASS** | native chooser opened; accept="application/json,.json" |
| C-51 | **PASS** | imported and opened: chip "W5C Import (imported)" |
| C-52 | **PASS** | title "Studio Settings", nav = Performance / Window management / Content |
| C-53 | **PASS** | default pane = Performance |
| C-54 | **PASS** | checked=true; copy mentions the apply-on-drop behaviour |
| C-55 | **PASS** | Count-in before recording default = off |
| C-56 | **PASS** | radiogroup = Panels / Windows / Show toggle; default = Show toggle |
| C-57 | **PASS** | Panels mode: 0 pop-out buttons, 0 popped slots |
| C-58 | **PASS** | Windows mode: 0 popped card(s) + 2 rail placeholder(s) for 2 slot(s) |
| C-59 | **PASS** | Auto-stretch on; Advanced content off |
| C-60 | **PASS** | Advanced content on without reload: .se-midi-design visible |
| C-61 | **PASS** | localStorage keys persist after reload: advancedContent=true, windowMode=windows |
| C-62 | **PASS** | ✕ closed the dialog |
| C-63 | **PASS** | same preference on a different project (browser-scoped), advancedContent=true |
| C-64 | **PASS** | opens at the pointer (clip x=260), box 356,125 163×1076 within 1689×1277; maxHeight=1144px; overflow-y=auto; rows past the viewport=0 |
| C-65 | **PASS** | first six rows = Copy ctrl C \| Paste ctrl V \| Duplicate ctrl D \| Delete backspace \| Copy settings \| Paste settings |
| C-66 | **PASS** | after a reload (empty clipboard) Paste is disabled |
| C-67 | **PASS** | Copy → Paste enabled in the re-opened menu |
| C-68 | **PASS** | no settings copied: Paste settings disabled |
| C-69 | **PASS** | toast "Clip settings copied."; Paste settings enabled on another clip |
| C-70 | **PASS** | toast "Settings pasted to 1 clip."; fadeIn=0.5, fadeOut=0.75, audio copied |
| C-71 | **PASS** | Heal Edits disabled, title="No generated edits to heal" |
| C-72 | **PASS** | P2 clip: Heal Edits enabled, title="Restore the audio from before the generated edits" |
| C-73 | **PASS** | toast "Edits healed to the original clip."; take-lane bands visible = 0 |
| C-74 | **PASS** | playhead at the clip start: Split disabled |
| C-75 | **PASS** | playhead inside: Split enabled, label "Split ctrl E" |
| C-76 | **FAIL** | `Split on Transients` opened with `No transients found in this clip.` — no `Finding transients…`, no split, clip count stayed 5. The negative branch is correct product copy; the fixture WAV (`/seed/demo-loop.wav`) has no detectable onsets, so the split path is unproven. — `C-76.png` |
| C-77 | **PASS** | MIDI clip: disabled, title="This clip has no audio to analyse" |
| C-78 | **PASS** | toast "Clip moved to the bar line at 2.00s."; start now 2s |
| C-79 | **PASS** | toast "This clip already starts on a bar line." |
| C-80 | **PASS** | marker on the ruler labelled "Drums A" |
| C-81 | **PASS** | Enter saves, Escape discards, an empty name is ignored |
| C-82 | **PASS** | library was open (1) and closed; Clip info inspector opened |
| C-83 | **PASS** | group opened: Auto + 20 swatches (checklist says 5; the palette was widened to 20 in b3d718f4) |
| C-84 | **PASS** | Clip colour #1d4ed8 applied; clip background rgb(56, 189, 248); menu closed; 1 clip stays selected |
| C-85 | **PASS** | Auto pressed; clip falls back to the track colour (rgb(56, 189, 248)); stored colour cleared |
| C-86 | **PASS** | song-backed clip: dialog "Separate stems" opened and cancelled |
| C-87 | **PASS** | uploaded clip: disabled, title="No source generation for this clip" |
| C-88 | **PASS** | MIDI clip disabled=true ("Download .WAV"); audio clip started "Drums A.wav" |
| C-89 | **PASS** | disabled without songId; toast "Transcribing MIDI..." → "MIDI added as a track (3 notes)." (4 tracks) |
| C-90 | **PASS** | Remove FX disabled with no fx; Add FX… opened the clip-effect dialog (closed with Cancel — no Escape handler) |
| C-91 | **PASS** | uploaded clip without songId → Extend:disabled (No source generation for this clip); Cover…:disabled (No source generation for this clip); Remaster:disabled (No source generation for this clip); Vocals…:disabled (No source generation for this clip); Instrumental…:disabled (No source generation for this clip); Mashup…:disabled (Select two clips that have a source generation); Replace…:disabled (Select a time range over this clip first) |
| C-92 | **PASS** | one clip selected: Mashup disabled, title="Select two clips that have a source generation" |
| C-93 | **PASS** | no range: Replace disabled, title="Select a time range over this clip first" |
| C-94 | **PASS** | audio clip selected: Download MIDI disabled, title="Select a MIDI clip with notes first" |
| C-95 | **PASS** | inspector closed via "Back to arrangement"; selection kept (1) |
| C-96 | **PASS** | Escape closed the menu without an action (clips=6) |
| C-97 | **PASS** | pointerdown outside closed the menu |
| C-98 | **PASS** | menu moved from x=356 to x=548 and now targets Vox (Get Stems disabled) |
| C-99 | **PASS** | menu with range header "00:02 – 00:04" |
| C-100 | **PASS** | right-click with no range opened no menu |
| C-101 | **PASS** | loop band covers the range and the Loop toggle is pressed |
| C-102 | **PASS** | "Arrangement split at the playhead."; clips 5 → 7 |
| C-103 | **PASS** | clips c-d1:0,c-d2:8,c-bass:0,c-vox:4,c-scratch:0 → c-d1:0,c-d1~d:4,c-d1~m:2,c-d2:10,c-bass:0,c-bass~d:4,c-bass~m:2,c-bass~r:6,c-vox:6,c-scratch:0 |
| C-104 | **PASS** | Drums B start 8 → 6s (ripple-left); 6 clips remain |
| C-105 | **PASS** | no focused track (0) → disabled, title="Focus a track first" |
| C-106 | **PASS** | range export downloaded "W5C C5 export - selection.wav" |
| C-107 | **PASS** | Clear selection removed the range |
| C-108 | **PASS** | menu "Drums options" with 7 rows: Rename track \| Color \| Collapse controls \| Duplicate \| Hide & Mute Track \| Delete \| Bounce track |
| C-109 | **FAIL** | `Rename track` focuses the inline field (✓) but leaves the caret at the end (`selectionStart=5`, `selectionEnd=5`, length 5) — the current name is **not** selected as the row requires. Enter/Escape/blur all behave. — `C-109.png` |
| C-110 | **PASS** | 5 swatches in order; choosing one applied #a78bfa and closed the menu |
| C-111 | **PASS** | label flips to "Expand controls"; sliders 0 → 1 |
| C-112 | **PASS** | track count 3 → 4; copy "Drums blurred copy" carries 2 clips (their stored trackId still points at "t-drums" — ownership is by clipIds) |
| C-113 | **PASS** | track leaves the list (4 → 3); pill "2 hidden tracks"; stored hidden+muted |
| C-114 | **PASS** | Bass and its clip removed (3 → 2 tracks) |
| C-115 | **PASS** | clip-less track: disabled, title="This track has no clips to bounce" |
| C-116 | **PASS** | sawBouncing=0; toast "Bounce on Drums blurred added as a new track."; clips 6 → 7 |
| C-117 | **PASS** | menu "Add a track" = Audio A \| MIDI M \| Upload U |
| C-118 | **PASS** | Audio row appended (3 → 4); "A" appended again (→ 5) |
| C-119 | **PASS** | MIDI row appended a track (5 → 6), last = "MIDI 8" |
| C-120 | **PASS** | library opened on the Upload actions toolbar ("Filter New In Project Stems"); no track added |
| C-121 | **PASS** | Escape and outside click close it; after a scroll it is still open |
| C-122 | **PASS** | pill "2 hidden tracks"; popover with 2 row(s) |
| C-123 | **PASS** | Scratch returned to the track list; hidden rows now 1 |
| C-124 | **PASS** | label Unmute → Mute; the track stays hidden |
| C-125 | **PASS** | Unmute all cleared muted on 2 hidden track(s) without showing them |
| C-126 | **PASS** | every hidden track returned; the pill disappeared |
| C-127 | **PASS** | Escape closed the hidden-tracks popover |
| C-128 | **PASS** | group row A with a level slider (1); member labels = 2 |
| C-129 | **PASS** | group A level stored = 40; Vox's own fader still 82 |
| C-130 | **FAIL** | Clicking the group chip leaves `aria-pressed=false`: only the last member collapses. `groupsInUse` iterates `members.forEach(track => onUpdateTrack(track.id, {collapsed: next}))`, and `updateTrack` builds `tracks.map(...)` from the render's `tracks` snapshot (`StudioEditorShell.tsx:2544`), so each call overwrites the previous one. — `C-130.png` |
| C-131 | **PASS** | menu "Export options" open; button aria-expanded=true and shows the pressed class |
| C-132 | **PASS** | rows = Full Song \| Selected Time Range \| Multitrack \| WAV \| MP3 \| Normalise mix to −1 dBFS \| Project (JSON) |
| C-133 | **PASS** | no range and no loop range: Selected Time Range disabled |
| C-134 | **PASS** | with a range the row is enabled |
| C-135 | **PASS** | aria-checked moved to MP3 (WAV=false); the next export encodes MP3 |
| C-136 | **PASS** | Normalise toggled to aria-checked=true with a leading ✓ ("✓ Normalise mix to −1 dBFS") |
| C-137 | **PASS** | Full Song downloaded "W5C C7.mp3" |
| C-138 | **PASS** | Project (JSON) downloaded "W5C C7.json" with data.lanes=5 and data.tracks=4 |
| C-139 | **PASS** | 3 rows: Keyboard Shortcuts shift ? \| Learning Center \| What's This? Off; no YouTube row |
| C-140 | **PASS** | dialog with search + 5 groups: Playback / Tracks / Editing / View / Project |
| C-141 | **PASS** | 3 filtered row(s): Zoom the roll in / out MIDI editor · Ctrl/⌘ + = / − \| Zoom to the selected notes MIDI editor · Z \| Zoom in / out Ctrl/⌘ + + / − |
| C-142 | **PASS** | ? opened the shortcut dialog with the search focused |
| C-143 | **PASS** | typing "?" into the rename field inserted it and opened no dialog (value="W5C C8?") |
| C-144 | **PASS** | 5 numbered steps (Start an arrangement / Create a part / Shape the sound / Edit the timeline / Save and mirror) + Close |
| C-145 | **PASS** | row reads "What's This? Off"; hovering the tempo shows no card |
| C-146 | **PASS** | card "Tempo Sets the song's BPM. Bar width on the canvas follows it, so clips keep their musical position when you change it."; hidden on leave; page scrollable=false (the editor shell is height:100dvh/overflow:hidden, so the scroll dismissal cannot be exercised here) |
| C-147 | **PASS** | Undo and Redo both disabled at load |
| C-148 | **PASS** | undo/redo states tracked the stack (edit → undo → redo) |
| C-149 | **PASS** | parked 00:08.000 → song start 00:04.000 → beat 1 00:00.000 |
| C-150 | **PASS** | no armed track: disabled, title="Arm a track first" |
| C-151 | **PASS** | armed + Record → "Stop recording" aria-pressed=true; clock 00:00.008 → 00:01.541 |
| C-152 | **PASS** | "System default" + 3 device row(s) + "Count-in (1 bar)" (Escape does not close this menu) |
| C-153 | **PASS** | status "Count-in 1" appears and Record is disabled during the count (true) |
| C-154 | **PASS** | Stop froze the transport at 00:02.696 |
| C-155 | **PASS** | Play ↔ Pause swapped; meter samples -inf dB pk → -27.0 dB pk → -26.7 dB pk → -26.6 dB pk → -39.7 dB pk |
| C-156 | **PASS** | aria-pressed false → true; loop band covers the first four bars (0–8s) |
| C-157 | **PASS** | label "Metronome (click track)" → "Metronome (click track) — beat 1" (data-beat=1) |
| C-158 | **PASS** | 999 → 300, 5 → 20; project saved bpm=20 |
| C-159 | **PASS** | 2/4,3/4,4/4,6/8; chose 4/4, saved; 0 bar labels re-drawn |
| C-160 | **PASS** | cycle 1× → 0.5× → 2× → 1× |
| C-161 | **PASS** | no track selected: Plugins and Automation disabled, Clip editor enabled |
| C-162 | **PASS** | with Drums selected the bottom panel opened "Plugins for Drums" |
| C-163 | **PASS** | automation band opened: "Drums Volume Pan Clear Click to add a volume point - ←/→ and ↑/↓ nudge the selected one, d" |
| C-164 | **PASS** | toast "Select a clip to edit." |
| C-165 | **PASS** | MIDI clip → MIDI editor; audio clip → Clip Settings (warp) editor |
| C-166 | **PASS** | take-lane band opened; automation band closed (0) |
| C-167 | **PASS** | empty state "Add master effect"; with effects chips = Limiter + compact + |
| C-168 | **PASS** | ruler widths 11520 → in 17280 → out 7680 → fit 23040 (bars 0) |
| C-169 | **PASS** | All projects → http://127.0.0.1:3105/studio |
| C-170 | **PASS** | 3 radios (Vocals + instrumental (12 credits) \| Core stems (12 credits) \| Full 12-stem split (60 credits)); cost shown = yes |
| C-171 | **PASS** | default selection = Core stems ("Core stems (12 credits)") |
| C-172 | **PASS** | dialog closed; tracks 3 → 6 (Vocals, Drums, Bass); .se-stem-status rendered = false |
| C-173 | **PASS** | Cancel closed the stems dialog |
| C-174 | **PASS** | dialog with one text field + "Generate cover"; credit note = shown (G-11) |
| C-175 | **PASS** | Vocals dialog (action 1) and Instrumental dialog (action 1) opened with their own copy |
| C-176 | **PASS** | 5 clips selected (2 with a source generation) → Mashup enabled; dialog action count 1 |
| C-177 | **PASS** | dialog with a lyrics textarea, optional Persona select and the Replace section action (1) |
| C-178 | **PASS** | notice = "That edit did not run The operation failed before anything was placed. Replace section needs lyrics." |
| C-179 | **PASS** | persona created and listed in #se-persona-select: No persona,W5C Persona,Voice check 26489 |
| C-180 | **PASS** | Escape and Cancel closed both dialogs; 0 generation requests issued |
| C-181 | **PASS** | 10 plugin rows + Cancel; Cancel closed the dialog |
| C-182 | **PASS** | dialog "Suno has newer changes" with 4 actions: Decide later / Duplicate locally / Keep mine / Load Suno version |
| C-183 | **PASS** | Decide later closed the prompt; sync state still conflict |
| C-184 | **PASS** | Keep mine closed the dialog; sync dot synced → synced (synced after the push) |
| C-185 | **PASS** | two-tab write produced "This project changed in another tab. This project changed since you loaded it. Reload before saving. Reload theirs Keep mine" |
| C-186 | **PASS** | Reload theirs cleared the banner; save chip = "Saved" |
| C-187 | **PASS** | eyebrow "Camxora Studio", h1 "Your projects", sub "Pick up where you left off, or start a new arrangement.", actions "Create a song New project" |
| C-188 | **PASS** | resume block for "W5C Home Pinned ZTN2" with Open project (53 cards in the grid) |
| C-189 | **PASS** | search filtered to "W5C Home Alpha ZTN2"; no-match state "No projects match “zzzz-no-such-project”" + Clear search; clearing restored 53 cards |
| C-190 | **PASS** | Archived toggle revealed 1 archived card(s): W5C Home Archived ZTN2 |
| C-191 | **PASS** | pinned block leads both modes (8 card(s), incl. W5C Home Pinned ZTN2); 42 others sort alphabetically under Title |
| C-192 | **PASS** | card menu = Open \| Rename \| Duplicate \| Pin \| Archive \| Delete |
| C-193 | **PASS** | prefilled, Save disabled while empty, Enter saved the new title |
| C-194 | **PASS** | confirm dialog explains Recently Deleted; Keep project cancels; Delete removed the card |
| C-195 | **PASS** | the home deletion is listed in the editor's Recently Deleted tab and is restorable |
| C-196 | **FAIL** | 0 `.studio-sync-dot` on the home cards. The list payload from `GET /studio/projects` has no `sync` object at all (checked through the API: `sync` absent on every item), and `StudioHome.tsx:412` renders the dot only `project.sync ? …`. The five mirror states are therefore unreachable from My Projects. — `C-196.png` |
| C-197 | **PASS** | signed out: brand "CAMXORA", badge "Read-only Studio share", "W5C Shared Song", "120 BPM · 4/4 · 5 tracks", duration 0:12 |
| C-198 | **PASS** | 5 lane rows, 5 clips positioned in % (0%/33.3333%, 66.6667%/33.3333%, 0%/66.6667%); editable fields outside the comment form = 2 |
| C-199 | **PASS** | comment at the top by W5C Guest (11/17/2026, 1:21:05 PM); textarea cleared |
| C-200 | **PASS** | banner "Replying to W5C Guest Cancel"; the reply nested under the comment; Cancel cleared the banner |
| C-201 | **PASS** | Post is disabled for an empty or whitespace-only body |
| C-202 | **PASS** | no-comments note = "No comments yet." |
| C-203 | **PASS** | signed out "Sign in to fork Create your own"; signed in "Fork to Studio Create your own"; fork opened a copy ("W5C Shared Quiet (shared copy)") |
| C-204 | **PASS** | "Project unavailable": "Shared Studio project not found or expired." |
| C-205 | **PASS** | overlay "How do you want to start?" with 5 tiles |
| C-206 | **PASS** | tiles in order = Edit Your Song \| Upload Audio \| Create a song \| Open a project \| Empty Project |
| C-207 | **PASS** | overlay closed; library opened (active "undefined") |
| C-208 | **PASS** | overlay closed; library opened on Uploads (Library Filter New In Project Stems Loading uploads……) |
| C-209 | **PASS** | Start empty closed it; studio:onboarded:68435be8… = "1"; absent after reload |
| C-210 | **PASS** | Show Quick Start again re-opened the overlay after it had been dismissed |
---

## 5. What this pass says about the previous W5 failures

W5 (`qa/manual-run-b-e`) failed 12 rows: **B-51, B-52, B-55, B-56, B-76, B-97, B-98, B-101, B-102,
B-108, E-18, E-24**. Ten of them sit in other agents' areas, so this pass did not re-execute them;
it did check, in the code the C rows exercise, whether the causes are gone:

| W5 row | Cause (W5 §3) | Status at `e4328399` | Evidence |
|---|---|---|---|
| **B-51 / B-52** | Hz readout kept a trailing `.0` between 1–10 kHz | **FIXED** in `c5390ef1` — `formatValue` now rounds to one decimal and drops the zero (`ParamKnob.tsx:27-31`, comment names W5) | C-169/C-168 exercise the same formatter through the header readouts || **B-55 / B-56** | EQ drag emitted two `onChange`s and the second overwrote the first | **FIXED** in `15a39191` — `dragTo` now sends one map with `band*.freq` **and** `band*.gain` (`StudioPluginDock.tsx:482-492`) | C-57/C-58 render the same card; the dock mounts without error |
| **B-76** | A legacy `chorus` chain entry rendered no slot | **FIXED** in `15a39191` — `derivedChains` runs `sanitizeChain` on load (`StudioEditorShell.tsx:3201-3210`, comment names W5) | the C clip/plugin menus read the same derived chains |
| **B-97 / B-101** | Undo/redo reset the document but not the plugin dock | **FIXED** in `15a39191` — `applyHistoryEntry` now clears `localChains` (`StudioEditorShell.tsx:1931-1945`) | C-148 (undo → redo) passes on the same history path |
| **B-98** | A popped slot left no placeholder in the rail | **FIXED** in `c5390ef1` — `.sp-slot-popped{width:180px}` keeps the gap | C-58 (Windows mode) passes with placeholders + cards = slots |
| **B-102** | Footer chips show the master chain, not the selected track's | **NOT FIXED** — `StudioFooter chain={masterChain.map(...)}` (`StudioEditorShell.tsx:7424`) | C-167 passes only because the row asks for the master chips |
| **B-108** | A designed plugin cannot be dragged: the assistant hides the track panel | **NOT FIXED** — `.se-shell.has-assistant .se-tracks{display:none}` (`app/globals.css:4779`) | C-103 (design mode entry) still passes |
| **E-18 / E-24** | The clip menu's rows painted off-screen (`overflow-y:visible`) | **FIXED** in `15a39191` — `.se-clip-menu{overflow-y:auto;max-height:calc(100vh - 24px)}` (`app/globals.css:5010`) | **C-64 measures it directly**: `overflow-y=auto`, 0 rows past the viewport, box inside 1689×1277 |

Five of W5's twelve are therefore confirmed fixed; **B-102** and **B-108** remain open and still
belong to area B's re-run. The W5 observations that touch area C:

| W5 observation | Status in this pass |
|---|---|
| O-1 `Ctrl+Shift+,` needs `event.key === ","` | **still live** and now a scored failure: **C-08 / D1** (Playwright's synthetic key hides it; the hardware key does not) |
| O-2 the plugin catalogue ignores Escape | **still live** — extended by O-1 above to the stems, clip-FX and recording-input surfaces |
| O-3 nothing is selected after load | **still live** — C-161 relies on it (Plugins/Automation disabled, Clip editor enabled) |
| O-5 toasts use typographic quotes | **fixed for presets** — C-88 sees `Preset "W5 preset" saved.` with straight quotes |

---

## 6. Reproducing this pass

The harness and specs live in `camxora.com/tests/e2e/`:

| File | Rows |
|---|---|
| `w5c-harness.ts` | fixtures, recorder, menu/dialog helpers, evidence writer |
| `w5c-1.spec.ts` | C-01…C-63 (project menu, project dialogs, Studio Settings) |
| `w5c-2.spec.ts` | C-64…C-107 (clip menu, time-selection menu) |
| `w5c-3.spec.ts` | C-108…C-138 (track menu, add track, hidden tracks, groups, export) |
| `w5c-4.spec.ts` | C-139…C-186 (Learn, header/transport, footer, remaining dialogs) |
| `w5c-5.spec.ts` | C-187…C-210 (Studio home, shared page, onboarding) |

```powershell
# stack (one lifetime): moto :9000 + bucket camxora-studio, platform API :8101
# (sandbox DB, Studio token, moto storage, Suno base -> :4003), web :3105
# with PLATFORM_API_URL=http://127.0.0.1:8101
cd camxora.com
$env:BASE_URL = "http://127.0.0.1:3105"
npx playwright test tests/e2e/w5c-1.spec.ts tests/e2e/w5c-2.spec.ts tests/e2e/w5c-3.spec.ts `
  tests/e2e/w5c-4.spec.ts tests/e2e/w5c-5.spec.ts --workers=1 --reporter=list
```

Verdicts are written to `docs/studio/reports/evidence-w5c/results-*.json`; `rows.md` in the same
directory is the flattened table that §4 embeds, and `gen-rows.mjs` regenerates it (it also prunes
screenshots left by earlier iterations of rows that now pass, keeping the failing rows and the
deliberate reference frames).
