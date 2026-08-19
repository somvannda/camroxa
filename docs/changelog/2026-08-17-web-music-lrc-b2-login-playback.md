# Web music LRC on Backblaze + login-required playback

**Date:** 2026-08-17  
**Surfaces:** platform_api, music_web

## Summary

Timed lyrics (LRC) are cached on Backblaze alongside MP3/WAV. Playback now requires a logged-in session; free-tier users can still play.

## Backend

- Migration `101_web_music_b2_lrc_storage`: `b2_lrc_storage_key_ok/alt` + upload timestamps on `suno_tasks`.
- LRC path: `web-music/{user_id}/{song_slug}-{ok|alt}.lrc` (SRT derived from cached LRC on download).
- `download_timed_lyrics` serves from B2 when available; otherwise fetches Suno and schedules B2 upload.
- MP3 upload pipeline also schedules background LRC upload.
- `/api/v1/web-music/play/{token}` requires auth (no anonymous IP playback).
- `/api/v1/public/streaming/tracks/{id}/play-url` requires auth.

## Frontend

- Player redirects to login when a logged-out user tries to play.

## Notes

- LRC/SRT **downloads** still require a paid subscription (unchanged).
- Free logged-in users can stream/play catalog and public playlist tracks.
