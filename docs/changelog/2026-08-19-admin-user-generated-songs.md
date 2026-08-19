# Admin user detail: Camxora Music generations

**Date:** 2026-08-19  
**Surfaces:** `platform_api`, `admin_portal`  
**Branch:** `feature/admin-user-generated-songs`

## Summary

Admin user detail now shows the user's Camxora Music workspace tracks in the
same layout as music.camxora.com: list + version cards, prompt/settings
sidebar, and in-page playback.

## Product impact

- Click a version to inspect model, vocal gender, style influence, weirdness,
  audio weight, negative tags, style prompt, and lyrics.
- Play MP3 from the cover, sidebar, or bottom player. Download LRC / SRT / MP3.
- WAV stays on music.camxora.com (Suno conversion). Workspace create/rename is
  not available in admin (read-only).

## Technical impact

- `GET /api/v1/users/{id}/web-music/workspaces`
- `GET /api/v1/users/{id}/web-music/generations`
- `GET /api/v1/users/{id}/web-music/generations/{task_id}/audio`
- `GET /api/v1/users/{id}/web-music/generations/{task_id}/download`
- `GET /api/v1/users/{id}/web-music/generations/{task_id}/timed-lyrics`

Reads `web_music_workspaces` + `suno_tasks` (`source = web_music`). Missing
tables/columns return an empty list instead of 500.

## Files touched

- `platform_api/routers/admin_user_web_music.py`
- `platform_api/routers/users.py`
- `platform_api/tests/test_admin_user_web_music.py`
- `admin_portal/src/pages/users/user-generated-songs.tsx`
- `admin_portal/src/pages/users/user-detail.tsx`
- `admin_portal/src/hooks/use-users.ts`

## Migration / deploy

No migration. File-scoped sandbox sync of the new admin router, users router
include, and admin user-detail UI.

## Tests

- Admin can list workspaces + generations with settings/clips.
- Non-admin gets 403.
- Unknown user gets 404.
- Audio stream returns MP3 bytes.
