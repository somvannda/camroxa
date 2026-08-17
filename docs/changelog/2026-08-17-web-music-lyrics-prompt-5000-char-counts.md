# Web music: lyrics draft prompt 5000 + char counters

**Date:** 2026-08-17  
**Surfaces:** platform_api, music_web

## Summary

- Auto-generate lyrics draft prompt limit raised from 500 → **5000** (matches lyrics field / Suno custom mode).
- Create page shows live character counts for **Lyrics** (5000) and **Styles** (1000 / Suno limit).

## Why 500 existed

`WebMusicDraftRequest.prompt` reused the old 500-char song-description cap — not a Suno requirement. Lyrics body was already 5000.

## Files

- `platform_api/routers/web_music.py` — draft request max_length
- `platform_api/services/web_music_service.py` — LLM user prompt cap
- `music_web/src/components/music-form-ui.tsx` — `MusicCharCount`, shared limits
- `music_web/src/components/create-page-client.tsx` — counters + clamping
