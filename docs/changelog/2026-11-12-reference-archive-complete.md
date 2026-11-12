# Reference capture archive complete: 65/65 screens

**Date:** 2026-11-12
**Branch:** `feat/studio-rebuild`
**Surfaces:** docs/studio/reference
**Status:** captured, documented, not deployed

## Summary

The last two open reference states — S60 (policy/moderation refusal) and S61
(insufficient credits) — are now captured with genuine triggers. The archive stands at
**65 DONE, 0 PART, 0 OPEN, 85 images**, with a measured spec section for every screen
(through §103).

## S60 — lyrics moderation

On `https://suno.com/create`, Advanced mode, four lines of a known copyrighted song were
submitted. Suno returned a bottom-centre toast:

> **Couldn't generate that.**
> Your lyrics contain copyrighted material. Please change it and try again.

The composer kept the lyrics, style and title, so the refusal is recoverable in place.
The provider feed confirmed the draft as `status: "error"` with
`metadata.error_type: "moderation_failure"` and the same message, so this is a real
server-side gate rather than a client warning.

Image: `screens/S60-moderation.jpeg` (1440 x 900), spec §102.

## S61 — insufficient credits

A paid test account (`kduke168@gmail.com`, 50 credits) was driven through five
generations until its balance reached **0**. The next Create submission opened:

- centred **“You're out of credits”** modal, **Monthly credits used 100%**, auto-reload
  **$6**, **Turn on auto-reload** / **Not now**;
- bottom-left **“You're out of songs for the month. Buy more credits.”** toast.

Image: `screens/S61-insufficient-credits.jpeg` (1440 x 900), spec §103.

A free account was tried first and does not work for this state: it hit **“Out of songs
for now / You can create again in 10:25”** at 50 credits, because the daily song cap
intercepts before the balance reaches zero. S61 therefore needs a paid balance that can
actually reach 0.

## Documentation

- `SUNO_STUDIO_IMPLEMENTATION_SPEC.md` — §102 (S60) and §103 (S61)
- `SCREEN_MANIFEST.md` / `SCREENSHOT_INDEX.md` — both DONE, 85 images
- `CAPTURE_GAPS.md` — final state and the free-tier finding
- `CAPTURE_LOG.md` — Run 7 (S60) and Run 8 (S61)
- `SESSION_HANDOFF.md`, `PROJECT_PROGRESS.md`, `PROJECT_NEXT_ACTIONS.md`,
  `PROJECT_BLOCKERS.md` — tallies and open items closed

## Notes

- `kduke168@gmail.com` is now at **0 credits**; `iamdukekh1987@gmail.com` spent 50 free
  credits in the failed free-tier attempt (replenishes daily).
- No product code changed in this pass; the previous code head was green on typecheck,
  UI gate, Vitest 277, Playwright 135/2 skipped, and backend 3361.
- The failed S60 generation remains in My Songs as a non-playable error row and can be
  trashed there.
