# Music web — embed Khmer OS Siemreap

**Date:** 2026-08-26  
**Surfaces:** music_web

## Summary

Music web only shipped Inter and Outfit. Those faces have no Khmer glyphs, so titles and lyrics in Khmer Unicode showed as boxes or fallback system junk. The site now self-hosts **Siemreap** (Khmer OS Siemreap, OFL) the same way it already hosts Inter and Outfit.

## Product impact

- Khmer song titles, lyrics, and Create fields render with a proper Khmer face.
- English / Latin UI is unchanged (Inter / Outfit stay first in the stack).
- Khmer blocks drop negative letter-spacing so clusters do not collide.

## Technical impact

- `@fontsource/siemreap` (weight 400, Khmer subset) imported from root layout.
- Font stacks: `Inter` / `Outfit`, then `Siemreap` / `Khmer OS Siemreap`.
- `.font-khmer` (and `:lang(km)`) applied when copy contains Khmer.

## Files touched

- `music_web/package.json`
- `music_web/package-lock.json`
- `music_web/src/app/layout.tsx`
- `music_web/src/app/globals.css`
- `music_web/tailwind.config.js`
- `music_web/src/lib/khmer-text.ts`
- `music_web/src/lib/khmer-text.test.ts`
- `music_web/src/components/synced-lyrics.tsx`
- `music_web/src/components/track-row.tsx`
- `music_web/src/components/player-bar.tsx`
- `music_web/src/components/now-playing-rail.tsx`
- `music_web/src/components/create-page-client.tsx`
- `music_web/src/components/playlist-detail-page-client.tsx`
- `music_web/CHANGELOG.md`

## Migration / deploy

No schema change. Rebuild sandbox music_web only.

```bash
python scripts/deploy/hotfix_music_web_khmer_siemreap_sandbox.py
```

Production only when asked.

## Tests

```bash
node --test --experimental-strip-types music_web/src/lib/khmer-text.test.ts
```

## Follow-ups

None.
