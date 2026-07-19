# Polish auto-Suno: stuck suno_pending + failed task fix

**Date:** 2026-07-17  
**Status:** implemented (sandbox redeployed)

## Summary

Auto-Suno after polish failed when a song showed as failed in history but the DB row stayed `suno_pending` while the latest `suno_tasks` row was `failed`. Client and server eligibility checks only accepted `suno_failed`, so polish returned 200 without queuing Suno and the desktop fallback never ran.

## Product impact

- **Before:** User selects failed history row → Polish → lyrics update only; no Suno (nginx showed polish 200 at 22:42–22:58 with no retry activity).
- **After:** Failed provider task (`failed`, `error`, etc.) on a `suno_pending` song is treated as retry-eligible; polish queues Suno server-side when batch/song context is sent.

## Technical impact

- **Desktop:** `is_song_suno_retry_eligible()` in `music_status.py`; `_polish_lyrics`, history context menu, and batch retry targets use it.
- **API:** `BatchService._assert_song_allows_suno_retry()` accepts `suno_pending` when latest Suno task is terminal failure; `batch_repo.get_latest_suno_task_for_song()`.

## Files touched

- `camxora_python/shared/lib/music_status.py`
- `camxora_python/features/music/views/music_view.py`
- `camxora_python/features/music/widgets/history_card.py`
- `camxora_python/tests/test_music_status.py`
- `camxora_python/tests/test_music_history_card.py`
- `platform_api/services/batch_service.py`
- `platform_api/repositories/batch_repo.py`
- `scripts/deploy/probe_polish_auto_suno_sandbox.py`

## Migration / deploy

- `python scripts/deploy/sync_platform_api_sandbox.py`
- Restart desktop app to pick up client eligibility fix.

## Tests

- `camxora_python/tests/test_music_status.py` (new eligibility cases)
- `camxora_python/tests/test_music_history_card.py` (stuck suno_pending)
- `platform_api/tests/test_generation_router.py::TestPolishLyrics`
- `scripts/deploy/probe_polish_auto_suno_sandbox.py` against sandbox

## Follow-ups

- Investigate why Suno callback/poll sometimes leaves `songs.status=suno_pending` after task failure instead of `suno_failed`.
