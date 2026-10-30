# IMPLEMENTATION ROADMAP

Ordered work for the Studio program. Each item names its dependency and its exit
test. The roadmap is authoritative: if `PROJECT_NEXT_ACTIONS.md` disagrees with
this file, fix one of them in the same commit.

## Current position

```
M0 Repository & environment audit ............. DONE (2026-10-30)
M1 Reference platform discovery .............. PARTIAL — live access blocked (B-001)
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

### W2 — Trustworthy persistence

| # | Task | Depends on | Exit test |
|---|---|---|---|
| W2.1 | Autosave status surface (saved / saving / error / offline) with retry | — | kill the API mid-edit → status shows error, retry recovers, no data lost |
| W2.2 | Conflict handling on 409 (reload vs. overwrite choice) | W2.1 | simulated 409 shows a resolution dialog, not a silent overwrite |
| W2.3 | Local draft recovery when the network is down | W2.1 | reload offline restores the last local draft with a banner |
| W2.4 | Unsaved-changes guard on navigation | W2.1 | leaving with pending writes prompts |

### W3 — Editor completeness against the inventory

Work the `GAP` column of `SUNO_STUDIO_FEATURE_MATRIX.md` top-down. Every item
needs an interaction spec row before code.

### W4 — Advanced audio

| # | Task | Exit test |
|---|---|---|
| W4.1 | Mixdown/mastering chain documented and audible (EQ, comp, drive on master + per track) | A/B render differs measurably from dry |
| W4.2 | Stem separation surfaced with credit cost from `pricing` | job starts, cost matches pricing table, result lands on new tracks |
| W4.3 | Export: full mix, selected range, stems, per-track WAV, project JSON | each produces a valid file; range export length matches selection |
| W4.4 | Loudness/true-peak readout on the master | readout matches an external analyser within tolerance |

### W5 — Test suite (M11)

| # | Task | Exit test |
|---|---|---|
| W5.1 | Unit tests for pure helpers (snap, bar/beat, WAV encode, MIDI build/parse, MIDI VLQ) | `npm test` green |
| W5.2 | Component tests for reduction/undo/mixer invariants | green |
| W5.3 | API contract tests for `lib/studio-api.ts` against a mock server | green |
| W5.4 | Playwright smoke: open project → add clip → move → undo → export | green in CI |
| W5.5 | Accessibility pass (axe) on `/studio` and `/studio/editor` | no serious violations |

### W6 — Verification (M12)

Re-walk the inventory against a live reference session and our build; update the
matrix with evidence links. Produce the coverage report with real percentages.

## Explicitly out of scope

- Any dependency on the reference platform's private API in a product path (D-002).
- Reproducing reference branding, copy, or assets.
- Desktop (PyQt6/Electron) Studio work — separate programme.
