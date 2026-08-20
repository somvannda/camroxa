# Music web: mobile logo, menu, Create, and playlists

**Date:** 2026-08-19  
**Surfaces:** music_web

## Summary

Phones lost the Camxora mark in the logged-in header, and the desktop sidebar disappeared below `md`, so Create and Playlists were hard to reach. The header now shows a compact logo, a floating menu button sits on the left over the player, and Create/Playlists stack for one-handed play.

## Product impact

**Before:** Mobile header was search + account only. The left nav was gone. Create used a cramped two-column workspace with tiny download chips. Playlist play controls hid until hover.

**After:** Compact Camxora Music lockup in the header. A 7px-radius menu button floats just above the left of the player and opens the same sidebar. On phones the Create button sits on that same row, filling the space after the menu. Player title and controls are centered. Create defaults to Simple. Playlists use full-width create/play buttons and always-visible play on each row. Focusing song description no longer triggers iOS input zoom; the menu and Create stay above the keyboard.

## Technical impact

- Shared `BrandLockup` for sidebar, mobile drawer, and header.
- Sidebar owns a `md:hidden` FAB (`z-60`, just above the player) and a left drawer (`z-80`) that locks body scroll.
- `--music-player-height` is `10.5rem` below 768px; `--music-menu-clearance` keeps page content and the Create CTA clear of the menu button.
- Mobile Create/Upgrade is `w-full` in the remaining row after the 48px menu (`left: 4.25rem` to `right: 0.75rem`).
- Create text fields use 16px on phones (plus a global input/textarea rule) so iOS does not auto-zoom. `interactive-widget: resizes-content` plus `--music-keyboard-inset` from `visualViewport` keep the menu and Create above the keyboard.
- Mobile player title/artwork sit centered above the centered transport controls.

## Files touched

- `music_web/src/components/brand-lockup.tsx` (new)
- `music_web/src/components/sidebar.tsx`
- `music_web/src/components/site-header.tsx`
- `music_web/src/components/player-bar.tsx`
- `music_web/src/components/user-menu.tsx`
- `music_web/src/components/create-page-client.tsx`
- `music_web/src/components/music-form-ui.tsx`
- `music_web/src/components/playlists-page-client.tsx`
- `music_web/src/components/playlist-detail-page-client.tsx`
- `music_web/src/app/globals.css`
- `music_web/src/app/layout.tsx`
- `music_web/src/lib/use-mobile-keyboard-inset.ts` (new)
- `music_web/CHANGELOG.md`
- `scripts/deploy/hotfix_music_web_mobile_khqr_production.py`

## Migration/deploy

No API or DB change. Sandbox: `python scripts/deploy/rebuild_music_web_sandbox.py`. Production ships with the KHQR/mobile hotfix (`scripts/deploy/hotfix_music_web_mobile_khqr_production.py`).

## Tests

- At 375px: logo visible in header; menu button sits over the left of the player and opens Create/Playlists.
- Create button fills the row after the hamburger (not a short pill).
- Focus song description on iPhone: page does not zoom; hamburger and Create stay visible above the keyboard.
- Create: Simple is default, a generated clip can play from the cover, details stack under the list.
- Playlist: Play is always visible; tapping a row starts playback in the bottom player.
- At 768px+: desktop sidebar and header search unchanged; menu button hidden.

## Follow-ups

- None.
