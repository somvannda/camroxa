# PROJECT NEXT ACTIONS

Resume here. **Execution order only** — the authoritative plans live elsewhere:

| Question | File |
|---|---|
| What is missing in the product? | `SUNO_STUDIO_GAP_ANALYSIS.md` (G1–G20) |
| In what order, with exit tests? | `IMPLEMENTATION_ROADMAP.md` (W1–W6) |
| What does the reference actually do? | `SUNO_STUDIO_IMPLEMENTATION_SPEC.md` (§1–§96) |
| Which screens are still uncaptured? | `reference/CAPTURE_GAPS.md` |
| Evidence per screen | `reference/SCREENSHOT_INDEX.md` |

## Phase 0 — Capture: **complete**

65 screens: **60 DONE, 3 PART, 2 OPEN-by-design**, 69 images, spec through §96.

The three `PART` (S30 warp markers, S32 CC lane, S44 convolution IR) and the two
`OPEN` (S60 moderation, S61 credits) are parked in `reference/CAPTURE_GAPS.md`. They
are **opportunistic**, not blocking: fill them when the trigger happens naturally.
Do not spend another session on interactive archaeology for them.

## Phase 1 — W1 Studio entry (start here)

The single largest structural gap: `/studio` is marketing, the chooser is an in-editor
dialog, and there is no `?project=` deep link.

| Order | Task | Exit test |
|---|---|---|
| **1** | **W1.1** `StudioHome` at `/studio` (authenticated): recent projects, resume card, new project, search/sort, archived toggle | renders with 0, 1 and 20 projects; empty state has a real CTA |
| 2 | W1.5 signed-out `/studio` keeps the marketing page with a sign-in CTA | signed-out render shows no broken controls |
| 3 | W1.2 create project → editor route with the id, autosaving | new project opens and persists |
| 4 | W1.3 card actions: open, rename, fork, archive, delete (confirm) | each action survives reload |
| 5 | W1.4 "Start from a song" seeds a project with that clip | clip appears on a track |

**Reference contract for phase 1:** §56 (My Projects chooser), §62 (signed-in entry
reopens the last project), §19.1 (library workspaces + project cards with ages),
§57 (loading), §58 (auth gate). This is the best-evidenced area we have — build it
without re-opening the reference.

## Phase 2 — W2 trustworthy persistence

Deliberate divergence, and say so in the code: the reference has **no** conflict UI
(§93) and **no** offline state (§96). We are adding both.

| Order | Task | Exit test |
|---|---|---|
| 6 | W2.1 autosave status (saved / saving / error / offline) + retry | kill the API mid-edit → status shows error, retry recovers |
| 7 | W2.4 unsaved-changes guard on navigation | leaving with pending writes prompts |
| 8 | W2.2 conflict handling on 409 (reload vs overwrite) | simulated 409 shows a resolution dialog |
| 9 | W2.3 local draft recovery offline | reload offline restores the draft with a banner |

## Phase 3 — W3 editor completeness

Work the `GAP` column of `SUNO_STUDIO_FEATURE_MATRIX.md` top-down. Highest-value
first, all evidenced: multi-select and marquee (G6), drag threshold (G8), snap
guideline (G7), clip focus on delete (G9), library stems/projects tabs (G12),
generation history (G16), first-run onboarding (G18).

## Phase 4 — W4 advanced audio, then W5 tests, then W6 verification

Unchanged from the roadmap: mastering chain (W4.1), stems with pricing (W4.2),
export matrix (W4.3), loudness readout (W4.4), then the test suite (W5.1–W5.5) and
the coverage re-walk (W6).

## Rules

1. One task per branch, one commit per logical change, gates before every commit:
   `cd camxora.com && npm run typecheck && npm run check:ui`.
2. If a task turns out to need a spec section that does not exist, capture it first —
   one screenshot, one section, one commit.
3. Keep this file as the *order*; never let it drift into a second plan.
