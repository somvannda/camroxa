# Web music: enhance Suno style generation prompt

**Date:** 2026-08-17

## Summary

- Music Style Tags AI now expands/refines the user's Styles field into a Suno-ready production prompt.
- Sends structured context (style, title, lyrics excerpt, song description) instead of a single generic seed string.
- Output is truncated to Suno's 1000-character style limit.

## Surfaces

- `platform_api` — `generate_styles`, `build_web_music_style_user_prompt`
- `music_web` — create page style wand passes full form context
