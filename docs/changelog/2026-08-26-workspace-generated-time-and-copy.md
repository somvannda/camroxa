# Workspace generated time and copy actions

**Date:** 2026-08-26  
**Surfaces:** music_web

## Summary

Create workspace rows and the selected-track header now show when the song was generated, after the model tag. Style and lyrics in the detail panel have a copy button.

## Product impact

- List and right-panel subtitle look like `3:17 · Ready v5.5 10:30 AM`.
- Same-day clips show clock time only; older clips add the date.
- Style and lyrics headers have a copy icon that switches to a check after a successful copy.

## Technical impact

- Uses existing `created_at` on web-music generation payloads. No API change.
- Time formatting lives in `music_web/src/lib/clip-display.ts` so the locale/day rules can be unit-tested.

## Files touched

- `music_web/src/lib/clip-display.ts`
- `music_web/src/lib/clip-display.test.ts`
- `music_web/src/components/create-page-client.tsx`
- `music_web/CHANGELOG.md`

## Migration/deploy

Rebuild music web on sandbox. Production stays untouched until asked.

## Tests

- `node --test --experimental-strip-types music_web/src/lib/clip-display.test.ts`
- On Create: Ready rows show a time after `v5.5`; the detail header matches.
- Copy style and lyrics; clipboard contains the visible text.

## Follow-ups

- None.
