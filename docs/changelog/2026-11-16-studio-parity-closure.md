# Closing the Studio QA ledger — batch by batch

**Date:** 2026-11-16
**Source:** `docs/studio/reports/2026-11-16-agent-c-consolidated.md` (19 rows: 11 product,
7 cosmetic, 1 evidence). D1, D2 and C1 shipped earlier (`2026-11-16-studio-qa-fixes.md`).

Each entry names the ledger row it closes and the test that pins it.

## Batch A — share truthfulness, master chain, transport

### B4 — the share dialog no longer invents a contract

- The link field shows the **relative path**; Copy Link writes the absolute URL, so a dev
  origin can never appear in the dialog.
- The copy uses the captured guarantee again: “create their own editable copy” and “Your
  original project will remain unchanged — others can't edit or affect your version.”
- The expiry sentence is derived from the created share's `expires_at`; when the API returns
  no expiry, the sentence is omitted instead of claiming seven days.
- Tests: `studio-project-menu.spec.ts` asserts the relative value, the absence of a localhost
  origin, and the captured copy; the unit test asserts the clipboard gets the absolute URL.

### B3 — footer and master rack

- The footer strip now always shows the **master** chain (S26), matching the capture, instead
  of the selected track's. The per-track chain stays in the dock.
- The permanently disabled “Add Track Effects” button is gone: the plus is **“Add master
  effect”**, enabled, and opens the master dock.
- A project seeded from a song starts with a real master rack (compressor + 2× EQ) instead of
  an empty one (`lib/studio-seed.ts`, unit-tested).
- Tests: `studio-components.test.tsx` (live add control), `studio-seed.test.ts` (seeded chain),
  `studio-pixel.spec.ts` duplicate-key case moved to the master chain.

### B3 (transport geometry)

- `.se-head` is `auto 1fr auto` with the transport left-aligned, so it sits in the left flow as
  captured rather than floating in the centre.
- “Back to start” now uses the captured `<<` (rewind) glyph instead of a step icon.
- The Stop control is **kept**: it is an addition, not a capture replacement, and removing it
  would take working behaviour away. Recorded here as a deliberate divergence.

## Open in the ledger

B1 shortcuts panel · B2 onboarding · B5 menu order/labels · B6 clip info · B7 hidden-tracks
wording · B8/B12/B13 chrome sweep · B9/B10 plugin/MIDI polish · B11 library truth · the mirror
enqueue backoff.
