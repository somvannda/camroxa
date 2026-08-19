# Web music Simple prompt follows Suno V5 limits

**Date:** 2026-08-18  
**Surfaces:** `platform_api`, `music_web`  
**Branch:** `fix/web-music-simple-prompt-suno-limits`

## Summary

Simple-mode **Song description** was capped at **500** characters by our API, which is not a Suno custom-mode limit. Create now follows Suno V5 / V5.5:

| Field | Suno | Create |
|---|---|---|
| Custom lyrics | 5000 | Advanced lyrics / prompt-as-lyrics |
| Style | 1000 | Simple description + Advanced styles |
| Lyrics-job prompt | 200 | Simple still uses the first 200 chars to write lyrics |

## Behavior

- `POST /web-music/generate` `prompt` max is **5000** (same as custom lyrics).
- Simple UI clamps to **1000** with a live counter (Suno style).
- Simple generate uses the description as **style** instead of defaulting to “Contemporary pop”.
- Suno’s lyrics API still only reads ~200 characters when writing lyrics.

## Files

- `platform_api/routers/web_music.py`
- `platform_api/services/web_music_service.py`
- `platform_api/tests/test_web_music_router.py`
- `music_web/src/components/create-page-client.tsx`
