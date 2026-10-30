# PROJECT NEXT ACTIONS

Resume here. `SUNO_STUDIO_IMPLEMENTATION_SPEC.md` §14 is the authoritative capture
backlog; this file is the execution order.

## 1. Finish the capture backlog — use the pointer, not `.click()` (2 h)

Programmatic clicks open Radix overlays unreliably (see `reference/CAPTURE_LOG.md`).
Use the real pointer path:

```
snapshot tab → find "Project menu" ref → click ref → snapshot → record
```

Capture in this order (C-01…C-05): project menu, export dialog, track options menu,
clip context menu (add a clip first), library panel tabs + empty states.
Record each into §8 of the spec and tick it in the capture log.

## 2. Capture responsive layouts (45 min)

Repeat the geometry probe at **1280**, **1024**, **768**. Record which panels
collapse/overlay. Update §1 and add the breakpoint rules.

## 3. Capture the keyboard map (45 min)

For each candidate (`Space`, `A`, `M`, `U`, `S`, `D`, `L`, `R`, `Delete`,
`Cmd/Ctrl+Z`, `Shift+Cmd/Ctrl+Z`, arrows, `Home`, `End`, `?`): focus the timeline,
dispatch the key, observe the state delta, record. Resolve C-07.

## 4. Fix the deep-link blocker (30 min)

`StudioEditorView` reads only `?share=`. `StudioHome` navigates with `?project=`.
Add `projectParam` with a terminal error state for 403/404.

## 5. Reconcile the 81 studio endpoints with musicapi (2 h)

For each: covered / partial / missing in `musicapi`. Emit
`reference/musicapi-coverage.md`. Port gaps per D-008.

## 6. Commit and run gates

```bash
cd camxora.com && npm run typecheck && npm run check:ui
```

Two commits: (a) `docs(studio): implementation spec + reference captures + toolkit`,
(b) `feat(studio): studio home + deep link`.

## Rules

- Never implement from a `?` row. Capture first, then build.
- Re-fetch the bundle before trusting `reference/`; record chunk count and date.
- Never commit chunks, HTML, fonts or reference assets. Derived facts only.
- `VERIFIED` requires a recorded run on current HEAD.

## 2. Diff our editor against the measurements (1 h)

Compare `StudioEditorView` region geometry with `reference/live-studio-layout.md`:

- header height, transport centring, right-aligned session settings
- track panel width (ours vs. 260 px)
- control heights (32 px standard, 28 px compact)
- prompt bar position and width

Write the delta into `SUNO_STUDIO_GAP_ANALYSIS.md` as measured items (replace
"unmeasured" notes with numbers).

## 3. Reconcile the endpoint inventory with musicapi (1–2 h)

For each of the **81 studio-related** reference endpoints:

1. Does `musicapi` expose it? (`/v1/*` public or `/internal/studio/*`)
2. Is the field shape compatible (names from `endpoint-inventory.json`)?
3. If missing, is it required for a workflow in `SUNO_STUDIO_WORKFLOW_DOCUMENTATION.md`?

Output: `reference/musicapi-coverage.md` with `covered / partial / missing`.

## 4. Fix the deep-link blocker (30 min)

`StudioEditorView` reads only `?share=`. `StudioHome` navigates with `?project=`.
Add `projectParam` handling in the load effect, with a terminal error state for
403/404. Without this, the new home is broken.

## 5. Commit and run gates

```bash
cd camxora.com && npm run typecheck && npm run check:ui
```

Then commit in two logical changes: (a) `docs(studio): programme docs + reference
extraction`, (b) `feat(studio): studio home + reference toolkit`.

## 6. Decide on merging `feat/studio-shell`

Per D-008 it is the reference implementation again. Do **not** merge the branch
wholesale. Instead: list the contracts/behaviours it proves, and port them one at a
time into `StudioEditorView` with a test each.

## Rules for the next session

- Re-fetch the bundle before trusting `reference/` — Suno ships often; note the
  chunk hashes you used.
- Never commit chunks, HTML, fonts or any reference asset. Derived facts only.
- A row moves to `VERIFIED` only with a recorded run on current HEAD.
- Keep `PROJECT_PROGRESS.md` updated in the same commit as the work.

## Mount the plugin dock (next coding task)

The dock is built and tested in isolation; it is **not** mounted in the editor yet.
The remaining work is data plumbing, not UI:

1. **Extend the track model.** `StudioEditorView` keeps `lanes: Clip[]` where each clip
   carries a `trackId`. Add `chain?: PluginChainEntry[]` to the track record (or to
   `StoredSession` as `chains: Record<trackId, PluginChainEntry[]>`). Prefer a map keyed
   by track id: a track with no clips still needs its chain.

2. **Normalise on load.** In `applySession`, run every stored chain through
   `sanitizeChain()` (`lib/studio-plugin-chain.ts`) before it reaches state, so stale
   documents cannot inject unknown plugins or parameters.

3. **Persist on save.** Include `chains` in the `data` payload sent to
   `updateStudioProject`. It is part of the document, so undo and versions cover it
   automatically — no separate endpoint.

4. **Mount the dock.** Render `<StudioPluginDock chain={chains[selectedTrackId] ?? []}
   onChange={(next) => commitChains({...chains, [selectedTrackId]: next})} />` in the
   track inspector region, next to `Plugins`. Reuse the existing `commitLanes`-style
   history push so a plugin tweak is one undoable step.

5. **Wire the audio.** Replace the fixed per-track FX chain with
   `buildPluginChain(ctx, activeChain(chain))`; connect
   `trackNode → pluginChain.input` and `pluginChain.output → panner → master`.
   Call `chain.update(entryId, params)` on parameter changes instead of rebuilding.

6. **Verify.** Typecheck, `check:ui`, then a manual run: add Delay + Compressor, play,
   confirm the sound changes, tweak a knob and confirm `Custom` appears, press
   `Update`, reload, confirm the chain and preset survive.

Acceptance: the chain round-trips through save/load, undo restores a removed plugin,
and a bypassed plugin is inaudible without leaving the graph disconnected.
