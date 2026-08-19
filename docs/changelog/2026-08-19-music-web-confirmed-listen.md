# Music web: confirmed email required to listen

**Date:** 2026-08-19  
**Branch:** `fix/music-web-confirmed-listen`

## Summary

Unconfirmed accounts could still hit catalog `/stream`, `/play-url`, Create `/stream`, and `/web-music/play/{token}`. Listening now requires a confirmed email, same as Create. Official MP3 / WAV / LRC / SRT downloads stay paid-only.

## Product impact

- Guest: still cannot play (401).
- Signed in, email not confirmed: 403 on play/stream/download; UI stays on verify-email.
- Confirmed free user: can listen through the proxy; cannot download files.
- Paid (web subscription or desktop license): can download MP3, WAV, LRC, and SRT.

## Technical impact

- Removed `_is_unconfirmed_play_path` from `get_current_user`. Unconfirmed allowlist is only `/users/me`, profiles status, logout, and refresh.
- Player refuses play when `email_confirmed === false` and sends the user to `/verify-email`.
- Download endpoints still call `_require_download_access` (unchanged).

## Files touched

- `platform_api/middleware/auth.py`
- `platform_api/tests/test_auth_middleware.py`
- `music_web/src/components/player-provider.tsx`

## Migration/deploy

No database migration. Sandbox API restart + music_web rebuild. Production only on explicit request.

## Tests

- Unconfirmed GET stream, play-url, play token, Create stream, and download all raise confirm-email 403.
- Unconfirmed GET `/users/me` still succeeds.

## Follow-ups

Production API + music_web when asked.
