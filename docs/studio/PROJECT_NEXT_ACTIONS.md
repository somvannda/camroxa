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

65 screens: **60 DONE, 3 PART, 2 OPEN-by-design**, 78 images, spec through §96.

The three `PART` (S30 warp markers, S32 CC lane, S44 convolution IR) and the two
`OPEN` (S60 moderation, S61 credits) are parked in `reference/CAPTURE_GAPS.md`. They
are **opportunistic**, not blocking: fill them when the trigger happens naturally.
Do not spend another session on interactive archaeology for them.

## Phase 1 — W1 Studio entry: **DONE**

`/studio` is routed (`app/studio/page.tsx`), the home lists/resumes/creates projects,
card actions work, the auth gate falls back to marketing, and "Start from a song"
seeds a project from a library generation.

## Phase 2 — W2 trustworthy persistence: **DONE**

W2.1 save status · W2.2 409 conflict detection + reload/overwrite · W2.3 offline draft
recovery · W2.4 unsaved-changes guard. All four are deliberate divergences from the
reference, which has none of them.

## Phase 3 — W3 editor completeness: mostly done

| Done | Remaining |
|---|---|
| G6 marquee + multi-drag + C/V/D · G7 snap · G8 drag threshold · G9 delete + focus · G16 clip provenance · G17 audition speed · G18 first-run onboarding · G19 visible-window culling · G20 touch targets · G23 project menu · G24 ghost drag + settings · G25 Learn + hover help · G26 add-track menu + keys | **G12** library: stems tab (needs a finished stems job, B-005) · **G21** track arm (needs recording) |

## Phase 4 — W4 advanced audio, then W5 tests, then W6 verification

Unchanged from the roadmap: mastering chain (W4.1), stems with pricing (W4.2),
export matrix (W4.3), loudness readout (W4.4), then the test suite (W5.1–W5.5) and
the coverage re-walk (W6). Export normalisation (G11) landed as an opt-in mix/range
gain match — see D-010.

## Rules

1. One task per branch, one commit per logical change, gates before every commit:
   `cd camxora.com && npm run typecheck && npm run check:ui`.
2. If a task turns out to need a spec section that does not exist, capture it first —
   one screenshot, one section, one commit.
3. Keep this file as the *order*; never let it drift into a second plan.
