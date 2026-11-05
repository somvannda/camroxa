# IMPLEMENTATION ROADMAP

Ordered work for the Studio program. Each item names its dependency and its exit
test. The roadmap is authoritative: if `PROJECT_NEXT_ACTIONS.md` disagrees with
this file, fix one of them in the same commit.

## Current position

```
M0 Repository & environment audit ............. DONE (2026-10-30)
M1 Reference platform discovery .............. DONE — 69 screenshots, spec §1–§96
M2 Feature inventory & documentation ......... DONE (this directory)
M3 Architecture & UX design .................. DONE (D-001..D-006)
M4 Application foundation .................... DONE (shell, routing, theme, state)
M5 Core music generation ..................... IMPLEMENTED, unverified end-to-end
M6 Audio player & timeline ................... IMPLEMENTED, unverified
M7 Studio editing ............................ IMPLEMENTED, unverified
M8 Advanced audio ............................ PARTIAL (FX/stems wired, mastering thin)
M9 Project & library management .............. PARTIAL (in-editor only; no Studio home)
M10 Backend & MusicAPI integration ........... DONE (own API, no reference coupling)
M11 Testing & optimisation ................... NOT STARTED (no Studio test suite)
M12 Final coverage verification .............. NOT STARTED
```

## Workstream sequencing

### W1 — Studio entry surface (do first)

The editor is reachable only at `/studio/editor`; `/studio` is a marketing page.
A user who lands on `/studio` has no way to see their projects, resume the last
one, or start from a song. This is the single largest structural gap.

| # | Task | Depends on | Exit test |
|---|---|---|---|
| W1.1 | `StudioHome` at `/studio` (authenticated): recent projects, resume card, new project, search/sort, archived toggle | studio-api `listStudioProjects` | renders with 0, 1 and 20 projects; empty state has a real CTA |
| W1.2 | Create project → editor route with the new id | W1.1 | new project opens in editor, autosaves |
| W1.3 | Project card actions: open, rename, fork, archive, delete (confirm) | W1.1 | each action reflected after reload |
| W1.4 | "Start from a song" list from the library, opens a project seeded with that clip | W1.1, library-api | clip appears on a track in the editor |
| W1.5 | Unauthenticated `/studio` → marketing page kept, with a sign-in CTA (no dead ends) | W1.1 | signed-out render shows no broken controls |

**Status (2026-11-01):** W1.1, W1.2, W1.3 and W1.5 are **implemented** — the
`StudioHome` component already had project list, search/sort, archived toggle, resume
card, rename/duplicate/pin/archive/delete dialogs and the `?project=` navigation; what
was missing was the **route**. `app/studio/page.tsx` now exists, so `/studio` serves
the home (signed in) or the marketing page (signed out). Verified signed-out: 200 +
marketing copy. Signed-in render still needs one manual check.

**W1.4 is the only open task in W1** — the library "start from a song" section has not
been built; `createStudioProject` accepts a `data` payload, so seeding is possible.

### W2 — Trustworthy persistence

| # | Task | Depends on | Exit test |
|---|---|---|---|
| W2.1 | ✅ Autosave status surface (saved / saving / error / offline) with retry — `StudioSaveStatus` + a single `persist()` path in the shell | — | header shows the four states; error chip is the retry button |
| W2.2 | ✅ Conflict handling on 409 — backend compares `expected_updated_at`, editor offers `Reload theirs` / `Keep mine` | W2.1 | stale write → 409 → resolution panel, not a silent overwrite |
| W2.3 | ✅ Local draft recovery — failed/offline writes persist to localStorage and are offered back on open | W2.1 | draft stored on failure, banner on reopen, restore writes through |
| W2.4 | ✅ Unsaved-changes guard on navigation — `beforeunload` while status ≠ saved | W2.1 | leaving with pending writes prompts |

### W3 — Editor completeness against the inventory

Work the `GAP` column of `SUNO_STUDIO_FEATURE_MATRIX.md` top-down. Every item
needs an interaction spec row before code.

### W4 — Advanced audio

| # | Task | Exit test |
|---|---|---|
| W4.1 | ✅ Mixdown/mastering chain audible — lib/studio-master-bus.ts builds real EQ/comp/limiter/drive nodes on the master | A/B render differs measurably from dry (measured) |
| W4.2 | ◐ Stem separation UI — "Get stems" on a clip, polls the operation, lands one track per stem | quote/debit/operation/forward/refund verified live (§D-009, `reference/STEMS_CHAIN.md`); receiving stems needs one genuinely generated clip, because musicapi resolves the owning Suno account |
| W4.3 | ✅ Export: full mix, one file per track, selected range, project JSON (stems open) | RIFF files, byte-exact lengths; range matches loopEnd - loopStart |
| W4.4 | ✅ Master peak readout — sample peak, RMS and a 4x inter-sample estimate on the master bus | maths verified against an independent calculation; live needle blocked by tab throttling |

### W5 — Test suite (M11)

| # | Task | Exit test |
|---|---|---|
| W5.1 | ◐ Unit tests for pure helpers (snap, meter, draft, seed, WAV encode) — 33 passing, enforced by CI | `npm test` green |
| W5.2 | ✅ Component tests for the extracted Studio components (header, footer, library strip, track panel) | green |
| W5.3 | ✅ API contract tests for lib/studio-api.ts against a stubbed fetch (14 tests incl. 409 mapping and the version field) | green |
| W5.4 | ✅ Playwright smoke: login, create fixture, drag a clip one bar, undo, open export | green (found and fixed a double-save bug) |
| W5.5 | ✅ Accessibility pass (axe) on /studio and /studio/editor — now an e2e assertion, not a one-off audit | no violations |

### W6 — Verification (M12)

Re-walk the inventory against a live reference session and our build; update the
matrix with evidence links. Produce the coverage report with real percentages.

## Explicitly out of scope

- Any dependency on the reference platform's private API in a product path (D-002).
- Reproducing reference branding, copy, or assets.
- Desktop (PyQt6/Electron) Studio work — separate programme.
