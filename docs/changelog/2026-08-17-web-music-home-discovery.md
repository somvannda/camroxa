# Home page public discovery (merged tracks + top artists)

**Date:** 2026-08-17  
**Surfaces:** `music_web`

## Summary

Logged-out home (`/`) now shows the same merged featured/recent tracks as Explore (streaming catalog + public playlist tracks), without long style prompts on rows. Top artists (streaming + web music creators) appear below the hero for both logged-out and logged-in visitors.

## Changes

- `music_web/src/app/page.tsx` — fetch and merge recent tracks and artists server-side.
- `music_web/src/components/home-gate.tsx` — render merged track list with `showGenre={false}`; add Top artists grid with link to `/artists`.
