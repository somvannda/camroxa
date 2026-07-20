# Video template server sync + music retry fix

**Date:** 2026-07-20  
**Status:** implemented (desktop restart to verify)

## Summary

Video template saves now upsert to the platform API even when no channel profile links the template yet. Music history Suno/draft retry no longer crashes after a successful retry API call.

## Product impact

**Before**
- Save showed “Saved locally. No profile currently links this template on the server” with no backend sync.
- Retry Suno from Music history could raise `AttributeError: 'MusicHistoryListResponse' object has no attribute 'rows'`.

**After**
- Unlinked templates sync to the server under the first channel profile (`set_as_profile_default=False`); user message explains linking in Settings for pipeline use.
- Retry completes and shows “Suno retry queued…” without crashing.

## Technical impact

- `VideoTemplateSyncWorker`: fallback upsert when no profile references `video_template_id` / `reel_template_id`.
- `music_view._on_history_retry_succeeded`: iterate `history.batches[].songs` via `history_track_number` helper.

## Files touched

- `camxora_python/features/video/workers/video_template_sync_worker.py`
- `camxora_python/features/music/views/music_view.py`
- `camxora_python/features/music/lib/history_retry.py`
- `camxora_python/tests/test_video_template_sync_worker.py`
- `camxora_python/tests/test_music_history_retry.py`

## Migration / deploy

Desktop app restart from this branch. No API/DB migration.

## Tests

- `test_video_template_sync_worker.py` (3)
- `test_music_history_retry.py` (1)

## Follow-ups

- Optional: user-level template upsert endpoint (avoid profile_id bucket for unlinked templates).
- Link template to profile from Video UI without opening Settings.
