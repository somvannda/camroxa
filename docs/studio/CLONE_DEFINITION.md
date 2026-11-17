# Clone definition — what “1:1 with Suno Studio” means here

Signed 2026-11-15. This is the contract the `check:clone` gate enforces.

## 1. Scope

The **web Studio** (`camxora.com/components/studio` and its routes), measured against the
reference captures in `reference/screens` (1689×1277, DPR 1) and the strings recovered from
the shipped bundle (`reference/ui-strings.md`, `derived-features.md`).

## 2. Definition of done (seven rules)

A build is clone-complete only when all seven hold:

1. **Coverage.** Every reference screen in `reference/PAIRING.json` is satisfied by either a
   paired capture in `docs/studio/compare/`, a named automated spec, or an explicit
   `negative` marker (matching Suno means the surface is absent here too). A named spec must
   contain at least one runnable declaration — a file that exists but is entirely skipped is
   not evidence. A capture may evidence more than one screen only when those screens declare
   `sharedWith` pointing at the frame's anchor, so recycled images are explicit.
2. **Geometry.** `reference/METRICS.json` is byte-identical to
   `camxora.com/public/studio-metrics.json`, every metric id is asserted by
   `tests/e2e/studio-pixel.spec.ts`, and paired screens are diffed per region at ±2 px.
3. **Content.** Every functional string in `reference/FUNCTIONAL_STRINGS.json` exists in the
   shipped UI — matched against `.ts`/`.tsx`/`.css` source **with comments removed by the
   TypeScript parser**, so neither a document nor a code comment can satisfy a string — and
   every captured menu row exists in the same order (YouTube Tutorials is the one sanctioned
   absence). The captured frames override the transcription **and the shipped UI**: S26 reads
   "Download .WAV" and S44 reads "NO ASSET LOADED". A gate that only proves *presence* cannot
   catch a label that was silently changed to match our own button, so any correction here
   must be read off the frame, not inferred from passing tests.
   `FUNCTIONAL_STRINGS.json` also carries an `additive` list: strings for our own operations
   (JSON export, normalise, transforms, import, wavetable designer) that no frame shows —
   checked for presence, never presented as captured.
4. **Behaviour.** Each captured interaction reproduces the reference behaviour; an addition
   may only *add* surfaces, never replace or move a captured control.
5. **Allowed divergence.** Brand wordmark/logo, palette tokens, our own help/marketing
   prose, and additive features (save status, conflict UI, offline replay, JSON export,
   IR/wavetable designers, per-clip comments). Nothing else.
6. **Provider parity.** Generation, stems and voice-persona paths verified against the live
   provider (ids recorded in `docs/changelog/2026-11-14-studio-1to1-completion.md`).
7. **Gate.** `npm run check:clone` fails on any uncovered screen, missing metric or missing
   functional string. A claim that is not gated is not a claim.

## 3. Functional strings vs prose

- **Functional strings** (menu rows, control labels, empty states, toasts, dialog actions)
  match the reference verbatim. This is rule 3.
- **Prose** (help copy, onboarding body text, marketing) is ours. It is allowed divergence
  under rule 5 because copying it would be a brand decision, not a behaviour one.

## 4. Additive features

These ship visibly and are **not** clone violations, because they never replace a captured
control: save status + retry, 409 reload/overwrite, offline draft/replay, project JSON
export, Wavetable/IR designers, FX sends, track groups A–D, master spectrum, MP3 export,
project JSON import, clip comments, presence, supersaw audition speed.

## 5. Known reference facts to keep matching

| Fact | Consequence |
|---|---|
| There is **no mixer surface** (S47) | We do not ship one |
| There is **no conflict UI** (S59) | Our 409 UI is additive |
| Deletion is **soft with recovery** (S04/§56) | Recently Deleted + restore |
| Learn has **YouTube Tutorials** | Dropped by product decision - the only sanctioned missing row |
| Start overlay has **Drum & Bass Demo** (S03/S06) | No bundled demo arrangement ships, so the tile would open nothing; recorded absence |
| Start overlay has **Video Tutorial** (S03/S06) | Same content as the dropped YouTube row; recorded absence |
| Clip rail header sits **inside the floating card** (S27) | The captured controls are all present (back, title, like/dislike, art, Remix, player, tabs); the card layout is ours, not a replacement |
| MIDI editor has **no overview strip** | The grid zooms 1–12× instead of scrolling a mini-map; an overview with no scroll position to reflect would be decorative |
| Footer strip shows the **master chain**, not the selected track’s (S26) | Deliberate: the capture’s footer centre is the master rack; per-track chains live in the dock |

The start overlay ships **Edit Your Song, Upload Audio, Create a song, Open a project and
Empty Project**, plus the captured ✕ and "Browse Studio projects ›" pill.

## 6. Sign-off checklist

- [x] `node scripts/check-clone-parity.mjs` exits 0 (73/73 screens, 70/70 strings)
- [x] Playwright, Vitest, platform pytest, musicapi unit green
- [x] Typecheck, `check:ui`, `next build` clean
- [x] `PAIRING.json` has no `capture: TBD` entries
- [x] Changelog and handoff updated

Signed off 2026-11-15 on `main` after the ledger reconciliation (`fb555d02`) and the
contract-test merge (`a9540403`).
