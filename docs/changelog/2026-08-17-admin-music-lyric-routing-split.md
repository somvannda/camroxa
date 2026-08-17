# Admin: separate Music Lyric from Desktop Lyric routing

**Date:** 2026-08-17

## Summary

- AI Routing shows **Music Lyric** (`web_music_lyrics`) as its own slot, separate from **Lyric (Desktop / Batch)** (`lyric`).
- Desktop lyric can stay on Suno; web music auto-generate uses chat LLMs via the Music Lyric slot.
- Credits and usage labels updated for both operations.

## Surfaces

- `admin_portal` — AI routing, credits, usage labels
- `platform_api` — usage transaction labels, cost estimates
