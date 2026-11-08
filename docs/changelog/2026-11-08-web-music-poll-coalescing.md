# Web-music read path no longer hammers Suno (and the API)

**Date:** 2026-11-08
**Surface:** `platform_api` (web music)
**Branch:** `fix/web-music-poll-coalescing`

## Summary

Production `GET /api/v3/web-music/generations/{id}` requests reached **200s+**
(681 requests over 5s in a two-hour window, max 215s), and unrelated endpoints
queued behind them — including `POST /api/v3/auth/refresh`, whose p95 hit
**13.5s** and max **89.7s** in the same window.

Cause: for a song whose callback had not landed, the read path polled the
provider **inline, once per pool key, with a 30s timeout each**
(`poll_suno_generate_with_pool`). `get_generation` could do that poll up to
three times per request (`_refresh_pending_from_suno`, `_ensure_cover_urls`,
`_ensure_durations`), and `music.camxora.com` polls the route every few seconds
from every open tab. With 3 active music keys that is easily 90–180s of provider
waiting per browser poll, multiplied by every polling client.

Those long requests also contribute to the DB-pool pressure (2 workers × 8
connections) that made auth refresh slow — the trigger behind the desktop
"Unauthenticated" logouts fixed earlier today.

## Product impact

- A generation poll returns the current DB row immediately when another poll is
  already running or one completed in the last 5 seconds, instead of hanging.
- Provider calls for a single song drop from "one multi-key scan per endpoint
  per browser poll" to at most one bounded scan per 5 seconds, shared by all
  requests on the worker.
- Completion still arrives through the normal Suno callback; the inline poll
  remains a fallback, now capped at 12 seconds instead of minutes.
- No change to billing, playback, or what the client sees besides faster
  responses.

## Technical impact

- `platform_api/services/web_music_service.py`
  - New process-wide read-path coalescer (`_pending_poll_results`,
    `_pending_poll_inflight`) with `_poll_pending_coalesced()`: 5s TTL,
    12s `asyncio.wait_for` cap, one in-flight poll per task, bounded cache
    (5 000 entries, 1h stale pruning).
  - `_refresh_pending_from_suno`, `_ensure_cover_urls` and `_ensure_durations`
    now use it; a timeout or provider error serves the cached row unchanged.
  - `reset_pending_poll_cache()` test hook.
- `platform_api/tests/test_web_music_poll_coalescing.py` (new, 5 tests):
  TTL sharing across request instances, concurrent coalescing, timeout serving
  the row, re-poll after TTL, and swallowed provider errors.

Background callers (`callbacks.py`, `batch_service`, `streaming_upload_service`)
keep using the direct poller — they need a fresh result and are not
browser-driven.

## Files touched

| File | Change |
|---|---|
| `platform_api/services/web_music_service.py` | Read-path poll coalescer + three call sites |
| `platform_api/tests/test_web_music_poll_coalescing.py` | New regression tests |
| `platform_api/CHANGELOG.md` | Entry |

## Migration/deploy

No schema change. API-only deploy; the change is scoped to `platform_api`.

## Tests

```bash
python -m pytest platform_api/tests/test_web_music_poll_coalescing.py -q
# 5 passed

python -m pytest platform_api/tests/test_web_music_*.py \
  platform_api/tests/test_suno_audio_resolver.py \
  platform_api/tests/test_reconcile_suno_404_terminal.py \
  platform_api/tests/test_protected_playback_theft_vectors.py \
  platform_api/tests/test_protected_playback_leaks.py -q
# 1249 passed
```

`ruff check` on `web_music_service.py` reports only pre-existing findings
(E402 import block, unused imports, `last_error`); none are on the added lines.

## Follow-ups

- The provider poll still scans every active key per call. Recording the owning
  key id on `suno_tasks` would cut each scan to one request.
- DB pool sizing/acquire timeout (`create_pool(min_size=4, max_size=8)`, no
  acquire timeout) still lets a stuck query queue behind others; consider a
  bounded acquire + slow-acquire logging.
- `music.camxora.com/create` still refreshes auth every ~3s while signed out.
