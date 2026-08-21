# iOS Safari play traces + AbortError

**Date:** 2026-08-21  
**Branch:** `bugfix/ios-safari-playback`  
**Surfaces:** music_web, platform_api

## Summary

iPhone Safari cannot be debugged from desktop DevTools in a useful way. The player now posts stage traces (`play_start`, `play_session`, `play_path`, `play_chunks`, `play_decode`, `play_ok`, `play_error`) to `POST /api/v1/web-music/licenses/client-trace`. The API writes `music_web_play_trace` to journald and stores `playback_events.detail`.

Safari `AbortError: The operation was aborted` was also treated as a red player error. That usually means `audio.load()` after clearing src, or play interrupted after the tap. The player now keeps Web Audio alive during license/chunk fetch, does not `load()` an empty src, and maps abort to “Tap play again” while still logging the real error.

## Product impact

- Next iPhone play on sandbox leaves a server-side trail.
- Abort should no longer show as a raw red Safari sentence.

## Files touched

- `platform_api/routers/web_music_licenses.py`
- `platform_api/services/content_license_service.py`
- `platform_api/migrations/versions/109_playback_event_detail.py`
- `music_web/src/lib/content-license.ts`
- `music_web/src/lib/mpeg-playback.ts`
- `music_web/src/components/player-provider.tsx`

## How to read traces (sandbox)

```
journalctl -u camxora-api --since "10 min ago" | grep music_web_play_trace
```

```
sudo -u postgres psql -d camxora_platform -c \
  "SELECT created_at, event, detail FROM playback_events ORDER BY id DESC LIMIT 30;"
```
