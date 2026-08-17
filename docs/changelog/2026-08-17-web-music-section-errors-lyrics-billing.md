# Web music: section errors, lyrics billing, sidebar account

**Date:** 2026-08-17

## Summary

- Style and lyrics AI assist errors now appear inside their collapsible sections instead of under the Create button.
- Lyrics auto-generate is credit-priced (`web_music_lyrics`) like style suggestions (`web_music_style`).
- Fixed credit unit mismatch (micro-units → display credits) via migration `094_web_music_lyrics_pricing`.
- Sidebar account card moved to bottom: menu links first, account stats last with name, email, sign out, equal songs/credits tiles.
- Free-tier daily quota (`N of M free today`) shown only when user is not Pro.
- Themed `MusicSelect` styling applied to workspace and model dropdowns.

## Surfaces

- `music_web` — create UI, sidebar, credit header, globals.css
- `platform_api` — `generate_draft` billing, migration 094
- `admin_portal` — AI routing label for `web_music_lyrics`

## Admin setup

1. Admin → AI Routing: assign models for `web_music_style` and `web_music_lyrics`.
2. Admin → Credits: approve pricing rows (default ~2 display credits each after migration 094).
