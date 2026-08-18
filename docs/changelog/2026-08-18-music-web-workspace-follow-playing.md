# Create workspace selection vs play, and ready-only playback

**Date:** 2026-08-18  
**Surfaces:** music_web, platform_api

## Summary

Create workspace clicking a row inspects that clip and does not start audio. Play moves selection to the playing clip. Covers show a spinner until Ready, then a play icon; while playing, the purple equalizer sits on the cover. Titles are inline-editable and save on blur. WAV download no longer runs through the MP3-only downloader.

## Product impact

- Click title/row body: select only. Audio does not change.
- Click the cover: play/pause. Playing shows the equalizer on the image.
- Click the song title to rename that clip only; blur or Enter saves automatically. Version 1 and Version 2 keep separate titles.
- The v5 / v5.5 tag sits after Ready on the second line.
- Cover equalizer uses fixed-height pink bars on the artwork (visible while that clip is current).
- Download badges keep their size; the spinner overlays the label and stays fully visible while loading.
- WAV download converts via Suno and returns a real WAV file. Mislabelled `audio/mp4` WAV URLs are accepted. WAV record-info 404s stay pending instead of failing the job. Polling waits up to ~60s and reuses an existing WAV task id on retry.

## Technical impact

- WAV uses `download_suno_wav_bytes` (RIFF/WAVE). The MP3 helper rejected WAV bytes. WAV downloads skip the MP3 `audio/mp4` content-type reject, retry a previous `failed` conversion, and map unexpected storage/runtime errors to a retryable 422.
- HTML/RSC responses send `Cache-Control: no-store` so Create does not keep stale Turbopack chunks after a sandbox rebuild.
- `PATCH /api/v1/web-music/generations/{id}` with `variant=ok|alt` updates `suno_tasks.title_ok` / `title_alt` so Version 1 and Version 2 can be renamed independently.
- Frontend retries WAV while conversion is still pending.
- Owner play URLs use `/stream/ok` and `/stream/alt` so Version 1/2 do not share one browser cache. The API accepts both path and `?variant=` stream routes.

## Files touched

- `music_web/src/components/create-page-client.tsx`
- `music_web/src/lib/web-music-api.ts`
- `music_web/src/components/playing-equalizer.tsx`
- `music_web/src/app/globals.css`
- `music_web/next.config.ts`
- `platform_api/services/web_music_service.py`
- `platform_api/clients/suno_client.py`
- `platform_api/services/suno_audio_resolver.py`
- `platform_api/migrations/versions/105_web_music_clip_titles.py`
- `platform_api/routers/web_music.py`
- `platform_api/tests/test_web_music_router.py`
- `platform_api/tests/test_suno_audio_resolver.py`
- `music_web/CHANGELOG.md`
- `platform_api/CHANGELOG.md`
- `scripts/deploy/hotfix_music_web_workspace_follow_playing_sandbox.py`
- `scripts/deploy/hotfix_music_web_workspace_follow_playing_production.py`

## Migration/deploy

File-scoped sandbox hotfix already applied: `title_ok` / `title_alt` plus WAV columns, API restart, music web rebuild. Production uses the same allowlisted files via `hotfix_music_web_workspace_follow_playing_production.py` (ALTER IF NOT EXISTS, no `npm ci`, no `.next` wipe).

## Tests

- Play a Ready clip: equalizer is on the cover, not next to Ready.
- Click WAV: badge size stays the same, spinner overlays the label, file downloads.
- Click a title, rename Version 1: Version 2 keeps the old name.
- `pytest platform_api/tests/test_web_music_router.py platform_api/tests/test_suno_audio_resolver.py`

## Follow-ups

- None.
