# PROJECT PROGRESS

Reverse-chronological. Newest session first.

## Session 2026-11-11 — Bounce a track (N-06)

The track menu can render one track on its own, on top of the warp-marker branch
(`feat/studio-bounce`).

| Area | What landed |
|---|---|
| **Bounce** | "Bounce track" in the track options menu renders that track's clips through its own effect chain (master chain included, unity master gain) and hands back a `<project> - <track> (bounce).wav` |
| **Reporting** | the toast follows the reference's `Exporting on track #`: `Bouncing <track>…` while it renders, then `Bounce on <track> started!`; the menu row disables with a reason when the track has no clips |
| **Solo rule** | a bounce ignores the other tracks' solo state, so bouncing a soloed-out track is never silent (same rule as the per-track export, G39) |

### Verified

`npm run typecheck`, `npm run check:ui`, vitest **234/234**, full studio e2e includes
the new bounce spec: a real 4 s clip downloads a valid RIFF of the expected size, and an
emptied track disables the action.

### Blocked

True render-in-place needs the rendered file stored: `POST /studio/uploads` answers
`storage_not_configured` on the running sandbox API. The in-place half is recorded in
D-031 and `PROJECT_BLOCKERS.md`; the mixdown form is what the captured strings describe.

## Session 2026-11-11 — Warp markers (S30)

The audio clip editor and its warp markers are in, on top of the time-selection branch
(`feat/studio-warp-markers`). Double-clicking an audio clip opens the captured
`Clip Settings` band; the markers are the editable object (D-030).

| Area | What landed |
|---|---|
| **Clip editor** | 280 px `Clip Settings` column beside a zoomed waveform with a bar ruler and playhead, in the same band geometry as the MIDI editor |
| **Stretch** | a switch plus `On Beat` / `Transients` / `Start and End` with the captured tooltips, and the Formant control; choosing a mode fills the clip with that mode's markers |
| **Markers** | white pennant heads on the waveform's top edge with hairline stems, clipped to the clip bounds; `Transients` detects onsets from the decoded peaks and falls back to the bounds for steady audio |
| **Editing** | drag a head (timeline position moves, source stays), click selects, `Ctrl A` selects all, `Shift Q` quantizes; every edit persists on the clip as `warp` and one undo step |
| **Shared decode** | `lib/studio-peaks.ts` now owns the peak cache and onset detection, used by both the timeline waveform and the clip editor |

### Verified

`npm run typecheck`, `npm run check:ui`, vitest **234/234** (25 files), full studio e2e
**110 passed / 1 skipped**, plus a screenshot pass over the panel and its marker row.
The captured-but-unbuilt half of §81 (Volume, Loop/Reverse, Pitch, Speed, Quantize) is
recorded in D-030 as the follow-up.

## Session 2026-11-11 — Time selection (N-01)

The editor has the reference's second selection type: a **time range** dragged on the
bar ruler, with its own verbs (D-029). Branch `feat/studio-time-selection`.

| Area | What landed |
|---|---|
| **Range selection** | dragging the bar ruler selects a snap-to-beat range; a click without movement still seeks, `Shift`-click extends it, `Shift ←/→` grows it a beat, `Esc` clears it; clips and empty lanes clear it (selection is contextual) |
| **Rendering** | an accent-tinted band over the ruler and the lanes with edge grips, kept separate from the loop band so loop playback and a transient edit scope never fight |
| **Verbs** | ruler right-click menu: loop selection, duplicate time, delete time (all tracks), delete time (focused track), export selection, clear; the same actions as `Ctrl Shift D`, `Ctrl Shift Backspace` and `Ctrl Backspace` |
| **Ripple edits** | `lib/studio-time.ts` deletes/duplicates a block: clips are cut at the range edges, content offsets advance, MIDI notes rebase onto their slice, later clips move, track `clipIds` rebuild, and each edit is one undo step |
| **Range export** | the header's `Selected time range (WAV)` unlocks for a range as well as a loop range, and exports the range when both exist |
| **Docs + Learn** | shortcut list, `PIXEL_PARITY` row and D-029 record the two-selection model |

### Verified

`npm run typecheck`, `npm run check:ui`, vitest **217/217** (23 files), full studio e2e
**108 passed / 1 skipped**, plus a manual screenshot pass over the band and the range menu.

## Session 2026-11-09 — Pixel parity (D-022)

The Studio is now built to the captured layout, palette and type scale, verified by a
Playwright gate at the capture viewport (1689×1277). Targets live in
`reference/METRICS.json`; the log of matched regions and intentional divergences is
`docs/studio/PIXEL_PARITY.md`.

### Shipped

| Area | What landed |
|---|---|
| **Brand palette** | Surfaces and plugin accents use the CAMXORA navy/purple tokens (D-025); captured geometry and type unchanged |
| **Frame** | `#111111` body, 52 px header/footer `#0a0a0a`, 260 px track panel `#141416`, 360 px library rail `#101012`, text `#f7f4ef` |
| **Header** | 36 px pill groups (project, undo/redo, transport, time, tempo), `120 BPM 4/4`, ellipsis project chip |
| **Tracks** | 85 px rows on `#141416` with `#1c1c1e` fader capsules, pan arch, 24 px controls, colour strip, `#262628` selection, pinned `Main` strip, wired all-controls head toggle and a 44 px panel-collapse rail |
| **Timeline** | 30 px ruler `#101012` with thinning labels, 22 px `#1e1e20` time ruler with adaptive ticks, grey playhead + cyan flag, 82 px clips with 10 px radius, decoded waveforms, hover-only trim/fade grips |
| **Library** | floating 360 px card inset 8 px; 64 px tiles with colour icon squares; 56 px rows; 30 px filter chips; uploads chip bar; colour flyout submenus |
| **Rails** | clip info and song detail rebuilt to the captured anatomy (hero, Remix, waveform, underlined tabs, section cards); history drawer on the captured surface |
| **Menus** | Learn popover, track/add-track/project/clip menus, export menu and toast, share dialog, the My Projects modal and the prompt bar (inline generation) on the captured surfaces |
| **Remix** | Song-detail Remix generates a style variation through the generation API, adds it to the library and confirms with a toast (D-024) |
| **Comments** | “Comments and notes” loads and posts project comments from the song rail (owner-only POST endpoint, replies supported by the model) |
| **Prompt bar + assistant** | 645x56 floating bar that generates through the model picker into a left assistant panel; the take can be auditioned or committed to the playhead track (S37). The song detail keeps the sticky mini-player (D-023) |
| **MIDI** | Add-track MIDI creates a four-bar clip and opens the bottom piano-roll editor (grid, velocity lane, tabs, quantize); notes are editable, persisted, synthesised in playback and included in exports |
| **Plugins** | dock band + slot cards, catalog with Learn chips, shared knob controls on every card, preset menus, and a working **four-band EQ card** backed by four cascaded biquads; **Create new plugin** opens the S45 designer (restate → Build it → draggable card saved to MY PLUGINS, never auto-inserted) |
| **Stems (G12)** | GET /studio/stems projects completed stem operations into one typed row per clip; the library Stems tile/chip lists them with audition and Add-at-playhead |
| **Take lanes (S29)** | footer control opens the band; regenerating over an audio clip stacks takes, newest on top, active take outlined with a tick and switchable |
| **Convolution (S44)** | IR slot with a 0–2 s preview, six-group/11-response picker, Mix/Gain/Pre/Width, and the picked impulse drives the convolver |
| **Master chain (S48)** | selecting Main opens the Limiter card (Lookahead/Pre Gain/Attack/Release/Link) wired to the master bus; EQ/Compressor Amount links |
| **Sidechain (S43)** | compressor routing menu with None and every track as Pre-fx/Post-fader; playback ducks the target from the chosen tap |
| **Refusals (S60/S61)** | credit errors show Not enough credits + View plans; policy errors show a refusal card + Edit prompt (own states, no capture) |

### Verified

`check:ui`, typecheck, `next build`, vitest 181/181, full studio e2e 80 passed / 1
skipped, plus the pixel gate (21 assertions) and axe checks.


## Session 2026-11-04 — Studio build: gaps closed, tests and CI in place

Continued from the 2026-11-03 capture/backfill session. This one is about **building**
against the captured contract rather than photographing it.

### Shipped (each verified in the running app, not just typechecked)

| Area | What landed |
|---|---|
| **W1 entry** | `/studio` routed to `StudioHome` (was a missing route; every page 500'd on a stale duplicate-route state); start-from-song seeds a project with playable audio |
| **W2 persistence** | save status with retry · 409 conflict detection (server `expected_updated_at`) + reload/overwrite panel · offline draft capture and restore · unsaved-changes guard |
| **W3 editor** | clip drag with 3px threshold, snap and guideline · marquee multi-select · multi-drag · copy/paste/duplicate · delete with focus management · library Songs/Projects + search · clip provenance · audition speed · first-run onboarding · clip culling (300 → 80–140 rendered) · 44px touch targets on coarse pointers · track options menu · hidden tracks · undo/redo |
| **W4 audio** | real master bus (EQ / compressor / limiter / drive, measured dry RMS 0.293 → 0.631) · export full mix, per-track, selected range, project JSON (byte-exact WAV) · master peak meter |
| **W5 tests** | vitest: 54 unit + component tests · Playwright smoke · CI job that runs typecheck, the UI gate and the tests on any `camxora.com` PR |

### Bugs the tests found (not hypothetical)

1. **Drag saved twice** — the commit ran inside a `setDrag(prev => …)` updater, which React
   double-invokes in dev, so the second write raced the first into a 409. Every clip drag
   would have shown `Save failed`. Found by the Playwright smoke, fixed with a ref.
2. **Two of my own assertions were wrong**, not the code: 40px of a 96px bar snaps to
   1.0s (not 0.5s), and `setInt16` truncates rather than rounds.
3. **Accessibility**: axe found six contrast failures (3.52:1 on ruler ticks), a
   label/content mismatch on the speed pill, and `role=main` wrapping header + footer.
   Both Studio routes are now axe-clean.

### Gates run every commit

```
cd camxora.com && npm run typecheck && npm run check:ui && npm test
```

Plus `npm run test:e2e` for anything touching the editor's interaction model.

### Environment notes that cost real time

- The platform API must run **from this worktree** or backend edits do not apply; see
  `SESSION_HANDOFF.md` for the exact command (quoted `set "VAR=value"`, `PYTHONIOENCODING`,
  and the `camxora_pfm_sandbox` database).
- Access tokens live **30 minutes** — expect a 401 mid-session and re-login rather than
  debugging a phantom failure.
- `requestAnimationFrame` is throttled in a background tab, so the playhead and the master
  meter cannot be observed there; that is not a playback bug.

## Session 2026-10-30 — decompilation groundwork + architecture correction

### Completed

| # | Work | Artifact |
|---|---|---|
| 1 | Repository audit; identified that the independent editor (`StudioEditorView`) is on `main` and the Suno-contract editor (`StudioShell`) is on `feat/studio-shell` | this doc |
| 2 | Programme documentation set (12 documents) | `docs/studio/*.md` |
| 3 | Feature inventory with permanent IDs (221 rows) | `SUNO_STUDIO_FEATURE_INVENTORY.md` |
| 4 | Architecture decisions, including the owner's correction of the target | `PROJECT_DECISIONS.md` (D-008) |
| 5 | Reference extraction toolkit (fetch + extract + parity) | `tools/suno-re/` |
| 6 | Public-bundle extraction: 101 chunks → 255 endpoints | `reference/endpoint-inventory.*` |
| 7 | **Authenticated** bundle extraction: 134 chunks (11.9 MB) → **322 endpoints, 81 studio-related** | `reference/endpoint-inventory.*` |
| 8 | UI string mining: 9,679 candidates, **2,400 in studio chunks** | `reference/ui-strings.md` |
| 9 | **First measured layout capture** (1958×1245): tokens, header 52 px, track panel 260 px, control geometry | `reference/live-studio-layout.md` |
| 10 | Studio home implementation (resume, grid, search, sort, create, per-card actions) | `components/studio/StudioHome.tsx` |
| 11 | Marketing page extracted to its own component; `/studio` now routes by auth | `components/studio/StudioMarketing.tsx` |

### Tests executed

| Check | Result |
|---|---|
| `npm run typecheck` (baseline `origin/main`) | pass |
| Bundle fetch (anonymous) | 101/101 chunks, 7,275 KB |
| Bundle fetch (authenticated) | 134/134 chunks, 11,884 KB |
| Endpoint extraction | 322 unique, 81 studio-related |
| String extraction | 9,679 unique, 2,400 studio-chunk |
| Layout capture | complete for 1 viewport (1958×1245) |
