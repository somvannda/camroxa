# Auto Suno retry after lyrics polish

**Date:** 2026-07-17  
**Status:** implemented (sandbox deploy pending verification)

## Summary

When a user polishes lyrics for a failed or draft-ready history song, the platform API now validates the song and queues a background Suno retry in the same request. The desktop client sends batch/song context with polish and skips a redundant client-side retry when the server reports `suno_queued: true`.

## Product impact

- **Before:** Polish returned polished lyrics only; Suno retry required a separate manual action or unreliable client-side follow-up. Sandbox logs at 22:42 showed `POST /generation/polish-lyrics` 200 with no following `retry-suno`.
- **After:** Select a failed history row → Polish → server queues Suno automatically when `batch_id` and `song_id` are provided; UI shows "Suno queued" and refreshes progress.

## Technical impact

- **API:** `POST /generation/polish-lyrics` accepts optional `batch_id`, `song_id`, `title`, `album`; response includes `suno_queued`. Uses `BatchService.validate_song_suno_retry` + background `retry_song_suno`.
- **Wire:** `wire_dependencies.py` now wires `_get_batch_service` for the generation router (was missing — would 500 if batch dep added without wiring).
- **Desktop:** `LyricsPolishRequest/Response`, `PolishLyricsWorker`, and `music_view` pass history context and honor `suno_queued`.

## Files touched

- `platform_api/routers/generation.py` (polish endpoint — already partially present)
- `platform_api/wire_dependencies.py`
- `platform_api/tests/test_generation_router.py`
- `camxora_python/shared/models/platform.py`
- `camxora_python/shared/workers/data_workers.py`
- `camxora_python/features/music/views/music_view.py`

## Migration / deploy

- Run `python scripts/deploy/sync_platform_api_sandbox.py` to sync `platform_api` and restart `camxora-api`.
- Desktop app rebuild not required for API-only verification via existing client once desktop changes ship.

## Tests

- `platform_api/tests/test_generation_router.py::TestPolishLyrics::test_queues_suno_when_history_context_provided`
- `platform_api/tests/test_generation_router.py::TestPolishLyrics::test_success` (asserts `suno_queued: false`)

## Follow-ups

- Confirm nginx shows `retry-suno` within seconds of polish when user selects a `suno_failed` history row.
- Optional: move generation polish schemas from `generation.py` into `models/schemas.py` for consistency with other routers.
