# Create workspace list pagination (all songs, not just the first page)

**Date:** 2026-10-13  
**Surfaces:** music_web

## Summary

The Create workspace only ever showed the newest 40 songs, so a user with more songs saw
just the first page (40 songs = up to 80 version rows). The list now paginates: the first
page is 50 songs (100 version rows) and more load automatically as the user scrolls, with a
**Load more** fallback button and a *Showing all N songs* line.

## Product impact

- Workspace list no longer caps at 40 songs; every song in the selected workspace is reachable.
- First page shows 50 songs (Version 1 + Version 2 = up to 100 version rows).
- Scrolling near the bottom loads the next page automatically.
- A **Load more (X of Y)** button is shown as a manual fallback; when everything is loaded the
  footer reads *Showing all N songs*.

## Technical impact

- Frontend only. `music_web/src/components/create-page-client.tsx` now tracks `total` and
  `loadingMore`, keeps the existing `GET /api/v3/web-music/generations?limit&offset&workspace_id`
  contract, and requests `offset = items.length` for the next page.
- `WORKSPACE_PAGE_SIZE = 50` (API caps `limit` at 100 songs/page).
- An `IntersectionObserver` (`rootMargin: '400px 0px'`) on a sentinel element triggers the next
  page; `loadingMoreRef` prevents duplicate concurrent requests. Pages are deduped by generation id.
- Switching workspace and initial load reset `items`/`total` to page 0.
- Backend already supported `limit`/`offset`/`total`; no API change.

## Files touched

- `music_web/src/components/create-page-client.tsx`
- `music_web/CHANGELOG.md`

## Migration/deploy

Rebuild music web on sandbox. No API change. Production stays untouched until asked.

## Tests

- `npx tsc --noEmit` — no new errors (only pre-existing `.ts`-extension errors in `src/lib/*.test.ts`).
- `npm test` (music_web) — 50/50 pass.
- Manual: open Create with a workspace holding 40+ songs; scroll to the bottom and confirm more
  load; the footer shows *Load more (X of Y)* then *Showing all N songs*.

## Follow-ups

- Consider an **"All workspaces"** option so songs in other workspaces are visible without
  switching; today the list is scoped to the selected workspace by design.
