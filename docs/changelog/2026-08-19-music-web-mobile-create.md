# Music web: mobile Create and pricing

**Date:** 2026-08-19  
**Branch:** `feature/music-web-mobile-create`

## Summary

Phone users could not generate music: the Create sidebar disappeared below `md`, the player covered the Create button, and the upgrade pricing dialog was a wide desktop overlay.

The logged-in shell now has bottom tabs (Create, Explore, Playlists, Profile), a compact player above those tabs, a Simple-first Create form, and a full-height pricing sheet.

## Product impact

- Signed-in phones can open Create, fill lyrics/style, tap Create, and play the result.
- Out-of-credit upgrade uses a scrollable full-screen plan sheet instead of a clipped desktop modal.
- Desktop (`md+`) keeps the sidebar, full player, and two-column Create layout.

## Technical impact

- CSS vars `--music-tab-bar-height` and `--music-chrome-bottom` size player + tab + iOS safe-area so Create CTA and main padding stay above chrome.
- Create defaults to Simple below 768px; clip details stack under the list instead of a `w-80` side column.
- Viewport `viewport-fit: cover` for safe-area insets.

## Surfaces

- `music_web` — shell, player, Create, pricing modal/page

## Files touched

- `music_web/src/components/mobile-tab-bar.tsx` (new)
- `music_web/src/components/shell-switcher.tsx`
- `music_web/src/components/site-header.tsx`
- `music_web/src/components/user-menu.tsx`
- `music_web/src/components/player-bar.tsx`
- `music_web/src/components/create-page-client.tsx`
- `music_web/src/components/music-form-ui.tsx`
- `music_web/src/components/pricing-modal.tsx`
- `music_web/src/components/pricing-page-client.tsx`
- `music_web/src/app/layout.tsx`
- `music_web/src/app/globals.css`

## Migration/deploy

Sandbox: `python scripts/deploy/rebuild_music_web_sandbox.py`  
No API/migration. Production only on request.

## Tests

Manual at 375px: tabs → Create, Simple default, Create visible above player, pricing sheet scrolls. At 768px+: sidebar and full player, tabs hidden.

## Follow-ups

None.
