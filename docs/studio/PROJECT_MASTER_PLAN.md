# PROJECT MASTER PLAN

## Mission

A production-grade AI music studio with comprehensive coverage of the observable
Suno Studio workflow, built independently on Camxora's stack with original branding,
UX and implementation.

## Non-goals

- Copying reference branding, copy, or assets.
- Depending on the reference platform's private API in any product path.
- UI automation of the reference site.
- Pixel-for-pixel replication (we match interaction quality and density).

## Milestones and gates

| # | Milestone | Gate (must be true to leave) | State |
|---|---|---|---|
| M0 | Repository & environment audit | Architecture, debt and ownership documented | ✅ 2026-10-30 |
| M1 | Reference discovery | Inventory covers every reachable surface; unknowns tagged `?` | 🟡 partial — live session blocked (B-001); bundle/help/prior captures cover the surface |
| M2 | Inventory & documentation | 12 programme documents + progress system exist and agree | ✅ 2026-10-30 |
| M3 | Architecture & UX design | Decisions D-001…D-006 recorded; region model fixed | ✅ 2026-10-30 |
| M4 | Application foundation | Routing, auth gate, standalone layout, theme, state model | ✅ exists on `main` |
| M5 | Core music generation | Prompt → job → clip on timeline, with credits and failures | 🟡 implemented, unverified E2E |
| M6 | Player & timeline | Transport, loop, metronome, seek, zoom all behave | 🟡 implemented, unverified |
| M7 | Studio editing | Clips, tracks, mixer, automation, MIDI, undo | 🟡 implemented, unverified |
| M8 | Advanced audio | Stems, FX, mastering, export pipeline | 🟡 FX + stems present; mastering thin (G10, G11) |
| M9 | Projects & library | Studio home, projects, versions, shares, library | 🔴 in progress (W1) |
| M10 | Backend & MusicAPI | Own studio API, provider isolation, credits | ✅ done |
| M11 | Testing & optimisation | L1–L5 suites green; budgets met | ⬜ not started |
| M12 | Final verification | Matrix rebuilt from evidence; coverage reported | ⬜ not started |

## Working agreement

- One task → one branch → one worktree. Commit early; never mix tasks.
- Every change updates the matrix or the interaction spec in the same commit.
- No feature ships on a `?` evidence row.
- A blocked task is recorded in `PROJECT_BLOCKERS.md` and work continues elsewhere.

## Definition of complete (programme level)

1. Every inventory row is `VERIFIED` or explicitly `N/A` with a reason.
2. Journeys W-A…W-H pass in the current HEAD.
3. L1–L5 suites exist and are green.
4. No known data-loss path.
5. Coverage report published with real numbers, not estimates.
6. Documentation set matches the code.
