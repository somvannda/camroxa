# Capture run (W3) — the 13 STATE re-shoots and the 14 unjudged screens

**Date:** 2026-11-17
**Workstream:** W3 of `docs/studio/RESIDUAL_VERIFICATION_PLAN.md`
**Branch:** `qa/capture-run` (base `origin/main` `0551b6fc`)
**Executes:** `docs/studio/reports/2026-11-17-capture-plan.md` §2–§7
**Script:** `camxora.com/scripts/capture-screens.mjs` (committed by W3-prep; three fixes below)

**Headline:** 25 screens planned, **24 files written**, **23 screens captured in the planned
state**, **2 BLOCKED** (`S28`, `S56`) with reasons. `check:clone` **passes**; `check:pixels`
now sees **64 diffable / 9 no-frame** (was 52 / 21).

---

## 1. Stack and scope

One shell lifetime: moto :9000 (bucket `camxora-studio` created), platform API :8100 on
`camxora_pfm_sandbox` with the Studio token, `musicapi` :4003 (`npm run serve`), web dev
:3103, logged in as `somvannda@gmail.com`. Readiness after the run:

```
tables ✓  pricing ✓  storage ✓  internal_token ✓  suno_api_base_url ✓
musicapi ✓  musicapi_accounts ✓   suno_callback_base_url ✗ (no tunnel — expected locally)
```

The web dev server on `:3103` was already live at the same commit (`0551b6fc`) from a clean
checkout when this run started; the host reaped it mid-run, so the whole stack was then
restarted from this worktree and every capture after that point came from the restarted
stack. Both serve the identical tree. No provider call was made — every provider-backed
state is a route mock inside the script (`quota`, `generations`, `uploads`, `generate`,
`generations/<id>`, project GET delay/500). **Zero credits spent.**

Nothing was deployed. No product component was changed.

---

## 2. What was captured

24 files, 25 rows (`EXTRA-generation-refused` and `…-legacy` share one file by declaration).

| Screen | File | State verified in the frame |
|---|---|---|
| S15 | `ours-whats-this.png` | What's This? card under `120 BPM` |
| S25 | `ours-clip-selected-master.png` | Clip pressed + master chain dock open |
| S28 | *(see §4 — BLOCKED)* | Clip menu open, swatch grid clipped by the menu |
| S29 | `ours-take-lanes-populated.png` | Take rows `2` (active) and `1` under the clip |
| S34 | `ours-magicbar-idle.png` | Idle bar + BETA, no menu, no MIDI editor |
| S35 | `ours-magicbar-attached.png` | `Drum Kit Main` chip with × |
| S40 | `ours-plugin-dock-master-eq.png` | Master chain, one EQ slot, ghost rail |
| S46 | `ours-plugin-preset-menu.png` | Preset menu open (Clear all settings / Save preset… / presets) |
| S53 | `ours-library-songs-tags.png` | All Songs, date groups + tag strip |
| S56 | `ours-shared-link-readonly.png` | Anonymous read-only share page (**frame blocked**, §4) |
| S63 | `ours-editor-1280-midi.png` | MIDI editor docked + master chain chips |
| EXTRA-library-uploads | `ours-library-uploads-resolved.png` | Uploads resolved, day headings + rows |
| EXTRA-take-lanes-empty | `ours-take-lanes-empty-clean.png` | Empty band, no first-run card |
| S01 | `ours-marketing-signed-out.png` | Signed-out `/studio`, `h1` Camxora Studio. |
| S02 | `ours-sign-in.png` | `/login`, `h1` Welcome back. + labelled Email |
| S43 | `ours-compressor-sidechain-routing.png` | Compressor card + Sidechain routing list |
| S57 | `ours-project-loading-1094.png` | Editor holding load, `.se-loading` |
| S60 | `ours-moderation-refusal.png` | Inline refusal after Create |
| S61 | `ours-insufficient-credits.png` | Zero balance, warn note, CTA disabled |
| S62 | `ours-offline-cold-load.png` | Offline cold load — no app shell |
| EXTRA-generation-refused | `ours-generation-refused.png` | `That prompt was refused` + Edit prompt |
| …-legacy | *(same file)* | same state |
| EXTRA-library-song-detail | `ours-library-song-detail.png` | Song details rail, Info tab |
| EXTRA-project-load-error | `ours-project-load-error.png` | `Project storage unavailable.` alert |
| EXTRA-restoring-last-project | `ours-restoring-last-project.png` | `.se-loading` at 1689×1277 |

Every PNG was inspected against the state the plan names, not just against the script's
assertion. Three needed a second pass (§3) and one is blocked (§4).

---

## 3. Script fixes (three, all fixture/selector — no product change)

The committed script's work list, viewports, mocks and assertions were kept as written.
Three scenarios could not reach their state as coded:

| Screen | What failed | Fix |
|---|---|---|
| **S46** | `getByRole("button", { name: "Track 1" })` timed out — the fixture seeded a track named `Drums`, while the plan's step and the dock's label (`Plugins for Track 1`) both say "Track 1". | Seeded the track as `Track 1` so the plan's literal step resolves. |
| **S43** | Same selector assuming `Track 1`; the plan seeds `Brass Section` as track 1. | Select `Brass Section` and assert `Plugins for Brass Section` (the dock's accessible name is `Plugins for <track name>`, `StudioPluginDock.tsx:767`). |
| **S63** | Two defects. (a) Creating the part via *Add new track ▸ MIDI* races the project save — the write can land after the load effect replaces the clip list, closing the editor. (b) `onSelectMaster` calls `setMidiClipId(null)`, and the bottom dock is a single slot (`takeLanes ? … : midiClip ? … : masterSelected ? …`, `StudioEditorShell.tsx:7273-7332`), so the MIDI editor and the master *dock* can never be on screen together — the plan's "MIDI editor **and** master chain selected" is unreachable as written. | Seed the MIDI clip in the project document, add EQ + Compressor to the master chain, then open the clip. The reference's 1280 px frame shows the master chain as the **footer chip row** (`Wavetable · Compressor · EQ · +`), which stays visible while the editor is docked, so the row's expectation is now `.se-chain-chip`, not the master dock. |

Two further small adjustments inside the S29 scenario: the assistant stays a docked column
and pushes the take band below the fold, and the "Take added to the clip." toast floats over
it. The scenario now closes the assistant and dismisses the toast, so the two take rows are
actually in the frame.

**Recorded product deltas found while capturing** (not fixed here — W3 is capture-only):

1. `S28` — **the Clip Color submenu is unreachable by mouse.** `.se-clip-menu` is
   `overflow:auto` (`globals.css`) and `.se-clip-menu-colors` is absolutely positioned at
   `left: calc(100% + 12px)`, so the swatch group is laid out at x≈458 inside a 163 px
   scroll box and clipped: it never paints. The element keeps a non-zero box and
   `aria-expanded="true"`, so the DOM assertion passes while the frame shows nothing. One-line CSS fix (use a portal/`position:fixed`, or drop the submenu to a
   grid inside the menu).
2. `S63` — master dock and MIDI editor are mutually exclusive (single bottom slot); the
   reference shows the MIDI editor plus the footer chain chips, which is what we captured.
3. `S57` / `EXTRA-restoring-last-project` — while the project GET is in flight the editor
   renders the empty-session placeholder ("Your session is empty · Add a track to start
   arranging.") next to a small `Loading project…` line at the bottom right. The reference
   loading frame is a blank canvas, so the diff (1.45 % for S57) is almost entirely that
   placeholder + chrome.
4. `EXTRA-project-load-error` — a failed project GET leaves the start overlay
   ("How do you want to start?") over the editor; the `.se-error` alert renders above it.

---

## 4. Blocked

| Screen | Status | Reason | What unblocks it |
|---|---|---|---|
| **S28** | **BLOCKED** | The Clip Color submenu is opened but clipped by `.se-clip-menu { overflow:auto }`. No viewport or step can show the swatch grid. Capture `ours-clip-color-open.png` is kept as evidence (menu open, grid clipped); **S28 stays paired to `ours-clip-color.png`**, so the gate still reads the row as `STATE`. | A product fix in its own branch, then a re-shoot. |
| **S56** | **BLOCKED** | The reference frame `S56-shared-link-logged-out.jpeg` is the **marketing hero** and contains no share surface. Nothing we can shoot matches it. Our capture is now the correct read-only share page and is paired, but the 39.12 % is a frame defect. | A W0 corpus decision: a real `/studio/shared/<token>` logged-out frame, or record the screen as frame-less. |

`S62` is captured (no app shell, `.se-head` absent) but the reference is Chrome's own
"no internet" page — browser UI, not a product surface. Treat its 99.99 % as a `RECORDED
GAP`, not a layout claim.

`S02`'s modal-vs-route divergence and `S61`'s missing out-of-credits modal remain the open
W7/absence decisions the plan already flags; the captures are evidence for them, not a
sanction of them. One cosmetic artefact worth knowing when reading `S61`: the sidebar
wallet badge still shows the account balance (448) because only the create form's `quota`
route is mocked — the frame's evidence is the blocked CTA and `.s-note.warn`.

---

## 5. PAIRING edits

31 field edits over 27 entries from the plan §6.1, applied in the same commit as the
captures. One correction to the plan's trap note: **`S41` did have `sharedWith: "S40"`**, not
none, so re-pointing only `S42`/`S44` to `S41` left the four-way group with no anchor and
`check:clone` failed with *"one capture is paired with S41, S42, S44"*. The fix is to clear
`S41.sharedWith` as well, which is what the plan's intent requires:

```
ours-plugin-dock-eq-convolution.png  →  S41 (anchor, no sharedWith)
                                        S42 sharedWith S41
                                        S44 sharedWith S41
ours-plugin-dock-master-eq.png       →  S40 (own file)
ours-plugin-preset-menu.png          →  S46 (own file)
```

`S28` was deliberately **not** re-pointed (§4). `EXTRA-library-song-detail` lost its dead
`spec: studio-components.test.tsx` pointer and gained the capture.

**S43's frame.** The rename the plan proposed is already in `origin/main` (`32b0323c`, "S43
frame restored"): the file is `docs/studio/reference/screens/S43-compressor-routing-list.jpeg`.
Only `SCREENSHOT_INDEX.md:74` still named the old `S46-compressor-routing-list.jpeg`; that is
corrected here. **S43 verdict:** `DELTA 47.89 %` against a 1040×660 card crop compared with a
1689×1277 viewport — a `REGION` framing artefact. Content matches the frame option-for-option:
`None`, then `Brass Section`, `Long Vocal`, `Bass Line`, `Bass Answer` each as `— Pre-fx` and
`— Post-fader`. The screen is judged, not blocked.

---

## 6. Gate counts, before → after

| Gate | Before | After |
|---|---|---|
| `check:clone` | passes — 73/73 evidenced, 53 captures, 32 specs, 2 negative | **passes** — 73/73 evidenced, **64 captures**, 31 specs, 2 negative; metrics 8/8; strings 70/70 |
| `check:pixels` diffable | 52 | **64** |
| `check:pixels` `NO-FRAME` | 21 (18 spec-only, 2 negative, 1 no frame) | **9 (7 spec-only, 2 negative, 0 no frame)** |
| `check:pixels` `WITHIN` | 0 | 0 |
| `check:pixels` exit | 1 | 1 |

Both gates reproduce with `cd camxora.com && npm run check:clone` / `npm run check:pixels`.
The remaining `NO-FRAME` rows are exactly the spec-only and negative screens; **no screen is
frame-less any more**.

---

## 7. Sign-off

- **Captured:** 23 screens in their planned state + `S28`'s near-state evidence file = **24
  files / 25 rows**.
- **Retaken after review:** S29, S43, S46, S63.
- **Blocked:** **2** — `S28` (product: submenu clipped by its own menu) and `S56` (reference
  frame is the marketing hero; W0 corpus decision).
- **New diffable count:** **64** (was 52); `NO-FRAME` **9** (was 21).
- **`check:clone`:** passes, 73/73 evidenced.
- Commit: see the message on `qa/capture-run`; nothing pushed, nothing deployed, production
  untouched.
