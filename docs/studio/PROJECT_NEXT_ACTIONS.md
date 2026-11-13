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

65 screens: **65 DONE, 0 PART, 0 OPEN**, 85 images, spec through §103.

All rows are captured; `reference/CAPTURE_GAPS.md` is the evidence log. S30, S32, S44 and S60 are closed (§97–§102, with S32 as a negative); the §100
detail-rail image is captured too; no captures remain.

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
| G6 marquee + multi-drag + C/V/D · G7 snap · G8 drag threshold · G9 delete + focus · G16 clip provenance · G17 audition speed · G18 first-run onboarding · G19 visible-window culling · G20 touch targets · G23 project menu · G24 ghost drag + settings · G25 Learn + hover help · G26 add-track menu + keys · G27 metronome click · G28 automatic versions · G29 serialized writes · G30 offline replay · G31 home menu stacking · G32 share fork target · G33 loop playback + seek · G34 fit to content · G35 plugin chains in the engine · G36 live chain edits · G37 live mute/solo · G38 no double graph on first play · G39 solo-aware bounce · G40 master fader + main mute · G41 track sliders + collapse · G42 stop vs rewind · G43 editable meter · G44 shortcut map · G45 trim grips · G46 fade + robust drag · G47 clip menu + split + ruler seek · G48 clip info panel · G49 history side panel | **G12** done - stems list (B-004/B-005 closed 2026-11-10) · **G21** done - arm + microphone takes (D-020) |

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

## Phase 5 - Suno Studio project mirror (2026-11-13)

Phase 1 is implemented: `musicapi/migrations/0044_studio_suno_sync.sql`, the
pinned-account link, the coalescing outbox and the editor's sync dot. Full details
in `SUNO_STUDIO_SYNC.md`.

Next, in order:

1. **Capture one live `GET /api/studio/project/{id}`.** The transport contract and
   every top-level `state` key are decoded from the shipped bundle, but the nested
   track/clip/note/plugin field names still need a real sample. This is the only
   thing blocking `STUDIO_SUNO_STATE_SYNC=1`.
2. **Prove the link end to end.** With a live account, create a project and confirm
   exactly one Suno project appears (and a retry does not create a second).
3. **Enable the arrangement merge** and run the round-trip test in
   `SUNO_STUDIO_SYNC.md` section 12.
4. **Pull/reconcile + conflict UI** (`Load Suno`, `Keep mine`, `Duplicate`).
5. **Coverage matrix = removal list** (D-034, `PARITY_REMOVAL_LIST.md`).

Known test lesson (fixed 2026-11-13): the automation and section-marker specs used
to reload while a serialized document write was still queued, so the reload won
the race. The editor now mirrors a queued write into the local draft (no data
loss for real users) and the specs wait for the `Saved` chip before reloading.
The suite is green at `--workers=4`.
