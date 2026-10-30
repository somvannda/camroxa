# Capture log

Audit trail for reference discovery. Every capture records **what**, **how**, **when**
and **what is still missing**, so "capture everything" is a finishable checklist rather
than a vibe.

## Run 1 — 2026-10-30, anonymous

| Item | Value |
|---|---|
| Route | `https://suno.com/studio` → redirected to `/studio-welcome` |
| Mode | anonymous (no session) |
| Method | `tools/suno-re/fetch-bundle.mjs` |
| Chunks | 101 (7,275 KB) |
| Endpoints | 255 unique (65 studio-related) |
| Notes | Marketing route loads the shared API client, not editor UI |

## Run 2 — 2026-10-30, authenticated

| Item | Value |
|---|---|
| Route | `https://suno.com/studio` (signed in, project "Untitled Project") |
| Mode | authenticated |
| Method | `performance.getEntriesByType('resource')` → `fetch-list.mjs` |
| Chunks | 134 (11,884 KB), includes `dsp-engine` workers |
| Endpoints | **322 unique**, **81 studio-related** |
| UI strings | 9,679 unique, 2,400 in `/api/studio` chunks |
| Layout | 1958×1245 viewport, full region + control geometry |

### Captured successfully (Run 2)

| Surface | Evidence |
|---|---|
| Design tokens + base frame | measured |
| Header: all 15 controls + geometry | measured |
| Track panel: 11 elements + geometry | measured |
| Prompt/Studio AI bar: 8 controls + geometry | measured |
| Model picker: 4 entries, descriptions, 100-credit custom model | text |
| Add-track menu: Audio / MIDI / Upload + accelerators | text |
| Onboarding overlay: title, 4 cards, 2 secondary entries, skip | text |
| "What's This?" hover-help card + Dismiss/Turn off | text |
| Empty project state (1 audio track, main bus) | text |

### Not captured (Run 2) — see §14 of the spec

| Surface | Attempted | Result |
|---|---|---|
| Project menu | programmatic click | overlay did not expose text |
| Export menu | programmatic click | no change |
| Clip context menu | not attempted (no clip) | — |
| Track options menu | not attempted | — |
| Library panel content | opened, not read | needs reading while open |
| Keyboard binding map | bundle scan | key literals found, bindings unresolved |
| Responsive layout | not attempted | needs 1280/1024/768 |

### Technique notes (reuse these)

```js
// 1. Enumerate loaded chunks
[...new Set(performance.getEntriesByType('resource').map(e => e.name))]
  .filter(n => n.includes('/_next/static/') && n.endsWith('.js'));

// 2. Geometry probe
const rect = el => { const b = el.getBoundingClientRect();
  return { x: Math.round(b.x), y: Math.round(b.y), w: Math.round(b.width), h: Math.round(b.height) }; };

// 3. Menu/dialog content that portals miss with innerText diffing:
//    read the accessibility snapshot (browser.snapshot) right after the click,
//    or query the floating layer directly:
[...document.querySelectorAll('body *')].filter(el => {
  const cs = getComputedStyle(el);
  return /fixed|absolute/.test(cs.position) && Number(cs.zIndex || 0) >= 20;
}).map(el => el.innerText);
```

**Lesson:** programmatic `.click()` opens Radix menus inconsistently. Use the real
pointer path (`browser.click` on a snapshot ref) for menu capture, then read the
snapshot. That is the reliable method for C-01…C-05.

## Run 3 — 2026-10-30, bundle mining (session lost)

The live tab was logged out mid-session (landed back on `/studio-welcome`), so menu
capture (C-01…C-05) could not continue. Work moved offline to the already-captured
134 chunks.

| Result | Value |
|---|---|
| Feature buckets | 14 areas, 2,845 bucketed strings |
| Newly discovered areas | **13** (`ST-NEW-01…13`) — see spec §16 |
| Largest surprise | time-selection editing, take lanes, master limiter lookahead, Ably realtime |
| Error/validation strings | **827** — a complete edge-case checklist |

Artifacts: `reference/derived-features.md`, spec §16.

**Consequence:** the clip model must be decided before more clip features are built.
Take lanes mean a clip is a stack with an active take, not a single audio source.

## Run 4 — 2026-10-30, live pointer capture (signed-in tab reused)

| Captured | Result |
|---|---|
| Project menu | New Project · Open Project · Rename · Duplicate Project · Version History · Share Project · Open a copy in v1 Studio · Settings `ctrl shift ,` · Show Quick Start again |
| Export menu | Full Song · Selected Time Range · Multitrack |
| Add-track menu | Audio `A` · MIDI `M` · Upload `U` |
| Full aria-label map | 38 controls (spec §17) |
| Library | workspace-scoped: New workspace, My Workspace (902 songs), BDBT50 (42), BDBT-16-May (67), BVBR19-May (20) |
| Per-track panels | Plugins · Automation · Clip editor · Take lanes · Add effect |
| Naming | the prompt bar is internally **"Magic Bar"** |

### Method that worked (replaces the failed `.click()` attempts)

Programmatic `element.click()` and helper-text diffing did **not** open Radix
overlays. What worked: resolve the trigger by
`aria-label`/text, then dispatch a full pointer sequence
(`pointerdown → mousedown → pointerup → mouseup → click`, `bubbles: true`,
`composed: true`) and read the floating layer:

```js
[...document.querySelectorAll('body *')].filter(el => {
  const cs = getComputedStyle(el), b = el.getBoundingClientRect();
  return /absolute|fixed/.test(cs.position) && Number(cs.zIndex||0) >= 30
      && b.width > 120 && b.width < innerWidth * 0.85 && b.height > 40;
}).map(el => el.innerText);
```

### Still open

| # | Missing | Note |
|---|---|---|
| C-03 | Clip context menu | needs a clip on the timeline (demo project did not load in this run) |
| C-04 | Track options menu | trigger not isolated yet (row has no labelled `…`) |
| C-05 | Library panel tabs/sub-panels | workspace list captured; per-workspace view not |
| C-06 | Timeline metrics | ruler/lane/clip heights, zoom steps |
| C-07 | Full keyboard map | only `ctrl shift ,`, `A`, `M`, `U` confirmed |
| C-08 | Responsive layouts | needs 1280 / 1024 / 768 |
| C-10 | Settings / Version history / Share dialogs | triggers known, contents pending |

### Run 4b — dialogs

| Surface | Result |
|---|---|
| Studio Settings (`ctrl shift ,`) | captured: Performance / Window management / Content; **Ghost drag for arrangement moves** semantics |
| Version History | opened from menu, no dialog text captured |
| Share Project | opened from menu, no dialog text captured |
| Clip context menu | blocked — no clip on the timeline |

### Run 4c — dialogs and panels

| Surface | Result |
|---|---|
| Share dialog | verbatim copy captured; link = view + **fork**, not co-editing |
| Version History | 300 px left panel, "Projects are saved automatically", second-level timestamps |
| Loaded demo | `Drum & Bass Demo` 174 BPM 4/4, tracks `Electric Keyboards`, `Soft Piano` |
| Magic Bar placeholder | context-sensitive: suggests "Add a warm reverb to this track" when audio is loaded |
| Clip context menu | still not captured — clips are not plain DOM nodes; use pointer click on a snapshot ref |

### Run 4d — architecture and settings

| Finding | Detail |
|---|---|
| Timeline renderer | **single canvas 1942×1141 @ (8,52)** — clips are not DOM |
| Track row metrics | 85 px tall, 260 px header column, 86 px step |
| Drag and drop | custom layer (`data-studio-nested-drop-target`), not HTML5 DnD |
| Magic Bar anchor | `data-studio-anchor="agent-composer"` |
| Settings → Content | tempo-on-import policy; **Wavetable Designer** + **Impulse Response Designer** gated behind "Advanced content features" |
| Consequence | C-03 must be captured with real pointer coordinates over the canvas |

### Run 4e — clip menu (canvas pointer sweep)

Method: sweep `elementFromPoint` over the arrangement canvas, dispatch
`pointerdown/mousedown/pointerup/mouseup/contextmenu` with `button: 2`, read the
floating layer. Hit on attempt 7 at (608, 142).

Captured clip menu (verbatim):
`Copy ctrl C · Paste ctrl V · Duplicate ctrl D · Delete backspace · Heal Edits ·
Split ctrl E · Rename · Clip Info · Clip Color · Get Stems · Download .WAV ·
Get MIDI · Remove FX`

New facts: clip-level FX, per-clip MIDI extraction, per-clip WAV export, and a
**healable edit chain** per clip.

Track-header right-click returned the same menu (the clip menu was still mounted);
C-04 remains open.

### Run 4f — track menu attempts

| Attempt | Result |
|---|---|
| Right-click track header (number/name) | no menu; returned the What's This? card |
| Right-click with clip menu dismissed first | same |
| Library workspace click | panel unchanged; per-workspace view still open (C-05) |

Conclusion: C-04 needs the track row's own action affordance (the 16×32 row-extend
control), not a generic right-click.

### Run 4g — shortcut overlay (closes C-07)

`shift ?` opens the built-in Keyboard Shortcuts overlay. Captured the **entire map**
by context (General, Timeline, Tracks, Effects chain, Clip editor audio/MIDI,
Automation CC/Velocity, Playable keyboard, Library).

Findings that change the plan: `CTRL S` manual save exists; warp markers + quantize;
take-lane promotion via `ENTER`; delete/duplicate time on selected tracks; hidden
tracks; four panels (chat/bottom/lanes/library); velocity + CC automation lanes;
playable keyboard velocity keys.

Also captured: Learn menu (`Keyboard Shortcuts shift ?`, YouTube Tutorials, Learning
Center, `What's This? On`) and Settings → Window management (dockable/poppable
plugin + keyboard windows).

### Run 6 — paid capture attempt (owner-approved)

| Action | Result |
|---|---|
| Clip menu → `Get MIDI` | no dialog surfaced; nothing confirmed |
| Clip menu → `Get Stems` | no dialog surfaced; nothing confirmed |
| Credits spent | **none** — no confirmation path was reached |

Cause: the menu entry was matched by text, but the synthetic click did not commit the
action (same class of failure as the earlier `.click()` attempts). The reliable path is
a **real pointer click on a snapshot ref**:

```
snapshot → find "Get MIDI" ref → browser.click(ref) → snapshot the new surface
```

Next session should redo Run 6 with that method. Approval stands, so the actual
execution (and its cost) can be completed then.

### Run 6b — pointer-ref attempt on paid capture

Method: `browser.find("Get MIDI")` → ref `e100145` → `browser.click(ref)`.

Result: the clip became selected (Magic Bar context switched to `Vocal Cuts`, plugins
panel showed `Delay` + `Compressor`) but **no dialog or status appeared**. No credits
were charged.

Conclusion: `Get MIDI` either enqueues silently, requires a specific clip state, or
opens a surface that is neither `role="dialog"` nor `role="status"`. Before retrying,
snapshot immediately after the click and inspect the whole tree rather than querying
by role.
