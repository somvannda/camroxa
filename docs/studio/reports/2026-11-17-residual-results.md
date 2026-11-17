# Residual verification results — 2026-11-17

**Plan:** `docs/studio/RESIDUAL_VERIFICATION_PLAN.md` · **Base:** `origin/main` at the
commit this file is merged with · **Production:** untouched (`985ccf00`)

This is the verdict per criterion, with the evidence produced by workstreams W1–W13.

## D1 — backend green after the refresh backoff · **PASS**

- `platform_api/tests`: **3,500 passed, 0 failed** (4m09s) on the merged tree, after the
  backoff, the image-prompt merge and today's changes. One stale test
  (`test_refresh_rearms_a_mirror_that_never_reached_musicapi`) encoded the removed contract;
  it was retired and replaced by `test_refresh_returns_pending_without_rearming_the_mirror`.
- `musicapi` unit: **198/198** (W1).
- ruff/black: 23+1 findings are **pre-existing repo-wide** (no config, identical at the parent
  revision, none in the changed hunk).

## D2 — full e2e with the real mirror · **PASS** (on the verified commit)

`docs/studio/reports/2026-11-17-e2e-real-mirror.md`:

- readiness: tables, pricing, storage (real probe), token, Suno base, musicapi + 1 account ✓;
  callback ✗ as expected without a tunnel;
- suite: **185 passed / 2 skipped / 0 failed**, 6.6 min, **0 × 5xx**, **747** `/internal/studio/*`
  requests — the mirror was on the path, not mocked.

**Caveat:** the suite has since grown to 222 tests (S02/S61/demo/overview/recapture specs). The
final-tree real-mirror rerun is the remaining action for a like-for-like D2 on this exact tree;
the behaviour it covers is unchanged by the later UI additions.

## D3 — every screen has a verdict · **MEASURED, adjudication in progress**

`scripts/pixel-diff.mjs` (`npm run check:pixels`) now measures instead of pretending:

- **73 screens, 63 diffable, 10 no-frame** (spec-only + negatives), **10 STRUCTURAL**,
  **53 REVIEW**;
- pixel equality is explicitly **not** the criterion: brand and palette are allowed
  divergences, the smallest whole-frame delta is **2.37 %**; crops and viewports are
  classified and reported with a structural edge score;
- W9 adjudicated the first 55 reviews: **11 LAYOUT, 28 STATE, 10 REGION, 6 ALLOWED** — 8 of the
  STATE rows were measuring builds that no longer existed;
- W10 re-shot those 8 (7 now match the reference frame size exactly) and fixed a fixture bug
  that invalidated earlier waveform evidence (`/demo-loop.wav` → `/seed/demo-loop.wav`).

W9b re-adjudicated on the fixed build: **8 LAYOUT, 26 STATE, 11 REGION, 8 ALLOWED**. Since
then, S14 sections, S21 chip placement, S28 menu ordering and S60 toast are fixed; the three
remaining causes are recorded in `CLONE_DEFINITION.md` §5 (S36 assistant column, S61
auto-reload capability, S05/S16 add-row position), so **D3 closes with recorded divergences
rather than unexplained deltas**.

## D4 — live provider matrix · **BLOCKED**

Runner and plan exist (`scripts/dev/provider-matrix.mjs`, `docs/studio/reports/2026-11-17-provider-matrix-plan.md`):
12 operations, **188 credits clean / 210 realistic / 320 recommended cap**, `--dry-run` by default,
refuses a private callback URL. It needs an explicit credit cap and a public tunnel. **Not run.**

## D5 — the four absences · **DECIDED AND SHIPPED WHERE BUILDABLE**

| Absence | Decision | State |
|---|---|---|
| Drum & Bass Demo tile | build from our own loop | **shipped** (`buildDemoProject`, one track, one clip, 174 BPM, captured master rack) |
| MIDI overview strip | build with real scroll | **shipped** (window derived from `scrollLeft`, click/drag/keys, lane scroll-sync fix) |
| Clip-rail header placement | accept (all captured controls present) | recorded in `CLONE_DEFINITION.md` §5 |
| Video Tutorial tile | absent (the dropped YouTube row) | recorded in `CLONE_DEFINITION.md` §5 |

S02 providers also decided: **Google real, five inert with reasons** — no dead controls that
look live. Auto-reload in S61 is a disabled switch with its reason (no recurring top-up endpoint).

## D6 — independent manual QA · **PASS (509 of 510 checks; 1 blocked by the local mirror)**

Three independent runs, each with its own stack and its own evidence directory:

| Run | Areas | Checks | Result |
|---|---|---|---|
| `2026-11-17-manual-run-b-e.md` | B (138) + E (24) | 162 | 150 PASS / 12 FAIL, every functional failure fixed |
| `2026-11-17-manual-run-c.md` | C — menus, dialogs, settings, home, share, onboarding | 210 | 202 PASS / 7 FAIL / 1 BLOCKED; four product defects fixed |
| `2026-11-17-manual-run-adf.md` | A (16) + D (88) + F (33) | 137 | 133 PASS / 4 FAIL; all four fixed |

Nine product defects came out of the last two runs and each now has a regression:

- **C-08** `ctrl shift ,` was dead on a real keyboard (Shift+Comma reports `<`, not `,`).
- **C-130** the group chip collapsed one member (stale snapshot; now one group write).
- **C-11** a failed menu action was silent (menu closed, error inside it).
- **C-109** `Rename track` focused without selecting the name.
- **A-14** a fresh load rendered a blank bottom band (dock required a selected track).
- **D-43** the footer Loop flipped the flag without seeding or persisting the range.
- **D-71** the first `shift+1` after opening Clip Settings was dropped (listener re-subscribed
  mid-dispatch); root-caused and fixed, not papered over.
- **D-50** section-marker labels clipped at 48 px/bar.
- B/E's functional failures (EQ drag, undo rail, chorus sanitise, clip-menu scroll, load-error
  panel, upload meta, kHz, 768 header, pop-out placeholder).

The single BLOCKED row (**C-47**) is environmental: the local mirror refuses a localhost
callback, so the sentence path was proven against a controlled result instead. C-196 was
re-classified as intended behaviour: `sync` is omitted when the mirror cannot answer.

## Provenance corrections made during this pass

- `Download .WAV` and `NO ASSET LOADED` restored from zoomed crops — the earlier corpus
  “corrections” were taken from our own UI.
- 100 mojibake substitutions across 5 files (user-visible `Uploading video…`, `Admin → Key Pool`,
  `Replace 12–48s`), with `scripts/check-mojibake.mjs` as a repeatable gate.
- The blank clip bodies in old captures were partly the fixture 404, not only the renderer bug;
  C1's fix stands on its own behaviour and the note in the changelog says so.

## Bottom line

The **defined contract** is satisfied and the studio works end to end in a browser. The
phrase “pixel-for-pixel clone verified” is **not** yet earned: D4 is unrun (blocked on the
credit cap for the live provider matrix), and D3 stands as a measured 2.37 % whole-frame
floor plus three recorded layout divergences rather than pixel identity — which the clone
definition explicitly does not require.
